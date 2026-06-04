"""Team endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.core.cache import cache
from app.core.deps import DbSession
from app.repositories.repos import TeamRepository
from app.schemas.domain import EloPoint, TeamOut

router = APIRouter(prefix="/teams", tags=["teams"])


@router.get("", response_model=list[TeamOut])
def list_teams(db: DbSession, confederation: str | None = Query(default=None)):
    cache_key = f"teams:{confederation or 'all'}"
    cached = cache.get_json(cache_key)
    if cached is not None:
        return cached
    teams = TeamRepository(db).list_all(confederation)
    payload = [TeamOut.model_validate(t).model_dump() for t in teams]
    cache.set_json(cache_key, payload)
    return payload


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return team


@router.get("/{team_id}/stats")
def team_stats(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    return {
        "id": team.id,
        "name": team.name,
        "elo": team.elo,
        "fifa_rank": team.fifa_rank,
        "attack": team.attack,
        "defence": team.defence,
        "chemistry": team.chemistry,
        "coach_quality": team.coach_quality,
    }


@router.get("/{team_id}/elo-history", response_model=list[EloPoint])
def elo_history(team_id: int, db: DbSession):
    repo = TeamRepository(db)
    if not repo.get(team_id):
        raise HTTPException(404, "Team not found")
    return repo.elo_history(team_id)
