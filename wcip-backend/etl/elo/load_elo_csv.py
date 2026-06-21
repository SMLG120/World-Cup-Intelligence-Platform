"""Load the static World Football Elo PDF CSV into Elo snapshot tables."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.db.base import SessionLocal
from app.models.team import EloHistory, EloRatingSnapshot, EloSourceLog, Team, TeamEloRating
from etl.transform.normalize import canonical
from scripts.validate_elo_csv import validate_csv

SOURCE_NAME = "World Football Elo Ratings PDF"
DEFAULT_CSV = Path("data/processed/world_football_elo_ratings_2026_06_21.csv")


def load_elo_csv(csv_path: str | Path = DEFAULT_CSV) -> dict[str, Any]:
    path = Path(csv_path)
    validation = validate_csv(path, require_full_extract=True, check_db_teams=True)
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    source_date = date.fromisoformat(rows[0]["source_date"])
    snapshot_version = f"elo-pdf-{source_date.isoformat()}-{source_hash[:12]}"

    db = SessionLocal()
    log = EloSourceLog(
        source_name=SOURCE_NAME,
        source_url=str(path.resolve()),
        status="started",
        snapshot_id=snapshot_version,
        data_version=snapshot_version,
        source_hash=source_hash,
        rows_fetched=len(rows),
        started_at=datetime.now(timezone.utc),
    )
    db.add(log)
    db.commit()

    try:
        result = _load_csv_rows(
            db,
            rows,
            csv_path=path,
            source_hash=source_hash,
            source_date=source_date,
            snapshot_version=snapshot_version,
            validation=validation,
        )
        log.status = "success"
        log.rows_loaded = int(result["rows_loaded"])
        log.completed_at = datetime.now(timezone.utc)
        log.metadata_json = json.dumps(result, default=str, sort_keys=True)
        db.commit()
        return result
    except Exception as exc:
        db.rollback()
        log = db.get(EloSourceLog, log.id)
        if log:
            log.status = "failed"
            log.error_message = str(exc)
            log.completed_at = datetime.now(timezone.utc)
            db.commit()
        raise
    finally:
        db.close()


def _load_csv_rows(
    db: Session,
    rows: list[dict[str, str]],
    *,
    csv_path: Path,
    source_hash: str,
    source_date: date,
    snapshot_version: str,
    validation: dict[str, Any],
) -> dict[str, Any]:
    existing = db.scalar(
        select(EloRatingSnapshot).where(EloRatingSnapshot.snapshot_id == snapshot_version)
    )
    if existing:
        entries = db.scalar(
            select(TeamEloRating.id).where(TeamEloRating.snapshot_id == existing.id).limit(1)
        )
        return {
            "snapshot_version": snapshot_version,
            "rating_date": source_date.isoformat(),
            "source_file": str(csv_path.resolve()),
            "source_name": SOURCE_NAME,
            "source_hash": source_hash,
            "rows_loaded": 0,
            "entries_already_present": bool(entries),
            "is_current": existing.is_current,
            "teams_matched": _count_matched_entries(db, existing.id),
            "validation": validation,
        }

    snapshot = EloRatingSnapshot(
        snapshot_id=snapshot_version,
        rating_date=source_date,
        source_url=str(csv_path.resolve()),
        source_hash=source_hash,
        team_count=len(rows),
        is_current=False,
        data_version=snapshot_version,
    )
    db.add(snapshot)
    db.flush()

    teams = db.scalars(select(Team)).all()
    teams_by_name = {canonical(team.name): team for team in teams}
    rows_loaded = 0
    teams_matched = 0
    ingested_at = datetime.now(timezone.utc).isoformat()
    source_file = str(csv_path.resolve())

    for row in rows:
        raw_name = row["team"].strip()
        normalized_name = canonical(raw_name)
        team = teams_by_name.get(normalized_name)
        if team:
            teams_matched += 1
        raw_payload = {
            "raw_team_name": raw_name,
            "normalized_team_name": normalized_name,
            "average_rank": _as_int(row["average_rank"]),
            "average_rating": _as_int(row["average_rating"]),
            "one_year_change_rank": _as_int(row["one_year_change_rank"]),
            "one_year_change_rating": _as_int(row["one_year_change_rating"]),
            "matches_total": _as_int(row["matches_total"]),
            "matches_home": _as_int(row["matches_home"]),
            "matches_away": _as_int(row["matches_away"]),
            "matches_neutral": _as_int(row["matches_neutral"]),
            "wins": _as_int(row["wins"]),
            "losses": _as_int(row["losses"]),
            "draws": _as_int(row["draws"]),
            "goals_for": _as_int(row["goals_for"]),
            "goals_against": _as_int(row["goals_against"]),
            "source_name": SOURCE_NAME,
            "source_date": row["source_date"],
            "source_file": source_file,
            "snapshot_version": snapshot_version,
            "ingested_at": ingested_at,
            "validation_status": "valid_matched" if team else "valid_unmatched",
        }
        db.add(
            TeamEloRating(
                snapshot_id=snapshot.id,
                team_id=team.id if team else None,
                team_name=normalized_name,
                team_code=team.code if team else None,
                rank=_as_int(row["rank"]),
                rating=float(row["rating"]),
                rating_date=source_date,
                source_url=source_file,
                data_version=snapshot_version,
                raw_payload=json.dumps(raw_payload, ensure_ascii=False, sort_keys=True),
            )
        )
        rows_loaded += 1

    current_snapshot = db.scalar(
        select(EloRatingSnapshot)
        .where(EloRatingSnapshot.is_current.is_(True))
        .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
        .limit(1)
    )
    should_be_current = current_snapshot is None or source_date >= current_snapshot.rating_date
    teams_updated = 0
    if should_be_current:
        db.query(EloRatingSnapshot).update({EloRatingSnapshot.is_current: False})
        snapshot.is_current = True
        teams_updated = _update_team_display_elo(db, snapshot.id, source_date, snapshot_version)

    db.commit()
    return {
        "snapshot_version": snapshot_version,
        "rating_date": source_date.isoformat(),
        "source_file": source_file,
        "source_name": SOURCE_NAME,
        "source_hash": source_hash,
        "rows_loaded": rows_loaded,
        "teams_matched": teams_matched,
        "teams_updated": teams_updated,
        "is_current": should_be_current,
        "validation": validation,
    }


def _update_team_display_elo(db: Session, snapshot_db_id: int, source_date: date, snapshot_version: str) -> int:
    entries = db.scalars(
        select(TeamEloRating).where(TeamEloRating.snapshot_id == snapshot_db_id)
    ).all()
    updated = 0
    recorded_at = datetime.combine(source_date, time.max).replace(tzinfo=timezone.utc)
    opponent = f"Elo snapshot:{snapshot_version}"
    for entry in entries:
        if not entry.team:
            continue
        if abs(float(entry.team.elo or 0) - float(entry.rating)) > 1e-6:
            entry.team.elo = float(entry.rating)
            updated += 1
        exists = db.scalar(
            select(EloHistory.id)
            .where(EloHistory.team_id == entry.team.id, EloHistory.opponent == opponent)
            .limit(1)
        )
        if not exists:
            db.add(
                EloHistory(
                    team_id=entry.team.id,
                    rating=float(entry.rating),
                    opponent=opponent,
                    recorded_at=recorded_at,
                )
            )
    return updated


def _count_matched_entries(db: Session, snapshot_db_id: int) -> int:
    return len(
        db.scalars(
            select(TeamEloRating).where(
                TeamEloRating.snapshot_id == snapshot_db_id,
                TeamEloRating.team_id.is_not(None),
            )
        ).all()
    )


def _as_int(value: str | int | None) -> int:
    return int(str(value or "0").strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_path", nargs="?", default=str(DEFAULT_CSV))
    args = parser.parse_args(argv)
    result = load_elo_csv(args.csv_path)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
