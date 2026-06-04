"""Scenario comparison + admin endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from app.core.deps import AdminUser, DbSession
from app.models.simulation import Simulation, SimStatus
from app.models.user import User
from app.schemas.domain import ScenarioCompareRequest
from app.services import prediction

router = APIRouter(tags=["scenarios"])


@router.post("/scenario/compare")
def compare(req: ScenarioCompareRequest):
    scenarios = [
        {"label": s.label,
         "overrides": {k: v.model_dump() for k, v in s.overrides.items()}}
        for s in req.scenarios
    ]
    try:
        return prediction.compare_scenarios(req.edition, req.runs, scenarios)
    except prediction.UnknownEdition as exc:
        raise HTTPException(404, str(exc))


@router.get("/editions")
def editions():
    return {"editions": prediction.list_editions()}


# --- admin ------------------------------------------------------------------
admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/analytics")
def analytics(_: AdminUser, db: DbSession):
    total_users = db.scalar(select(func.count()).select_from(User)) or 0
    total_sims = db.scalar(select(func.count()).select_from(Simulation)) or 0
    by_status = dict(
        db.execute(
            select(Simulation.status, func.count())
            .group_by(Simulation.status)
        ).all()
    )
    return {
        "users": total_users,
        "simulations": total_sims,
        "simulations_by_status": {
            (k.value if isinstance(k, SimStatus) else k): v
            for k, v in by_status.items()
        },
    }
