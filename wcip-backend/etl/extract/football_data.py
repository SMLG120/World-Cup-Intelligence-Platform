"""Extract layer: football-data.org API.

Fetches competition listings, team rosters, and match results.
Requires FOOTBALL_DATA_API_KEY environment variable (free tier available).
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.football-data.org/v4"
_HEADERS = {"X-Auth-Token": os.getenv("FOOTBALL_DATA_API_KEY", "")}
_RATE_SLEEP = 6.5  # free tier: 10 req/min


def _get(path: str, params: dict | None = None, retries: int = 3) -> dict | list:
    url = f"{BASE_URL}{path}"
    for attempt in range(retries):
        try:
            resp = httpx.get(url, headers=_HEADERS, params=params, timeout=30)
            if resp.status_code == 429:
                wait = int(resp.headers.get("Retry-After", 60))
                logger.warning("Rate limited, sleeping %ds", wait)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("HTTP error %s on %s (attempt %d)", e.response.status_code, url, attempt + 1)
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts")


def fetch_competition_teams(competition_code: str) -> list[dict[str, Any]]:
    """Return team list for a competition code (e.g. 'WC', 'EC')."""
    data = _get(f"/competitions/{competition_code}/teams")
    teams = data.get("teams", [])
    logger.info("Fetched %d teams for competition %s", len(teams), competition_code)
    time.sleep(_RATE_SLEEP)
    return teams


def fetch_competition_matches(
    competition_code: str,
    season: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """Return matches for a competition.

    Args:
        competition_code: e.g. 'WC', 'EC', 'CL'
        season: 4-digit year (start year of the season)
        status: 'SCHEDULED', 'FINISHED', 'LIVE', etc.
    """
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    if status:
        params["status"] = status
    data = _get(f"/competitions/{competition_code}/matches", params=params)
    matches = data.get("matches", [])
    logger.info("Fetched %d matches for %s season=%s", len(matches), competition_code, season)
    time.sleep(_RATE_SLEEP)
    return matches


def fetch_team_squad(team_id: int) -> dict[str, Any]:
    """Return squad (players) for a given team id."""
    data = _get(f"/teams/{team_id}")
    time.sleep(_RATE_SLEEP)
    return data


def fetch_standings(competition_code: str, season: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if season:
        params["season"] = season
    data = _get(f"/competitions/{competition_code}/standings", params=params)
    time.sleep(_RATE_SLEEP)
    return data
