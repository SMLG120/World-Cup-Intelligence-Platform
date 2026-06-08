"""Monitoring for official FIFA ranking updates."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select

from app.db.base import SessionLocal
from app.models.ranking import FifaRankingEntry, FifaRankingSnapshot
from etl.extract.fifa_rankings import RankingSnapshot, fetch_fifa_ranking_snapshot
from etl.load.ranking_loader import load_fifa_ranking_snapshot

logger = logging.getLogger(__name__)

DEFAULT_RANK_DELTA_THRESHOLD = 5
DEFAULT_TOP_N = 50
DEFAULT_POINTS_DELTA_THRESHOLD = 25.0


@dataclass(frozen=True)
class RankingChange:
    team_name: str
    old_rank: int | None
    new_rank: int
    rank_delta: int | None
    old_points: float | None
    new_points: float | None
    points_delta: float | None


def check_fifa_ranking_update(
    *,
    force_refresh: bool = True,
    trigger_retraining: bool = False,
    rank_delta_threshold: int = DEFAULT_RANK_DELTA_THRESHOLD,
    points_delta_threshold: float = DEFAULT_POINTS_DELTA_THRESHOLD,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """Fetch, compare, store, and optionally trigger retraining."""

    snapshot = fetch_fifa_ranking_snapshot(force_refresh=force_refresh)
    current = _get_current_snapshot()
    changes = _compare_snapshots(current, snapshot)

    changed = current is None or current["ranking_id"] != snapshot.ranking_id or bool(changes)
    material_changes = [
        change for change in changes
        if _is_material(change, rank_delta_threshold, points_delta_threshold, top_n)
    ]
    should_retrain = bool(material_changes)

    load_result: dict[str, Any] | None = None
    if changed:
        load_result = load_fifa_ranking_snapshot(snapshot)
        logger.info(
            "FIFA ranking update detected: %s material changes out of %s total",
            len(material_changes),
            len(changes),
        )
    else:
        logger.info("No FIFA ranking update detected for %s", snapshot.ranking_id)

    retrain_result: Any = None
    retrain_error: str | None = None
    if should_retrain and trigger_retraining:
        try:
            from ml.retrain import run_retrain

            retrain_result = run_retrain(model_filter="all")
        except Exception as exc:  # noqa: BLE001
            retrain_error = str(exc)
            logger.error("Ranking-triggered retraining failed: %s", exc)

    return {
        "ranking_id": snapshot.ranking_id,
        "ranking_date": snapshot.ranking_date.isoformat(),
        "changed": changed,
        "changes": len(changes),
        "material_changes": len(material_changes),
        "should_retrain": should_retrain,
        "retraining_triggered": bool(should_retrain and trigger_retraining),
        "retrain_error": retrain_error,
        "retrain_result": retrain_result,
        "load_result": load_result,
        "top_changes": [
            {
                "team_name": change.team_name,
                "old_rank": change.old_rank,
                "new_rank": change.new_rank,
                "rank_delta": change.rank_delta,
                "old_points": change.old_points,
                "new_points": change.new_points,
                "points_delta": change.points_delta,
            }
            for change in material_changes[:20]
        ],
    }


def _get_current_snapshot() -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        snapshot = db.scalar(
            select(FifaRankingSnapshot)
            .where(FifaRankingSnapshot.is_current.is_(True))
            .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
        )
        if not snapshot:
            return None
        entries = db.scalars(
            select(FifaRankingEntry).where(FifaRankingEntry.snapshot_id == snapshot.id)
        ).all()
        return {
            "ranking_id": snapshot.ranking_id,
            "ranking_date": snapshot.ranking_date,
            "entries": {
                entry.team_name: {
                    "rank": entry.rank,
                    "points": entry.points,
                }
                for entry in entries
            },
        }
    finally:
        db.close()


def _compare_snapshots(
    current: dict[str, Any] | None,
    incoming: RankingSnapshot,
) -> list[RankingChange]:
    if current is None:
        return [
            RankingChange(
                team_name=entry.team_name,
                old_rank=None,
                new_rank=entry.rank,
                rank_delta=None,
                old_points=None,
                new_points=entry.points,
                points_delta=None,
            )
            for entry in incoming.entries
        ]

    old_entries = current.get("entries") or {}
    changes: list[RankingChange] = []
    for entry in incoming.entries:
        old = old_entries.get(entry.team_name)
        old_rank = old.get("rank") if old else None
        old_points = old.get("points") if old else None
        rank_delta = old_rank - entry.rank if old_rank is not None else None
        points_delta = (
            round(entry.points - old_points, 2)
            if entry.points is not None and old_points is not None
            else None
        )
        if old_rank != entry.rank or points_delta:
            changes.append(
                RankingChange(
                    team_name=entry.team_name,
                    old_rank=old_rank,
                    new_rank=entry.rank,
                    rank_delta=rank_delta,
                    old_points=old_points,
                    new_points=entry.points,
                    points_delta=points_delta,
                )
            )
    return changes


def _is_material(
    change: RankingChange,
    rank_delta_threshold: int,
    points_delta_threshold: float,
    top_n: int,
) -> bool:
    if change.old_rank is None:
        return change.new_rank <= top_n
    if min(change.old_rank, change.new_rank) <= 10 and change.old_rank != change.new_rank:
        return True
    if min(change.old_rank, change.new_rank) <= top_n and change.rank_delta is not None:
        return abs(change.rank_delta) >= rank_delta_threshold
    if change.points_delta is not None:
        return abs(change.points_delta) >= points_delta_threshold
    return False
