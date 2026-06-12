"""Saved simulations: create (sync or async), list, fetch, share, delete."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings
from app.core.deps import CurrentUser, DbSession
from app.models.simulation import SimKind, Simulation, SimStatus
from app.repositories.repos import SimulationRepository
from app.schemas.domain import (Page, SimulationCompareRequest,
                                SimulationCreateResponse, SimulationOut,
                                SimulationSaveRequest, SimulationUpdate)
from app.services import prediction

router = APIRouter(prefix="/simulations", tags=["simulations"])


@router.post("", response_model=SimulationCreateResponse, status_code=201)
def create_simulation(req: SimulationSaveRequest, user: CurrentUser, db: DbSession):
    repo = SimulationRepository(db)
    result = _saved_result_payload(req)
    params = _saved_params_payload(req)

    if result is not None:
        sim = Simulation(
            owner_id=user.id,
            name=req.name,
            kind=_sim_kind(req.simulation_type),
            params=params,
            result=result,
            status=SimStatus.completed,
        )
        repo.add(sim)
        return SimulationCreateResponse(id=sim.id, status="completed", result=result)

    runs = int(req.runs or 10000)
    overrides = req.overrides or req.scenario_overrides
    sim = Simulation(
        owner_id=user.id,
        name=req.name,
        kind=SimKind.monte_carlo,
        params={
            "edition": req.edition or "2022",
            "runs": runs,
            "overrides": overrides,
            "seed": req.seed,
            "deterministic": req.deterministic,
        },
    )
    repo.add(sim)

    # Small runs execute inline; large ones go to Celery.
    if runs <= settings.SYNC_SIM_RUN_THRESHOLD:
        result = prediction.run_monte_carlo(
            req.edition or "2022",
            runs,
            overrides,
            seed=req.seed,
            deterministic=req.deterministic,
        )
        repo.mark_completed(sim, result)
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


@router.post("/{sim_id}/compare")
def compare_simulations(
    sim_id: int,
    payload: SimulationCompareRequest,
    user: CurrentUser,
    db: DbSession,
):
    repo = SimulationRepository(db)
    ids = [sim_id, *payload.simulation_ids]
    seen: set[int] = set()
    sims: list[Simulation] = []
    for candidate_id in ids:
        if candidate_id in seen:
            continue
        seen.add(candidate_id)
        sim = repo.get(candidate_id)
        if not sim or sim.owner_id != user.id:
            raise HTTPException(404, "Simulation not found")
        sims.append(sim)

    return {
        "base_id": sim_id,
        "simulations": [
            {
                "id": sim.id,
                "name": sim.name,
                "kind": sim.kind.value if hasattr(sim.kind, "value") else str(sim.kind),
                "params": sim.params,
                "result": sim.result,
                "champion": _champion_summary(sim.result),
            }
            for sim in sims
        ],
        "champion_deltas": _champion_deltas(sims),
    }


@router.delete("/{sim_id}", status_code=204)
def delete_simulation(sim_id: int, user: CurrentUser, db: DbSession):
    repo = SimulationRepository(db)
    sim = repo.get(sim_id)
    if not sim or sim.owner_id != user.id:
        raise HTTPException(404, "Simulation not found")
    repo.delete(sim)


def _sim_kind(value: str) -> SimKind:
    normalized = (value or "tournament").strip().lower().replace("-", "_")
    mapping = {
        "match": SimKind.match,
        "prediction": SimKind.prediction,
        "ml": SimKind.prediction,
        "tournament": SimKind.tournament,
        "monte_carlo": SimKind.monte_carlo,
        "wc2026": SimKind.wc2026,
        "world_cup_2026": SimKind.wc2026,
        "scenario": SimKind.scenario,
        "scenarios": SimKind.scenario,
    }
    return mapping.get(normalized, SimKind.tournament)


def _saved_params_payload(req: SimulationSaveRequest) -> dict:
    return {
        "simulation_type": req.simulation_type,
        "edition": req.edition,
        "runs": req.runs,
        "seed": req.seed,
        "deterministic": req.deterministic,
        "input_teams": req.input_teams,
        "input_parameters": req.input_parameters,
        "overrides": req.overrides or req.scenario_overrides,
    }


def _saved_result_payload(req: SimulationSaveRequest) -> dict | None:
    if req.result is not None:
        return req.result
    payload = {
        "statistical_result": req.statistical_result,
        "ml_result": req.ml_result,
        "ensemble_result": req.ensemble_result,
        "tournament_result": req.tournament_result,
        "champion_probabilities": req.champion_probabilities,
        "bracket_output": req.bracket_output,
    }
    compact = {key: value for key, value in payload.items() if value is not None}
    if not compact:
        return None
    if req.tournament_result and "teams" in req.tournament_result:
        compact.setdefault("teams", req.tournament_result["teams"])
    return compact


def _champion_summary(result: dict | None) -> dict | None:
    if not result:
        return None
    teams = result.get("teams")
    if teams and isinstance(teams, list):
        top = teams[0]
        return {
            "team": top.get("team") or top.get("team_name"),
            "champion": top.get("champion") or top.get("champion_probability"),
        }
    tournament = result.get("tournament_result")
    if isinstance(tournament, dict):
        return _champion_summary(tournament)
    return None


def _champion_deltas(sims: list[Simulation]) -> list[dict]:
    if len(sims) < 2:
        return []
    base = _probability_map(sims[0].result)
    rows = []
    for sim in sims[1:]:
        current = _probability_map(sim.result)
        teams = sorted(set(base) | set(current))
        rows.append(
            {
                "simulation_id": sim.id,
                "name": sim.name,
                "deltas": [
                    {
                        "team": team,
                        "delta": current.get(team, 0.0) - base.get(team, 0.0),
                    }
                    for team in teams
                ],
            }
        )
    return rows


def _probability_map(result: dict | None) -> dict[str, float]:
    if not result:
        return {}
    teams = result.get("teams")
    if not isinstance(teams, list) and isinstance(result.get("tournament_result"), dict):
        teams = result["tournament_result"].get("teams")
    if not isinstance(teams, list):
        return {}
    out = {}
    for row in teams:
        team = row.get("team") or row.get("team_name")
        value = row.get("champion")
        if value is None:
            value = row.get("champion_probability", 0.0)
            value = float(value) / 100.0 if value and value > 1 else float(value or 0.0)
        if team:
            out[str(team)] = float(value or 0.0)
    return out
