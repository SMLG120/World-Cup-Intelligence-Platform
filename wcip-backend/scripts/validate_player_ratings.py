"""Validate player-rating coverage for WC2026 teams."""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.models.match_result import QualifiedTeam  # noqa: E402
from app.models.player import Player, PlayerRatingImport, PlayerRatingRecord  # noqa: E402


def validate_player_ratings() -> dict[str, Any]:
    with SessionLocal() as db:
        wc_teams = db.scalars(
            select(QualifiedTeam.team_name)
            .where(QualifiedTeam.tournament_year == 2026)
            .order_by(QualifiedTeam.team_name)
        ).all()
        rated_rows = db.scalars(
            select(Player.team_name)
            .where(
                Player.is_active.is_(True),
                Player.player_rating.is_not(None),
            )
        ).all()
        rated_by_team = Counter(rated_rows)
        missing = [team for team in wc_teams if rated_by_team[team] == 0]
        latest_import = db.scalar(
            select(PlayerRatingImport)
            .order_by(PlayerRatingImport.imported_at.desc(), PlayerRatingImport.id.desc())
            .limit(1)
        )
        total_rated_players = db.scalar(
            select(func.count()).select_from(Player).where(
                Player.is_active.is_(True),
                Player.player_rating.is_not(None),
            )
        ) or 0
        rating_records = db.scalar(select(func.count()).select_from(PlayerRatingRecord)) or 0

    return {
        "status": "available" if total_rated_players and not missing else "partial" if total_rated_players else "missing",
        "teams_checked": len(wc_teams),
        "teams_with_ratings": len(wc_teams) - len(missing),
        "teams_missing_ratings": missing,
        "rated_players": int(total_rated_players),
        "rating_records": int(rating_records),
        "fallback_defaults_used": bool(missing),
        "latest_import": {
            "source_name": latest_import.source_name,
            "source_version": latest_import.source_version,
            "status": latest_import.status,
            "valid_rows": latest_import.valid_rows,
            "imported_at": latest_import.imported_at.isoformat() if latest_import.imported_at else None,
        } if latest_import else None,
    }


def main() -> int:
    result = validate_player_ratings()
    print("Player ratings validation")
    print(f"- status: {result['status']}")
    print(f"- teams checked: {result['teams_checked']}")
    print(f"- teams with ratings: {result['teams_with_ratings']}")
    print(f"- rated players: {result['rated_players']}")
    print(f"- rating records: {result['rating_records']}")
    print(f"- fallback defaults used: {result['fallback_defaults_used']}")
    if result["latest_import"]:
        print(f"- latest import: {json.dumps(result['latest_import'], default=str)}")
    if result["teams_missing_ratings"]:
        print("- teams missing ratings:")
        for team in result["teams_missing_ratings"]:
            print(f"  - {team}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
