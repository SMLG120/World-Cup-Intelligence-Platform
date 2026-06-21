"""Celery-scheduled ETL tasks."""
from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _evaluate_retrain(
    *,
    material_ranking_changes: int = 0,
    material_elo_changes: int = 0,
    changed_player_records: int = 0,
    changed_match_results: int = 0,
) -> None:
    """Evaluate whether any ETL changes warrant model recalibration, and mark models if so."""
    if not any([material_ranking_changes, material_elo_changes, changed_player_records, changed_match_results]):
        return
    try:
        from ml.retrain_if_needed import evaluate_retraining_need

        report = evaluate_retraining_need(
            material_ranking_changes=material_ranking_changes,
            material_elo_changes=material_elo_changes,
            changed_player_records=changed_player_records,
            changed_match_results=changed_match_results,
            apply=True,
        )
        if report.get("action") != "none":
            logger.info(
                "Retraining evaluation: action=%s models_marked=%s reasons=%s",
                report.get("action"),
                report.get("models_marked"),
                report.get("reasons"),
            )
    except Exception:  # noqa: BLE001
        logger.exception("evaluate_retraining_need failed — skipping")


def _inner(result: dict[str, Any]) -> dict[str, Any]:
    """Extract the inner ETL result dict from a _run_refresh wrapper."""
    return result.get("result") or {}


@celery_app.task(name="etl.refresh_world_cup_results", bind=True, max_retries=3)
def refresh_world_cup_results(self):
    """Refresh match results during tournament windows."""
    try:
        from app.services.data_refresh_service import refresh_world_cup_results as _refresh

        result = _refresh()
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail") or "match result refresh failed")
        _evaluate_retrain(changed_match_results=int(_inner(result).get("inserted") or 0))
        return result
    except Exception as exc:
        logger.error("ETL daily results failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 10)


@celery_app.task(name="etl.refresh_elo_ratings", bind=True, max_retries=3)
def refresh_elo_ratings(self):
    """Refresh Elo ratings daily as immutable snapshots."""
    try:
        from app.services.data_refresh_service import refresh_elo_ratings as _refresh

        result = _refresh()
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail") or "Elo refresh failed")
        inner = _inner(result)
        material_elo = int(inner.get("entries_inserted") or 0) + int(inner.get("entries_replaced") or 0)
        _evaluate_retrain(material_elo_changes=material_elo)
        return result
    except Exception as exc:
        logger.error("ETL Elo update failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


@celery_app.task(name="etl.refresh_fifa_rankings", bind=True, max_retries=3)
def refresh_fifa_rankings(self):
    """Check for new official FIFA rankings and store a versioned snapshot."""
    try:
        from app.services.data_refresh_service import refresh_fifa_rankings as _refresh

        result = _refresh()
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail") or "FIFA ranking refresh failed")
        material_ranking = int(_inner(result).get("material_changes") or 0)
        _evaluate_retrain(material_ranking_changes=material_ranking)
        return result
    except Exception as exc:
        logger.error("ETL FIFA ranking update failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


@celery_app.task(name="etl.refresh_player_availability", bind=True, max_retries=3)
def refresh_player_availability(self):
    """Refresh legal player availability/rating CSV data when present."""
    try:
        from app.services.data_refresh_service import refresh_player_availability as _refresh

        result = _refresh()
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail") or "player availability refresh failed")
        inner = _inner(result)
        # Only count rows when the import actually ran (not "skipped" due to missing CSV)
        player_records = int(inner.get("valid_rows") or 0) if inner.get("status") not in ("skipped", None) else 0
        _evaluate_retrain(changed_player_records=player_records)
        return result
    except Exception as exc:
        logger.error("ETL player availability refresh failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


@celery_app.task(name="etl.refresh_prediction_cache")
def refresh_prediction_cache():
    from app.services.data_refresh_service import refresh_prediction_cache as _refresh

    return _refresh()


@celery_app.task(name="etl.retrain_if_needed")
def retrain_if_needed():
    """Scheduled no-op threshold check for model freshness monitoring."""
    try:
        from ml.retrain_if_needed import evaluate_retraining_need

        return evaluate_retraining_need(apply=True)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Scheduled retrain_if_needed failed")
        return {"status": "failed", "detail": str(exc)}


@celery_app.task(name="etl.refresh_all_live_football_data", bind=True, max_retries=2)
def refresh_all_live_football_data(self):
    """Coordinated refresh: results → Elo → FIFA → players → cache → retrain check."""
    try:
        from app.services.data_refresh_service import refresh_all_live_football_data as _refresh

        return _refresh()
    except Exception as exc:
        logger.error("refresh_all_live_football_data failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 15)


@celery_app.task(name="etl.full_pipeline", bind=True, max_retries=2)
def full_pipeline(self, force_refresh: bool = False):
    """Run the complete ETL pipeline (triggered manually or on deploy)."""
    try:
        from etl.pipeline import run_full_pipeline
        return run_full_pipeline(force_refresh=force_refresh)
    except Exception as exc:
        logger.error("Full ETL pipeline failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)


@celery_app.task(name="etl.daily_results_update", bind=True, max_retries=3)
def daily_results_update(self):
    from app.services.data_refresh_service import refresh_world_cup_results as _refresh

    return _refresh()


@celery_app.task(name="etl.weekly_elo_update", bind=True, max_retries=3)
def weekly_elo_update(self):
    from app.services.data_refresh_service import refresh_elo_ratings as _refresh

    return _refresh()


@celery_app.task(name="etl.fifa_rankings_update", bind=True, max_retries=3)
def fifa_rankings_update(self, force_refresh: bool = True, trigger_retraining: bool = True):
    _ = (force_refresh, trigger_retraining)
    from app.services.data_refresh_service import refresh_fifa_rankings as _refresh

    return _refresh()
