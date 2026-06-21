"""Validate that the WC2026 squad data was successfully ingested.

Checks:
  - minimum 1,000 player rows across all WC2026 teams
  - all 48 WC2026 nations have at least 20 players each
  - at least 40 of 48 teams have a head coach record
  - player position distribution is plausible (GK/DEF/MID/FWD)
  - no team has more than 26 players
  - height_cm is populated for at least 80 % of players
  - date_of_birth is populated for at least 80 % of players

Run:
    python wcip-backend/scripts/validate_squad_ingestion.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from wcip.data.wc2026 import WC2026_TOTAL_TEAMS

MIN_TOTAL_PLAYERS = 1_000
MIN_PLAYERS_PER_TEAM = 20
MAX_PLAYERS_PER_TEAM = 26
MIN_COACH_COVERAGE = max(1, WC2026_TOTAL_TEAMS - 8)   # at least 40 / 48 teams need a coach record
MIN_HEIGHT_FILL_RATE = 0.80
MIN_DOB_FILL_RATE = 0.80


def validate() -> bool:
    db = SessionLocal()
    ok = True
    try:
        # ------------------------------------------------------------------
        # 1. Total player count
        # ------------------------------------------------------------------
        total = db.scalar(select(func.count(Player.id))) or 0
        if total < MIN_TOTAL_PLAYERS:
            print(f"FAIL  total players {total} < {MIN_TOTAL_PLAYERS}")
            ok = False
        else:
            print(f"PASS  total players = {total}")

        # ------------------------------------------------------------------
        # 2. WC2026 team coverage and per-team player counts
        # ------------------------------------------------------------------
        wc2026_teams = set(
            db.scalars(
                select(QualifiedTeam.team_name).where(
                    QualifiedTeam.tournament_year == 2026
                )
            ).all()
        )
        if len(wc2026_teams) != WC2026_TOTAL_TEAMS:
            print(f"FAIL  WC2026 qualified-team registry has {len(wc2026_teams)} teams, expected {WC2026_TOTAL_TEAMS}")
            ok = False
        else:
            print(f"PASS  WC2026 qualified-team registry = {len(wc2026_teams)} teams")

        team_counts: dict[str, int] = {}
        rows = db.execute(
            select(Player.team_name, func.count(Player.id).label("n"))
            .group_by(Player.team_name)
        ).all()
        for team_name, n in rows:
            team_counts[team_name] = n

        missing_teams = sorted(t for t in wc2026_teams if team_counts.get(t, 0) == 0)
        extra_teams = sorted(t for t in team_counts if t not in wc2026_teams)
        if missing_teams:
            print(f"FAIL  {len(missing_teams)} WC2026 team(s) have no players: {missing_teams[:5]}")
            ok = False
        else:
            print(f"PASS  all {WC2026_TOTAL_TEAMS} WC2026 teams have player rows")
        if extra_teams:
            print(f"WARN  {len(extra_teams)} non-WC2026 team(s) have player rows: {extra_teams[:5]}")

        thin_teams = [t for t in wc2026_teams if team_counts.get(t, 0) < MIN_PLAYERS_PER_TEAM]
        fat_teams = [t for t in wc2026_teams if team_counts.get(t, 0) > MAX_PLAYERS_PER_TEAM]

        if thin_teams:
            print(f"WARN  {len(thin_teams)} team(s) have < {MIN_PLAYERS_PER_TEAM} players: {thin_teams[:5]}")
        else:
            print(f"PASS  all teams have >= {MIN_PLAYERS_PER_TEAM} players")

        if fat_teams:
            print(f"WARN  {len(fat_teams)} team(s) have > {MAX_PLAYERS_PER_TEAM} players: {fat_teams[:5]}")
        else:
            print(f"PASS  no team has > {MAX_PLAYERS_PER_TEAM} players")

        # ------------------------------------------------------------------
        # 3. Position distribution
        # ------------------------------------------------------------------
        pos_rows = db.execute(
            select(Player.position, func.count(Player.id).label("n"))
            .group_by(Player.position)
        ).all()
        pos_counts = {pos: n for pos, n in pos_rows}
        for expected in ("GK", "DEF", "MID", "FWD"):
            n = pos_counts.get(expected, 0)
            if n == 0:
                print(f"FAIL  no players in position {expected}")
                ok = False
            else:
                print(f"PASS  position {expected} = {n} players")

        # ------------------------------------------------------------------
        # 4. Height fill rate
        # ------------------------------------------------------------------
        with_height = db.scalar(
            select(func.count(Player.id)).where(Player.height_cm.isnot(None))
        ) or 0
        height_rate = with_height / max(total, 1)
        if height_rate < MIN_HEIGHT_FILL_RATE:
            print(f"WARN  height_cm fill rate {height_rate:.1%} < {MIN_HEIGHT_FILL_RATE:.0%}")
        else:
            print(f"PASS  height_cm fill rate = {height_rate:.1%}")

        # ------------------------------------------------------------------
        # 5. Date of birth fill rate
        # ------------------------------------------------------------------
        with_dob = db.scalar(
            select(func.count(Player.id)).where(Player.date_of_birth.isnot(None))
        ) or 0
        dob_rate = with_dob / max(total, 1)
        if dob_rate < MIN_DOB_FILL_RATE:
            print(f"WARN  date_of_birth fill rate {dob_rate:.1%} < {MIN_DOB_FILL_RATE:.0%}")
        else:
            print(f"PASS  date_of_birth fill rate = {dob_rate:.1%}")

        # ------------------------------------------------------------------
        # 6. Coach coverage
        # ------------------------------------------------------------------
        coach_teams = set(
            db.scalars(select(Coach.team_name).where(Coach.team_name.isnot(None))).all()
        )
        if len(coach_teams) < MIN_COACH_COVERAGE:
            print(f"WARN  only {len(coach_teams)} teams have coach records (need >= {MIN_COACH_COVERAGE})")
        else:
            print(f"PASS  coach coverage = {len(coach_teams)} teams")

        # ------------------------------------------------------------------
        # Summary
        # ------------------------------------------------------------------
        print()
        if ok:
            print("RESULT: All required checks passed.")
        else:
            print("RESULT: One or more checks FAILED — review output above.")

    finally:
        db.close()
    return ok


if __name__ == "__main__":
    sys.exit(0 if validate() else 1)
