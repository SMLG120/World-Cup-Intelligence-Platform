"""Migration and bootstrap guardrails."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect


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
