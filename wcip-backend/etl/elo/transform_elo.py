"""Normalize raw Elo records into the local schema."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from etl.elo.extract_elo import RawEloSnapshot
from etl.transform.normalize import canonical


@dataclass(frozen=True)
class EloRatingRecord:
    team_name: str
    rating: float
    rank: int | None
    raw_team_name: str
    raw_payload: dict[str, Any] | None


@dataclass(frozen=True)
class EloSnapshot:
    snapshot_id: str
    data_version: str
    rating_date: date
    source_url: str
    source_hash: str
    records: list[EloRatingRecord]
    http_status: int | None = None


def transform_raw_elo_snapshot(raw: RawEloSnapshot) -> EloSnapshot:
    records: list[EloRatingRecord] = []
    seen: set[str] = set()
    for idx, record in enumerate(sorted(raw.records, key=lambda row: row.rank or 9999), start=1):
        team_name = canonical(record.team_name)
        if not team_name or team_name in seen:
            continue
        seen.add(team_name)
        records.append(
            EloRatingRecord(
                team_name=team_name,
                rating=float(record.rating),
                rank=record.rank or idx,
                raw_team_name=record.team_name,
                raw_payload=record.raw_payload,
            )
        )

    snapshot_id = f"elo-{raw.rating_date.isoformat()}-{raw.source_hash[:12]}"
    return EloSnapshot(
        snapshot_id=snapshot_id,
        data_version=snapshot_id,
        rating_date=raw.rating_date,
        source_url=raw.source_url,
        source_hash=raw.source_hash,
        records=records,
        http_status=raw.http_status,
    )
