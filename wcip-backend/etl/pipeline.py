"""Master ETL pipeline orchestrator.

Runs extract -> transform -> validate -> load for each data source.
Supports full refresh or incremental (since last run).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

_STATE_FILE = Path(__file__).parent / "data" / "etl_state.json"


def _load_state() -> dict:
    import json
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if _STATE_FILE.exists():
        try:
            return json.loads(_STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    import json
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, default=str), encoding="utf-8")


def run_historical_results(force_refresh: bool = False) -> int:
    """Load all international match results since last run (or all-time on first run)."""
    from etl.extract.international_results import fetch_results_csv, parse_results
    from etl.load.db_loader import load_match_results
    from etl.transform.normalize import normalize_match
    from etl.validation.schema import ValidationError, validate_match

    state = _load_state()
    last_date_str = state.get("last_results_date")
    since: date | None = None
    if last_date_str and not force_refresh:
        since = date.fromisoformat(last_date_str) - timedelta(days=7)  # 7-day overlap
        logger.info("Incremental load since %s", since)

    csv_text = fetch_results_csv(force_refresh=force_refresh)

    def _validated() -> Iterator:
        errors = 0
        total = 0
        for raw in parse_results(csv_text, since=since):
            total += 1
            normalized = normalize_match(raw)
            try:
                yield validate_match(normalized)
            except ValidationError as e:
                errors += 1
                if errors <= 10:
                    logger.debug("Validation skip: %s", e)
        logger.info("Parsed %d records, skipped %d validation errors", total, errors)

    inserted = load_match_results(_validated())

    state["last_results_date"] = str(date.today())
    _save_state(state)
    logger.info("Historical results pipeline complete. Inserted: %d", inserted)
    return inserted


def run_elo_update() -> dict:
    """Refresh Elo ratings in the Team table from eloratings.net."""
    from etl.extract.elo_ratings import fetch_elo_ratings
    from etl.transform.normalize import canonical

    from sqlalchemy import select
    from app.db.base import SessionLocal
    from app.models.team import Team

    ratings = fetch_elo_ratings(force_refresh=True)
    db = SessionLocal()
    updated = 0
    try:
        teams = db.scalars(select(Team)).all()
        for team in teams:
            canon = canonical(team.name)
            if canon in ratings:
                team.elo = ratings[canon]
                updated += 1
            elif team.name in ratings:
                team.elo = ratings[team.name]
                updated += 1
        db.commit()
    finally:
        db.close()

    logger.info("Elo update complete. Updated %d teams", updated)
    return {"updated_teams": updated, "source_teams": len(ratings)}


def run_fifa_rankings_update(force_refresh: bool = False) -> dict:
    """Fetch and store the latest official FIFA rankings as a versioned snapshot."""
    from etl.load.ranking_loader import load_latest_fifa_ranking_snapshot

    result = load_latest_fifa_ranking_snapshot(force_refresh=force_refresh)
    logger.info("FIFA rankings update complete: %s", result)
    return result


def run_wc2026_seed(source_path: str | Path | None = None) -> dict:
    """Load WC2026 teams, players, and coaches from the dedicated seed ETL."""
    from etl.world_cup_2026.ingest import run_wc2026_seed as _run_wc2026_seed

    return _run_wc2026_seed(source_path=source_path)


def run_full_pipeline(force_refresh: bool = False) -> dict:
    """Run all ETL jobs in order."""
    logger.info("Starting full ETL pipeline (force_refresh=%s)", force_refresh)
    results: dict = {}

    try:
        results["historical_results"] = run_historical_results(force_refresh=force_refresh)
    except Exception as e:
        logger.error("Historical results pipeline failed: %s", e)
        results["historical_results_error"] = str(e)

    try:
        results["elo_update"] = run_elo_update()
    except Exception as e:
        logger.error("Elo update failed: %s", e)
        results["elo_update_error"] = str(e)

    try:
        results["fifa_rankings"] = run_fifa_rankings_update(force_refresh=force_refresh)
    except Exception as e:
        logger.error("FIFA rankings update failed: %s", e)
        results["fifa_rankings_error"] = str(e)

    try:
        results["wc2026_seed"] = run_wc2026_seed()
    except Exception as e:
        logger.error("WC2026 seed failed: %s", e)
        results["wc2026_seed_error"] = str(e)

    logger.info("ETL pipeline complete: %s", results)
    return results
