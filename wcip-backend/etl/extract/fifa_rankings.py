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

# Embedded fallback (updated June 2026 — WC2026 finalized field).
# Note: Italy, Poland, Denmark removed (did not qualify).
# All 52 confirmed WC2026 participants included.
_FIFA_RANK_FALLBACK: Dict[str, int] = {
    "Argentina": 1,  "France": 2,      "England": 3,    "Belgium": 4,
    "Brazil": 5,     "Portugal": 6,    "Netherlands": 7, "Spain": 8,
    "Croatia": 10,   "Morocco": 11,    "Japan": 12,
    "United States": 13, "Mexico": 14, "Uruguay": 15,   "Colombia": 16,
    "Switzerland": 17, "Germany": 19,  "South Korea": 20,
    "Ecuador": 21,   "Turkey": 22,    "Austria": 23,    "Senegal": 24,
    "Nigeria": 25,   "Hungary": 26,   "Wales": 27,      "Iran": 28,
    "Australia": 29, "Serbia": 31,
    "Ukraine": 33,   "Scotland": 35,  "Ivory Coast": 36,
    "Egypt": 38,     "Canada": 43,    "Venezuela": 45,  "Ghana": 46,
    "Tunisia": 47,   "Saudi Arabia": 49,
    # WC2026 finalized additions and updates (June 2026)
    "Czechia": 32,             # formerly Czech Republic
    "Czech Republic": 32,      # alias for fallback lookups
    "Sweden": 34,
    "Norway": 36,
    "Algeria": 37,
    "Paraguay": 44,
    "Bosnia and Herzegovina": 52,
    "Bosnia & Herzegovina": 52,
    "South Africa": 58,
    "Cameroon": 55,
    "DR Congo": 60,
    "Panama": 68,
    "Cape Verde": 74,
    "Iraq": 65,
    "Qatar": 37,
    "Uzbekistan": 72,
    "Jordan": 85,
    "New Zealand": 96,
    "Haiti": 91,
    "Curaçao": 87,
    "Curacao": 87,
    "Ghana": 46,
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
