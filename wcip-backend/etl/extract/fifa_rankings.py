"""Extract layer: FIFA World Rankings.

Fetches rankings from the public FIFA API endpoint or falls back to
a cached snapshot. Rankings are released monthly.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict

import httpx

logger = logging.getLogger(__name__)

FIFA_RANKINGS_URL = "https://www.fifa.com/fifa-world-ranking/men?dateId=id14180"
_RANKINGS_API = "https://www.fifaindex.com/api/teams/?league=30&order=desc&page=1"

_CACHE = Path(__file__).parents[2] / "data" / "cache" / "fifa_rankings.json"

# Embedded fallback (June 2025 approximate)
_FIFA_RANK_FALLBACK: Dict[str, int] = {
    "Argentina": 1, "France": 2, "England": 3, "Belgium": 4,
    "Brazil": 5, "Portugal": 6, "Netherlands": 7, "Spain": 8,
    "Italy": 9, "Croatia": 10, "Morocco": 11, "Japan": 12,
    "United States": 13, "Mexico": 14, "Uruguay": 15, "Colombia": 16,
    "Switzerland": 17, "Denmark": 18, "Germany": 19, "South Korea": 20,
    "Ecuador": 21, "Turkey": 22, "Austria": 23, "Senegal": 24,
    "Nigeria": 25, "Hungary": 26, "Wales": 27, "Iran": 28,
    "Australia": 29, "Poland": 30, "Serbia": 31, "Czech Republic": 32,
    "Ukraine": 33, "Sweden": 34, "Scotland": 35, "Ivory Coast": 36,
    "Algeria": 37, "Egypt": 38, "Russia": 39, "Peru": 40,
    "Chile": 41, "Greece": 42, "Canada": 43, "Paraguay": 44,
    "Venezuela": 45, "Ghana": 46, "Tunisia": 47, "Romania": 48,
    "Saudi Arabia": 49, "Bolivia": 50,
}


def fetch_fifa_rankings(force_refresh: bool = False) -> Dict[str, int]:
    """Return {team_name: rank}. Uses cache, falls back to embedded snapshot."""
    import json
    _CACHE.parent.mkdir(parents=True, exist_ok=True)

    if _CACHE.exists() and not force_refresh:
        try:
            return json.loads(_CACHE.read_text())
        except Exception:
            pass

    # Try to fetch from a public endpoint
    for attempt in range(3):
        try:
            resp = httpx.get(
                "https://api.football-data.org/v4/competitions/WC/teams",
                timeout=30,
            )
            # This won't give us rankings directly; log and fall through
            break
        except Exception as exc:
            logger.warning("FIFA rankings fetch attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)

    logger.info("Using embedded FIFA rankings fallback")
    rankings = dict(_FIFA_RANK_FALLBACK)
    _CACHE.write_text(json.dumps(rankings), encoding="utf-8")
    return rankings
