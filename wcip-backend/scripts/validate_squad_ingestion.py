"""Validate WC2026 squad ingestion integrity.

This is intended to run after loading the official FIFA squad PDF. It checks
that the WC2026 field is complete enough for the frontend, prediction features,
and RAG indexing to consume without falling back to placeholder records.
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from app.models.team import Team
from etl.transform.normalize import canonical
from wcip.data.wc2026 import WC2026_TOTAL_TEAMS

MIN_TOTAL_PLAYERS = 1_200
MIN_PLAYERS_PER_TEAM = 20
PLACEHOLDER_SOURCE = "world_cup_2026_placeholder"

POSITION_GROUPS = {
    "GK": "GK",
    "DF": "DF",
    "DEF": "DF",
    "MF": "MF",
    "MID": "MF",
    "FW": "FW",
    "FWD": "FW",
}


def _norm_text(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _position_group(value: str | None) -> str | None:
    if not value:
        return None
    return POSITION_GROUPS.get(value.strip().upper())


def _is_nonnegative_number(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, bool):
        return False
    if not isinstance(value, (int, float)):
        return False
    return math.isfinite(float(value)) and float(value) >= 0


def _failures_for_player_numeric_fields(player: Player) -> list[str]:
    fields = {
        "age": player.age,
        "height_cm": player.height_cm,
        "minutes_played": player.minutes_played,
        "goals": player.goals,
        "assists": player.assists,
        "international_caps": player.international_caps,
        "international_goals": player.international_goals,
        "fitness_score": player.fitness_score,
        "recent_form_score": player.recent_form_score,
    }
    return [name for name, value in fields.items() if not _is_nonnegative_number(value)]


def validate() -> bool:
    failures: list[str] = []
    warnings: list[str] = []

    db = SessionLocal()
    try:
        wc_teams = db.scalars(
            select(QualifiedTeam)
            .where(QualifiedTeam.tournament_year == 2026)
            .order_by(QualifiedTeam.team_name)
        ).all()
        wc_names = {canonical(row.team_name) for row in wc_teams}

        all_team_names = {canonical(row.name) for row in db.scalars(select(Team)).all()}
        valid_team_names = all_team_names | wc_names

        players = db.scalars(select(Player).where(Player.is_active.is_(True))).all()
        coaches = db.scalars(select(Coach)).all()
    finally:
        db.close()

    if len(wc_names) != WC2026_TOTAL_TEAMS:
        failures.append(
            f"Expected {WC2026_TOTAL_TEAMS} WC2026 teams, found {len(wc_names)}."
        )

    if len(players) < MIN_TOTAL_PLAYERS:
        failures.append(
            f"Expected at least {MIN_TOTAL_PLAYERS} players, found {len(players)}."
        )

    player_counts: Counter[str] = Counter(canonical(player.team_name) for player in players)
    coach_names_by_team: dict[str, list[str]] = defaultdict(list)
    placeholder_coach_teams: set[str] = set()
    for coach in coaches:
        canon_team = canonical(coach.team_name)
        coach_names_by_team[canon_team].append(coach.name)
        if coach.data_source == PLACEHOLDER_SOURCE:
            placeholder_coach_teams.add(canon_team)

    missing_players = sorted(team for team in wc_names if player_counts[team] == 0)
    thin_squads = sorted(
        team for team in wc_names
        if 0 < player_counts[team] < MIN_PLAYERS_PER_TEAM
    )
    missing_coaches = sorted(team for team in wc_names if not coach_names_by_team.get(team))

    if missing_players:
        failures.append(
            "WC2026 teams with no players: " + ", ".join(missing_players)
        )
    if thin_squads:
        failures.append(
            "WC2026 teams with fewer than "
            f"{MIN_PLAYERS_PER_TEAM} players: "
            + ", ".join(f"{team} ({player_counts[team]})" for team in thin_squads)
        )
    if missing_coaches:
        failures.append(
            "WC2026 teams with no coach row: " + ", ".join(missing_coaches)
        )

    bosnia = "Bosnia and Herzegovina"
    if player_counts[bosnia] < MIN_PLAYERS_PER_TEAM:
        failures.append(
            f"{bosnia} has {player_counts[bosnia]} players; expected at least "
            f"{MIN_PLAYERS_PER_TEAM}."
        )
    bosnia_coaches = coach_names_by_team.get(bosnia, [])
    if not bosnia_coaches:
        failures.append(f"{bosnia} has no coach row.")
    elif bosnia in placeholder_coach_teams:
        failures.append(f"{bosnia} still uses a placeholder coach row.")

    invalid_team_players = [
        player for player in players
        if canonical(player.team_name) not in valid_team_names
    ]
    if invalid_team_players:
        sample = ", ".join(
            f"{player.name} ({player.team_name})" for player in invalid_team_players[:10]
        )
        failures.append(
            f"{len(invalid_team_players)} players map to unknown teams. Sample: {sample}"
        )

    duplicate_keys: Counter[tuple[str, str]] = Counter(
        (canonical(player.team_name), _norm_text(player.name)) for player in players
    )
    duplicates = [
        (team, name, count)
        for (team, name), count in duplicate_keys.items()
        if team in wc_names and name and count > 1
    ]
    if duplicates:
        sample = ", ".join(
            f"{team}:{name} x{count}" for team, name, count in duplicates[:10]
        )
        failures.append(f"Duplicate player rows detected. Sample: {sample}")

    invalid_positions = [
        player for player in players
        if _position_group(player.position) is None
    ]
    if invalid_positions:
        sample = ", ".join(
            f"{player.name} ({player.team_name}: {player.position})"
            for player in invalid_positions[:10]
        )
        failures.append(
            f"{len(invalid_positions)} players have invalid positions. Sample: {sample}"
        )

    bad_numeric: list[str] = []
    for player in players:
        fields = _failures_for_player_numeric_fields(player)
        if fields:
            bad_numeric.append(f"{player.name} ({player.team_name}): {', '.join(fields)}")
    if bad_numeric:
        failures.append(
            f"{len(bad_numeric)} players have invalid numeric fields. Sample: "
            + "; ".join(bad_numeric[:10])
        )

    placeholder_player_teams = sorted(
        {
            canonical(player.team_name)
            for player in players
            if player.data_source == PLACEHOLDER_SOURCE and canonical(player.team_name) in wc_names
        }
    )
    if placeholder_player_teams:
        warnings.append(
            "Placeholder player rows still present for: "
            + ", ".join(placeholder_player_teams)
        )

    print("WC2026 squad ingestion validation")
    print(f"- WC2026 teams: {len(wc_names)}")
    print(f"- Total players: {len(players)}")
    print(f"- Teams with players: {sum(1 for team in wc_names if player_counts[team] > 0)}")
    print(f"- Coaches for WC teams: {sum(1 for team in wc_names if coach_names_by_team.get(team))}")
    print(f"- Bosnia players: {player_counts[bosnia]}")
    print(f"- Bosnia coach: {', '.join(bosnia_coaches) if bosnia_coaches else 'missing'}")

    for warning in warnings:
        print(f"WARN: {warning}")
    for failure in failures:
        print(f"FAIL: {failure}")

    if failures:
        return False
    print("PASS: squad ingestion is complete and consistent.")
    return True


def main() -> int:
    return 0 if validate() else 1


if __name__ == "__main__":
    sys.exit(main())
