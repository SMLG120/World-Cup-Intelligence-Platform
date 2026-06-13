"""Celery-scheduled ETL tasks."""
from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="etl.refresh_world_cup_results", bind=True, max_retries=3)
def refresh_world_cup_results(self):
    """Refresh match results during tournament windows."""
    try:
        from app.services.data_refresh_service import refresh_world_cup_results as _refresh

        result = _refresh()
        if result.get("status") == "failed":
            raise RuntimeError(result.get("detail") or "match result refresh failed")
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
        return result
    except Exception as exc:
        logger.error("ETL player availability refresh failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


@celery_app.task(name="etl.refresh_prediction_cache")
def refresh_prediction_cache():
    from app.services.data_refresh_service import refresh_prediction_cache as _refresh

    return _refresh()


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
