"""Extract World Football Elo ratings for versioned ingestion."""
from __future__ import annotations

import hashlib
import html
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

import httpx

from etl.extract.elo_ratings import _ELO_FALLBACK

logger = logging.getLogger(__name__)

ELO_WORLD_CUP_URL = "https://www.eloratings.net/2026_World_Cup"
ELO_WORLD_TSV_URL = "https://www.eloratings.net/World.tsv"
_CACHE = Path(__file__).parents[2] / "data" / "cache" / "elo_snapshot.json"

try:
    from app.core.config import settings

    ELO_WORLD_CUP_URL = settings.ELO_RATING_SOURCE_URL or ELO_WORLD_CUP_URL
    ELO_WORLD_TSV_URL = settings.ELO_RATING_TSV_URL or ELO_WORLD_TSV_URL
except Exception:
    pass


@dataclass(frozen=True)
class RawEloRecord:
    team_name: str
    rating: float
    rank: int | None = None
    raw_payload: dict[str, Any] | None = None


@dataclass(frozen=True)
class RawEloSnapshot:
    source_url: str
    rating_date: date
    source_hash: str
    records: list[RawEloRecord]
    http_status: int | None = None


def fetch_latest_elo_snapshot(
    *,
    force_refresh: bool = False,
    allow_network: bool = True,
) -> RawEloSnapshot:
    """Fetch the latest Elo ratings.

    The 2026 World Cup page is attempted first because it is the requested
    tournament-specific source. The public World.tsv feed is used as a stable
    fallback when the page is unavailable or cannot be parsed. Tests can set
    ``allow_network=False`` to use the embedded offline snapshot.
    """

    if not force_refresh and _CACHE.exists():
        cached = _read_cache()
        if cached:
            return cached

    if allow_network:
        for url in (ELO_WORLD_CUP_URL, ELO_WORLD_TSV_URL):
            try:
                response = httpx.get(
                    url,
                    timeout=30,
                    follow_redirects=True,
                    headers={"User-Agent": "wcip-elo-ingestion/1.0"},
                )
                response.raise_for_status()
                records = _parse_payload(response.text, url)
                if len(records) >= 20:
                    snapshot = RawEloSnapshot(
                        source_url=url,
                        rating_date=_parse_rating_date(response.text) or date.today(),
                        source_hash=_hash_text(response.text),
                        records=records,
                        http_status=response.status_code,
                    )
                    _write_cache(snapshot)
                    return snapshot
                logger.warning("Elo source %s parsed only %d rows", url, len(records))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Elo source %s unavailable: %s", url, exc)

    snapshot = _fallback_snapshot()
    _write_cache(snapshot)
    return snapshot


def _parse_payload(text: str, source_url: str) -> list[RawEloRecord]:
    if source_url.endswith(".tsv") or "\t" in text:
        return _parse_tsv(text)
    return _parse_html_table(text)


def _parse_tsv(text: str) -> list[RawEloRecord]:
    rows: list[RawEloRecord] = []
    for line in text.splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) < 3:
            continue
        try:
            rank = int(float(parts[0]))
            rating = float(parts[2])
        except ValueError:
            continue
        name = parts[1]
        if name:
            rows.append(
                RawEloRecord(
                    team_name=name,
                    rank=rank,
                    rating=rating,
                    raw_payload={"source_row": parts},
                )
            )
    return sorted(rows, key=lambda row: row.rank or 9999)


def _parse_html_table(text: str) -> list[RawEloRecord]:
    rows: list[RawEloRecord] = []
    for tr in re.findall(r"<tr\b.*?</tr>", text, flags=re.IGNORECASE | re.DOTALL):
        cells = [
            html.unescape(re.sub(r"<.*?>", " ", cell, flags=re.DOTALL)).strip()
            for cell in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, flags=re.IGNORECASE | re.DOTALL)
        ]
        cells = [re.sub(r"\s+", " ", cell) for cell in cells if cell.strip()]
        if len(cells) < 3:
            continue
        rank = _first_int(cells[0])
        rating = _first_float(" ".join(cells[1:]))
        name = _first_teamish_cell(cells)
        if name and rating is not None:
            rows.append(
                RawEloRecord(
                    team_name=name,
                    rank=rank,
                    rating=rating,
                    raw_payload={"source_row": cells},
                )
            )
    return sorted(rows, key=lambda row: row.rank or 9999)


def _first_teamish_cell(cells: list[str]) -> str | None:
    for cell in cells[1:4]:
        if re.search(r"[A-Za-z]", cell) and not re.fullmatch(r"[\d.,+\- ]+", cell):
            return cell.strip()
    return None


def _first_int(text: str) -> int | None:
    match = re.search(r"\d+", text)
    return int(match.group(0)) if match else None


def _first_float(text: str) -> float | None:
    candidates = re.findall(r"\b\d{3,4}(?:\.\d+)?\b", text)
    if not candidates:
        return None
    values = [float(value) for value in candidates]
    plausible = [value for value in values if 500 <= value <= 2500]
    return plausible[-1] if plausible else None


def _parse_rating_date(text: str) -> date | None:
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        try:
            return date.fromisoformat(match.group(0))
        except ValueError:
            return None
    return None


def _fallback_snapshot() -> RawEloSnapshot:
    records = [
        RawEloRecord(team_name=name, rating=rating, rank=idx + 1, raw_payload={"source": "embedded_fallback"})
        for idx, (name, rating) in enumerate(
            sorted(_ELO_FALLBACK.items(), key=lambda item: item[1], reverse=True)
        )
    ]
    payload = json.dumps([asdict(record) for record in records], sort_keys=True, default=str)
    return RawEloSnapshot(
        source_url="embedded://etl.extract.elo_ratings._ELO_FALLBACK",
        rating_date=date.today(),
        source_hash=_hash_text(payload),
        records=records,
        http_status=None,
    )


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_cache(snapshot: RawEloSnapshot) -> None:
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    payload = asdict(snapshot)
    payload["rating_date"] = snapshot.rating_date.isoformat()
    _CACHE.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _read_cache() -> RawEloSnapshot | None:
    try:
        payload = json.loads(_CACHE.read_text(encoding="utf-8"))
        return RawEloSnapshot(
            source_url=str(payload["source_url"]),
            rating_date=date.fromisoformat(str(payload["rating_date"])),
            source_hash=str(payload["source_hash"]),
            http_status=payload.get("http_status"),
            records=[
                RawEloRecord(
                    team_name=str(item["team_name"]),
                    rating=float(item["rating"]),
                    rank=int(item["rank"]) if item.get("rank") is not None else None,
                    raw_payload=item.get("raw_payload"),
                )
                for item in payload.get("records", [])
            ],
        )
    except Exception:
        logger.debug("Could not read Elo cache", exc_info=True)
        return None
