"""WC2026-specific seed ETL.

This module ingests a WC2026 source snapshot into the existing Team,
QualifiedTeam, Player, and Coach schema. It intentionally sits outside the
generic football-data ETL so tournament data can be refreshed independently.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import delete, or_, select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from app.models.team import EloHistory, Team
from etl.players.profiles import build_player_profile
from etl.transform.normalize import canonical
from etl.world_cup_2026.seed_data import (
    DATA_SOURCE_NAME,
    PLACEHOLDER_DATA_SOURCE,
    TOURNAMENT_YEAR,
    empty_payload,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TeamSeedRecord:
    name: str
    code: str = ""
    confederation: str = ""
    fifa_rank: int | None = None
    elo: float | None = None
    group_label: str | None = None
    pot: int | None = None
    host_nation: bool = False
    confirmed: bool = True
    qualification_path: str | None = None
    attack: float = 1.0
    defence: float = 1.0
    chemistry: float = 1.0
    coach_quality: float = 1.0


@dataclass(slots=True)
class PlayerSeedRecord:
    name: str
    team_name: str
    position: str = ""
    club: str | None = None
    age: int | None = None
    nationality: str | None = None
    external_id: str | None = None
    minutes_played: float = 0.0
    goals: float = 0.0
    assists: float = 0.0
    xg: float = 0.0
    xag: float = 0.0
    market_value_eur: float | None = None
    international_caps: int = 0
    international_goals: int = 0
    injured: bool = False
    suspended: bool = False
    injury_notes: str | None = None
    fitness_score: float = 1.0
    recent_form_score: float = 0.5


@dataclass(slots=True)
class CoachSeedRecord:
    name: str
    team_name: str
    nationality: str | None = None
    preferred_formation: str | None = None
    win_pct: float = 0.5
    draw_pct: float = 0.2
    loss_pct: float = 0.3
    matches_managed: int = 0
    tournament_experience: int = 0
    knockout_record: float = 0.5
    tactical_flexibility: float = 0.5
    recent_form_score: float = 0.5
    impact_score: float = 1.0


@dataclass(slots=True)
class WC2026SeedPayload:
    teams: list[TeamSeedRecord] = field(default_factory=list)
    players: list[PlayerSeedRecord] = field(default_factory=list)
    coaches: list[CoachSeedRecord] = field(default_factory=list)
    tournament_year: int = TOURNAMENT_YEAR
    source: str = DATA_SOURCE_NAME


def run_wc2026_seed(
    payload: dict[str, Any] | WC2026SeedPayload | None = None,
    *,
    source_path: str | Path | None = None,
    data_source: str = DATA_SOURCE_NAME,
) -> dict[str, int]:
    """Normalize and upsert WC2026 team, player, and coach seed data.

    Args:
        payload: Raw API-Football-like payload or already-normalized dataclass.
        source_path: Optional JSON file containing the payload.
        data_source: Source label stored on Player and Coach records.

    Returns:
        Counts for inserted/updated records by entity type.
    """
    if source_path is not None:
        payload = json.loads(Path(source_path).read_text(encoding="utf-8"))
    if payload is None:
        payload = empty_payload()

    normalized = normalize_seed_payload(payload, data_source=data_source)
    source = normalized.source or data_source
    db = SessionLocal()
    try:
        result = {
            **_upsert_teams(db, normalized.teams, normalized.tournament_year),
            **_upsert_players(db, normalized.players, source),
            **_upsert_coaches(db, normalized.coaches, source),
        }
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("WC2026 seed ETL complete: %s", result)
    return result


def normalize_seed_payload(
    payload: dict[str, Any] | WC2026SeedPayload,
    *,
    data_source: str = DATA_SOURCE_NAME,
) -> WC2026SeedPayload:
    """Convert raw/source-shaped seed input to validated dataclasses."""
    if isinstance(payload, WC2026SeedPayload):
        return payload

    teams = _normalize_teams(payload.get("teams", []))
    players = _normalize_players(payload.get("players", []))
    coaches = _normalize_coaches(payload.get("coaches", payload.get("coachs", [])))

    return WC2026SeedPayload(
        teams=teams,
        players=players,
        coaches=coaches,
        tournament_year=int(payload.get("tournament_year") or TOURNAMENT_YEAR),
        source=str(payload.get("source") or data_source),
    )


def _normalize_teams(records: Iterable[dict[str, Any]]) -> list[TeamSeedRecord]:
    teams: dict[str, TeamSeedRecord] = {}
    for raw in records:
        team = raw.get("team") if isinstance(raw.get("team"), dict) else raw
        name = canonical(str(team.get("team_name") or team.get("name") or "").strip())
        if not name:
            continue
        code = str(team.get("team_code") or team.get("code") or "").strip().upper()[:3]
        teams[name] = TeamSeedRecord(
            name=name,
            code=code,
            confederation=str(raw.get("confederation") or team.get("confederation") or "").strip(),
            fifa_rank=_optional_int(raw.get("fifa_rank") or team.get("fifa_rank")),
            elo=_optional_float(raw.get("elo") or team.get("elo")),
            group_label=_optional_str(raw.get("group_label") or raw.get("group")),
            pot=_optional_int(raw.get("pot")),
            host_nation=bool(raw.get("host_nation", False)),
            confirmed=bool(raw.get("confirmed", True)),
            qualification_path=_optional_str(raw.get("qualification_path")),
            attack=_to_float(raw.get("attack"), default=1.0),
            defence=_to_float(raw.get("defence"), default=1.0),
            chemistry=_to_float(raw.get("chemistry"), default=1.0),
            coach_quality=_to_float(raw.get("coach_quality"), default=1.0),
        )
    return list(teams.values())


def _normalize_players(records: Iterable[dict[str, Any]]) -> list[PlayerSeedRecord]:
    players: dict[tuple[str, str], PlayerSeedRecord] = {}
    for raw in records:
        player = raw.get("player") if isinstance(raw.get("player"), dict) else raw
        stats = _first_dict(raw.get("statistics"))
        team = stats.get("team") if isinstance(stats.get("team"), dict) else {}
        games = stats.get("games") if isinstance(stats.get("games"), dict) else {}
        goals = stats.get("goals") if isinstance(stats.get("goals"), dict) else {}
        shots = stats.get("shots") if isinstance(stats.get("shots"), dict) else {}

        name = str(player.get("name") or raw.get("name") or "").strip()
        team_name = canonical(str(
            raw.get("team_name")
            or team.get("name")
            or player.get("team_name")
            or ""
        ).strip())
        if not name or not team_name:
            continue

        key = (name.casefold(), team_name.casefold())
        players[key] = PlayerSeedRecord(
            name=name,
            team_name=team_name,
            position=_normalize_position(
                player.get("position") or raw.get("position") or games.get("position")
            ),
            club=_optional_str(player.get("club") or raw.get("club")),
            age=_optional_int(player.get("age") or raw.get("age")),
            nationality=_optional_str(player.get("nationality") or raw.get("nationality")),
            external_id=_optional_str(player.get("id") or raw.get("external_id") or raw.get("id")),
            minutes_played=_to_float(games.get("minutes") or raw.get("minutes_played"), default=0.0),
            goals=_to_float(goals.get("total") or raw.get("goals"), default=0.0),
            assists=_to_float(goals.get("assists") or raw.get("assists"), default=0.0),
            xg=_to_float(raw.get("xg") or shots.get("xg"), default=0.0),
            xag=_to_float(raw.get("xag") or raw.get("xa") or raw.get("xA"), default=0.0),
            market_value_eur=_optional_float(raw.get("market_value_eur") or raw.get("market_value")),
            international_caps=_to_int(raw.get("international_caps") or raw.get("caps"), default=0),
            international_goals=_to_int(raw.get("international_goals"), default=0),
            injured=bool(raw.get("injured", False)),
            suspended=bool(raw.get("suspended", False)),
            injury_notes=_optional_str(raw.get("injury_notes")),
            fitness_score=_bounded(_to_float(raw.get("fitness_score"), default=1.0), 0.0, 1.0),
            recent_form_score=_bounded(_to_float(raw.get("recent_form_score"), default=0.5), 0.0, 1.0),
        )
    return list(players.values())


def _normalize_coaches(records: Iterable[dict[str, Any]]) -> list[CoachSeedRecord]:
    coaches: dict[str, CoachSeedRecord] = {}
    for raw in records:
        coach = raw.get("coach") if isinstance(raw.get("coach"), dict) else raw
        team = coach.get("team") if isinstance(coach.get("team"), dict) else raw.get("team")
        if not isinstance(team, dict):
            team = {}

        name = str(coach.get("name") or raw.get("name") or "").strip()
        team_name = canonical(str(raw.get("team_name") or team.get("name") or "").strip())
        if not name or not team_name:
            continue

        coaches[team_name] = CoachSeedRecord(
            name=name,
            team_name=team_name,
            nationality=_optional_str(coach.get("nationality") or raw.get("nationality")),
            preferred_formation=_optional_str(raw.get("preferred_formation") or raw.get("formation")),
            win_pct=_bounded(_to_float(raw.get("win_pct"), default=0.5), 0.0, 1.0),
            draw_pct=_bounded(_to_float(raw.get("draw_pct"), default=0.2), 0.0, 1.0),
            loss_pct=_bounded(_to_float(raw.get("loss_pct"), default=0.3), 0.0, 1.0),
            matches_managed=_to_int(raw.get("matches_managed"), default=0),
            tournament_experience=_to_int(raw.get("tournament_experience"), default=0),
            knockout_record=_bounded(_to_float(raw.get("knockout_record"), default=0.5), 0.0, 1.0),
            tactical_flexibility=_bounded(_to_float(raw.get("tactical_flexibility"), default=0.5), 0.0, 1.0),
            recent_form_score=_bounded(_to_float(raw.get("recent_form_score"), default=0.5), 0.0, 1.0),
            impact_score=_bounded(_to_float(raw.get("impact_score"), default=1.0), 0.1, 2.0),
        )
    return list(coaches.values())


def _upsert_teams(
    db: Session,
    teams: list[TeamSeedRecord],
    tournament_year: int,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    qualified_inserted = 0
    qualified_updated = 0

    for record in teams:
        team = db.scalar(select(Team).where(Team.name == record.name))
        if team:
            updated += 1
        else:
            team = Team(
                name=record.name,
                code=record.code or "???",
                confederation=record.confederation,
                elo=record.elo or 1500.0,
                fifa_rank=record.fifa_rank or 100,
            )
            db.add(team)
            db.flush()
            db.add(EloHistory(team_id=team.id, rating=record.elo or 1500.0, opponent=None))
            inserted += 1

        team.code = record.code or team.code
        team.confederation = record.confederation or team.confederation
        if record.elo is not None:
            team.elo = record.elo
        if record.fifa_rank is not None:
            team.fifa_rank = record.fifa_rank
        team.attack = record.attack
        team.defence = record.defence
        team.chemistry = record.chemistry
        team.coach_quality = record.coach_quality

        qualified = db.scalar(
            select(QualifiedTeam).where(
                QualifiedTeam.team_name == record.name,
                QualifiedTeam.tournament_year == tournament_year,
            )
        )
        if qualified:
            qualified_updated += 1
        else:
            qualified = QualifiedTeam(
                team_name=record.name,
                team_code=record.code or team.code,
                confederation=record.confederation or team.confederation,
                tournament_year=tournament_year,
            )
            db.add(qualified)
            qualified_inserted += 1

        qualified.team_code = record.code or qualified.team_code
        qualified.confederation = record.confederation or qualified.confederation
        qualified.group_label = record.group_label
        qualified.pot = record.pot
        qualified.host_nation = record.host_nation
        qualified.confirmed = record.confirmed
        qualified.qualification_path = record.qualification_path

    return {
        "teams_inserted": inserted,
        "teams_updated": updated,
        "qualified_teams_inserted": qualified_inserted,
        "qualified_teams_updated": qualified_updated,
    }


def _upsert_players(
    db: Session,
    players: list[PlayerSeedRecord],
    data_source: str,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for record in players:
        if _skip_placeholder_player(db, record.team_name, data_source):
            skipped += 1
            continue
        if data_source != PLACEHOLDER_DATA_SOURCE:
            _delete_placeholder_players(db, record.team_name)

        existing = None
        if record.external_id:
            existing = db.scalar(
                select(Player).where(
                    Player.external_id == record.external_id,
                    Player.data_source == data_source,
                )
            )
        if existing is None:
            existing = db.scalar(
                select(Player).where(
                    Player.name == record.name,
                    Player.team_name == record.team_name,
                )
            )

        if existing:
            updated += 1
            player = existing
        else:
            inserted += 1
            player = Player(name=record.name, team_name=record.team_name, position=record.position)
            db.add(player)

        player.team_name = record.team_name
        player.position = record.position
        player.club = record.club
        player.age = record.age
        player.nationality = record.nationality
        player.external_id = record.external_id
        player.data_source = data_source
        player.minutes_played = record.minutes_played
        player.goals = record.goals
        player.assists = record.assists
        player.xg = record.xg
        player.xag = record.xag
        player.market_value_eur = record.market_value_eur
        player.international_caps = record.international_caps
        player.international_goals = record.international_goals
        player.injured = record.injured
        player.suspended = record.suspended
        player.injury_notes = record.injury_notes
        player.fitness_score = record.fitness_score
        player.recent_form_score = record.recent_form_score
        player.profile_description = build_player_profile(player)
        player.updated_at = now

    return {"players_inserted": inserted, "players_updated": updated, "players_skipped": skipped}


def _upsert_coaches(
    db: Session,
    coaches: list[CoachSeedRecord],
    data_source: str,
) -> dict[str, int]:
    inserted = 0
    updated = 0
    skipped = 0
    now = datetime.now(timezone.utc)
    for record in coaches:
        if _skip_placeholder_coach(db, record.team_name, data_source):
            skipped += 1
            continue
        if data_source != PLACEHOLDER_DATA_SOURCE:
            _delete_placeholder_coach(db, record.team_name)

        coach = db.scalar(select(Coach).where(Coach.team_name == record.team_name))
        if coach:
            updated += 1
        else:
            inserted += 1
            coach = Coach(name=record.name, team_name=record.team_name)
            db.add(coach)

        coach.name = record.name
        coach.team_name = record.team_name
        coach.nationality = record.nationality
        coach.preferred_formation = record.preferred_formation
        coach.win_pct = record.win_pct
        coach.draw_pct = record.draw_pct
        coach.loss_pct = record.loss_pct
        coach.matches_managed = record.matches_managed
        coach.tournament_experience = record.tournament_experience
        coach.knockout_record = record.knockout_record
        coach.tactical_flexibility = record.tactical_flexibility
        coach.recent_form_score = record.recent_form_score
        coach.impact_score = record.impact_score
        coach.data_source = data_source
        coach.updated_at = now

    return {"coaches_inserted": inserted, "coaches_updated": updated, "coaches_skipped": skipped}


def _skip_placeholder_player(db: Session, team_name: str, data_source: str) -> bool:
    if data_source != PLACEHOLDER_DATA_SOURCE:
        return False
    return db.scalar(
        select(Player.id).where(
            Player.team_name == team_name,
            or_(Player.data_source.is_(None), Player.data_source != PLACEHOLDER_DATA_SOURCE),
        )
    ) is not None


def _delete_placeholder_players(db: Session, team_name: str) -> None:
    db.execute(
        delete(Player).where(
            Player.team_name == team_name,
            Player.data_source == PLACEHOLDER_DATA_SOURCE,
        )
    )


def _skip_placeholder_coach(db: Session, team_name: str, data_source: str) -> bool:
    if data_source != PLACEHOLDER_DATA_SOURCE:
        return False
    return db.scalar(
        select(Coach.id).where(
            Coach.team_name == team_name,
            or_(Coach.data_source.is_(None), Coach.data_source != PLACEHOLDER_DATA_SOURCE),
        )
    ) is not None


def _delete_placeholder_coach(db: Session, team_name: str) -> None:
    db.execute(
        delete(Coach).where(
            Coach.team_name == team_name,
            Coach.data_source == PLACEHOLDER_DATA_SOURCE,
        )
    )


def _normalize_position(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "g": "GK",
        "goalkeeper": "GK",
        "keeper": "GK",
        "d": "DEF",
        "defender": "DEF",
        "m": "MID",
        "midfielder": "MID",
        "a": "FWD",
        "f": "FWD",
        "attacker": "FWD",
        "forward": "FWD",
    }
    if raw.upper() in {"GK", "DEF", "MID", "FWD"}:
        return raw.upper()
    return mapping.get(raw, str(value or "").strip().upper()[:30])


def _first_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return value[0]
    if isinstance(value, dict):
        return value
    return {}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return _to_int(value, default=0)


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return _to_float(value, default=0.0)


def _to_int(value: Any, *, default: int) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
