"""Team endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.core.cache import cache
from app.core.deps import DbSession
from app.models.player import Player
from app.repositories.repos import TeamRepository
from app.schemas.domain import EloPoint, PlayerOut, TeamOut
from ml.features import _get_player_strength_stats

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


@router.get("/{team_id}/players", response_model=list[PlayerOut])
def team_players(
    team_id: int,
    db: DbSession,
    position: str | None = Query(default=None, description="Filter by position: GK, DEF, MID, FWD"),
):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    stmt = (
        select(Player)
        .where(Player.team_name == team.name)
        .order_by(Player.position, Player.name)
    )
    if position:
        stmt = stmt.where(Player.position == position.upper())
    return db.scalars(stmt).all()


@router.get("/{team_id}/squad-strength")
def squad_strength(team_id: int, db: DbSession):
    team = TeamRepository(db).get(team_id)
    if not team:
        raise HTTPException(404, "Team not found")
    strength = _get_player_strength_stats(team.name)
    player_count = db.scalar(
        select(func.count(Player.id)).where(Player.team_name == team.name)
    ) or 0
    return {
        "team_id": team_id,
        "team_name": team.name,
        "player_count": player_count,
        **strength,
    }
