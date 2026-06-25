"""Player registry endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.player import Player
from app.schemas.domain import PlayerOut
from etl.transform.normalize import canonical

router = APIRouter(prefix="/players", tags=["players"])


@router.get("", response_model=list[PlayerOut])
def list_players(
    db: DbSession,
    team_name: str | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1),
    limit: int = Query(default=200, ge=1, le=1000),
):
    stmt = (
        select(Player)
        .where(Player.is_active.is_(True))
        .order_by(Player.team_name, Player.position, Player.name)
        .limit(limit)
    )
    if team_name:
        stmt = stmt.where(Player.team_name == canonical(team_name))
    if q:
        stmt = stmt.where(Player.name.ilike(f"%{q}%"))
    return db.scalars(stmt).all()


@router.get("/{player_id}", response_model=PlayerOut)
def get_player(player_id: int, db: DbSession):
    player = db.get(Player, player_id)
    if not player or not player.is_active:
        raise HTTPException(404, "Player not found")
    return player
