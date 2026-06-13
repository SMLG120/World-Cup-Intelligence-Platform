"""Ensemble prediction service.

Combines:
  1. Statistical prediction (Elo + Poisson from existing engine)
  2. Machine learning models (logistic, RF, XGBoost, LightGBM, CatBoost)

into a weighted ensemble output.

Also provides SHAP-based explainability for every prediction.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import numpy as np

from ml.features import FEATURE_NAMES, FeatureVector, build_feature_metadata, build_feature_vector
from ml.predict import predict_all_models, predict_with_model

logger = logging.getLogger(__name__)


@dataclass
class MatchOutcome:
    home_win: float
    draw: float
    away_win: float

    def to_dict(self) -> dict:
        return {
            "home_win": round(self.home_win, 4),
            "draw": round(self.draw, 4),
            "away_win": round(self.away_win, 4),
        }


@dataclass
class FactorExplanation:
    name: str
    display_name: str
    value: float
    impact: float        # positive = favours home, negative = favours away
    direction: str       # "home" | "away" | "neutral"


@dataclass
class PredictionExplanation:
    top_positive: List[FactorExplanation]   # factors favouring home
    top_negative: List[FactorExplanation]   # factors favouring away
    shap_values: Optional[List[float]] = None
    narrative: str = ""


@dataclass
class HybridPrediction:
    home_team: str
    away_team: str
    match_date: date

    # Three-way prediction split
    statistical: MatchOutcome = field(default_factory=lambda: MatchOutcome(0.4, 0.25, 0.35))
    ml_predictions: Dict[str, MatchOutcome] = field(default_factory=dict)
    ensemble: MatchOutcome = field(default_factory=lambda: MatchOutcome(0.4, 0.25, 0.35))

    # xG
    home_xg: float = 1.35
    away_xg: float = 1.35
    expected_scoreline: str = ""

    # Confidence
    confidence_score: float = 0.5     # 0..1 based on model agreement
    model_agreement: float = 0.5      # std dev across model predictions

    # Explainability
    explanation: Optional[PredictionExplanation] = None
    model_weights_used: Dict[str, float] = field(default_factory=dict)
    feature_values_used: Dict[str, float] = field(default_factory=dict)
    data_snapshot: Dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "home_team": self.home_team,
            "away_team": self.away_team,
            "match_date": str(self.match_date),
            "statistical": self.statistical.to_dict(),
            "ml_predictions": {k: v.to_dict() for k, v in self.ml_predictions.items()},
            "ensemble": self.ensemble.to_dict(),
            "home_xg": round(self.home_xg, 3),
            "away_xg": round(self.away_xg, 3),
            "expected_scoreline": self.expected_scoreline,
            "confidence_score": round(self.confidence_score, 3),
            "model_agreement": round(self.model_agreement, 3),
            "model_weights_used": {
                key: round(float(value), 4)
                for key, value in self.model_weights_used.items()
            },
            "feature_values_used": {
                key: round(float(value), 4)
                for key, value in self.feature_values_used.items()
            },
            "data_snapshot": self.data_snapshot,
            "explanation": _explanation_to_dict(self.explanation),
        }


def _explanation_to_dict(exp: Optional[PredictionExplanation]) -> dict:
    if exp is None:
        return {}
    return {
        "top_positive": [
            {"name": f.name, "display_name": f.display_name,
             "value": round(f.value, 3), "impact": round(f.impact, 4)}
            for f in exp.top_positive
        ],
        "top_negative": [
            {"name": f.name, "display_name": f.display_name,
             "value": round(f.value, 3), "impact": round(f.impact, 4)}
            for f in exp.top_negative
        ],
        "shap_values": [round(v, 4) for v in (exp.shap_values or [])],
        "narrative": exp.narrative,
    }


# ---------------------------------------------------------------------------
# Statistical engine wrapper
# ---------------------------------------------------------------------------

def _statistical_prediction(
    home_team: str,
    away_team: str,
    home_overrides: Optional[Dict] = None,
    away_overrides: Optional[Dict] = None,
) -> tuple[MatchOutcome, float, float]:
    """Run the existing Elo/Poisson engine."""
    try:
        from app.services.prediction import predict_match
        result = predict_match(
            home=home_team,
            away=away_team,
            home_mods=home_overrides or {},
            away_mods=away_overrides or {},
            edition="2022",
        )
        probs = result["probabilities"]
        return (
            MatchOutcome(
                home_win=probs.get("home_win", 0.4),
                draw=probs.get("draw", 0.25),
                away_win=probs.get("away_win", 0.35),
            ),
            result.get("home_xg", 1.35),
            result.get("away_xg", 1.35),
        )
    except Exception as e:
        logger.debug("Statistical engine failed (%s vs %s): %s", home_team, away_team, e)
        # Fallback: use Elo-only estimate
        return _elo_fallback(home_team, away_team, home_overrides, away_overrides)


def _elo_fallback(
    home_team: str,
    away_team: str,
    home_overrides: Optional[Dict] = None,
    away_overrides: Optional[Dict] = None,
) -> tuple[MatchOutcome, float, float]:
    try:
        from wcip.engine.elo import expected_score
        from ml.features import _get_team_elo
        h_elo = (home_overrides or {}).get("elo", _get_team_elo(home_team))
        a_elo = (away_overrides or {}).get("elo", _get_team_elo(away_team))
        e_home = expected_score(h_elo, a_elo)
        e_away = expected_score(a_elo, h_elo)
        draw = max(0.1, 1.0 - e_home - e_away * 0.7)
        hw = max(0.05, e_home - draw / 2)
        aw = max(0.05, 1 - hw - draw)
        # Normalise
        total = hw + draw + aw
        return MatchOutcome(hw / total, draw / total, aw / total), 1.35, 1.35
    except Exception:
        return MatchOutcome(0.4, 0.25, 0.35), 1.35, 1.35


# ---------------------------------------------------------------------------
# Ensemble weighting
# ---------------------------------------------------------------------------

def _get_model_weights() -> Dict[str, float]:
    """Load normalized ensemble weights from the DB."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import MLModelRecord

        db = SessionLocal()
        try:
            records = db.scalars(
                select(MLModelRecord).where(MLModelRecord.is_active == True)
            ).all()
            if not records:
                return {}
            return {r.model_name: r.ensemble_weight for r in records}
        finally:
            db.close()
    except Exception:
        # Equal weights fallback
        return {"logistic": 0.2, "random_forest": 0.2, "xgboost": 0.2,
                "lightgbm": 0.2, "catboost": 0.2}


# ---------------------------------------------------------------------------
# SHAP explainability
# ---------------------------------------------------------------------------

def _compute_shap(model_name: str, fv: FeatureVector) -> Optional[List[float]]:
    """Compute SHAP values for the home_win probability."""
    try:
        import shap
        from ml.predict import _features_for_model, _load_model

        model = _load_model(model_name)
        if model is None:
            return None

        X = _features_for_model(model, fv)

        # Use TreeExplainer for tree-based models, LinearExplainer for logistic
        if model_name == "logistic":
            # Extract the actual classifier from the Pipeline
            actual_model = model.named_steps.get("clf", model)
            scaler = model.named_steps.get("scaler")
            X_scaled = scaler.transform(X) if scaler else X
            explainer = shap.LinearExplainer(actual_model, X_scaled)
            shap_vals = explainer.shap_values(X_scaled)
        else:
            actual_model = model
            explainer = shap.TreeExplainer(actual_model)
            shap_vals = explainer.shap_values(X)

        # shap_vals shape: (n_classes, n_samples, n_features) or (n_samples, n_features)
        if isinstance(shap_vals, list):
            # Multi-class: take home_win class (index 2)
            home_shap = shap_vals[2][0] if len(shap_vals) > 2 else shap_vals[0][0]
        else:
            home_shap = shap_vals[0]

        return [float(v) for v in home_shap]
    except Exception as e:
        logger.debug("SHAP computation failed for %s: %s", model_name, e)
        return None


def _feature_importance_explanation(
    fv: FeatureVector,
    shap_vals: Optional[List[float]] = None,
) -> PredictionExplanation:
    """Build a human-readable explanation from feature values.

    If SHAP is available, uses SHAP values as impact scores.
    Otherwise, uses raw feature values normalized by expected range.
    """
    features = fv.features
    names = FEATURE_NAMES

    # Approximate impact: use SHAP if available, else heuristic importance
    if shap_vals and len(shap_vals) == len(names):
        impacts = shap_vals
    else:
        # Heuristic: scale features by approximate importance weights
        importance_weights = np.array([
            0.30,  # elo_diff
            0.15,  # fifa_rank_diff
            0.12,  # xg_diff
            0.08,  # xga_diff
            0.10,  # goals_scored_diff
            0.08,  # goals_conceded_diff
            0.12,  # form_diff
            0.02,  # avg_age_diff
            0.05,  # market_value_diff
            0.08,  # injury_burden_diff
            0.05,  # coach_impact_diff
            0.03,  # squad_chemistry_diff
            0.01,  # travel_distance_km
            0.01,  # rest_days
            0.03,  # tournament_exp_diff
            0.06,  # starting_xi_strength_diff
            0.04,  # bench_strength_diff
            0.05,  # average_starting_xi_rating_diff
            0.04,  # average_squad_rating_diff
            0.05,  # top_5_player_rating_avg_diff
            0.04,  # goalkeeper_rating_diff
            0.04,  # defensive_unit_rating_diff
            0.04,  # midfield_unit_rating_diff
            0.04,  # attacking_unit_rating_diff
            0.05,  # squad_depth_score_diff
            0.05,  # star_player_score_diff
            0.05,  # injury_burden_score_diff
            0.05,  # player_form_score_diff
            0.06,  # player_availability_score_diff
            0.04,  # international_experience_score_diff
            0.03,  # average_caps_diff
            0.03,  # total_international_goals_diff
            0.06,  # weighted_player_strength_diff
        ])
        if len(importance_weights) != len(features):
            importance_weights = np.resize(importance_weights, len(features))
        # Normalize features to [-1, 1] range
        norm_features = np.clip(features / (np.abs(features).max() + 1e-8), -1, 1)
        impacts = (norm_features * importance_weights).tolist()

    display_map = {
        "elo_diff": "Elo Rating Difference",
        "fifa_rank_diff": "FIFA Ranking Difference",
        "xg_diff": "Expected Goals Difference",
        "xga_diff": "Expected Goals Against Difference",
        "goals_scored_diff": "Goals Scored Difference (last 10)",
        "goals_conceded_diff": "Goals Conceded Difference",
        "form_diff": "Recent Form Difference",
        "avg_age_diff": "Average Squad Age Difference",
        "market_value_diff": "Squad Market Value Difference",
        "injury_burden_diff": "Injury Burden Difference",
        "coach_impact_diff": "Coach Impact Difference",
        "squad_chemistry_diff": "Squad Chemistry Difference",
        "travel_distance_km": "Travel Distance (km)",
        "rest_days": "Rest Days",
        "tournament_exp_diff": "World Cup Experience Difference",
        "starting_xi_strength_diff": "Starting XI Strength",
        "bench_strength_diff": "Bench Depth",
        "average_starting_xi_rating_diff": "Average Starting XI Rating",
        "average_squad_rating_diff": "Average Squad Rating",
        "top_5_player_rating_avg_diff": "Top 5 Player Rating",
        "goalkeeper_rating_diff": "Goalkeeper Rating",
        "defensive_unit_rating_diff": "Defensive Unit Rating",
        "midfield_unit_rating_diff": "Midfield Unit Rating",
        "attacking_unit_rating_diff": "Attacking Unit Rating",
        "squad_depth_score_diff": "Squad Depth Score",
        "star_player_score_diff": "Star Player Score",
        "injury_burden_score_diff": "Player Availability From Injuries",
        "player_form_score_diff": "Player Form Score",
        "player_availability_score_diff": "Player Availability Score",
        "international_experience_score_diff": "International Experience",
        "average_caps_diff": "Average International Caps",
        "total_international_goals_diff": "Total International Goals",
        "weighted_player_strength_diff": "Weighted Player Strength",
    }

    factors = []
    for i, name in enumerate(names):
        val = float(features[i])
        imp = float(impacts[i]) if impacts else 0.0
        factors.append(FactorExplanation(
            name=name,
            display_name=display_map.get(name, name),
            value=val,
            impact=imp,
            direction="home" if imp > 0 else ("away" if imp < 0 else "neutral"),
        ))

    factors.sort(key=lambda f: abs(f.impact), reverse=True)
    positive = [f for f in factors if f.impact > 0][:4]
    negative = [f for f in factors if f.impact < 0][:4]

    # Narrative
    home = fv.home_team
    away = fv.away_team
    lines = []
    if positive:
        top = positive[0]
        lines.append(f"{home} is favoured due to {top.display_name} ({top.value:+.1f}).")
    if negative:
        bot = negative[0]
        lines.append(f"{away} benefits from {bot.display_name} ({bot.value:+.1f}).")

    # Check injuries
    inj_idx = names.index("injury_burden_diff")
    inj_val = float(features[inj_idx])
    if inj_val > 0.1:
        lines.append(f"{away} has fewer injury concerns.")
    elif inj_val < -0.1:
        lines.append(f"{home} has fewer injury concerns.")

    narrative = " ".join(lines) if lines else f"Prediction based on {len(names)} match features."

    return PredictionExplanation(
        top_positive=positive,
        top_negative=negative,
        shap_values=shap_vals,
        narrative=narrative,
    )


# ---------------------------------------------------------------------------
# Main hybrid prediction function
# ---------------------------------------------------------------------------

def predict_hybrid(
    home_team: str,
    away_team: str,
    match_date: Optional[date] = None,
    home_overrides: Optional[Dict] = None,
    away_overrides: Optional[Dict] = None,
    include_shap: bool = True,
    best_model_for_shap: str = "xgboost",
) -> HybridPrediction:
    """Generate a full hybrid (statistical + ML + ensemble) prediction.

    Args:
        home_team: Canonical team name
        away_team: Canonical team name
        match_date: Date for feature computation (default today)
        home_overrides: Dict of feature overrides for the home team
        away_overrides: Dict of feature overrides for the away team
        include_shap: Whether to compute SHAP values (slower)
        best_model_for_shap: Which model to use for SHAP
    """
    if match_date is None:
        match_date = date.today()

    # 1. Feature vector
    fv = build_feature_vector(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        home_overrides=home_overrides,
        away_overrides=away_overrides,
    )
    data_snapshot = build_feature_metadata(home_team, away_team, match_date)

    # 2. Statistical prediction
    stat_outcome, home_xg, away_xg = _statistical_prediction(
        home_team, away_team, home_overrides, away_overrides
    )

    # 3. ML predictions
    ml_raw = predict_all_models(fv)
    ml_outcomes: Dict[str, MatchOutcome] = {}
    for model_name, probs in ml_raw.items():
        ml_outcomes[model_name] = _sanitize_outcome(MatchOutcome(
            home_win=probs["home_win"],
            draw=probs["draw"],
            away_win=probs["away_win"],
        ))

    # 4. Ensemble
    weights = _get_model_weights()
    ensemble, weights_used = _compute_ensemble(stat_outcome, ml_outcomes, weights)

    # 5. Confidence score
    confidence, agreement = _compute_confidence(stat_outcome, ml_outcomes)

    # 6. Expected scoreline
    exp_home = round(home_xg)
    exp_away = round(away_xg)
    expected_scoreline = f"{home_team} {exp_home} - {exp_away} {away_team}"

    # 7. SHAP explanation
    shap_vals = None
    if include_shap and ml_raw:
        # Try best_model_for_shap first, fall back to any available
        shap_model = best_model_for_shap if best_model_for_shap in ml_raw else next(iter(ml_raw))
        shap_vals = _compute_shap(shap_model, fv)

    explanation = _feature_importance_explanation(fv, shap_vals)

    return HybridPrediction(
        home_team=home_team,
        away_team=away_team,
        match_date=match_date,
        statistical=stat_outcome,
        ml_predictions=ml_outcomes,
        ensemble=ensemble,
        home_xg=home_xg,
        away_xg=away_xg,
        expected_scoreline=expected_scoreline,
        confidence_score=confidence,
        model_agreement=agreement,
        explanation=explanation,
        model_weights_used=weights_used,
        feature_values_used={
            name: float(fv.features[idx])
            for idx, name in enumerate(FEATURE_NAMES)
        },
        data_snapshot=data_snapshot,
    )


def _compute_ensemble(
    statistical: MatchOutcome,
    ml_outcomes: Dict[str, MatchOutcome],
    weights: Dict[str, float],
) -> tuple[MatchOutcome, Dict[str, float]]:
    """Weighted average of statistical + ML predictions.

    Statistical model gets a fixed 30% weight; the remaining 70% is split
    among ML models proportionally to their ensemble_weight.
    """
    STAT_WEIGHT = 0.30

    statistical = _sanitize_outcome(statistical)
    if not ml_outcomes:
        return statistical, {"statistical": 1.0}

    total_hw = statistical.home_win * STAT_WEIGHT
    total_dw = statistical.draw * STAT_WEIGHT
    total_aw = statistical.away_win * STAT_WEIGHT
    total_w = STAT_WEIGHT
    weights_used: Dict[str, float] = {"statistical": STAT_WEIGHT}

    raw_model_weights = {
        model_name: max(0.0, float(weights.get(model_name, 0.0)))
        for model_name in ml_outcomes
        if np.isfinite(float(weights.get(model_name, 0.0)))
    }
    raw_total = sum(raw_model_weights.values())
    if raw_total <= 0 and ml_outcomes:
        raw_model_weights = {
            model_name: 1.0 / len(ml_outcomes)
            for model_name in ml_outcomes
        }
        raw_total = 1.0

    for model_name, outcome in ml_outcomes.items():
        outcome = _sanitize_outcome(outcome)
        w = (raw_model_weights.get(model_name, 0.0) / raw_total) * (1 - STAT_WEIGHT)
        total_hw += outcome.home_win * w
        total_dw += outcome.draw * w
        total_aw += outcome.away_win * w
        total_w += w
        weights_used[model_name] = w

    if total_w < 1e-8:
        return statistical, {"statistical": 1.0}

    norm = total_hw + total_dw + total_aw
    return _sanitize_outcome(MatchOutcome(
        home_win=total_hw / norm,
        draw=total_dw / norm,
        away_win=total_aw / norm,
    )), weights_used


def _sanitize_outcome(outcome: MatchOutcome) -> MatchOutcome:
    values = np.array(
        [outcome.home_win, outcome.draw, outcome.away_win],
        dtype=float,
    )
    values = np.where(np.isfinite(values), values, 0.0)
    values = np.clip(values, 0.0, 1.0)
    total = float(values.sum())
    if total <= 1e-8:
        values = np.array([1 / 3, 1 / 3, 1 / 3], dtype=float)
    else:
        values = values / total
    return MatchOutcome(
        home_win=float(values[0]),
        draw=float(values[1]),
        away_win=float(values[2]),
    )


def _compute_confidence(
    statistical: MatchOutcome,
    ml_outcomes: Dict[str, MatchOutcome],
) -> tuple[float, float]:
    """Return (confidence_score, model_agreement).

    confidence_score: how decisive the ensemble prediction is (0..1)
    model_agreement: 1 - std dev across model home_win probs (0..1)
    """
    all_hw = [statistical.home_win] + [o.home_win for o in ml_outcomes.values()]
    std = float(np.std(all_hw)) if len(all_hw) > 1 else 0.0
    agreement = max(0.0, 1.0 - std * 3)

    # Decisiveness: how far is the winner probability from a coin flip
    max_prob = max(statistical.home_win, statistical.draw, statistical.away_win)
    confidence = (max_prob - 0.333) / 0.667  # 0 at uniform, 1 at certain
    confidence = max(0.0, min(1.0, confidence))

    return confidence, agreement
