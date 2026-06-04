"""Extract layer: International Football Results dataset.

Primary source: https://github.com/martj42/international_results
CSV contains all international matches since 1872. We download on first run
and cache locally; subsequent runs do an incremental CSV append.

If the remote is unavailable, the extractor falls back to any locally cached copy.
"""
from __future__ import annotations

import io
import logging
from datetime import date
from pathlib import Path
from typing import Iterator

import httpx

logger = logging.getLogger(__name__)

RESULTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"
)
GOALSCORERS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/goalscorers.csv"
)
SHOOTOUTS_URL = (
    "https://raw.githubusercontent.com/martj42/international_results/master/shootouts.csv"
)

_CACHE_DIR = Path(__file__).parents[2] / "data" / "cache"


def _download(url: str, cache_file: Path, retries: int = 3) -> str:
    """Download CSV text, using cache if remote fails."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(retries):
        try:
            resp = httpx.get(url, timeout=60, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
            cache_file.write_text(text, encoding="utf-8")
            logger.info("Downloaded %s (%d bytes)", url, len(text))
            return text
        except Exception as exc:
            logger.warning("Download attempt %d failed: %s", attempt + 1, exc)
    if cache_file.exists():
        logger.warning("Using cached copy of %s", cache_file.name)
        return cache_file.read_text(encoding="utf-8")
    raise RuntimeError(f"Cannot fetch {url} and no cache found")


def fetch_results_csv(force_refresh: bool = False) -> str:
    cache = _CACHE_DIR / "results.csv"
    if cache.exists() and not force_refresh:
        logger.info("Using cached results.csv")
        return cache.read_text(encoding="utf-8")
    return _download(RESULTS_URL, cache)


def fetch_goalscorers_csv(force_refresh: bool = False) -> str:
    cache = _CACHE_DIR / "goalscorers.csv"
    if cache.exists() and not force_refresh:
        return cache.read_text(encoding="utf-8")
    return _download(GOALSCORERS_URL, cache)


def parse_results(csv_text: str, since: date | None = None) -> Iterator[dict]:
    """Yield parsed match dicts from the CSV.

    Columns: date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
    """
    import csv
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        try:
            match_date = date.fromisoformat(row["date"])
        except (KeyError, ValueError):
            continue
        if since and match_date < since:
            continue
        home_score_raw = row.get("home_score", "").strip()
        away_score_raw = row.get("away_score", "").strip()
        # Skip rows with NA/empty scores (unplayed/scheduled matches)
        if not home_score_raw or not away_score_raw or home_score_raw.upper() == "NA" or away_score_raw.upper() == "NA":
            continue
        try:
            home_goals = int(home_score_raw)
            away_goals = int(away_score_raw)
        except ValueError:
            continue
        yield {
            "match_date": match_date,
            "home_team": row["home_team"].strip(),
            "away_team": row["away_team"].strip(),
            "home_goals": home_goals,
            "away_goals": away_goals,
            "tournament": row.get("tournament", "").strip() or None,
            "city": row.get("city", "").strip() or None,
            "country": row.get("country", "").strip() or None,
            "neutral": row.get("neutral", "True").strip().lower() in ("true", "1", "yes"),
        }
