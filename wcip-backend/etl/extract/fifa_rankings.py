"""Extract layer for FIFA Men's World Ranking snapshots.

The production source is FIFA's own ranking page plus the FDCP JSON endpoint
used by that page:

    https://inside.fifa.com/fifa-world-ranking/men
    https://api.fifa.com/api/v3/fifarankings/rankings/rankingsbyschedule

Snapshots are versioned by FIFA's ranking schedule id. The legacy
``fetch_fifa_rankings`` wrapper is kept for older seed code, but it now reads
from a versioned snapshot whenever one is available.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable

import httpx

from etl.transform.normalize import canonical

logger = logging.getLogger(__name__)

FIFA_RANKING_PAGE_URL = "https://inside.fifa.com/fifa-world-ranking/men"
FIFA_RANKINGS_API_URL = (
    "https://api.fifa.com/api/v3/fifarankings/rankings/rankingsbyschedule"
)
DEFAULT_LANGUAGE = "en-GB"
DEFAULT_MIN_ENTRIES = 150

_CACHE = Path(__file__).parents[2] / "data" / "cache" / "fifa_rankings.json"


@dataclass(frozen=True)
class RankingEntry:
    team_name: str
    rank: int
    team_code: str | None = None
    confederation: str | None = None
    previous_rank: int | None = None
    rank_change: int | None = None
    points: float | None = None
    previous_points: float | None = None
    points_change: float | None = None
    raw_team_name: str | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class RankingSnapshot:
    ranking_id: str
    ranking_date: date
    published_at: datetime | None
    next_update_at: datetime | None
    source_url: str
    source_hash: str
    entries: list[RankingEntry]
    gender: str = "men"
    sport_type: str = "football"


def fetch_fifa_ranking_snapshot(
    *,
    force_refresh: bool = False,
    ranking_id: str | None = None,
    language: str = DEFAULT_LANGUAGE,
    min_entries: int = DEFAULT_MIN_ENTRIES,
) -> RankingSnapshot:
    """Fetch and normalize one official FIFA ranking snapshot."""

    if not force_refresh and _CACHE.exists():
        cached = _read_cached_snapshot()
        if cached and (ranking_id is None or cached.ranking_id == ranking_id):
            return cached

    metadata = _fetch_ranking_metadata(language=language)
    selected = _select_ranking_date(metadata, ranking_id)
    selected_id = str(selected["id"])
    published_at = _parse_datetime(selected.get("iso"))
    ranking_date = _parse_date(selected.get("matchWindowEndDate")) or (
        published_at.date() if published_at else date.today()
    )
    next_update_at = _parse_datetime(metadata.get("next_update_at"))

    raw = _fetch_ranking_payload(selected_id, language=language)
    entries = _normalize_entries(raw.get("Results") or [])
    snapshot = RankingSnapshot(
        ranking_id=selected_id,
        ranking_date=ranking_date,
        published_at=published_at,
        next_update_at=next_update_at,
        source_url=f"{FIFA_RANKING_PAGE_URL}?dateId={selected_id}",
        source_hash=_payload_hash(raw),
        entries=entries,
    )
    validate_ranking_snapshot(snapshot, min_entries=min_entries)
    _write_cached_snapshot(snapshot)
    return snapshot


def fetch_fifa_rankings(force_refresh: bool = False) -> Dict[str, int]:
    """Return a compatibility ``{team_name: rank}`` map from the latest snapshot."""

    if not force_refresh and _CACHE.exists():
        try:
            payload = json.loads(_CACHE.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and "entries" not in payload:
                return {canonical(k): int(v) for k, v in payload.items()}
        except Exception:
            logger.debug("Could not read legacy ranking cache", exc_info=True)

    try:
        snapshot = fetch_fifa_ranking_snapshot(force_refresh=force_refresh)
    except Exception as exc:
        logger.warning("Official FIFA ranking snapshot unavailable: %s", exc)
        cached = _read_cached_snapshot()
        if cached:
            snapshot = cached
        else:
            return _read_legacy_cache()

    return {entry.team_name: entry.rank for entry in snapshot.entries}


def validate_ranking_snapshot(
    snapshot: RankingSnapshot,
    *,
    min_entries: int = DEFAULT_MIN_ENTRIES,
) -> None:
    """Raise ``ValueError`` when a snapshot is not plausible enough to store."""

    if not snapshot.ranking_id:
        raise ValueError("FIFA ranking snapshot is missing ranking_id")
    if len(snapshot.entries) < min_entries:
        raise ValueError(
            f"FIFA ranking snapshot has {len(snapshot.entries)} entries; "
            f"expected at least {min_entries}"
        )

    ranks = [entry.rank for entry in snapshot.entries]
    if len(ranks) != len(set(ranks)):
        raise ValueError("FIFA ranking snapshot contains duplicate rank values")
    if min(ranks) != 1:
        raise ValueError("FIFA ranking snapshot does not start at rank 1")

    duplicates = _duplicates(entry.team_name for entry in snapshot.entries)
    if duplicates:
        raise ValueError(f"FIFA ranking snapshot has duplicate teams: {duplicates[:5]}")


def snapshot_to_dict(snapshot: RankingSnapshot) -> dict[str, Any]:
    """Serialize a ranking snapshot to JSON-compatible data."""

    payload = asdict(snapshot)
    payload["ranking_date"] = snapshot.ranking_date.isoformat()
    payload["published_at"] = snapshot.published_at.isoformat() if snapshot.published_at else None
    payload["next_update_at"] = snapshot.next_update_at.isoformat() if snapshot.next_update_at else None
    return payload


def snapshot_from_dict(payload: dict[str, Any]) -> RankingSnapshot:
    """Deserialize a cached ranking snapshot."""

    return RankingSnapshot(
        ranking_id=str(payload["ranking_id"]),
        ranking_date=date.fromisoformat(str(payload["ranking_date"])),
        published_at=_parse_datetime(payload.get("published_at")),
        next_update_at=_parse_datetime(payload.get("next_update_at")),
        source_url=str(payload.get("source_url") or FIFA_RANKING_PAGE_URL),
        source_hash=str(payload.get("source_hash") or ""),
        gender=str(payload.get("gender") or "men"),
        sport_type=str(payload.get("sport_type") or "football"),
        entries=[
            RankingEntry(
                team_name=canonical(str(item["team_name"])),
                team_code=item.get("team_code"),
                confederation=item.get("confederation"),
                rank=int(item["rank"]),
                previous_rank=_optional_int(item.get("previous_rank")),
                rank_change=_optional_int(item.get("rank_change")),
                points=_optional_float(item.get("points")),
                previous_points=_optional_float(item.get("previous_points")),
                points_change=_optional_float(item.get("points_change")),
                raw_team_name=item.get("raw_team_name"),
                raw_payload=item.get("raw_payload"),
            )
            for item in payload.get("entries", [])
        ],
    )


def _fetch_ranking_metadata(*, language: str) -> dict[str, Any]:
    params = {"language": language}
    response = httpx.get(FIFA_RANKING_PAGE_URL, params=params, timeout=30)
    response.raise_for_status()
    next_data = _extract_next_data(response.text)
    ranking = next_data["props"]["pageProps"]["pageData"]["ranking"]
    return {
        "dates": ranking.get("dates") or [],
        "all_available_dates": ranking.get("allAvailableDates") or [],
        "last_update_at": ranking.get("lastUpdateDate"),
        "next_update_at": ranking.get("nextUpdateDate"),
    }


def _fetch_ranking_payload(ranking_id: str, *, language: str) -> dict[str, Any]:
    response = httpx.get(
        FIFA_RANKINGS_API_URL,
        params={"rankingScheduleId": ranking_id, "language": language},
        timeout=30,
        headers={"User-Agent": "wcip-ranking-ingestion/1.0"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError("FIFA ranking API returned a non-object payload")
    return payload


def _select_ranking_date(metadata: dict[str, Any], ranking_id: str | None) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for year_group in metadata.get("dates") or []:
        candidates.extend(year_group.get("dates") or [])
    if not candidates:
        raise ValueError("FIFA ranking page did not expose ranking dates")

    if ranking_id:
        for item in candidates:
            if item.get("id") == ranking_id:
                return item
        raise ValueError(f"FIFA ranking date id not found: {ranking_id}")

    return candidates[0]


def _normalize_entries(rows: Iterable[dict[str, Any]]) -> list[RankingEntry]:
    entries: list[RankingEntry] = []
    for row in rows:
        raw_name = row.get("TeamName")
        rank = _optional_int(row.get("Rank"))
        if not raw_name or rank is None:
            continue
        points = _optional_float(row.get("TotalPoints"))
        previous_points = _optional_float(row.get("PrevPoints"))
        previous_rank = _optional_int(row.get("PrevRank"))
        entries.append(
            RankingEntry(
                team_name=canonical(str(raw_name)),
                team_code=row.get("IdCountry"),
                confederation=row.get("ConfederationName"),
                rank=rank,
                previous_rank=previous_rank,
                rank_change=(previous_rank - rank) if previous_rank is not None else None,
                points=points,
                previous_points=previous_points,
                points_change=(
                    round(points - previous_points, 2)
                    if points is not None and previous_points is not None
                    else None
                ),
                raw_team_name=str(raw_name),
                raw_payload=row,
            )
        )
    return sorted(entries, key=lambda entry: entry.rank)


def _extract_next_data(html: str) -> dict[str, Any]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.+?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise ValueError("FIFA ranking page did not include __NEXT_DATA__")
    return json.loads(match.group(1))


def _write_cached_snapshot(snapshot: RankingSnapshot) -> None:
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(
        json.dumps(snapshot_to_dict(snapshot), ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _read_cached_snapshot() -> RankingSnapshot | None:
    try:
        payload = json.loads(_CACHE.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and "entries" in payload:
            snapshot = snapshot_from_dict(payload)
            validate_ranking_snapshot(snapshot, min_entries=1)
            return snapshot
    except Exception:
        logger.debug("Could not read structured FIFA ranking cache", exc_info=True)
    return None


def _read_legacy_cache() -> Dict[str, int]:
    try:
        payload = json.loads(_CACHE.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return {canonical(k): int(v) for k, v in payload.items() if isinstance(v, int)}
    except Exception:
        logger.debug("Could not read legacy FIFA ranking cache", exc_info=True)
    return {}


def _payload_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _duplicates(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    dupes: list[str] = []
    for value in values:
        if value in seen and value not in dupes:
            dupes.append(value)
        seen.add(value)
    return dupes
