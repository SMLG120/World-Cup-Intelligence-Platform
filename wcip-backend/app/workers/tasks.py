"""Celery tasks: heavy simulations and scheduled ETL."""
from __future__ import annotations

import logging

from app.db.base import SessionLocal
from app.models.simulation import SimStatus
from app.repositories.repos import SimulationRepository
from app.services import prediction
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="app.workers.tasks.run_simulation")
def run_simulation(self, simulation_id: int) -> dict:
    """Execute a stored Monte Carlo simulation and persist the result."""
    db = SessionLocal()
    repo = SimulationRepository(db)
    sim = repo.get(simulation_id)
    if sim is None:
        return {"error": "simulation not found"}
    try:
        sim.status = SimStatus.running
        db.commit()
        params = sim.params or {}
        result = prediction.run_monte_carlo(
            edition=params.get("edition", "2022"),
            runs=int(params.get("runs", 10000)),
            overrides=params.get("overrides", {}),
            seed=params.get("seed"),
            deterministic=bool(params.get("deterministic", False)),
        )
        repo.mark_completed(sim, result)
        return {"simulation_id": simulation_id, "status": "completed"}
    except Exception as exc:  # noqa: BLE001
        logger.exception("simulation %s failed", simulation_id)
        repo.mark_failed(sim, str(exc))
        return {"simulation_id": simulation_id, "status": "failed",
                "error": str(exc)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.refresh_data")
def refresh_data() -> dict:
    """Scheduled ETL refresh hook.

    In a full build this pulls fixtures/results from Football-Data.org /
    StatsBomb, recomputes Elo, and updates team feature multipliers. Stubbed
    here to keep the worker self-contained.
    """
    logger.info("refresh_data tick (no data feed configured)")
    return {"status": "noop", "reason": "no data feed configured"}
