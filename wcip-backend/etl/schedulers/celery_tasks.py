"""Celery-scheduled ETL tasks."""
from __future__ import annotations

import logging

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="etl.daily_results_update", bind=True, max_retries=3)
def daily_results_update(self):
    """Run incremental historical results update daily."""
    try:
        from etl.pipeline import run_historical_results
        count = run_historical_results(force_refresh=False)
        return {"status": "ok", "inserted": count}
    except Exception as exc:
        logger.error("ETL daily results failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 10)


@celery_app.task(name="etl.weekly_elo_update", bind=True, max_retries=3)
def weekly_elo_update(self):
    """Refresh Elo ratings weekly."""
    try:
        from etl.pipeline import run_elo_update
        result = run_elo_update()
        return {"status": "ok", **result}
    except Exception as exc:
        logger.error("ETL Elo update failed: %s", exc)
        raise self.retry(exc=exc, countdown=60 * 30)


@celery_app.task(name="etl.full_pipeline", bind=True, max_retries=2)
def full_pipeline(self, force_refresh: bool = False):
    """Run the complete ETL pipeline (triggered manually or on deploy)."""
    try:
        from etl.pipeline import run_full_pipeline
        return run_full_pipeline(force_refresh=force_refresh)
    except Exception as exc:
        logger.error("Full ETL pipeline failed: %s", exc)
        raise self.retry(exc=exc, countdown=60)
