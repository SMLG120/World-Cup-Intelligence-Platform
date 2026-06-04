"""Celery application."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "wcip",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
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

# Periodic ETL refresh hook (wired up when a real data feed is added).
celery_app.conf.beat_schedule = {
    "refresh-data-every-6h": {
        "task": "app.workers.tasks.refresh_data",
        "schedule": 6 * 60 * 60,
    },
}
