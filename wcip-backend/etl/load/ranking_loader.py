"""Load versioned FIFA ranking snapshots into the database."""
from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import SessionLocal
from app.models.ranking import FifaRankingEntry, FifaRankingSnapshot
from app.models.team import Team
from etl.extract.fifa_rankings import RankingSnapshot, fetch_fifa_ranking_snapshot
from etl.transform.normalize import canonical

logger = logging.getLogger(__name__)


def load_latest_fifa_ranking_snapshot(force_refresh: bool = False) -> dict[str, Any]:
    """Fetch the latest official FIFA snapshot and store it historically."""

    snapshot = fetch_fifa_ranking_snapshot(force_refresh=force_refresh)
    return load_fifa_ranking_snapshot(snapshot)


def load_fifa_ranking_snapshot(snapshot: RankingSnapshot) -> dict[str, Any]:
    """Upsert one ranking snapshot and its entries.

    The snapshot row is keyed by FIFA's ranking schedule id. Existing snapshots
    are not overwritten unless the same schedule id returns a different payload
    hash, which lets us correct partial or failed loads while preserving the
    historical version boundary.
    """

    db = SessionLocal()
    try:
        return _load_fifa_ranking_snapshot(db, snapshot)
    finally:
        db.close()


def _load_fifa_ranking_snapshot(db: Session, snapshot: RankingSnapshot) -> dict[str, Any]:
    existing = db.scalar(
        select(FifaRankingSnapshot).where(
            FifaRankingSnapshot.ranking_id == snapshot.ranking_id
        )
    )

    inserted_snapshot = False
    replaced_entries = False
    if existing:
        record = existing
        if existing.source_hash != snapshot.source_hash or existing.team_count != len(snapshot.entries):
            db.query(FifaRankingEntry).filter(
                FifaRankingEntry.snapshot_id == existing.id
            ).delete()
            replaced_entries = True
    else:
        record = FifaRankingSnapshot(ranking_id=snapshot.ranking_id)
        db.add(record)
        inserted_snapshot = True

    record.gender = snapshot.gender
    record.sport_type = snapshot.sport_type
    record.ranking_date = snapshot.ranking_date
    record.published_at = snapshot.published_at
    record.next_update_at = snapshot.next_update_at
    record.source_url = snapshot.source_url
    record.source_hash = snapshot.source_hash
    record.team_count = len(snapshot.entries)
    db.flush()

    entries_exist = db.scalar(
        select(FifaRankingEntry.id).where(FifaRankingEntry.snapshot_id == record.id)
    )
    entries_inserted = 0
    if not entries_exist:
        for entry in snapshot.entries:
            db.add(
                FifaRankingEntry(
                    snapshot_id=record.id,
                    team_name=entry.team_name,
                    team_code=entry.team_code,
                    confederation=entry.confederation,
                    rank=entry.rank,
                    previous_rank=entry.previous_rank,
                    rank_change=entry.rank_change,
                    points=entry.points,
                    previous_points=entry.previous_points,
                    points_change=entry.points_change,
                    raw_team_name=entry.raw_team_name,
                    raw_payload=json.dumps(entry.raw_payload, ensure_ascii=False)
                    if entry.raw_payload
                    else None,
                )
            )
            entries_inserted += 1

    current_snapshot = db.scalar(
        select(FifaRankingSnapshot)
        .where(FifaRankingSnapshot.is_current.is_(True))
        .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
    )
    should_be_current = (
        current_snapshot is None
        or snapshot.ranking_date >= current_snapshot.ranking_date
    )
    teams_updated = 0
    if should_be_current:
        db.query(FifaRankingSnapshot).update({FifaRankingSnapshot.is_current: False})
        record.is_current = True
        teams_updated = _update_team_display_ranks(db, snapshot)

    db.commit()

    logger.info(
        "Loaded FIFA ranking snapshot %s (%s): %d entries, %d teams updated",
        snapshot.ranking_id,
        snapshot.ranking_date,
        len(snapshot.entries),
        teams_updated,
    )
    return {
        "ranking_id": snapshot.ranking_id,
        "ranking_date": snapshot.ranking_date.isoformat(),
        "entries": len(snapshot.entries),
        "snapshot_inserted": inserted_snapshot,
        "entries_inserted": entries_inserted,
        "entries_replaced": replaced_entries,
        "is_current": should_be_current,
        "teams_updated": teams_updated,
    }


def _update_team_display_ranks(db: Session, snapshot: RankingSnapshot) -> int:
    teams = db.scalars(select(Team)).all()
    by_name = {canonical(team.name): team for team in teams}
    by_code = {team.code: team for team in teams if team.code}

    updated = 0
    for entry in snapshot.entries:
        team = by_name.get(entry.team_name)
        if team is None and entry.team_code:
            team = by_code.get(entry.team_code)
        if team is None:
            continue
        if team.fifa_rank != entry.rank:
            team.fifa_rank = entry.rank
            updated += 1
    return updated
