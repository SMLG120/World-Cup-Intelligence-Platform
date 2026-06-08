"""Extract layer: World Football Elo Ratings.

Scrapes/parses the current Elo ratings table from eloratings.net.
Returns a mapping of country name -> Elo rating.

Falls back to an embedded snapshot if the web fetch fails.
"""
from __future__ import annotations

import logging
import re
import time
from pathlib import Path
from typing import Dict

import httpx

logger = logging.getLogger(__name__)

ELO_URL = "https://www.eloratings.net/World.tsv"
_CACHE = Path(__file__).parents[2] / "data" / "cache" / "elo_ratings.tsv"

# Embedded fallback snapshot (updated June 2026 — WC2026 finalized field).
# Includes all 52 confirmed WC2026 participants.
# Note: "Czech Republic" key kept for historical TSV compatibility; canonical is "Czechia".
_ELO_FALLBACK: Dict[str, float] = {
    # Top tier
    "Argentina": 2141, "France": 2028, "England": 1977,
    "Spain": 1977, "Brazil": 1967, "Portugal": 1939,
    "Belgium": 1895, "Netherlands": 1877,
    "Germany": 1852, "Croatia": 1829, "Morocco": 1825,
    "Colombia": 1819, "Mexico": 1812, "United States": 1802,
    "Uruguay": 1799, "Japan": 1796,
    "Switzerland": 1779, "South Korea": 1761,
    "Senegal": 1737, "Turkey": 1735, "Ecuador": 1730,
    "Austria": 1728, "Ukraine": 1722, "Australia": 1719,
    "Nigeria": 1712, "Iran": 1706, "Chile": 1705,
    "Hungary": 1700, "Serbia": 1696,
    "Russia": 1688, "Egypt": 1682, "Peru": 1679, "Scotland": 1678,
    "Wales": 1672, "Ivory Coast": 1670, "Ghana": 1666,
    "Canada": 1660, "Greece": 1654,
    "Venezuela": 1645, "Tunisia": 1643, "Romania": 1638,
    "Bolivia": 1630, "Saudi Arabia": 1627,
    "Qatar": 1585, "Uzbekistan": 1580, "Jordan": 1540,
    "New Zealand": 1510,

    # WC2026 newly confirmed nations (added June 2026)
    "Czechia": 1704,          # ex-"Czech Republic" — canonical renamed
    "Czech Republic": 1704,   # kept for TSV parser compatibility
    "Sweden": 1692,
    "Norway": 1685,
    "Algeria": 1686,
    "Paraguay": 1658,
    "Bosnia and Herzegovina": 1651,
    "Bosnia & Herzegovina": 1651,  # TSV variant
    "South Africa": 1622,
    "Cameroon": 1618,
    "DR Congo": 1562,
    "Panama": 1538,
    "Cape Verde": 1545,
    "Iraq": 1488,
    "Haiti": 1410,
    "Curaçao": 1425,
    "Curacao": 1425,           # TSV variant
}


def fetch_elo_ratings(force_refresh: bool = False, allow_network: bool = True) -> Dict[str, float]:
    """Return {team_name: elo_rating} from eloratings.net (or fallback)."""
    _CACHE.parent.mkdir(parents=True, exist_ok=True)

    if _CACHE.exists() and not force_refresh:
        result = _parse_tsv(_CACHE.read_text(encoding="utf-8"))
        if result:
            return result
        # Cache is stale / format changed — fall through to HTTP fetch

    if not allow_network:
        return dict(_ELO_FALLBACK)

    for attempt in range(3):
        try:
            resp = httpx.get(ELO_URL, timeout=30, follow_redirects=True)
            resp.raise_for_status()
            text = resp.text
            _CACHE.write_text(text, encoding="utf-8")
            logger.info("Fetched Elo ratings (%d bytes)", len(text))
            return _parse_tsv(text)
        except Exception as exc:
            logger.warning("Elo fetch attempt %d failed: %s", attempt + 1, exc)
            time.sleep(2 ** attempt)

    logger.warning("Using embedded Elo fallback snapshot")
    return dict(_ELO_FALLBACK)


def _parse_tsv(text: str) -> Dict[str, float]:
    """Parse eloratings.net TSV: columns are rank, team, elo, ..."""
    ratings: Dict[str, float] = {}
    for line in text.splitlines():
        parts = line.strip().split("\t")
        if len(parts) < 3:
            continue
        try:
            name = parts[1].strip()
            elo = float(parts[2].strip())
            if name:
                ratings[name] = elo
        except (ValueError, IndexError):
            continue
    if not ratings:
        # Fallback: try regex-based HTML parse if TSV failed
        logger.warning("TSV parse yielded no rows; trying regex")
        for m in re.finditer(r'<td[^>]*>([A-Z][a-z ]+)</td>\s*<td[^>]*>([\d.]+)</td>', text):
            ratings[m.group(1)] = float(m.group(2))
    return ratings
