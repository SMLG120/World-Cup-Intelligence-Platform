"""Prediction service — the bridge between API/worker layers and the engine.

Keeps all engine-construction logic in one place so routers and Celery tasks
share identical behaviour. Pure functions (no DB), easy to unit-test.
"""
from __future__ import annotations

from typing import Dict, Optional

from app.core.config import settings
from wcip.data.teams_2022 import BRACKET_2022, GROUPS_2022, Team, build_teams
from wcip.engine.explain import explain_match
from wcip.engine.match import MatchSimulator
from wcip.engine.montecarlo import MonteCarloEngine
from wcip.engine.scoreline import ScorelineModel, TeamMatchProfile

_EDITIONS = {
    "2022": (build_teams, GROUPS_2022, BRACKET_2022),
}


class UnknownTeam(ValueError):
    pass


class UnknownEdition(ValueError):
    pass


def _edition(edition: str):
    if edition not in _EDITIONS:
        raise UnknownEdition(f"Unknown edition '{edition}'")
    builder, groups, bracket = _EDITIONS[edition]
    return builder(), groups, bracket


def _profile(team_obj, mods: Optional[dict]) -> TeamMatchProfile:
    mods = mods or {}
    return TeamMatchProfile(
        name=team_obj.name,
        elo=team_obj.elo,
        attack=mods.get("attack", team_obj.attack),
        defence=mods.get("defence", team_obj.defence),
        injury=mods.get("injury", 1.0),
        morale=mods.get("morale", 1.0),
        fatigue=mods.get("fatigue", 1.0),
        chemistry=mods.get("chemistry", team_obj.chemistry),
        coaching=mods.get("coaching", team_obj.coach_quality),
    )


def predict_match(home: str, away: str, home_mods: dict, away_mods: dict,
                  edition: str = "2022") -> dict:
    teams, _, _ = _edition(edition)
    _ensure_team(teams, home)
    _ensure_team(teams, away)
    if home not in teams:
        raise UnknownTeam(home)
    if away not in teams:
        raise UnknownTeam(away)
    model = ScorelineModel()
    a = _profile(teams[home], home_mods)
    b = _profile(teams[away], away_mods)
    probs = model.outcome_probabilities(a, b)
    xg = model.expected_goal_pair(a, b)
    exp = explain_match(a, b, model)
    return {
        "home": home,
        "away": away,
        "probabilities": probs,
        "home_xg": round(xg["home_xg"], 3),
        "away_xg": round(xg["away_xg"], 3),
        "explanation": exp.summary,
        "factors": [
            {"name": f.name, "detail": f.detail, "impact": round(f.impact, 3)}
            for f in exp.factors
        ],
    }


def _ensure_team(teams: Dict[str, object], name: str) -> None:
    if name in teams:
        return

    loaded = _load_team_profile(name)
    if loaded:
        teams[name] = loaded


def _load_team_profile(name: str):
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import Team as DBTeam

        db = SessionLocal()
        try:
            row = db.scalar(select(DBTeam).where(DBTeam.name == name))
            if row:
                return Team(
                    name=row.name,
                    code=row.code,
                    confederation=row.confederation,
                    elo=row.elo,
                    fifa_rank=row.fifa_rank,
                    attack=row.attack,
                    defence=row.defence,
                    chemistry=row.chemistry,
                    coach_quality=row.coach_quality,
                )
        finally:
            db.close()
    except Exception:
        pass

    try:
        from wcip.data.wc2026 import CONFIRMED_QUALIFIERS

        for raw in CONFIRMED_QUALIFIERS:
            if raw["team_name"] == name:
                return Team(
                    name=raw["team_name"],
                    code=raw.get("team_code", "???"),
                    confederation=raw.get("confederation", ""),
                    elo=float(raw.get("elo", 1500.0)),
                    fifa_rank=int(raw.get("fifa_rank", 100)),
                )
    except Exception:
        pass

    return None


def _apply_overrides(teams: Dict[str, object], overrides: dict) -> None:
    """Bake scenario overrides directly into team objects for a sim run."""
    for name, mods in (overrides or {}).items():
        t = teams.get(name)
        if not t:
            continue
        t.attack = mods.get("attack", t.attack)
        t.defence = mods.get("defence", t.defence)
        t.chemistry = mods.get("chemistry", t.chemistry)
        t.coach_quality = mods.get("coaching", t.coach_quality)
        # injury/morale/fatigue fold into attack as an availability proxy.
        avail = (mods.get("injury", 1.0) * mods.get("morale", 1.0)
                 * mods.get("fatigue", 1.0))
        t.attack *= avail


def run_monte_carlo(edition: str, runs: int, overrides: dict,
                    workers: Optional[int] = None) -> dict:
    runs = min(runs, settings.MAX_MONTE_CARLO_RUNS)
    teams, groups, bracket = _edition(edition)
    _apply_overrides(teams, overrides)
    engine = MonteCarloEngine(teams, groups, bracket)
    probs = engine.run(n_runs=runs, workers=workers)
    return {
        "edition": edition,
        "runs": runs,
        "teams": [
            {
                "team": p.team,
                "champion": round(p.champion, 5),
                "final": round(p.final, 5),
                "semi": round(p.semi, 5),
                "quarter": round(p.quarter, 5),
                "round_of_16": round(p.round_of_16, 5),
                "expected_finish": round(p.expected_finish, 3),
                "champion_ci_low": round(p.champion_ci_low, 5),
                "champion_ci_high": round(p.champion_ci_high, 5),
            }
            for p in probs.values()
        ],
    }


def compare_scenarios(edition: str, runs: int, scenarios: list[dict]) -> dict:
    """Run several scenarios and return per-scenario champion probabilities."""
    out = []
    for sc in scenarios:
        result = run_monte_carlo(edition, runs, sc.get("overrides", {}))
        out.append({"label": sc["label"], "result": result})
    return {"edition": edition, "runs": runs, "scenarios": out}


def list_editions() -> list[str]:
    return list(_EDITIONS.keys())
