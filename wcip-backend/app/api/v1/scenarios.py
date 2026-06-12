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
    if _is_wc2026(req.edition):
        if req.runs < 100:
            raise HTTPException(422, "runs must be at least 100 for WC2026 scenarios")
        from app.api.v1.world_cup import SimulateRequest, simulate_tournament as simulate_world_cup

        return {
            "edition": "2026",
            "runs": req.runs,
            "scenarios": [
                {
                    "label": scenario["label"],
                    "result": simulate_world_cup(
                        SimulateRequest(
                            year=2026,
                            runs=req.runs,
                            overrides=scenario["overrides"],
                            seed=req.seed,
                            deterministic=req.deterministic,
                        )
                    ),
                }
                for scenario in scenarios
            ],
        }

    try:
        for scenario in scenarios:
            scenario["seed"] = req.seed
            scenario["deterministic"] = req.deterministic
        return prediction.compare_scenarios(req.edition, req.runs, scenarios)
    except prediction.UnknownEdition as exc:
        raise HTTPException(404, str(exc))


@router.get("/editions")
def editions():
    editions = prediction.list_editions()
    if "2026" not in editions:
        editions.append("2026")
    return {"editions": editions}


def _is_wc2026(edition: str) -> bool:
    return edition.strip().lower() in {"2026", "wc2026", "world-cup-2026", "world_cup_2026"}


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
