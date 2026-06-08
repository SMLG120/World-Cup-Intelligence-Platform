"""Versioned ranking endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from sqlalchemy import select

from app.core.deps import AdminUser, DbSession
from app.models.ranking import FifaRankingEntry, FifaRankingSnapshot

router = APIRouter(prefix="/rankings", tags=["rankings"])


@router.get("/fifa/latest")
def latest_fifa_ranking(
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=250),
) -> dict[str, Any]:
    """Return the current stored FIFA ranking snapshot."""

    snapshot = _current_snapshot(db)
    if not snapshot:
        raise HTTPException(404, "No FIFA ranking snapshot has been loaded")
    return _snapshot_payload(db, snapshot, limit=limit)


@router.get("/fifa/snapshots")
def list_fifa_ranking_snapshots(db: DbSession) -> list[dict[str, Any]]:
    """List stored FIFA ranking snapshots without entry payloads."""

    rows = db.scalars(
        select(FifaRankingSnapshot)
        .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
    ).all()
    return [_snapshot_meta(row) for row in rows]


@router.get("/fifa/snapshots/{ranking_id}")
def get_fifa_ranking_snapshot(
    ranking_id: str,
    db: DbSession,
    limit: int = Query(default=250, ge=1, le=250),
) -> dict[str, Any]:
    """Return one stored FIFA ranking snapshot by FIFA schedule id."""

    snapshot = db.scalar(
        select(FifaRankingSnapshot).where(FifaRankingSnapshot.ranking_id == ranking_id)
    )
    if not snapshot:
        raise HTTPException(404, "FIFA ranking snapshot not found")
    return _snapshot_payload(db, snapshot, limit=limit)


@router.post("/fifa/refresh")
def refresh_fifa_ranking(
    background_tasks: BackgroundTasks,
    _user: AdminUser,
    force_refresh: bool = True,
    trigger_retraining: bool = False,
) -> dict[str, Any]:
    """Fetch the latest official FIFA ranking snapshot and store it."""

    background_tasks.add_task(
        _refresh_fifa_ranking,
        force_refresh,
        trigger_retraining,
    )
    return {
        "status": "ranking_refresh_started",
        "force_refresh": force_refresh,
        "trigger_retraining": trigger_retraining,
    }


def _refresh_fifa_ranking(force_refresh: bool, trigger_retraining: bool) -> None:
    from etl.monitoring.ranking_monitor import check_fifa_ranking_update

    check_fifa_ranking_update(
        force_refresh=force_refresh,
        trigger_retraining=trigger_retraining,
    )


def _current_snapshot(db) -> FifaRankingSnapshot | None:
    return db.scalar(
        select(FifaRankingSnapshot)
        .where(FifaRankingSnapshot.is_current.is_(True))
        .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
    )


def _snapshot_payload(db, snapshot: FifaRankingSnapshot, *, limit: int) -> dict[str, Any]:
    entries = db.scalars(
        select(FifaRankingEntry)
        .where(FifaRankingEntry.snapshot_id == snapshot.id)
        .order_by(FifaRankingEntry.rank.asc())
        .limit(limit)
    ).all()
    return {
        **_snapshot_meta(snapshot),
        "entries": [
            {
                "team_name": entry.team_name,
                "team_code": entry.team_code,
                "confederation": entry.confederation,
                "rank": entry.rank,
                "previous_rank": entry.previous_rank,
                "rank_change": entry.rank_change,
                "points": entry.points,
                "previous_points": entry.previous_points,
                "points_change": entry.points_change,
            }
            for entry in entries
        ],
    }


def _snapshot_meta(snapshot: FifaRankingSnapshot) -> dict[str, Any]:
    return {
        "id": snapshot.id,
        "ranking_id": snapshot.ranking_id,
        "gender": snapshot.gender,
        "sport_type": snapshot.sport_type,
        "ranking_date": snapshot.ranking_date.isoformat(),
        "published_at": snapshot.published_at.isoformat() if snapshot.published_at else None,
        "next_update_at": snapshot.next_update_at.isoformat() if snapshot.next_update_at else None,
        "source_url": snapshot.source_url,
        "team_count": snapshot.team_count,
        "is_current": snapshot.is_current,
        "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
    }
