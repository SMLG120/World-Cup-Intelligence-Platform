"""Dynamic head-to-head prediction service."""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from etl.transform.normalize import canonical
from ml.ensemble import MatchOutcome, predict_hybrid


def predict_head_to_head(
    home_team: str,
    away_team: str,
    *,
    match_date: date | None = None,
    home_overrides: dict[str, Any] | None = None,
    away_overrides: dict[str, Any] | None = None,
    include_shap: bool = False,
) -> dict[str, Any]:
    home = canonical(home_team)
    away = canonical(away_team)
    if match_date is None:
        match_date = date.today()

    hybrid = predict_hybrid(
        home_team=home,
        away_team=away,
        match_date=match_date,
        home_overrides=home_overrides,
        away_overrides=away_overrides,
        include_shap=include_shap,
    )

    features = dict(hybrid.feature_values_used)
    method_breakdown = _build_method_breakdown(hybrid, features)
    ensemble, weights = _weighted_ensemble(method_breakdown)
    key_factors = _key_factors(features, home, away)
    confidence = _confidence_score(ensemble, hybrid.confidence_score)

    return {
        "home_team": home,
        "away_team": away,
        "match_date": str(match_date),
        "method_used": "ensemble",
        "probabilities": _outcome_to_dict(ensemble),
        "expected_score": {
            "home_xg": round(float(hybrid.home_xg), 3),
            "away_xg": round(float(hybrid.away_xg), 3),
            "scoreline": hybrid.expected_scoreline,
        },
        "confidence": confidence,
        "model_version": str(hybrid.data_snapshot.get("data_snapshot_version") or hybrid.data_snapshot.get("feature_version") or "unknown"),
        "feature_snapshot": {
            "features": {key: round(float(value), 4) for key, value in features.items()},
            "data_snapshot": hybrid.data_snapshot,
        },
        "method_breakdown": {
            name: _outcome_to_dict(outcome)
            for name, outcome in method_breakdown.items()
        },
        "method_weights": weights,
        "model_agreement": round(float(hybrid.model_agreement), 3),
        "key_factors": key_factors,
        "explanation": hybrid.to_dict().get("explanation", {}),
    }


def _build_method_breakdown(hybrid, features: dict[str, float]) -> dict[str, MatchOutcome]:
    elo = _edge_to_outcome(float(features.get("elo_diff", 0.0)) / 260.0, draw_base=0.25)
    fifa = _edge_to_outcome(float(features.get("fifa_rank_diff", 0.0)) / 32.0, draw_base=0.27)
    player_edge = (
        float(features.get("average_squad_rating_diff", 0.0)) / 9.0
        + float(features.get("top_5_player_rating_avg_diff", 0.0)) / 12.0
        + float(features.get("weighted_player_strength_diff", 0.0)) / 9.0
        + float(features.get("player_availability_score_diff", 0.0)) * 0.8
    ) / 4.0
    player_strength = _edge_to_outcome(player_edge, draw_base=0.26)

    ml = _average_outcomes(hybrid.ml_predictions) if hybrid.ml_predictions else hybrid.statistical
    return {
        "elo": _sanitize(elo),
        "fifa": _sanitize(fifa),
        "player_strength": _sanitize(player_strength),
        "statistical": _sanitize(hybrid.statistical),
        "ml": _sanitize(ml),
    }


def _edge_to_outcome(edge: float, *, draw_base: float) -> MatchOutcome:
    edge = max(-5.0, min(5.0, edge))
    draw = max(0.16, min(0.34, draw_base - min(abs(edge), 2.0) * 0.035))
    home_share = 1.0 / (1.0 + math.exp(-edge))
    non_draw = 1.0 - draw
    return MatchOutcome(
        home_win=non_draw * home_share,
        draw=draw,
        away_win=non_draw * (1.0 - home_share),
    )


def _average_outcomes(outcomes: dict[str, MatchOutcome]) -> MatchOutcome:
    if not outcomes:
        return MatchOutcome(1 / 3, 1 / 3, 1 / 3)
    total = float(len(outcomes))
    return MatchOutcome(
        home_win=sum(outcome.home_win for outcome in outcomes.values()) / total,
        draw=sum(outcome.draw for outcome in outcomes.values()) / total,
        away_win=sum(outcome.away_win for outcome in outcomes.values()) / total,
    )


def _weighted_ensemble(methods: dict[str, MatchOutcome]) -> tuple[MatchOutcome, dict[str, float]]:
    weights = {
        "elo": 0.20,
        "fifa": 0.15,
        "player_strength": 0.20,
        "statistical": 0.20,
        "ml": 0.25,
    }
    active_weights = {name: weights[name] for name in methods if name in weights}
    total_weight = sum(active_weights.values()) or 1.0
    normalized = {name: round(weight / total_weight, 4) for name, weight in active_weights.items()}
    outcome = MatchOutcome(
        home_win=sum(methods[name].home_win * active_weights[name] for name in active_weights) / total_weight,
        draw=sum(methods[name].draw * active_weights[name] for name in active_weights) / total_weight,
        away_win=sum(methods[name].away_win * active_weights[name] for name in active_weights) / total_weight,
    )
    return _sanitize(outcome), normalized


def _sanitize(outcome: MatchOutcome) -> MatchOutcome:
    values = [
        max(0.0, min(1.0, float(outcome.home_win))),
        max(0.0, min(1.0, float(outcome.draw))),
        max(0.0, min(1.0, float(outcome.away_win))),
    ]
    total = sum(values)
    if total <= 1e-8:
        return MatchOutcome(1 / 3, 1 / 3, 1 / 3)
    return MatchOutcome(values[0] / total, values[1] / total, values[2] / total)


def _outcome_to_dict(outcome: MatchOutcome) -> dict[str, float]:
    clean = _sanitize(outcome)
    return {
        "home_win": round(clean.home_win, 4),
        "draw": round(clean.draw, 4),
        "away_win": round(clean.away_win, 4),
    }


def _confidence_score(ensemble: MatchOutcome, hybrid_confidence: float) -> float:
    ordered = sorted([ensemble.home_win, ensemble.draw, ensemble.away_win], reverse=True)
    margin = ordered[0] - ordered[1]
    confidence = 0.55 * max(0.0, min(1.0, float(hybrid_confidence))) + 0.45 * max(0.0, min(1.0, margin * 2.0))
    return round(confidence, 3)


def _key_factors(features: dict[str, float], home: str, away: str) -> list[dict[str, Any]]:
    factor_defs = [
        ("elo_diff", "Elo rating", "ratings"),
        ("fifa_rank_diff", "FIFA ranking", "ranking places"),
        ("average_squad_rating_diff", "Average squad rating", "rating points"),
        ("top_5_player_rating_avg_diff", "Top five player rating", "rating points"),
        ("weighted_player_strength_diff", "Weighted player strength", "rating points"),
        ("form_diff", "Recent form", "points per game"),
        ("injury_burden_diff", "Injury burden", "squad share"),
    ]
    factors = []
    for key, label, unit in factor_defs:
        value = float(features.get(key, 0.0))
        if abs(value) < 1e-6:
            continue
        factors.append({
            "name": key,
            "label": label,
            "value": round(value, 3),
            "unit": unit,
            "favours": home if value > 0 else away,
            "impact": round(value, 3),
        })
    return sorted(factors, key=lambda item: abs(float(item["impact"])), reverse=True)[:6]
