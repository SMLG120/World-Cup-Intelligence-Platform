"""Celery application."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "wcip",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks", "etl.schedulers.celery_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,          # hard kill heavy 50k runs after 10 min
    task_soft_time_limit=540,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    worker_max_tasks_per_child=50,
)

celery_app.conf.beat_schedule = {
    "refresh-world-cup-results-every-3h": {
        "task": "etl.refresh_world_cup_results",
        "schedule": 3 * 60 * 60,
    },
    "refresh-elo-ratings-daily": {
        "task": "etl.refresh_elo_ratings",
        "schedule": 24 * 60 * 60,
    },
    "check-fifa-rankings-daily": {
        "task": "etl.refresh_fifa_rankings",
        "schedule": 24 * 60 * 60,
    },
    "refresh-player-availability-daily": {
        "task": "etl.refresh_player_availability",
        "schedule": 24 * 60 * 60,
    },
    "refresh-prediction-cache-every-6h": {
        "task": "etl.refresh_prediction_cache",
        "schedule": 6 * 60 * 60,
    },
    "check-ml-retraining-daily": {
        "task": "etl.retrain_if_needed",
        "schedule": 24 * 60 * 60,
    },
}
