"""Migration and bootstrap guardrails."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_from_empty_database_creates_required_tables(tmp_path):
    db_path = tmp_path / "fresh_migration.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=BACKEND_ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    engine = create_engine(env["DATABASE_URL"])
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert {
        "teams",
        "qualified_teams",
        "players",
        "coaches",
        "match_results",
        "match_features",
        "ml_models",
        "elo_rating_snapshots",
        "team_elo_ratings",
        "fifa_ranking_snapshots",
        "fifa_ranking_entries",
        "player_rating_imports",
        "player_rating_records",
        "rag_documents",
        "rag_chunks",
        "rag_embeddings",
    }.issubset(tables)


def test_bootstrap_data_populates_production_required_data_idempotently(tmp_path):
    db_path = tmp_path / "bootstrap.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"

    for _ in range(2):
        subprocess.run(
            [sys.executable, "-m", "scripts.bootstrap_data", "--skip-network", "--json"],
            cwd=BACKEND_ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    engine = create_engine(env["DATABASE_URL"])
    try:
        with engine.connect() as conn:
            counts = {
                table: conn.execute(text(f"select count(*) from {table}")).scalar_one()
                for table in (
                    "teams",
                    "qualified_teams",
                    "players",
                    "coaches",
                    "match_results",
                    "elo_rating_snapshots",
                    "team_elo_ratings",
                    "fifa_ranking_snapshots",
                    "fifa_ranking_entries",
                    "player_rating_imports",
                    "player_rating_records",
                    "ml_models",
                )
            }
            freshness_markers = conn.execute(
                text(
                    """
                    select
                      (select count(*) from elo_rating_snapshots where is_current = 1) as current_elo,
                      (select count(*) from fifa_ranking_snapshots where is_current = 1) as current_fifa,
                      (select count(*) from player_rating_imports where status = 'success') as successful_player_imports,
                      (select count(*) from ml_models where is_active = 1) as active_models
                    """
                )
            ).mappings().one()
    finally:
        engine.dispose()

    assert counts["qualified_teams"] == 48
    assert counts["players"] >= 1_200
    assert counts["coaches"] == 48
    assert counts["match_results"] >= 40_000
    assert counts["elo_rating_snapshots"] >= 1
    assert counts["team_elo_ratings"] >= 200
    assert counts["fifa_ranking_snapshots"] >= 1
    assert counts["fifa_ranking_entries"] >= 150
    assert counts["player_rating_imports"] == 1
    assert counts["player_rating_records"] >= 1_200
    assert counts["ml_models"] >= 5
    assert freshness_markers["current_elo"] >= 1
    assert freshness_markers["current_fifa"] >= 1
    assert freshness_markers["successful_player_imports"] == 1
    assert freshness_markers["active_models"] >= 5
