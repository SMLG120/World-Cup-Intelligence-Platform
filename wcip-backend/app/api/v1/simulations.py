"""Saved simulations: create (sync or async), list, fetch, share, delete."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.simulation import SimKind, Simulation, SimStatus
from app.repositories.repos import SimulationRepository
from app.schemas.domain import (Page, SimulationCreateResponse, SimulationOut,
                                SimulationUpdate, TournamentRequest)
from app.services import prediction

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", response_model=SimulationCreateResponse, status_code=201)
def create_simulation(req: TournamentRequest, user: CurrentUser, db: DbSession):
    overrides = {k: v.model_dump() for k, v in req.overrides.items()}
    sim = Simulation(
        owner_id=user.id,
        name=req.name,
        kind=SimKind.monte_carlo,
        params={"edition": req.edition, "runs": req.runs, "overrides": overrides},
    )
    SimulationRepository(db).add(sim)

    # Small runs execute inline; large ones go to Celery.
    if req.runs <= settings.SYNC_SIM_RUN_THRESHOLD:
        result = prediction.run_monte_carlo(req.edition, req.runs, overrides)
        SimulationRepository(db).mark_completed(sim, result)
        return SimulationCreateResponse(id=sim.id, status="completed", result=result)

    from app.workers.tasks import run_simulation
    task = run_simulation.delay(sim.id)
    sim.task_id = task.id
    sim.status = SimStatus.pending
    db.commit()
    return SimulationCreateResponse(id=sim.id, status="pending", task_id=task.id)


@router.get("", response_model=Page[SimulationOut])
def list_simulations(user: CurrentUser, db: DbSession,
                     page: int = Query(1, ge=1),
                     page_size: int = Query(20, ge=1, le=100)):
    items, total = SimulationRepository(db).list_for_user(user.id, page, page_size)
    return Page[SimulationOut](items=items, total=total, page=page,
                               page_size=page_size)


@router.get("/{sim_id}", response_model=SimulationOut)
def get_simulation(sim_id: int, user: CurrentUser, db: DbSession):
    sim = SimulationRepository(db).get(sim_id)
    if not sim or sim.owner_id != user.id:
        raise HTTPException(404, "Simulation not found")
    return sim


@router.get("/public/{token}", response_model=SimulationOut)
def get_public_simulation(token: str, db: DbSession):
    sim = SimulationRepository(db).get_by_token(token)
    if not sim or not sim.is_public:
        raise HTTPException(404, "Public simulation not found")
    return sim


@router.patch("/{sim_id}", response_model=SimulationOut)
def update_simulation(sim_id: int, payload: SimulationUpdate,
                      user: CurrentUser, db: DbSession):
    repo = SimulationRepository(db)
    sim = repo.get(sim_id)
    if not sim or sim.owner_id != user.id:
        raise HTTPException(404, "Simulation not found")
    if payload.name is not None:
        sim.name = payload.name
    if payload.is_public is not None:
        sim.is_public = payload.is_public
    db.commit()
    db.refresh(sim)
    return sim


@router.post("/{sim_id}/duplicate", response_model=SimulationOut, status_code=201)
def duplicate_simulation(sim_id: int, user: CurrentUser, db: DbSession):
    repo = SimulationRepository(db)
    src = repo.get(sim_id)
    if not src or src.owner_id != user.id:
        raise HTTPException(404, "Simulation not found")
    copy = Simulation(owner_id=user.id, name=f"{src.name} (copy)",
                      kind=src.kind, params=src.params, result=src.result,
                      status=src.status)
    return repo.add(copy)


@router.delete("/{sim_id}", status_code=204)
def delete_simulation(sim_id: int, user: CurrentUser, db: DbSession):
    repo = SimulationRepository(db)
    sim = repo.get(sim_id)
    if not sim or sim.owner_id != user.id:
        raise HTTPException(404, "Simulation not found")
    repo.delete(sim)
