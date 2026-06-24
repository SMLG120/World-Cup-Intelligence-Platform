"""Data refresh orchestration and freshness summaries."""
from __future__ import annotations

import logging
from datetime import date, datetime, time, timezone
from typing import Any, Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.db.base import SessionLocal
from app.models.match_result import MLModelRecord, MatchResult, QualifiedTeam
from app.models.player import Coach, Player, PlayerRatingImport
from app.models.ranking import FifaRankingSnapshot, RankingSourceLog
from app.models.team import EloRatingSnapshot, EloSourceLog, TeamEloRating
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


def refresh_all_live_football_data() -> dict[str, Any]:
    """Coordinated refresh of all live football data sources.

    Runs in a fixed, safe order:
      1. Match results  — latest scores and fixtures
      2. Elo ratings    — updated world rankings from eloratings.net / Wikipedia fallback
      3. FIFA rankings  — latest official FIFA publication
      4. Player data    — squad/availability CSV if present
      5. Prediction cache — invalidate stale predictions
      6. Retraining check — mark models for recalibration if data changed materially

    Each step is fault-tolerant: a failure in one source does not block the others.
    All steps are idempotent; running this twice is safe.
    """
    started_at = _iso(datetime.now(timezone.utc))
    results: dict[str, Any] = {}
    step_log: list[dict[str, Any]] = []

    def _step(name: str, fn) -> dict[str, Any]:
        logger.info("refresh_all_live_football_data: starting %s", name)
        result = fn()
        step_log.append({"step": name, "status": result.get("status"), "at": _iso(datetime.now(timezone.utc))})
        logger.info("refresh_all_live_football_data: %s → %s", name, result.get("status"))
        return result

    # 1. Latest match results (martj42 CSV → MatchResult table)
    results["match_results"] = _step("match_results", refresh_world_cup_results)

    # 2. Elo ratings (eloratings.net → Wikipedia fallback → embedded fallback)
    results["elo"] = _step("elo", refresh_elo_ratings)

    # 3. FIFA rankings
    results["fifa_rankings"] = _step("fifa_rankings", refresh_fifa_rankings)

    # 4. Player availability / squad CSV
    results["player_availability"] = _step("player_availability", refresh_player_availability)

    # 5. Invalidate prediction cache so fresh data is used next request
    results["prediction_cache"] = _step("prediction_cache", refresh_prediction_cache)

    # 6. Evaluate whether updated data warrants model recalibration
    try:
        from ml.retrain_if_needed import evaluate_retraining_need

        match_inserted = int((results["match_results"].get("result") or {}).get("inserted") or 0)
        elo_inner = results["elo"].get("result") or {}
        elo_changed = int(elo_inner.get("entries_inserted") or 0) + int(elo_inner.get("entries_replaced") or 0)
        fifa_inner = results["fifa_rankings"].get("result") or {}
        ranking_changes = int(fifa_inner.get("material_changes") or 0)
        player_inner = results["player_availability"].get("result") or {}
        player_changed = int(player_inner.get("valid_rows") or 0) if player_inner.get("status") not in (None, "skipped") else 0

        retrain_report = evaluate_retraining_need(
            material_ranking_changes=ranking_changes,
            material_elo_changes=elo_changed,
            changed_player_records=player_changed,
            changed_match_results=match_inserted,
            apply=True,
        )
        results["retraining_check"] = {"status": "ok", "result": retrain_report}
        step_log.append({"step": "retraining_check", "status": "ok", "action": retrain_report.get("action"), "at": _iso(datetime.now(timezone.utc))})
        logger.info(
            "refresh_all_live_football_data: retraining_check → action=%s reasons=%s",
            retrain_report.get("action"),
            retrain_report.get("reasons"),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("refresh_all_live_football_data: retraining_check failed")
        results["retraining_check"] = {"status": "failed", "detail": str(exc)}
        step_log.append({"step": "retraining_check", "status": "failed"})

    ok_statuses = sum(1 for v in results.values() if v.get("status") == "ok")
    overall = "ok" if ok_statuses == len(results) else ("partial" if ok_statuses > 0 else "failed")

    return {
        "task": "refresh_all_live_football_data",
        "status": overall,
        "started_at": started_at,
        "finished_at": _iso(datetime.now(timezone.utc)),
        "steps": step_log,
        "results": results,
    }


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
    wc_team_names = db.scalars(
        select(QualifiedTeam.team_name)
        .where(QualifiedTeam.tournament_year == 2026)
        .order_by(QualifiedTeam.team_name)
    ).all()
    team_count = len(wc_team_names)
    player_count = db.scalar(select(func.count()).select_from(Player)) or 0
    coach_count = db.scalar(select(func.count()).select_from(Coach)) or 0
    match_count = db.scalar(select(func.count()).select_from(MatchResult)) or 0
    model_count = db.scalar(
        select(func.count()).select_from(MLModelRecord).where(MLModelRecord.is_active.is_(True))
    ) or 0
    elo_rows = (
        db.scalar(
            select(func.count())
            .select_from(TeamEloRating)
            .where(TeamEloRating.snapshot_id == elo.id)
        )
        if elo
        else 0
    )
    fifa_rows = fifa.team_count if fifa else 0
    rated_player_count = db.scalar(
        select(func.count()).select_from(Player).where(Player.player_rating.is_not(None))
    ) or 0

    missing_rating_teams: list[str] = []
    for team_name in wc_team_names:
        rated_for_team = db.scalar(
            select(func.count())
            .select_from(Player)
            .where(Player.team_name == team_name, Player.player_rating.is_not(None))
        ) or 0
        if rated_for_team == 0:
            missing_rating_teams.append(team_name)

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
    warnings: list[str] = []
    if missing_rating_teams:
        sample = ", ".join(missing_rating_teams[:8])
        suffix = "" if len(missing_rating_teams) <= 8 else f", and {len(missing_rating_teams) - 8} more"
        warnings.append(
            f"Player ratings missing for {sample}{suffix}; neutral defaults are used."
        )

    source_status = {
        "elo": {
            "status": "available" if elo else "missing",
            "source_name": getattr(last_elo_log, "source_name", None) if last_elo_log else "World Football Elo",
            "source_date": elo.rating_date.isoformat() if elo else None,
            "source_url": elo.source_url if elo else None,
            "rows": int(elo_rows or 0),
            "version": elo.data_version if elo else None,
            "last_run_status": _log_status(last_elo_log),
        },
        "fifa_rankings": {
            "status": "available" if fifa else "missing",
            "source_name": getattr(last_fifa_log, "source_name", None) if last_fifa_log else "FIFA",
            "source_date": fifa.ranking_date.isoformat() if fifa else None,
            "source_url": fifa.source_url if fifa else None,
            "rows": int(fifa_rows or 0),
            "version": fifa.ranking_id if fifa else None,
            "last_run_status": _log_status(last_fifa_log),
        },
        "squads": {
            "status": "available" if team_count >= 48 and player_count >= 1200 and coach_count >= 48 else "partial" if player_count or coach_count or team_count else "missing",
            "teams": int(team_count),
            "players": int(player_count),
            "coaches": int(coach_count),
            "source_name": player_import.source_name if player_import else None,
            "source_date": _iso(player_timestamp),
        },
        "player_ratings": {
            "status": "available" if rated_player_count and not missing_rating_teams else "partial" if rated_player_count else "missing",
            "rated_players": int(rated_player_count),
            "missing_teams": missing_rating_teams,
            "source_name": player_import.source_name if player_import else None,
            "source_version": player_import.source_version if player_import else None,
            "last_run_status": player_import.status if player_import else "not_loaded",
        },
        "matches": {
            "status": "available" if match_count else "missing",
            "rows": int(match_count),
            "last_update": _iso(match_updated),
        },
        "models": {
            "status": "available" if model_count else "missing",
            "active_models": int(model_count),
            "latest_model": model.version if model else None,
            "last_trained_at": _iso(model.trained_at if model else None),
        },
    }
    missing_sources = [
        label
        for label, source in (
            ("Elo", source_status["elo"]),
            ("FIFA rankings", source_status["fifa_rankings"]),
            ("squads", source_status["squads"]),
            ("player ratings", source_status["player_ratings"]),
            ("matches", source_status["matches"]),
            ("models", source_status["models"]),
        )
        if source["status"] in {"missing", "partial"}
    ]
    has_any_freshness = any((elo, fifa, match_updated, player_timestamp, model))
    status = "available" if not missing_sources and not warnings else "partial"
    message = None
    if not has_any_freshness:
        status = "unavailable"
        message = "Database is reachable but no source data has been imported."
    elif missing_sources:
        message = f"Some sources are missing or partial: {', '.join(missing_sources)}."

    return {
        "status": status,
        "message": message,
        "warnings": warnings,
        "sources": source_status,
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
