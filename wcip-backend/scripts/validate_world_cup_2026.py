#!/usr/bin/env python3
"""Validate local World Cup 2026 data and API readiness.

Run from `wcip-backend`:
    python scripts/validate_world_cup_2026.py
"""
from __future__ import annotations

import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from app.models.team import Team
from app.services.prediction import predict_match
from wcip.data.wc2026 import CONFIRMED_QUALIFIERS, WC2026_TEAMS_PER_GROUP


def ok(label: str, detail: str = "") -> tuple[bool, str, str]:
    return True, label, detail


def fail(label: str, detail: str = "") -> tuple[bool, str, str]:
    return False, label, detail


def main() -> int:
    from app.db.init_db import init_db

    # Ensure a fresh local database has the startup-safe WC2026 registry before
    # validating. Real roster snapshots can still replace placeholder rows.
    init_db()

    expected = {team["team_name"]: team for team in CONFIRMED_QUALIFIERS}
    checks: list[tuple[bool, str, str]] = []

    db = SessionLocal()
    try:
        qualified = db.scalars(
            select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
        ).all()
        teams = db.scalars(select(Team)).all()
        players = db.scalars(select(Player).where(Player.is_active.is_(True))).all()
        coaches = db.scalars(select(Coach)).all()

        qualified_names = [team.team_name for team in qualified]
        duplicate_teams = [name for name, count in Counter(qualified_names).items() if count > 1]
        checks.append(
            fail("No duplicate qualified teams", ", ".join(duplicate_teams))
            if duplicate_teams else ok("No duplicate qualified teams")
        )

        missing = sorted(set(expected) - set(qualified_names))
        extra = sorted(set(qualified_names) - set(expected))
        checks.append(
            ok("All 48 official WC2026 teams are present")
            if not missing and not extra and len(qualified_names) == 48
            else fail("All 48 official WC2026 teams are present", f"missing={missing}; extra={extra}; count={len(qualified_names)}")
        )

        missing_groups = [team.team_name for team in qualified if not team.group_label]
        checks.append(
            fail("Every WC2026 team has a group", ", ".join(missing_groups))
            if missing_groups else ok("Every WC2026 team has a group")
        )

        groups: dict[str, list[str]] = defaultdict(list)
        for team in qualified:
            if team.group_label:
                groups[team.group_label].append(team.team_name)
        bad_groups = {
            label: names for label, names in sorted(groups.items())
            if len(names) != WC2026_TEAMS_PER_GROUP
        }
        checks.append(
            fail("Every group has four teams", str(bad_groups))
            if bad_groups or len(groups) != 12 else ok("Every group has four teams")
        )

        duplicate_players = []
        player_counts = Counter()
        seen_players: set[tuple[str, str]] = set()
        for player in players:
            player_counts[player.team_name] += 1
            key = (player.team_name, player.name.casefold())
            if key in seen_players:
                duplicate_players.append(f"{player.team_name}:{player.name}")
            seen_players.add(key)
        checks.append(
            fail("No duplicate players per team", ", ".join(duplicate_players))
            if duplicate_players else ok("No duplicate players per team")
        )

        teams_without_players = [name for name in expected if player_counts[name] == 0]
        checks.append(
            fail("Every WC2026 team has at least one player", ", ".join(teams_without_players))
            if teams_without_players else ok("Every WC2026 team has at least one player")
        )

        if coaches:
            coach_teams = {coach.team_name for coach in coaches}
            teams_without_coaches = sorted(set(expected) - coach_teams)
            checks.append(
                fail("Every WC2026 team has a coach", ", ".join(teams_without_coaches))
                if teams_without_coaches else ok("Every WC2026 team has a coach")
            )
        else:
            checks.append(fail("Coach data loaded", "No coach rows exist"))

        team_table_names = {team.name for team in teams}
        missing_team_rows = sorted(set(expected) - team_table_names)
        checks.append(
            fail("Every WC2026 team exists in teams table", ", ".join(missing_team_rows))
            if missing_team_rows else ok("Every WC2026 team exists in teams table")
        )

        prediction_failures = []
        reference = "Brazil" if "Brazil" in expected else next(iter(expected))
        for name in expected:
            opponent = "Argentina" if name == reference else reference
            try:
                result = predict_match(name, opponent, {}, {})
                probs = result["probabilities"]
                total = sum(float(value) for value in probs.values())
                finite = all(math.isfinite(float(value)) for value in probs.values())
                bounded = all(0 <= float(value) <= 1 for value in probs.values())
                if not finite or not bounded or abs(total - 1.0) > 1e-6:
                    prediction_failures.append(name)
            except Exception as exc:
                prediction_failures.append(f"{name} ({exc})")
        checks.append(
            fail("Every WC2026 team can be used in match predictions", "; ".join(prediction_failures))
            if prediction_failures else ok("Every WC2026 team can be used in match predictions")
        )

        # Tournament-readiness without running a large Monte Carlo job.
        checks.append(
            ok("Every WC2026 team can be placed in tournament simulation")
            if set().union(*[set(names) for names in groups.values()]) == set(expected)
            else fail("Every WC2026 team can be placed in tournament simulation", "group membership mismatch")
        )

    finally:
        db.close()

    print("World Cup 2026 validation report")
    print("=" * 40)
    failures = 0
    for passed, label, detail in checks:
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {label}")
        if detail:
            print(f"       {detail}")
        if not passed:
            failures += 1
    print("=" * 40)
    print(f"Result: {len(checks) - failures}/{len(checks)} checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
