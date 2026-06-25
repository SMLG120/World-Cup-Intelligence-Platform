"""World Cup 2026 data and simulation API endpoints."""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/world-cup", tags=["world-cup"])
alias_router = APIRouter(prefix="/world_cup", tags=["world-cup"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SimulateRequest(BaseModel):
    year: int = Field(2026, description="Tournament year")
    runs: int = Field(10_000, ge=1, le=50_000)
    overrides: Optional[Dict[str, Dict]] = None
    seed: Optional[int] = None
    deterministic: bool = False
    prediction_mode: str = Field(
        "ensemble",
        description="Match prediction layer used for displayed bracket probabilities: statistical, ml, or ensemble.",
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/qualified-teams")
def get_qualified_teams(
    year: int = Query(2026),
    confederation: Optional[str] = Query(None),
    confirmed_only: bool = Query(True),
) -> List[Dict[str, Any]]:
    """Return currently qualified teams with current Elo and FIFA ranking."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import QualifiedTeam
        from app.models.team import EloRatingSnapshot, TeamEloRating
        from app.models.ranking import FifaRankingSnapshot, FifaRankingEntry

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

            # Build Elo lookup from current snapshot
            elo_by_name: Dict[str, float] = {}
            elo_snapshot = db.scalar(
                select(EloRatingSnapshot)
                .where(EloRatingSnapshot.is_current.is_(True))
                .order_by(EloRatingSnapshot.rating_date.desc(), EloRatingSnapshot.id.desc())
                .limit(1)
            )
            if elo_snapshot:
                for entry in db.scalars(
                    select(TeamEloRating).where(TeamEloRating.snapshot_id == elo_snapshot.id)
                ).all():
                    elo_by_name[entry.team_name] = entry.rating

            # Build FIFA ranking lookup from current snapshot
            fifa_by_name: Dict[str, int] = {}
            fifa_snapshot = db.scalar(
                select(FifaRankingSnapshot)
                .where(FifaRankingSnapshot.is_current.is_(True))
                .order_by(FifaRankingSnapshot.ranking_date.desc(), FifaRankingSnapshot.id.desc())
                .limit(1)
            )
            if fifa_snapshot:
                for entry in db.scalars(
                    select(FifaRankingEntry).where(FifaRankingEntry.snapshot_id == fifa_snapshot.id)
                ).all():
                    fifa_by_name[entry.team_name] = entry.rank

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
                    "elo_rating": elo_by_name.get(r.team_name),
                    "fifa_rank": fifa_by_name.get(r.team_name),
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


@alias_router.get("/2026/groups")
def get_2026_groups_alias() -> Dict[str, Any]:
    return get_groups(year=2026)


@alias_router.get("/2026/bracket")
def get_2026_bracket_alias() -> Dict[str, Any]:
    return get_bracket(year=2026)


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
            prediction_mode=req.prediction_mode,
        )

    raise HTTPException(400, f"Year {req.year} not supported")


@alias_router.post("/2026/simulate")
def simulate_2026_alias(req: SimulateRequest) -> Dict[str, Any]:
    """Contract-friendly alias for the WC2026 tournament simulator."""
    return _simulate_2026(
        req.runs,
        req.overrides or {},
        seed=req.seed,
        deterministic=req.deterministic,
        prediction_mode=req.prediction_mode,
    )


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


@router.get("/2026/predictions")
def get_2026_predictions(
    runs: int = Query(5000, ge=100, le=50_000),
    seed: int | None = Query(None),
    deterministic: bool = Query(False),
) -> Dict[str, Any]:
    """Return the current WC2026 prediction bundle."""
    from app.services.data_refresh_service import get_data_freshness

    return {
        "year": 2026,
        "prediction_type": "ensemble",
        "freshness": get_data_freshness(),
        "winner_predictions": get_2026_winner_predictions(
            runs=runs,
            seed=seed,
            deterministic=deterministic,
        ),
    }


@alias_router.get("/2026/winner-predictions")
def get_2026_winner_predictions_alias(
    runs: int = Query(5000, ge=100, le=50_000),
    seed: int | None = Query(None),
    deterministic: bool = Query(False),
) -> List[Dict[str, Any]]:
    return get_2026_winner_predictions(runs=runs, seed=seed, deterministic=deterministic)


@alias_router.get("/2026/predictions")
def get_2026_predictions_alias(
    runs: int = Query(5000, ge=100, le=50_000),
    seed: int | None = Query(None),
    deterministic: bool = Query(False),
) -> Dict[str, Any]:
    return get_2026_predictions(runs=runs, seed=seed, deterministic=deterministic)


def _simulate_2026(
    runs: int,
    overrides: Dict,
    *,
    seed: int | None = None,
    deterministic: bool = False,
    prediction_mode: str = "ensemble",
) -> Dict[str, Any]:
    """Run 2026 WC simulation.

    If groups are available from DB, uses those. Otherwise falls back to
    a simplified pair-elimination using qualified teams sorted by Elo.
    """
    from wcip.data.wc2026 import build_2026_groups_from_db, get_qualified_teams_from_db, build_2026_bracket
    from wcip.data.teams_2022 import Team
    from wcip.engine.montecarlo import generate_seed
    from app.services.data_refresh_service import get_data_freshness

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
    prediction_mode = _normalize_prediction_mode(prediction_mode)

    from wcip.engine.montecarlo import MonteCarloEngine
    engine = MonteCarloEngine(teams_dict, groups, bracket)
    probs = engine.run(n_runs=runs, seed=seed_to_use)
    sample_seed = _sample_seed_for_monte_carlo(seed_to_use, runs)
    sample_run = _simulate_single_2026_run(
        teams_dict,
        groups,
        bracket,
        seed=sample_seed,
        prediction_mode=prediction_mode,
        champion_probabilities=probs,
    )
    champion = sample_run["champion"]

    return {
        "year": 2026,
        "runs": runs,
        "seed": seed_to_use,
        "deterministic": bool(deterministic or seed is not None),
        "prediction_mode": prediction_mode,
        "draw_complete": bool(build_2026_groups_from_db()),
        "groups": groups,
        "champion": champion,
        "runner_up": sample_run["runner_up"],
        "third_place": sample_run["third_place"],
        "fourth_place": sample_run["fourth_place"],
        "champion_probability": round(probs.get(champion).champion, 5) if champion in probs else None,
        "group_tables": sample_run["group_tables"],
        "group_stage_matches": sample_run["group_stage_matches"],
        "qualified_teams": sample_run["qualified_teams"],
        "best_third_place": sample_run["best_third_place"],
        "knockout_bracket": sample_run["knockout_bracket"],
        "matches": sample_run["matches"],
        "data_snapshot": get_data_freshness(),
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


def _sample_seed_for_monte_carlo(seed: int, runs: int) -> Any:
    """Use the same first RNG stream as MonteCarloEngine for the replay path."""
    import os
    import numpy as np

    workers = min(os.cpu_count() or 1, 8)
    base = runs // workers
    rem = runs % workers
    chunks = [base + (1 if i < rem else 0) for i in range(workers)]
    chunks = [c for c in chunks if c > 0]
    if not chunks:
        return seed
    return np.random.SeedSequence(seed).spawn(len(chunks))[0]


def _simulate_single_2026_run(
    teams_dict: Dict[str, Any],
    groups: Dict[str, List[str]],
    bracket: List[tuple],
    *,
    seed: Any,
    prediction_mode: str,
    champion_probabilities: Dict[str, Any],
) -> Dict[str, Any]:
    """Run one replayable WC2026 bracket for group tables and match details."""
    import numpy as np
    from wcip.engine.match import MatchSimulator
    from wcip.engine.scoreline import ScorelineModel
    from wcip.engine.tournament import GroupRow, TournamentEngine

    rng = np.random.default_rng(seed)
    sim = MatchSimulator(model=ScorelineModel(), rng=rng)
    result = TournamentEngine(teams_dict, groups, bracket, simulator=sim).simulate()
    team_meta = {
        name: {
            "code": getattr(team, "code", None) or "???",
            "confederation": getattr(team, "confederation", None),
            "elo": getattr(team, "elo", None),
            "fifa_rank": getattr(team, "fifa_rank", None),
        }
        for name, team in teams_dict.items()
    }
    prediction_cache: Dict[tuple[str, str], Dict[str, Any]] = {}

    qualified = set(result.round_of_32)
    best_third_teams = {row.team for row in result.best_third_place}

    def row_to_dict(row: GroupRow, rank: int, label: str) -> Dict[str, Any]:
        if rank <= 2:
            qualification_type = "automatic"
        elif row.team in best_third_teams:
            qualification_type = "best_third"
        else:
            qualification_type = "eliminated"
        return {
            "rank": rank,
            "team": row.team,
            "group": label,
            "played": row.played,
            "won": row.won,
            "drawn": row.drawn,
            "lost": row.lost,
            "goals_for": row.gf,
            "goals_against": row.ga,
            "goal_difference": row.gd,
            "points": row.points,
            "qualified": row.team in qualified,
            "qualification_type": qualification_type,
        }

    group_tables = {
        label: [row_to_dict(row, idx, label) for idx, row in enumerate(rows, start=1)]
        for label, rows in result.group_tables.items()
    }
    group_lookup = {
        row["team"]: row["group"]
        for rows in group_tables.values()
        for row in rows
    }
    best_third_place = [
        {
            **row_to_dict(row, 3, group_lookup.get(row.team, "")),
            "rank": idx,
        }
        for idx, row in enumerate(result.best_third_place, start=1)
    ]
    qualified_teams = [
        row
        for rows in group_tables.values()
        for row in rows
        if row["qualified"]
    ]

    group_stage_matches = {
        label: [
            _match_to_dict(
                f"{label}{idx}",
                match,
                team_meta=team_meta,
                prediction_mode=prediction_mode,
                prediction_cache=prediction_cache,
                champion_probabilities=champion_probabilities,
                round_name="Group Stage",
                order=idx,
                group=label,
            )
            for idx, match in enumerate(matches, start=1)
        ]
        for label, matches in result.group_matches.items()
    }

    matches = [
        _match_to_dict(
            match_id,
            match,
            team_meta=team_meta,
            prediction_mode=prediction_mode,
            prediction_cache=prediction_cache,
            champion_probabilities=champion_probabilities,
        )
        for match_id, match in result.knockout.items()
    ]
    round_order = [
        "Round of 32",
        "Round of 16",
        "Quarter-finals",
        "Semi-finals",
        "Third-place match",
        "Final",
    ]
    knockout_bracket = [
        {
            "round": round_name,
            "matches": [
                match for match in matches
                if match["round"] == round_name
            ],
        }
        for round_name in round_order
    ]

    return {
        "seed": seed,
        "champion": result.champion,
        "runner_up": result.runner_up,
        "third_place": result.third_place,
        "fourth_place": result.fourth_place,
        "group_tables": group_tables,
        "group_stage_matches": group_stage_matches,
        "qualified_teams": qualified_teams,
        "best_third_place": best_third_place,
        "knockout_bracket": knockout_bracket,
        "matches": matches,
    }


def _match_to_dict(
    match_id: str,
    match: Any,
    *,
    team_meta: Dict[str, Dict[str, Any]],
    prediction_mode: str,
    prediction_cache: Dict[tuple[str, str], Dict[str, Any]],
    champion_probabilities: Dict[str, Any],
    round_name: str | None = None,
    order: int | None = None,
    group: str | None = None,
) -> Dict[str, Any]:
    resolved_round, resolved_order = _round_for_match(match_id)
    round_name = round_name or resolved_round
    order = resolved_order if order is None else order
    loser = None
    if match.winner:
        loser = match.away if match.winner == match.home else match.home
    layers = _prediction_layers(match.home, match.away, prediction_mode, prediction_cache)
    selected = layers["selected_prediction"]
    winner_probability = _winner_probability(match, selected)
    winner_champion_probability = None
    if match.winner in champion_probabilities:
        winner_champion_probability = round(champion_probabilities[match.winner].champion, 5)
    scoreline = f"{match.home_goals}-{match.away_goals}"
    return {
        "match_id": match_id,
        "round": round_name,
        "order": order,
        "group": group,
        "home": match.home,
        "away": match.away,
        "home_code": _team_code(match.home, team_meta),
        "away_code": _team_code(match.away, team_meta),
        "home_goals": match.home_goals,
        "away_goals": match.away_goals,
        "winner": match.winner,
        "loser": loser,
        "advancing_team": match.winner if round_name != "Group Stage" else None,
        "decided_by": match.decided_by,
        "home_xg": round(match.home_xg, 3),
        "away_xg": round(match.away_xg, 3),
        "scoreline": scoreline,
        "expected_scoreline": layers["expected_scoreline"] or f"{match.home} {round(match.home_xg)} - {round(match.away_xg)} {match.away}",
        "statistical_prediction": layers["statistical_prediction"],
        "ml_prediction": layers["ml_prediction"],
        "ensemble_prediction": layers["ensemble_prediction"],
        "selected_prediction": selected,
        "prediction_mode": prediction_mode,
        "effective_prediction_mode": layers["effective_prediction_mode"],
        "model_used": layers["effective_prediction_mode"],
        "winner_probability": winner_probability,
        "champion_probability": winner_champion_probability,
        "advancement_reason": _advancement_reason(round_name, match, layers["effective_prediction_mode"]),
    }


def _normalize_prediction_mode(mode: str | None) -> str:
    normalized = (mode or "ensemble").strip().lower()
    if normalized in {"stat", "stats", "statistical"}:
        return "statistical"
    if normalized in {"machine_learning", "machine-learning", "ml"}:
        return "ml"
    if normalized == "ensemble":
        return "ensemble"
    raise HTTPException(400, "prediction_mode must be one of: statistical, ml, ensemble")


def _round_for_match(match_id: str) -> tuple[str, int]:
    if match_id == "FINAL":
        return "Final", 999
    if match_id == "THIRD_PLACE":
        return "Third-place match", 998
    try:
        number = int(match_id.removeprefix("M"))
    except ValueError:
        return "Knockout", 0
    if 49 <= number <= 64:
        return "Round of 32", number
    if 65 <= number <= 72:
        return "Round of 16", number
    if 73 <= number <= 76:
        return "Quarter-finals", number
    if number in {200, 201}:
        return "Semi-finals", number
    return "Knockout", number


def _team_code(team: str, team_meta: Dict[str, Dict[str, Any]]) -> str:
    return str(team_meta.get(team, {}).get("code") or team[:3].upper())


def _prediction_layers(
    home: str,
    away: str,
    requested_mode: str,
    cache: Dict[tuple[str, str], Dict[str, Any]],
) -> Dict[str, Any]:
    key = (home, away)
    if key in cache:
        payload = cache[key]
    else:
        payload = _build_prediction_layers(home, away)
        cache[key] = payload

    effective_mode = requested_mode
    selected = payload[f"{requested_mode}_prediction"]
    if requested_mode == "ml" and not selected.get("available", False):
        selected = payload["ensemble_prediction"]
        effective_mode = "ensemble_fallback"

    return {
        **payload,
        "selected_prediction": selected,
        "effective_prediction_mode": effective_mode,
    }


def _build_prediction_layers(home: str, away: str) -> Dict[str, Any]:
    try:
        from ml.ensemble import predict_hybrid

        prediction = predict_hybrid(home_team=home, away_team=away, include_shap=False).to_dict()
        statistical = _sanitize_probability_dict(prediction.get("statistical", {}), available=True)
        ensemble = _sanitize_probability_dict(prediction.get("ensemble", {}), available=True)
        ml_prediction = _average_ml_predictions(prediction.get("ml_predictions", {}), fallback=ensemble)
        return {
            "statistical_prediction": statistical,
            "ml_prediction": ml_prediction,
            "ensemble_prediction": ensemble,
            "expected_scoreline": prediction.get("expected_scoreline", ""),
        }
    except Exception as exc:
        logger.warning("Hybrid prediction failed for %s vs %s: %s", home, away, exc)
        fallback = _sanitize_probability_dict({}, available=False)
        return {
            "statistical_prediction": fallback,
            "ml_prediction": {**fallback, "available": False},
            "ensemble_prediction": fallback,
            "expected_scoreline": "",
        }


def _average_ml_predictions(
    predictions: Dict[str, Dict[str, Any]],
    *,
    fallback: Dict[str, Any],
) -> Dict[str, Any]:
    if not predictions:
        return {**fallback, "available": False, "models_used": []}
    values = [_sanitize_probability_dict(p, available=True) for p in predictions.values()]
    averaged = {
        "home_win": sum(v["home_win"] for v in values) / len(values),
        "draw": sum(v["draw"] for v in values) / len(values),
        "away_win": sum(v["away_win"] for v in values) / len(values),
    }
    return {
        **_sanitize_probability_dict(averaged, available=True),
        "models_used": sorted(predictions.keys()),
    }


def _sanitize_probability_dict(raw: Dict[str, Any], *, available: bool) -> Dict[str, Any]:
    vals = [
        _safe_probability(raw.get("home_win", 1 / 3)),
        _safe_probability(raw.get("draw", 1 / 3)),
        _safe_probability(raw.get("away_win", 1 / 3)),
    ]
    total = sum(vals)
    if total <= 1e-8:
        vals = [1 / 3, 1 / 3, 1 / 3]
    else:
        vals = [v / total for v in vals]
    return {
        "home_win": round(vals[0], 6),
        "draw": round(vals[1], 6),
        "away_win": round(vals[2], 6),
        "available": available,
    }


def _safe_probability(value: Any) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric):
        return 0.0
    return max(0.0, min(1.0, numeric))


def _winner_probability(match: Any, selected: Dict[str, Any]) -> float:
    if match.winner == match.home:
        return selected["home_win"]
    if match.winner == match.away:
        return selected["away_win"]
    return selected["draw"]


def _advancement_reason(round_name: str, match: Any, mode: str) -> str:
    if round_name == "Group Stage":
        return "Group-stage result updates the table; qualification is decided by points, goal difference, and goals for."
    if match.decided_by == "penalties":
        return f"{match.winner} advanced on penalties after a drawn knockout scoreline."
    if match.decided_by == "extra_time":
        return f"{match.winner} advanced after extra time under {mode} prediction mode."
    return f"{match.winner} advanced by simulated scoreline under {mode} prediction mode."


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
    from app.services.data_refresh_service import get_data_freshness

    canon = canonical(team_name)
    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == canon))
        team_names = _team_name_variants(canon)
        coach = db.scalar(select(Coach).where(Coach.team_name.in_(team_names)))
        players = db.scalars(
            select(Player).where(
                Player.team_name.in_(team_names),
                Player.is_active.is_(True),
            )
        ).all()

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
            "data_snapshot": get_data_freshness(),
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
            select(Player).where(
                Player.team_name.in_(_team_name_variants(canon)),
                Player.is_active.is_(True),
            )
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
                    # FIFA squad PDF fields
                    "shirt_number": p.shirt_number,
                    "first_names": p.first_names,
                    "last_names": p.last_names,
                    "name_on_shirt": p.name_on_shirt,
                    "date_of_birth": p.date_of_birth,
                    "height_cm": p.height_cm,
                    # Playing metrics
                    "goals": p.goals,
                    "assists": p.assists,
                    "xg": p.xg,
                    "xag": p.xag,
                    "minutes_played": p.minutes_played,
                    "international_caps": p.international_caps,
                    "international_goals": p.international_goals,
                    "player_rating": p.player_rating,
                    "ea_fc_rating": p.ea_fc_rating,
                    "player_rating_source": p.player_rating_source,
                    "player_rating_version": p.player_rating_version,
                    "injured": p.injured,
                    "suspended": p.suspended,
                    "fitness_score": p.fitness_score,
                    "recent_form_score": p.recent_form_score,
                    "market_value_eur": p.market_value_eur,
                    "data_source": p.data_source,
                    "updated_at": p.updated_at.isoformat() if p.updated_at else None,
                    "profile_description": p.profile_description,
                }
                for p in players
            ],
        }
    finally:
        db.close()


def _team_name_variants(team_name: str) -> list[str]:
    from etl.transform.normalize import canonical

    canon = canonical(team_name)
    variants = {
        team_name,
        canon,
        canon.replace(" and ", " And "),
    }
    if canon == "Bosnia and Herzegovina":
        variants.update({
            "Bosnia And Herzegovina",
            "Bosnia & Herzegovina",
            "Bosnia-Herzegovina",
            "BIH",
        })
    return sorted(variants)
