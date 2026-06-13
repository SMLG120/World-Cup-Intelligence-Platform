"""Load versioned World Football Elo snapshots into the database."""
from __future__ import annotations

import json
import logging
from datetime import datetime, time, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.team import EloHistory, EloRatingSnapshot, EloSourceLog, Team, TeamEloRating
from etl.elo.extract_elo import ELO_WORLD_CUP_URL, fetch_latest_elo_snapshot
from etl.elo.transform_elo import EloSnapshot, transform_raw_elo_snapshot
from etl.elo.validate_elo import assert_valid_elo_snapshot
from etl.transform.normalize import canonical

logger = logging.getLogger(__name__)


def load_latest_elo_snapshot(
    *,
    force_refresh: bool = False,
    allow_network: bool = True,
) -> dict[str, Any]:
    """Fetch, validate, and store the latest Elo snapshot."""

    log_id = _start_source_log(ELO_WORLD_CUP_URL)
    try:
        raw = fetch_latest_elo_snapshot(force_refresh=force_refresh, allow_network=allow_network)
        snapshot = transform_raw_elo_snapshot(raw)
        assert_valid_elo_snapshot(snapshot)
        result = load_elo_snapshot(snapshot)
        _finish_source_log(
            log_id,
            status="success",
            snapshot=snapshot,
            rows_loaded=int(result.get("entries", 0)),
            metadata={"force_refresh": force_refresh, "allow_network": allow_network, **result},
        )
        return result
    except Exception as exc:
        _finish_source_log(
            log_id,
            status="failed",
            error_message=str(exc),
            metadata={"force_refresh": force_refresh, "allow_network": allow_network},
        )
        raise


def load_elo_snapshot(snapshot: EloSnapshot) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return _load_elo_snapshot(db, snapshot)
    finally:
        db.close()


def _load_elo_snapshot(db: Session, snapshot: EloSnapshot) -> dict[str, Any]:
    existing = db.scalar(
        select(EloRatingSnapshot).where(EloRatingSnapshot.snapshot_id == snapshot.snapshot_id)
    )

    inserted_snapshot = False
    entries_replaced = False
    if existing:
        record = existing
        if existing.source_hash != snapshot.source_hash or existing.team_count != len(snapshot.records):
            db.query(TeamEloRating).filter(TeamEloRating.snapshot_id == existing.id).delete()
            entries_replaced = True
    else:
        record = EloRatingSnapshot(snapshot_id=snapshot.snapshot_id)
        db.add(record)
        inserted_snapshot = True

    record.rating_date = snapshot.rating_date
    record.source_url = snapshot.source_url
    record.source_hash = snapshot.source_hash
    record.team_count = len(snapshot.records)
    record.data_version = snapshot.data_version
    db.flush()

    entries_exist = db.scalar(
        select(TeamEloRating.id).where(TeamEloRating.snapshot_id == record.id).limit(1)
    )
    entries_inserted = 0
    if not entries_exist:
        teams = db.scalars(select(Team)).all()
        by_name = {canonical(team.name): team for team in teams}
        by_code = {team.code: team for team in teams if team.code}
        for entry in snapshot.records:
            team = by_name.get(entry.team_name)
            if team is None and entry.raw_payload:
                team_code = entry.raw_payload.get("team_code")
                if team_code:
                    team = by_code.get(str(team_code))
            db.add(
                TeamEloRating(
                    snapshot_id=record.id,
                    team_id=team.id if team else None,
                    team_name=entry.team_name,
                    team_code=team.code if team else None,
                    rank=entry.rank,
                    rating=entry.rating,
                    rating_date=snapshot.rating_date,
                    source_url=snapshot.source_url,
                    data_version=snapshot.data_version,
                    raw_payload=json.dumps(entry.raw_payload or {}, ensure_ascii=False, sort_keys=True),
                )
            )
            entries_inserted += 1

    current_snapshot = db.scalar(
        select(EloRatingSnapshot)
        .where(EloRatingSnapshot.is_current.is_(True))
        .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
        .limit(1)
    )
    should_be_current = (
        current_snapshot is None
        or snapshot.rating_date >= current_snapshot.rating_date
    )

    teams_updated = 0
    if should_be_current:
        db.query(EloRatingSnapshot).update({EloRatingSnapshot.is_current: False})
        record.is_current = True
        teams_updated = _update_team_display_elo(db, snapshot)

    db.commit()
    return {
        "snapshot_id": snapshot.snapshot_id,
        "data_version": snapshot.data_version,
        "rating_date": snapshot.rating_date.isoformat(),
        "entries": len(snapshot.records),
        "snapshot_inserted": inserted_snapshot,
        "entries_inserted": entries_inserted,
        "entries_replaced": entries_replaced,
        "is_current": should_be_current,
        "teams_updated": teams_updated,
        "source_url": snapshot.source_url,
    }


def _update_team_display_elo(db: Session, snapshot: EloSnapshot) -> int:
    teams = db.scalars(select(Team)).all()
    by_name = {canonical(team.name): team for team in teams}
    updated = 0
    recorded_at = datetime.combine(snapshot.rating_date, time.max).replace(tzinfo=timezone.utc)
    opponent = f"Elo snapshot:{snapshot.snapshot_id}"

    for entry in snapshot.records:
        team = by_name.get(entry.team_name)
        if team is None:
            continue
        if abs(float(team.elo or 0) - entry.rating) > 1e-6:
            team.elo = entry.rating
            updated += 1
        exists = db.scalar(
            select(EloHistory.id)
            .where(
                EloHistory.team_id == team.id,
                EloHistory.opponent == opponent,
            )
            .limit(1)
        )
        if not exists:
            db.add(
                EloHistory(
                    team_id=team.id,
                    rating=entry.rating,
                    opponent=opponent,
                    recorded_at=recorded_at,
                )
            )
    return updated


def _start_source_log(source_url: str) -> int | None:
    db = SessionLocal()
    try:
        row = EloSourceLog(
            source_name="WorldFootballElo",
            source_url=source_url,
            status="started",
            started_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        return row.id
    except Exception:
        logger.debug("Could not create Elo source log", exc_info=True)
        db.rollback()
        return None
    finally:
        db.close()


def _finish_source_log(
    log_id: int | None,
    *,
    status: str,
    snapshot: EloSnapshot | None = None,
    rows_loaded: int | None = None,
    error_message: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    if log_id is None:
        return
    db = SessionLocal()
    try:
        row = db.get(EloSourceLog, log_id)
        if not row:
            return
        row.status = status
        row.completed_at = datetime.now(timezone.utc)
        row.error_message = error_message
        row.metadata_json = json.dumps(metadata or {}, default=str, sort_keys=True)
        if snapshot:
            row.snapshot_id = snapshot.snapshot_id
            row.data_version = snapshot.data_version
            row.source_hash = snapshot.source_hash
            row.http_status = snapshot.http_status
            row.rows_fetched = len(snapshot.records)
            row.rows_loaded = rows_loaded
            row.source_url = snapshot.source_url
        db.commit()
    except Exception:
        logger.debug("Could not finish Elo source log", exc_info=True)
        db.rollback()
    finally:
        db.close()
