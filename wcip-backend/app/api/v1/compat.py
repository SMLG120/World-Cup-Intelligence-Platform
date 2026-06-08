"""Compatibility aliases for older API route names.

Canonical routes use hyphenated resources such as `/world-cup/*` and singular
prediction routes such as `/match/simulate`. These aliases keep older clients
from receiving avoidable 404s.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.v1 import matches, scenarios, world_cup
from app.schemas.domain import MatchRequest, ScenarioCompareRequest, TournamentRequest

router = APIRouter(tags=["compatibility"])


@router.get("/world_cup/groups")
def world_cup_groups_alias(year: int = 2026) -> dict[str, Any]:
    return world_cup.get_groups(year)


@router.get("/world_cup/bracket")
def world_cup_bracket_alias(year: int = 2026) -> dict[str, Any]:
    return world_cup.get_bracket(year)


@router.get("/world_cup/standings")
def world_cup_standings_alias(year: int = 2026) -> dict[str, Any]:
    groups = world_cup.get_groups(year)
    standings = {
        label: [
            {"team": team, "played": 0, "won": 0, "drawn": 0, "lost": 0, "gf": 0, "ga": 0, "points": 0}
            for team in teams
        ]
        for label, teams in groups.get("groups", {}).items()
    }
    return {
        "year": year,
        "draw_complete": groups.get("draw_complete", False),
        "standings": standings,
    }


@router.post("/matches/predict")
def matches_predict_alias(req: MatchRequest):
    return matches.simulate_match(req)


@router.post("/simulations/tournament")
def simulations_tournament_alias(req: TournamentRequest):
    return matches.simulate_tournament(req)


@router.post("/scenarios")
def scenarios_alias(req: ScenarioCompareRequest):
    return scenarios.compare(req)
