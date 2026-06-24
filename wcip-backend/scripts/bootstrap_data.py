"""Bootstrap WCIP data after migrations.

Run from ``wcip-backend``:

    python -m scripts.bootstrap_data

The command is idempotent. It uses migrations and existing ETL upserts instead
of manually creating production tables.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import func, select, text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.base import SessionLocal, engine  # noqa: E402
from app.models.match_result import MLModelRecord, MatchResult, QualifiedTeam  # noqa: E402
from app.models.player import Coach, Player, PlayerRatingImport, PlayerRatingRecord  # noqa: E402
from app.models.ranking import FifaRankingEntry, FifaRankingSnapshot  # noqa: E402
from app.models.team import EloRatingSnapshot, Team, TeamEloRating  # noqa: E402
from app.services.data_refresh_service import get_data_freshness_from_db  # noqa: E402

logger = logging.getLogger(__name__)

ELO_CSV = ROOT / "data" / "processed" / "world_football_elo_ratings_2026_06_21.csv"
SQUAD_PDF = ROOT / "data" / "external" / "fifa_wc2026_squad_lists_english.pdf"
SQUAD_CSV = ROOT / "data" / "external" / "fifa_wc2026_squad_players.csv"
MODEL_DIR = ROOT / "models"
MODEL_FILES = {
    "logistic": "logistic.pkl",
    "random_forest": "random_forest.pkl",
    "xgboost": "xgboost.pkl",
    "lightgbm": "lightgbm.pkl",
    "catboost": "catboost.pkl",
}


def run_bootstrap(*, build_rag: bool = False, skip_network: bool = False) -> dict[str, Any]:
    warnings: list[str] = []
    results: dict[str, Any] = {}

    _verify_database()
    _run_migrations()

    from etl.pipeline import run_player_rating_import, run_wc2026_seed
    from etl.players.fifa_squad_pdf import build_csv_from_source
    from etl.players.load_squad_pdf import load_squad_from_pdf
    from etl.elo.load_elo_csv import load_elo_csv
    from etl.pipeline import run_fifa_rankings_update

    results["wc2026_seed"] = run_wc2026_seed()

    if not SQUAD_PDF.exists():
        raise FileNotFoundError(
            f"Required FIFA squad PDF is missing: {SQUAD_PDF}. "
            "Do not fake squad data; add the verified source file before bootstrapping."
        )
    results["squad_pdf"] = load_squad_from_pdf(source_pdf=SQUAD_PDF)

    if not SQUAD_CSV.exists():
        results["squad_csv"] = build_csv_from_source(source_pdf=SQUAD_PDF, output_path=SQUAD_CSV)
    results["player_ratings"] = run_player_rating_import(SQUAD_CSV)
    if results["player_ratings"].get("status") == "skipped":
        warnings.append("Player ratings source is missing; neutral defaults will be used.")

    if ELO_CSV.exists():
        results["elo"] = load_elo_csv(ELO_CSV)
    else:
        warnings.append(f"Elo CSV missing: {ELO_CSV}")

    if skip_network:
        warnings.append("FIFA ranking import skipped because --skip-network was set.")
    else:
        try:
            results["fifa_rankings"] = run_fifa_rankings_update(force_refresh=False)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"FIFA ranking import failed or cache unavailable: {exc}")

    results["model_metadata"] = _ensure_model_metadata()

    if build_rag:
        results["rag"] = _build_rag_index()

    with SessionLocal() as db:
        freshness = get_data_freshness_from_db(db)
        counts = _counts(db)
    warnings.extend(freshness.get("warnings") or [])

    summary = {
        "status": "complete",
        "counts": counts,
        "results": results,
        "freshness_status": freshness.get("status"),
        "warnings": warnings,
    }
    return summary


def _verify_database() -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def _run_migrations() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")


def _ensure_model_metadata() -> dict[str, Any]:
    inserted = 0
    skipped = 0
    missing: list[str] = []

    with SessionLocal() as db:
        active_count = db.scalar(
            select(func.count()).select_from(MLModelRecord).where(MLModelRecord.is_active.is_(True))
        ) or 0
        if active_count:
            return {"status": "already_present", "active_models": int(active_count)}

        for model_name, filename in MODEL_FILES.items():
            path = MODEL_DIR / filename
            if not path.exists():
                missing.append(str(path))
                continue
            digest = hashlib.sha256(path.read_bytes()).hexdigest()[:12]
            db.add(
                MLModelRecord(
                    model_name=model_name,
                    version=f"artifact-{digest}",
                    file_path=str(path),
                    accuracy=None,
                    f1_score=None,
                    brier_score=None,
                    log_loss=None,
                    calibration_score=None,
                    ensemble_weight=1.0,
                    feature_version="v2",
                    data_snapshot_version=None,
                    calibration_status="artifact_registered",
                    requires_recalibration=True,
                    training_samples=None,
                    is_active=True,
                    notes="Registered by bootstrap_data from existing model artifact; metrics unavailable.",
                )
            )
            inserted += 1
        db.commit()
    return {"status": "created" if inserted else "missing", "inserted": inserted, "skipped": skipped, "missing": missing}


def _build_rag_index() -> dict[str, Any]:
    from rag.indexer import run_index

    with SessionLocal() as db:
        return run_index(db, force=False)


def _counts(db) -> dict[str, int]:
    models = [
        Team,
        QualifiedTeam,
        Player,
        Coach,
        MatchResult,
        EloRatingSnapshot,
        TeamEloRating,
        FifaRankingSnapshot,
        FifaRankingEntry,
        PlayerRatingImport,
        PlayerRatingRecord,
        MLModelRecord,
    ]
    return {
        model.__tablename__: int(db.scalar(select(func.count()).select_from(model)) or 0)
        for model in models
    }


def _print_summary(summary: dict[str, Any]) -> None:
    counts = summary["counts"]
    player_ratings = summary["results"].get("player_ratings") or {}
    elo = summary["results"].get("elo") or {}
    fifa = summary["results"].get("fifa_rankings") or {}
    model_metadata = summary["results"].get("model_metadata") or {}

    lines = [
        "Bootstrap complete:",
        f"teams={counts.get('teams', 0)}",
        f"qualified_teams={counts.get('qualified_teams', 0)}",
        f"players={counts.get('players', 0)}",
        f"coaches={counts.get('coaches', 0)}",
        f"elo_rows_imported={elo.get('rows_loaded', counts.get('team_elo_ratings', 0))}",
        f"fifa_rankings_imported={fifa.get('entries', counts.get('fifa_ranking_entries', 0))}",
        f"player_ratings_imported={player_ratings.get('valid_rows', counts.get('player_rating_records', 0))}",
        f"model_metadata_imported={model_metadata.get('inserted', 0)}",
        f"freshness_status={summary.get('freshness_status')}",
        f"warnings={json.dumps(summary.get('warnings', []), ensure_ascii=False)}",
    ]
    print("\n".join(lines))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-rag", action="store_true", help="Build the RAG index after data imports.")
    parser.add_argument("--skip-network", action="store_true", help="Skip network-dependent FIFA ranking refresh.")
    parser.add_argument("--json", action="store_true", help="Print the full summary as JSON.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        summary = run_bootstrap(build_rag=args.build_rag, skip_network=args.skip_network)
    except Exception as exc:  # noqa: BLE001
        print(f"Bootstrap failed: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    else:
        _print_summary(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
