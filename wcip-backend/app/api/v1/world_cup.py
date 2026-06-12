"""World Cup 2026 data and simulation API endpoints."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/world-cup", tags=["world-cup"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    year: int = Field(2026, description="Tournament year")
    runs: int = Field(10_000, ge=100, le=50_000)
    overrides: Optional[Dict[str, Dict]] = None
    seed: Optional[int] = None
    deterministic: bool = False


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/qualified-teams")
def get_qualified_teams(
    year: int = Query(2026),
    confederation: Optional[str] = Query(None),
    confirmed_only: bool = Query(True),
) -> List[Dict[str, Any]]:
    """Return currently qualified teams for the given World Cup year."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import QualifiedTeam

        db = SessionLocal()
        try:
            q = select(QualifiedTeam).where(QualifiedTeam.tournament_year == year)
            if confirmed_only:
                q = q.where(QualifiedTeam.confirmed == True)
            if confederation:
                q = q.where(QualifiedTeam.confederation == confederation)
            rows = db.scalars(q.order_by(QualifiedTeam.confederation, QualifiedTeam.team_name)).all()

            # If DB is empty, fall back to seed data
            if not rows:
                _seed_qualified_teams(year)
                rows = db.scalars(q.order_by(QualifiedTeam.team_name)).all()

            return [
                {
                    "team_name": r.team_name,
                    "team_code": r.team_code,
                    "confederation": r.confederation,
                    "group_label": r.group_label,
                    "pot": r.pot,
                    "host_nation": r.host_nation,
                    "confirmed": r.confirmed,
                    "qualification_path": r.qualification_path,
                }
                for r in rows
            ]
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(500, str(e))


def _seed_qualified_teams(year: int) -> None:
    """Seed qualified teams from the static module if DB is empty."""
    try:
        from wcip.data.wc2026 import CONFIRMED_QUALIFIERS
        from etl.load.db_loader import load_qualified_teams
        load_qualified_teams(CONFIRMED_QUALIFIERS, tournament_year=year)
    except Exception as e:
        logger.warning("Could not seed qualified teams: %s", e)


@router.get("/groups")
def get_groups(year: int = Query(2026)) -> Dict[str, Any]:
    """Return the current group assignments (empty if draw not yet held)."""
    from wcip.data.wc2026 import build_2026_groups_from_db, get_qualified_teams_from_db

    if year == 2026:
        groups = build_2026_groups_from_db()
        teams = get_qualified_teams_from_db()
        return {
            "year": year,
            "draw_complete": bool(groups),
            "groups": groups,
            "total_qualified": len(teams),
            "qualification_status": {
                "confirmed": sum(1 for t in teams if t.get("confirmed", True)),
                "total_slots": 48,
            },
        }
    raise HTTPException(400, f"Year {year} not supported. Use 2026.")


@router.get("/bracket")
def get_bracket(year: int = Query(2026)) -> Dict[str, Any]:
    """Return the knockout bracket structure."""
    from wcip.data.wc2026 import build_2026_groups_from_db, build_2026_bracket

    if year != 2026:
        raise HTTPException(400, "Only 2026 bracket supported here. Use /simulate for historical.")

    groups = build_2026_groups_from_db()
    bracket = build_2026_bracket(groups)

    return {
        "year": year,
        "draw_complete": bool(groups),
        "bracket": [
            {"match_id": m[0], "slot_1": m[1], "slot_2": m[2]}
            for m in bracket
        ],
    }


@router.post("/simulate")
def simulate_tournament(req: SimulateRequest) -> Dict[str, Any]:
    """Run Monte Carlo tournament simulation with optional team overrides.

    Supports both the 2022 (32-team) and 2026 (48-team) formats.
    For 2026: runs a simplified simulation using available qualified teams
    until the official group draw is complete.
    """
    from app.services.prediction import run_monte_carlo

    if req.year == 2022:
        return run_monte_carlo("2022", req.runs, req.overrides or {})

    if req.year == 2026:
        return _simulate_2026(
            req.runs,
            req.overrides or {},
            seed=req.seed,
            deterministic=req.deterministic,
        )

    raise HTTPException(400, f"Year {req.year} not supported")


@router.get("/2026/winner-predictions")
def get_2026_winner_predictions(
    runs: int = Query(5000, ge=100, le=50_000),
    seed: int | None = Query(None),
    deterministic: bool = Query(False),
) -> List[Dict[str, Any]]:
    """Return ranked 2026 World Cup winner predictions."""
    from app.services.winner_predictions import world_cup_2026_winner_predictions

    return world_cup_2026_winner_predictions(
        runs=runs,
        seed=seed,
        deterministic=deterministic,
    )


def _simulate_2026(
    runs: int,
    overrides: Dict,
    *,
    seed: int | None = None,
    deterministic: bool = False,
) -> Dict[str, Any]:
    """Run 2026 WC simulation.

    If groups are available from DB, uses those. Otherwise falls back to
    a simplified pair-elimination using qualified teams sorted by Elo.
    """
    from wcip.data.wc2026 import build_2026_groups_from_db, get_qualified_teams_from_db, build_2026_bracket
    from wcip.data.teams_2022 import Team
    from wcip.engine.montecarlo import generate_seed

    qualified = get_qualified_teams_from_db()
    if not qualified:
        raise HTTPException(503, "No qualified team data available. Run ETL first.")

    groups = build_2026_groups_from_db()

    # If no draw has happened, create provisional groups by Elo ranking
    if not groups:
        groups = _provisional_groups_by_elo(qualified)

    bracket = build_2026_bracket(groups)

    # Build teams dict for the simulator
    from ml.features import _get_team_elo, _get_team_fifa_rank
    from etl.transform.normalize import canonical

    teams_dict: Dict[str, Team] = {}
    for t in qualified:
        name = t["team_name"]
        teams_dict[name] = Team(
            name=name,
            code=t.get("team_code", "???"),
            confederation=t.get("confederation", ""),
            elo=_get_team_elo(name),
            fifa_rank=_get_team_fifa_rank(name),
        )

    # Apply overrides
    for name, mods in overrides.items():
        canon = canonical(name)
        if canon in teams_dict:
            t = teams_dict[canon]
            t.attack = mods.get("attack", 1.0)
            t.defence = mods.get("defence", 1.0)

    seed_to_use = int(seed) if seed is not None else (12345 if deterministic else generate_seed())

    from wcip.engine.montecarlo import MonteCarloEngine
    engine = MonteCarloEngine(teams_dict, groups, bracket)
    probs = engine.run(n_runs=runs, seed=seed_to_use)

    return {
        "year": 2026,
        "runs": runs,
        "seed": seed_to_use,
        "deterministic": bool(deterministic or seed is not None),
        "draw_complete": bool(build_2026_groups_from_db()),
        "teams": [
            {
                "team": p.team,
                "champion": round(p.champion, 5),
                "final": round(p.final, 5),
                "semi": round(p.semi, 5),
                "quarter": round(p.quarter, 5),
                "round_of_32": round(getattr(p, "round_of_32", 0.0), 5),
                "round_of_16": round(p.round_of_16, 5),
                "expected_finish": round(p.expected_finish, 3),
                "champion_ci_low": round(p.champion_ci_low, 5),
                "champion_ci_high": round(p.champion_ci_high, 5),
            }
            for p in probs.values()
        ],
    }


def _provisional_groups_by_elo(qualified: List[Dict]) -> Dict[str, List[str]]:
    """Create provisional 12-group draw sorted by Elo (seeded pot distribution)."""
    from ml.features import _get_team_elo

    # Sort by Elo descending
    sorted_teams = sorted(qualified, key=lambda t: _get_team_elo(t["team_name"]), reverse=True)
    group_labels = [chr(ord("A") + i) for i in range(12)]
    groups: Dict[str, List[str]] = {g: [] for g in group_labels}

    # Serpentine distribution (1→A,B,...,L,L,...,A pattern) to balance strength
    n_groups = 12
    for i, t in enumerate(sorted_teams[:48]):
        pass_num = i // n_groups
        pos_in_pass = i % n_groups
        group_idx = pos_in_pass if pass_num % 2 == 0 else (n_groups - 1 - pos_in_pass)
        groups[group_labels[group_idx]].append(t["team_name"])

    # Trim to 4 per group
    return {g: teams[:4] for g, teams in groups.items() if teams}


@router.get("/schedule")
def get_schedule(year: int = Query(2026)) -> Dict[str, Any]:
    """Return the official fixture schedule."""
    if year != 2026:
        raise HTTPException(400, "Only 2026 schedule available")

    # 2026 WC will be played June 11 - July 19, 2026
    return {
        "year": 2026,
        "start_date": "2026-06-11",
        "final_date": "2026-07-19",
        "host_countries": ["United States", "Canada", "Mexico"],
        "host_cities": {
            "USA": ["New York/New Jersey", "Los Angeles", "Dallas", "San Francisco Bay Area",
                    "Seattle", "Boston", "Miami", "Atlanta", "Houston", "Philadelphia", "Kansas City"],
            "Canada": ["Toronto", "Vancouver"],
            "Mexico": ["Mexico City", "Guadalajara", "Monterrey"],
        },
        "format": {
            "group_stage": "12 groups of 4 (top 2 + 8 best 3rd place teams advance)",
            "round_of_32": 16,
            "round_of_16": 8,
            "quarter_finals": 4,
            "semi_finals": 2,
            "third_place_match": 1,
            "final": 1,
            "total_matches": 104,
        },
    }


@router.get("/teams/{team_name}")
def get_team_detail(team_name: str) -> Dict[str, Any]:
    """Return detailed team information including players and coach."""
    from etl.transform.normalize import canonical
    from sqlalchemy import select
    from app.db.base import SessionLocal
    from app.models.team import Team
    from app.models.player import Coach, Player
    from ml.features import _get_team_elo, _get_team_fifa_rank, _get_form, _get_squad_stats

    canon = canonical(team_name)
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == canon))
        coach = db.scalar(select(Coach).where(Coach.team_name == canon))
        players = db.scalars(select(Player).where(Player.team_name == canon)).all()

        squad_stats = _get_squad_stats(canon)

        return {
            "team_name": canon,
            "elo": _get_team_elo(canon),
            "fifa_rank": _get_team_fifa_rank(canon),
            "confederation": team.confederation if team else None,
            "attack": team.attack if team else 1.0,
            "defence": team.defence if team else 1.0,
            "chemistry": team.chemistry if team else 1.0,
            "form_ppg": round(_get_form(canon, __import__("datetime").date.today()), 2),
            "squad_stats": squad_stats,
            "coach": {
                "name": coach.name if coach else None,
                "formation": coach.preferred_formation if coach else None,
                "win_pct": coach.win_pct if coach else None,
                "impact_score": coach.impact_score if coach else 1.0,
                "data_source": coach.data_source if coach else None,
            },
            "squad_size": len(players),
            "injured_count": sum(1 for p in players if p.injured),
            "suspended_count": sum(1 for p in players if p.suspended),
        }
    finally:
        db.close()


@router.get("/players/{team_name}")
def get_team_players(team_name: str) -> Dict[str, Any]:
    """Return squad list for a team."""
    from etl.transform.normalize import canonical
    from sqlalchemy import select
    from app.db.base import SessionLocal
    from app.models.player import Player

    canon = canonical(team_name)
    db = SessionLocal()
    try:
        players = db.scalars(
            select(Player).where(Player.team_name == canon)
        ).all()

        return {
            "team_name": canon,
            "squad": [
                {
                    "id": p.id,
                    "name": p.name,
                    "team_name": p.team_name,
                    "position": p.position,
                    "club": p.club,
                    "age": p.age,
                    "nationality": p.nationality,
                    "goals": p.goals,
                    "assists": p.assists,
                    "xg": p.xg,
                    "xag": p.xag,
                    "minutes_played": p.minutes_played,
                    "international_caps": p.international_caps,
                    "international_goals": p.international_goals,
                    "injured": p.injured,
                    "suspended": p.suspended,
                    "fitness_score": p.fitness_score,
                    "recent_form_score": p.recent_form_score,
                    "market_value_eur": p.market_value_eur,
                    "data_source": p.data_source,
                }
                for p in players
            ],
        }
    finally:
        db.close()
