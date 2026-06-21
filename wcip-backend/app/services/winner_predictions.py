"""World Cup 2026 winner prediction service."""
from __future__ import annotations

import math
from typing import Any

from fastapi import HTTPException

from app.services.probabilities import (
    normalize_probabilities,
    normalize_probability_value,
    validate_probability_distribution,
)


def world_cup_2026_winner_predictions(
    *,
    runs: int = 5000,
    seed: int | None = None,
    deterministic: bool = False,
    workers: int = 1,
) -> list[dict[str, Any]]:
    """Return ranked, normalized 2026 World Cup winner predictions."""

    if runs < 100 or runs > 50_000:
        raise HTTPException(
            status_code=422,
            detail={
                "error_code": "invalid_simulation_count",
                "message": "runs must be between 100 and 50000",
                "detail": {"runs": runs},
            },
        )

    from etl.transform.normalize import canonical
    from app.services.data_refresh_service import get_data_freshness
    from ml.features import (
        _get_coach_impact,
        _get_form,
        _get_team_elo_metadata,
        _get_player_strength_stats,
        _get_team_elo,
        _get_team_fifa_rank,
    )
    from wcip.data.teams_2022 import Team
    from wcip.data.wc2026 import (
        build_2026_bracket,
        build_2026_groups_from_db,
        get_qualified_teams_from_db,
    )
    from wcip.engine.montecarlo import MonteCarloEngine, generate_seed

    qualified = get_qualified_teams_from_db()
    if not qualified:
        raise HTTPException(
            status_code=503,
            detail={
                "error_code": "empty_world_cup_dataset",
                "message": "No World Cup 2026 teams are available",
                "detail": "Run the WC2026 seed ETL before requesting winner predictions.",
            },
        )

    groups = build_2026_groups_from_db() or _provisional_groups_by_elo(qualified)
    bracket = build_2026_bracket(groups)
    group_by_team = {
        canonical(team): f"Group {label}"
        for label, teams in groups.items()
        for team in teams
    }
    meta_by_team = {canonical(row["team_name"]): row for row in qualified}

    teams_dict: dict[str, Team] = {}
    strength_inputs: dict[str, dict[str, float]] = {}
    for row in qualified:
        name = canonical(row["team_name"])
        elo = float(_get_team_elo(name))
        fifa_rank = int(_get_team_fifa_rank(name))
        player_stats = _get_player_strength_stats(name)
        form = float(_get_form(name, __import__("datetime").date.today()))
        coach = float(_get_coach_impact(name))
        teams_dict[name] = Team(
            name=name,
            code=row.get("team_code", "???"),
            confederation=row.get("confederation", ""),
            elo=elo,
            fifa_rank=fifa_rank,
        )
        strength_inputs[name] = {
            "elo": elo,
            "fifa_rank": fifa_rank,
            "weighted_player_strength": float(player_stats["weighted_player_strength"]),
            "squad_depth_score": float(player_stats["squad_depth_score"]),
            "star_player_score": float(player_stats["star_player_score"]),
            "player_availability_score": float(player_stats["player_availability_score"]),
            "player_form_score": float(player_stats["player_form_score"]),
            "international_experience_score": float(player_stats["international_experience_score"]),
            "form": form,
            "coach": coach,
        }

    seed_to_use = int(seed) if seed is not None else (12345 if deterministic else generate_seed())
    engine = MonteCarloEngine(teams_dict, groups, bracket)
    statistical = engine.run(n_runs=runs, workers=workers, seed=seed_to_use)
    stat_probs = normalize_probabilities({
        team: probs.champion for team, probs in statistical.items()
    })
    ml_probs = _ml_strength_probabilities(strength_inputs)
    uniform = 1.0 / max(len(teams_dict), 1)
    ensemble_probs = normalize_probabilities({
        team: (
            0.42 * stat_probs.get(team, 0.0)
            + 0.48 * ml_probs.get(team, 0.0)
            + 0.10 * uniform
        )
        for team in teams_dict
    })

    freshness = get_data_freshness()
    rows: list[dict[str, Any]] = []
    for team, ensemble_probability in ensemble_probs.items():
        sim = statistical[team]
        meta = meta_by_team.get(team, {})
        strengths = strength_inputs[team]
        elo_meta = _get_team_elo_metadata(team)
        rows.append(
            {
                "rank": 0,
                "team_id": _team_id(team),
                "team_name": team,
                "seed": seed_to_use,
                "deterministic": bool(deterministic or seed is not None),
                "fifa_code": meta.get("team_code") or teams_dict[team].code,
                "group": group_by_team.get(team),
                "confederation": meta.get("confederation") or teams_dict[team].confederation,
                "fifa_rank": int(strengths["fifa_rank"]),
                "elo_rating_used": round(float(elo_meta.get("elo_rating_used", strengths["elo"])), 3),
                "elo_rank_used": elo_meta.get("elo_rank_used"),
                "elo_source": elo_meta.get("elo_source"),
                "elo_source_date": elo_meta.get("elo_source_date"),
                "elo_snapshot_version": elo_meta.get("elo_snapshot_version"),
                "fifa_ranking_used": int(strengths["fifa_rank"]),
                "data_snapshot": freshness.get("data_snapshot_timestamp") or freshness.get("generated_at"),
                "data_snapshot_version": freshness.get("data_snapshot_version"),
                "player_data_freshness_timestamp": freshness.get("last_player_data_update"),
                "model_version": freshness.get("model_version"),
                "prediction_type": "ensemble",
                "champion_probability": _prob(ensemble_probability),
                "final_probability": _prob(sim.final),
                "semifinal_probability": _prob(sim.semi),
                "quarterfinal_probability": _prob(sim.quarter),
                "round_of_16_probability": _prob(sim.round_of_16),
                "group_qualification_probability": _prob(getattr(sim, "round_of_32", 0.0)),
                "expected_finish": round(sim.expected_finish, 3),
                "confidence_interval_low": _prob(sim.champion_ci_low),
                "confidence_interval_high": _prob(sim.champion_ci_high),
                "statistical_probability": _prob(stat_probs.get(team, 0.0)),
                "ml_probability": _prob(ml_probs.get(team, 0.0)),
                "ensemble_probability": _prob(ensemble_probability),
                "explanation": _explain_team(team, strengths, stat_probs.get(team, 0.0), ml_probs.get(team, 0.0)),
            }
        )

    rows.sort(key=lambda row: row["champion_probability"], reverse=True)
    for idx, row in enumerate(rows, start=1):
        row["rank"] = idx
    _normalize_probability_field(rows, "champion_probability")
    _normalize_probability_field(rows, "ensemble_probability")
    if not validate_probability_distribution({row["team_name"]: row["champion_probability"] for row in rows}):
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "invalid_probability_distribution",
                "message": "Winner predictions did not produce a valid probability distribution.",
            },
        )
    return rows


def _ml_strength_probabilities(inputs: dict[str, dict[str, float]]) -> dict[str, float]:
    scores = {}
    for team, values in inputs.items():
        fifa_score = max(0.0, min(1.0, (250.0 - values["fifa_rank"]) / 249.0))
        elo_score = max(0.0, min(1.2, values["elo"] / 2100.0))
        player_score = max(0.0, min(1.2, values["weighted_player_strength"] / 85.0))
        depth = max(0.0, min(1.0, values["squad_depth_score"]))
        availability = max(0.0, min(1.0, values["player_availability_score"]))
        form = max(0.0, min(1.0, values["form"] / 3.0))
        player_form = max(0.0, min(1.0, values["player_form_score"]))
        coach = max(0.0, min(1.0, values["coach"] / 1.5))
        experience = max(0.0, min(1.0, values["international_experience_score"]))
        raw_score = (
            0.20 * elo_score
            + 0.24 * fifa_score
            + 0.18 * player_score
            + 0.10 * depth
            + 0.08 * availability
            + 0.10 * form
            + 0.05 * player_form
            + 0.03 * coach
            + 0.02 * experience
        )
        scores[team] = raw_score if math.isfinite(raw_score) else 0.0
    return _softmax(scores, temperature=3.5)


def _softmax(scores: dict[str, float], *, temperature: float) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values())
    exps = {
        key: math.exp((value - max_score) * temperature)
        for key, value in scores.items()
    }
    return normalize_probabilities(exps)


def _normalize_probability_field(rows: list[dict[str, Any]], field: str) -> None:
    total = sum(float(row[field]) for row in rows)
    if total <= 0:
        return
    for row in rows:
        row[field] = _prob(float(row[field]) / total)


def _prob(value: float) -> float:
    return round(normalize_probability_value(value), 6)


def _team_id(team_name: str) -> int | None:
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.team import Team

        db = SessionLocal()
        try:
            team = db.scalar(select(Team).where(Team.name == team_name))
            return team.id if team else None
        finally:
            db.close()
    except Exception:
        return None


def _provisional_groups_by_elo(qualified: list[dict[str, Any]]) -> dict[str, list[str]]:
    from ml.features import _get_team_elo

    sorted_teams = sorted(qualified, key=lambda row: _get_team_elo(row["team_name"]), reverse=True)
    labels = [chr(ord("A") + idx) for idx in range(12)]
    groups: dict[str, list[str]] = {label: [] for label in labels}
    for idx, row in enumerate(sorted_teams[:48]):
        pass_num = idx // 12
        pos = idx % 12
        group_idx = pos if pass_num % 2 == 0 else 11 - pos
        groups[labels[group_idx]].append(row["team_name"])
    return groups


def _explain_team(team: str, strengths: dict[str, float], stat_prob: float, ml_prob: float) -> str:
    reasons: list[str] = []
    if strengths["elo"] >= 1900:
        reasons.append("strong Elo")
    if strengths["fifa_rank"] <= 10:
        reasons.append("elite FIFA ranking")
    if strengths["weighted_player_strength"] >= 75:
        reasons.append("high player-strength rating")
    if strengths["squad_depth_score"] >= 0.75:
        reasons.append("squad depth")
    if strengths["player_availability_score"] >= 0.9:
        reasons.append("good player availability")
    if ml_prob > stat_prob:
        reasons.append("model strength above simulation baseline")
    if not reasons:
        reasons.append("balanced statistical and squad profile")
    return f"{team} ranks here because of " + ", ".join(reasons[:4]) + "."
