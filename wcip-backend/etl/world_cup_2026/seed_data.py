"""WC2026 seed data and source metadata.

The static team list is a safe fallback for local/dev startup. Player and
coach records should come from a source snapshot, typically exported from the
API-Football endpoints documented for `league=1` and `season=2026`.

Until a real roster snapshot is loaded, the empty/default payload includes one
explicitly marked placeholder player and coach per team. That keeps local API
responses non-empty without pretending those records are verified athletes or
staff.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from wcip.data.wc2026 import CONFIRMED_QUALIFIERS

TOURNAMENT_YEAR = 2026
API_FOOTBALL_LEAGUE_ID = 1
API_FOOTBALL_SEASON = 2026
API_FOOTBALL_SOURCE_URL = (
    "https://www.api-football.com/news/post/"
    "fifa-world-cup-2026-guide-to-using-data-with-api-sports"
)
DATA_SOURCE_NAME = "world_cup_2026_seed"
PLACEHOLDER_DATA_SOURCE = "world_cup_2026_placeholder"


def seed_teams() -> list[dict[str, Any]]:
    """Return an isolated copy of the canonical WC2026 team seed."""
    return deepcopy(CONFIRMED_QUALIFIERS)


def placeholder_players() -> list[dict[str, Any]]:
    """Return one clearly marked roster placeholder per WC2026 team."""
    players: list[dict[str, Any]] = []
    for team in CONFIRMED_QUALIFIERS:
        code = str(team.get("team_code") or "").upper()
        name = team["team_name"]
        players.append(
            {
                "name": "Roster pending",
                "team_name": name,
                "position": "TBD",
                "nationality": name,
                "external_id": f"wc2026-placeholder-player-{code or _slug(name)}",
                "fitness_score": 1.0,
                "recent_form_score": 0.5,
            }
        )
    return players


def placeholder_coaches() -> list[dict[str, Any]]:
    """Return one clearly marked coach placeholder per WC2026 team."""
    coaches: list[dict[str, Any]] = []
    for team in CONFIRMED_QUALIFIERS:
        code = str(team.get("team_code") or "").upper()
        name = team["team_name"]
        coaches.append(
            {
                "name": "Coach pending",
                "team_name": name,
                "nationality": name,
                "external_id": f"wc2026-placeholder-coach-{code or _slug(name)}",
                "preferred_formation": None,
                "win_pct": 0.5,
                "draw_pct": 0.2,
                "loss_pct": 0.3,
                "impact_score": 1.0,
            }
        )
    return coaches


def empty_payload() -> dict[str, Any]:
    """Return the minimum payload shape accepted by the WC2026 seed ETL."""
    return {
        "source": PLACEHOLDER_DATA_SOURCE,
        "tournament_year": TOURNAMENT_YEAR,
        "teams": seed_teams(),
        "players": placeholder_players(),
        "coaches": placeholder_coaches(),
    }


def _slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")
