"""Data refresh orchestration and freshness summaries."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.db.base import SessionLocal
from app.models.match_result import MLModelRecord, MatchResult
from app.models.player import Player, PlayerRatingImport
from app.models.ranking import FifaRankingSnapshot, RankingSourceLog
from app.models.team import EloRatingSnapshot, EloSourceLog
from ml.features import FEATURE_VERSION

logger = logging.getLogger(__name__)


def refresh_elo_ratings() -> dict[str, Any]:
    from etl.elo import load_latest_elo_snapshot

    return _run_refresh("refresh_elo_ratings", lambda: load_latest_elo_snapshot(force_refresh=True))


def refresh_fifa_rankings() -> dict[str, Any]:
    from etl.monitoring.ranking_monitor import check_fifa_ranking_update

    return _run_refresh(
        "refresh_fifa_rankings",
        lambda: check_fifa_ranking_update(force_refresh=True, trigger_retraining=False),
    )


def refresh_world_cup_results() -> dict[str, Any]:
    from etl.pipeline import run_historical_results

    return _run_refresh(
        "refresh_world_cup_results",
        lambda: {"inserted": run_historical_results(force_refresh=False)},
    )


def refresh_player_availability() -> dict[str, Any]:
    from etl.pipeline import run_player_rating_import

    return _run_refresh("refresh_player_availability", run_player_rating_import)


def refresh_prediction_cache() -> dict[str, Any]:
    def _refresh() -> dict[str, Any]:
        deleted = cache.invalidate_prefix("match:", "teams:", "wc2026", "prediction:")
        return {"cache_backend": cache.kind, "keys_invalidated": deleted}

    return _run_refresh("refresh_prediction_cache", _refresh)


def refresh_all_data() -> dict[str, Any]:
    results = {
        "elo": refresh_elo_ratings(),
        "fifa_rankings": refresh_fifa_rankings(),
        "match_results": refresh_world_cup_results(),
        "player_availability": refresh_player_availability(),
        "prediction_cache": refresh_prediction_cache(),
    }
    status = "ok" if all(item.get("status") == "ok" for item in results.values()) else "partial"
    return {"status": status, "results": results}


def get_data_freshness() -> dict[str, Any]:
    db = SessionLocal()
    try:
        return get_data_freshness_from_db(db)
    finally:
        db.close()


def get_data_freshness_from_db(db: Session) -> dict[str, Any]:
    elo = db.scalar(
        select(EloRatingSnapshot)
        .where(EloRatingSnapshot.is_current.is_(True))
        .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
        .limit(1)
    )
    fifa = db.scalar(
        select(FifaRankingSnapshot)
        .where(FifaRankingSnapshot.is_current.is_(True))
        .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
        .limit(1)
    )
    match_updated = db.scalar(select(func.max(MatchResult.created_at)))
    player_updated = db.scalar(select(func.max(Player.updated_at)))
    player_import = db.scalar(
        select(PlayerRatingImport)
        .order_by(PlayerRatingImport.imported_at.desc(), PlayerRatingImport.id.desc())
        .limit(1)
    )
    model = db.scalar(
        select(MLModelRecord)
        .where(MLModelRecord.is_active.is_(True))
        .order_by(MLModelRecord.trained_at.desc(), MLModelRecord.id.desc())
        .limit(1)
    )
    last_elo_log = db.scalar(
        select(EloSourceLog)
        .order_by(EloSourceLog.started_at.desc(), EloSourceLog.id.desc())
        .limit(1)
    )
    last_fifa_log = db.scalar(
        select(RankingSourceLog)
        .order_by(RankingSourceLog.started_at.desc(), RankingSourceLog.id.desc())
        .limit(1)
    )

    snapshot_parts = [
        f"elo:{elo.data_version}" if elo else "elo:none",
        f"fifa:{fifa.ranking_id}" if fifa else "fifa:none",
        f"feature:{FEATURE_VERSION}",
        f"model:{model.version}" if model else "model:none",
    ]

    player_timestamp = player_updated or (player_import.imported_at if player_import else None)
    data_snapshot_timestamp = _latest_iso(
        elo.created_at if elo else None,
        fifa.created_at if fifa else None,
        match_updated,
        player_timestamp,
        model.trained_at if model else None,
    )

    return {
        "generated_at": _iso(datetime.now(timezone.utc)),
        "data_snapshot_timestamp": data_snapshot_timestamp,
        "last_elo_update": _iso(elo.created_at if elo else None),
        "last_elo_rating_date": elo.rating_date.isoformat() if elo else None,
        "elo_data_version": elo.data_version if elo else None,
        "elo_source_url": elo.source_url if elo else None,
        "last_fifa_ranking_update": _iso(fifa.created_at if fifa else None),
        "last_fifa_ranking_date": fifa.ranking_date.isoformat() if fifa else None,
        "fifa_data_version": fifa.ranking_id if fifa else None,
        "fifa_source_url": fifa.source_url if fifa else None,
        "last_match_result_update": _iso(match_updated),
        "last_player_data_update": _iso(player_timestamp),
        "player_data_source": player_import.source_name if player_import else None,
        "model_version": model.version if model else None,
        "model_trained_at": _iso(model.trained_at if model else None),
        "feature_version": FEATURE_VERSION,
        "data_snapshot_version": "|".join(snapshot_parts),
        "using_latest_cached_snapshot": bool(elo or fifa),
        "source_status": {
            "elo": _log_status(last_elo_log),
            "fifa": _log_status(last_fifa_log),
            "players": player_import.status if player_import else "not_loaded",
        },
    }


def _run_refresh(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    logger.info("%s started", name)
    try:
        result = fn()
        logger.info("%s finished: %s", name, result)
        return {
            "task": name,
            "status": "ok",
            "started_at": _iso(started),
            "finished_at": _iso(datetime.now(timezone.utc)),
            "result": result,
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("%s failed", name)
        return {
            "task": name,
            "status": "failed",
            "started_at": _iso(started),
            "finished_at": _iso(datetime.now(timezone.utc)),
            "error_code": "data_refresh_failed",
            "message": f"{name} failed; using latest cached snapshot when available.",
            "detail": str(exc),
        }


def _log_status(row: Any) -> str:
    if not row:
        return "not_loaded"
    return str(getattr(row, "status", "unknown"))


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _latest_iso(*values: Any) -> str | None:
    normalized = [_as_datetime(value) for value in values]
    normalized = [value for value in normalized if value is not None]
    if not normalized:
        return None
    return max(normalized).isoformat()


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, date):
        return datetime.combine(value, time.min).replace(tzinfo=timezone.utc)
    return None
