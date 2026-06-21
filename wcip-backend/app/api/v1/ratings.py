"""Rating APIs for Elo history and latest snapshots."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.deps import DbSession
from app.models.team import EloRatingSnapshot, Team, TeamEloRating

router = APIRouter(prefix="/ratings", tags=["ratings"])


@router.get("/elo/latest")
def latest_elo_ratings(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=250),
) -> dict[str, Any]:
    snapshot = db.scalar(
        select(EloRatingSnapshot)
        .where(EloRatingSnapshot.is_current.is_(True))
        .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
        .limit(1)
    )
    if not snapshot:
        teams = db.scalars(select(Team).order_by(Team.elo.desc(), Team.name.asc()).limit(limit)).all()
        if not teams:
            raise HTTPException(
                404,
                {
                    "error_code": "elo_snapshot_missing",
                    "message": "No Elo ratings are available yet.",
                    "detail": "Run the WC2026 seed ETL or Elo refresh pipeline first.",
                },
            )
        today = date.today().isoformat()
        return {
            "snapshot_id": "teams-display-cache",
            "data_version": "teams-display-cache",
            "rating_date": today,
            "source_url": "local-team-table-cache:elo",
            "source_note": "No versioned Elo snapshot is current; displaying cached Team.elo values last written by Elo seed/refresh.",
            "team_count": len(teams),
            "created_at": None,
            "entries": [
                {
                    "team_name": team.name,
                    "team_code": team.code,
                    "rank": index,
                    "rating": float(team.elo),
                    "rating_date": today,
                    "data_version": "teams-display-cache",
                    "source_url": "local-team-table-cache:elo",
                    "created_at": None,
                }
                for index, team in enumerate(teams, start=1)
            ],
        }
    rows = db.scalars(
        select(TeamEloRating)
        .where(TeamEloRating.snapshot_id == snapshot.id)
        .order_by(TeamEloRating.rank.asc(), TeamEloRating.rating.desc())
        .limit(limit)
    ).all()
    return {
        "snapshot_id": snapshot.snapshot_id,
        "data_version": snapshot.data_version,
        "rating_date": snapshot.rating_date.isoformat(),
        "source_url": snapshot.source_url,
        "team_count": snapshot.team_count,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        "entries": [_elo_entry(row) for row in rows],
    }


@router.get("/elo/history/{team_id}")
def team_elo_history(
    team_id: int,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    team = db.get(Team, team_id)
    if not team:
        raise HTTPException(404, {"error_code": "team_not_found", "message": "Team not found", "detail": team_id})
    rows = db.scalars(
        select(TeamEloRating)
        .where(TeamEloRating.team_id == team_id)
        .order_by(TeamEloRating.rating_date.desc(), TeamEloRating.id.desc())
        .limit(limit)
    ).all()
    return {
        "team_id": team.id,
        "team_name": team.name,
        "entries": [_elo_entry(row) for row in rows],
    }


def _elo_entry(row: TeamEloRating) -> dict[str, Any]:
    return {
        "team_name": row.team_name,
        "team_code": row.team_code,
        "rank": row.rank,
        "rating": row.rating,
        "rating_date": row.rating_date.isoformat(),
        "data_version": row.data_version,
        "source_url": row.source_url,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
