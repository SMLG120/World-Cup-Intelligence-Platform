#!/usr/bin/env python3
"""WC2026 team dataset migration — June 2026.

Applies the finalized WC2026 participant list to the live database:

  REMOVED (did not qualify):
    Italy, Poland, Denmark

  ADDED (newly confirmed qualifiers):
    AFC:      Iraq
    CAF:      Algeria, Cape Verde, DR Congo
    CONCACAF: Curaçao, Haiti, Panama
    CONMEBOL: Paraguay
    UEFA:     Bosnia and Herzegovina, Czechia, Norway, Sweden

Canonical name updates:
  "Czech Republic"     -> "Czechia"
  "Bosnia & Herzegovina" -> "Bosnia and Herzegovina"

Run from the wcip-backend directory:
    python scripts/migrate_wc2026_teams.py

Idempotent: safe to run multiple times.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# Ensure the backend package root is on sys.path
sys.path.insert(0, str(Path(__file__).parents[1]))

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Teams removed from the WC2026 field
# ---------------------------------------------------------------------------

REMOVED_TEAMS = ["Italy", "Poland", "Denmark"]

# ---------------------------------------------------------------------------
# Canonical name renames (old_name -> new_name)
# These teams exist in historical data under the old name; the qualified_teams
# and teams tables should use the new canonical name going forward.
# ---------------------------------------------------------------------------

RENAMES: dict[str, str] = {
    "Czech Republic": "Czechia",
    "Bosnia & Herzegovina": "Bosnia and Herzegovina",
}

# ---------------------------------------------------------------------------
# New entrants — complete records for upsert
# ---------------------------------------------------------------------------

NEW_QUALIFIERS: list[dict] = [
    # AFC
    {"team_name": "Iraq",                   "team_code": "IRQ", "confederation": "AFC",      "host_nation": False, "confirmed": True},
    # CAF
    {"team_name": "Algeria",                "team_code": "ALG", "confederation": "CAF",      "host_nation": False, "confirmed": True},
    {"team_name": "Cape Verde",             "team_code": "CPV", "confederation": "CAF",      "host_nation": False, "confirmed": True},
    {"team_name": "DR Congo",               "team_code": "COD", "confederation": "CAF",      "host_nation": False, "confirmed": True},
    # CONCACAF
    {"team_name": "Panama",                 "team_code": "PAN", "confederation": "CONCACAF", "host_nation": False, "confirmed": True},
    {"team_name": "Haiti",                  "team_code": "HAI", "confederation": "CONCACAF", "host_nation": False, "confirmed": True},
    {"team_name": "Curaçao",               "team_code": "CUW", "confederation": "CONCACAF", "host_nation": False, "confirmed": True},
    # CONMEBOL
    {"team_name": "Paraguay",              "team_code": "PAR", "confederation": "CONMEBOL", "host_nation": False, "confirmed": True},
    # UEFA
    {"team_name": "Bosnia and Herzegovina","team_code": "BIH", "confederation": "UEFA",     "host_nation": False, "confirmed": True},
    {"team_name": "Czechia",               "team_code": "CZE", "confederation": "UEFA",     "host_nation": False, "confirmed": True},
    {"team_name": "Norway",                "team_code": "NOR", "confederation": "UEFA",     "host_nation": False, "confirmed": True},
    {"team_name": "Sweden",                "team_code": "SWE", "confederation": "UEFA",     "host_nation": False, "confirmed": True},
]


def run_migration() -> None:
    from sqlalchemy import select, delete
    from app.db.base import SessionLocal
    from app.models.match_result import QualifiedTeam
    from app.models.team import Team
    from app.models import EloHistory
    from etl.extract.elo_ratings import fetch_elo_ratings
    from etl.extract.fifa_rankings import fetch_fifa_rankings
    from etl.transform.normalize import canonical

    db = SessionLocal()
    stats: dict[str, int] = {
        "qualified_teams_removed": 0,
        "qualified_teams_added": 0,
        "qualified_teams_renamed": 0,
        "teams_removed": 0,
        "teams_added": 0,
        "teams_renamed": 0,
    }

    try:
        # ── 1. Fetch current ratings ────────────────────────────────────────
        logger.info("Fetching Elo ratings and FIFA rankings …")
        elo_ratings = fetch_elo_ratings()
        fifa_ranks = fetch_fifa_rankings()

        # ── 2. Remove disqualified teams from qualified_teams ───────────────
        for name in REMOVED_TEAMS:
            row = db.scalar(
                select(QualifiedTeam).where(
                    QualifiedTeam.team_name == name,
                    QualifiedTeam.tournament_year == 2026,
                )
            )
            if row:
                db.delete(row)
                stats["qualified_teams_removed"] += 1
                logger.info("  qualified_teams: removed %s", name)
            else:
                logger.debug("  qualified_teams: %s not found (already removed?)", name)

        # ── 3. Apply canonical name renames in qualified_teams ──────────────
        for old_name, new_name in RENAMES.items():
            row = db.scalar(
                select(QualifiedTeam).where(
                    QualifiedTeam.team_name == old_name,
                    QualifiedTeam.tournament_year == 2026,
                )
            )
            if row:
                row.team_name = new_name
                stats["qualified_teams_renamed"] += 1
                logger.info("  qualified_teams: renamed '%s' -> '%s'", old_name, new_name)

        # ── 4. Upsert new qualifiers into qualified_teams ───────────────────
        for t in NEW_QUALIFIERS:
            name = t["team_name"]
            existing = db.scalar(
                select(QualifiedTeam).where(
                    QualifiedTeam.team_name == name,
                    QualifiedTeam.tournament_year == 2026,
                )
            )
            if existing:
                # Update fields in case they were stale
                existing.team_code = t.get("team_code", existing.team_code)
                existing.confederation = t.get("confederation", existing.confederation)
                existing.confirmed = True
                logger.debug("  qualified_teams: updated (already exists) %s", name)
            else:
                db.add(QualifiedTeam(
                    team_name=name,
                    team_code=t.get("team_code", ""),
                    confederation=t.get("confederation", ""),
                    tournament_year=2026,
                    host_nation=t.get("host_nation", False),
                    confirmed=True,
                ))
                stats["qualified_teams_added"] += 1
                logger.info("  qualified_teams: added %s (%s)", name, t["confederation"])

        db.commit()

        # ── 5. Apply canonical renames in the teams table ───────────────────
        for old_name, new_name in RENAMES.items():
            team_row = db.scalar(select(Team).where(Team.name == old_name))
            if team_row:
                team_row.name = new_name
                stats["teams_renamed"] += 1
                logger.info("  teams: renamed '%s' -> '%s'", old_name, new_name)

        db.commit()

        # ── 6. Add new teams to the teams table ─────────────────────────────
        existing_team_names = set(db.scalars(select(Team.name)).all())

        for t in NEW_QUALIFIERS:
            name = t["team_name"]
            if name in existing_team_names:
                logger.debug("  teams: %s already exists", name)
                continue

            # Elo: try canonical name, then raw name, then fallback 1500
            elo = (
                elo_ratings.get(name)
                or elo_ratings.get(canonical(name))
                or 1500.0
            )
            rank = (
                fifa_ranks.get(name)
                or fifa_ranks.get(canonical(name))
                or 100
            )

            team = Team(
                name=name,
                code=t.get("team_code", "???"),
                confederation=t.get("confederation", ""),
                elo=float(elo),
                fifa_rank=int(rank),
            )
            db.add(team)
            db.flush()
            db.add(EloHistory(team_id=team.id, rating=float(elo), opponent=None))
            existing_team_names.add(name)
            stats["teams_added"] += 1
            logger.info("  teams: added %s  elo=%.0f  rank=%d", name, elo, rank)

        db.commit()

        # ── 7. Summary ───────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("WC2026 MIGRATION COMPLETE")
        print("=" * 60)
        for k, v in stats.items():
            print(f"  {k:<35} {v}")

        # Verify final count
        total = db.scalar(
            select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
        )
        final_count = len(
            db.scalars(
                select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
            ).all()
        )
        print(f"\n  qualified_teams total (2026)        {final_count}")
        print("=" * 60)

        confs = {}
        for row in db.scalars(
            select(QualifiedTeam).where(QualifiedTeam.tournament_year == 2026)
        ).all():
            confs.setdefault(row.confederation, []).append(row.team_name)

        print("\nBy confederation:")
        for conf in sorted(confs):
            teams_in = sorted(confs[conf])
            print(f"  {conf} ({len(teams_in)}): {', '.join(teams_in)}")

    except Exception as exc:
        db.rollback()
        logger.exception("Migration failed — rolling back: %s", exc)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_migration()
