"""Create tables and seed reference data."""
from __future__ import annotations

import logging

from sqlalchemy import inspect, select, text

from app.core.config import settings
from app.db.base import Base, SessionLocal, engine
from app.models import EloHistory, Team
from wcip.data.teams_2022 import build_teams

logger = logging.getLogger(__name__)


def create_tables() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_runtime_columns()


def _ensure_sqlite_runtime_columns() -> None:
    """Patch dev SQLite DBs created before the latest Alembic migrations.

    Production should still run Alembic. This guard keeps local existing
    ``wcip.db`` files from failing at runtime when SQLAlchemy selects newly
    added columns that ``CREATE TABLE IF NOT EXISTS`` cannot add.
    """

    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    def add_missing_columns(table_name: str, columns: dict[str, str]) -> None:
        if table_name not in existing_tables:
            return
        existing_columns = {column["name"] for column in inspector.get_columns(table_name)}
        statements = [
            f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
            for column_name, definition in columns.items()
            if column_name not in existing_columns
        ]
        if not statements:
            return
        with engine.begin() as conn:
            for statement in statements:
                conn.execute(text(statement))
        logger.info("Added %d missing SQLite column(s) to %s", len(statements), table_name)

    add_missing_columns(
        "players",
        {
            "player_rating": "FLOAT",
            "ea_fc_rating": "FLOAT",
            "player_rating_source": "VARCHAR(120)",
            "player_rating_version": "VARCHAR(80)",
            "player_rating_updated_at": "DATETIME",
        },
    )
    add_missing_columns(
        "match_features",
        {
            "average_starting_xi_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "average_squad_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "top_5_player_rating_avg_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "goalkeeper_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "defensive_unit_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "midfield_unit_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "attacking_unit_rating_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "squad_depth_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "star_player_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "injury_burden_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "player_form_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "player_availability_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "international_experience_score_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "average_caps_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "total_international_goals_diff": "FLOAT NOT NULL DEFAULT 0.0",
            "weighted_player_strength_diff": "FLOAT NOT NULL DEFAULT 0.0",
        },
    )


def seed_teams() -> int:
    """Idempotently seed national teams from 2022 snapshot. Returns number inserted."""
    db = SessionLocal()
    inserted = 0
    try:
        existing = set(db.scalars(select(Team.name)).all())
        for name, t in build_teams().items():
            if name in existing:
                continue
            team = Team(name=t.name, code=t.code, confederation=t.confederation,
                        elo=t.elo, fifa_rank=t.fifa_rank)
            db.add(team)
            db.flush()
            db.add(EloHistory(team_id=team.id, rating=t.elo, opponent=None))
            inserted += 1
        db.commit()
    finally:
        db.close()
    if inserted:
        logger.info("Seeded %d teams (2022 snapshot)", inserted)
    return inserted


def seed_qualified_teams_2026() -> int:
    """Seed the 2026 qualified teams table from the static module."""
    try:
        from sqlalchemy import delete
        from app.models.match_result import QualifiedTeam
        from wcip.data.wc2026 import CONFIRMED_QUALIFIERS
        from etl.load.db_loader import load_qualified_teams

        official_names = {team["team_name"] for team in CONFIRMED_QUALIFIERS}
        db = SessionLocal()
        try:
            db.execute(
                delete(QualifiedTeam).where(
                    QualifiedTeam.tournament_year == 2026,
                    QualifiedTeam.team_name.not_in(official_names),
                )
            )
            db.commit()
        finally:
            db.close()

        inserted = load_qualified_teams(CONFIRMED_QUALIFIERS, tournament_year=2026)
        if inserted:
            logger.info("Seeded %d WC2026 qualified teams", inserted)
        return inserted
    except Exception as e:
        logger.warning("Could not seed WC2026 qualified teams: %s", e)
        return 0


def seed_2026_teams_into_team_table() -> int:
    """Ensure all WC2026 qualified teams exist in the main teams table."""
    from wcip.data.wc2026 import CONFIRMED_QUALIFIERS
    from etl.transform.normalize import canonical
    from etl.extract.elo_ratings import fetch_elo_ratings
    from etl.extract.fifa_rankings import fetch_fifa_rankings

    db = SessionLocal()
    inserted = 0
    try:
        elo_ratings = fetch_elo_ratings(allow_network=False)
        fifa_ranks = fetch_fifa_rankings()
        existing = set(db.scalars(select(Team.name)).all())

        for t in CONFIRMED_QUALIFIERS:
            name = t["team_name"]
            if name in existing:
                continue
            elo = elo_ratings.get(name, elo_ratings.get(canonical(name), 1500.0))
            rank = fifa_ranks.get(name, fifa_ranks.get(canonical(name), 100))
            team = Team(
                name=name,
                code=t.get("team_code", "???"),
                confederation=t.get("confederation", ""),
                elo=elo,
                fifa_rank=rank,
            )
            db.add(team)
            db.flush()
            db.add(EloHistory(team_id=team.id, rating=elo, opponent=None))
            inserted += 1

        db.commit()
    except Exception as e:
        logger.warning("Error seeding 2026 teams into team table: %s", e)
    finally:
        db.close()

    if inserted:
        logger.info("Seeded %d new teams from WC2026 qualified list", inserted)
    return inserted


def seed_world_cup_2026_registry() -> dict[str, int]:
    """Seed WC2026 teams/players/coaches through the dedicated ETL module."""
    try:
        from etl.world_cup_2026.ingest import run_wc2026_seed

        result = run_wc2026_seed()
        if any(result.values()):
            logger.info("WC2026 registry seed result: %s", result)
        return result
    except Exception as e:
        logger.warning("Could not run WC2026 registry seed ETL: %s", e)
        return {}


def init_db() -> None:
    create_tables()
    seed_teams()
    seed_qualified_teams_2026()
    seed_2026_teams_into_team_table()
    seed_world_cup_2026_registry()
    if settings.ETL_AUTO_RUN_ON_STARTUP:
        logger.info("ETL_AUTO_RUN_ON_STARTUP is enabled; startup-safe WC2026 seed already ran")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
    print("Database initialised and seeded.")
