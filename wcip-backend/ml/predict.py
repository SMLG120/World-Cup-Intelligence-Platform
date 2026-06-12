"""ML prediction layer.

Loads trained model(s) and generates match outcome probabilities.
All models return P(home_win), P(draw), P(away_win).
"""
from __future__ import annotations

import logging
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np

from ml.features import FEATURE_NAMES, FeatureVector

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parents[1] / "models"

MODEL_FILES = {
    "logistic": "logistic.pkl",
    "random_forest": "random_forest.pkl",
    "xgboost": "xgboost.pkl",
    "lightgbm": "lightgbm.pkl",
    "catboost": "catboost.pkl",
}


@lru_cache(maxsize=None)
def _load_model(name: str) -> Optional[Any]:
    path = MODELS_DIR / MODEL_FILES.get(name, f"{name}.pkl")
    if not path.exists():
        logger.debug("Model file not found: %s", path)
        return None
    try:
        with open(path, "rb") as f:
            model = pickle.load(f)
        logger.info("Loaded model %s from %s", name, path)
        return model
    except Exception as e:
        logger.error("Failed to load model %s: %s", name, e)
        return None


def load_all_models() -> Dict[str, Any]:
    """Return all available (trained) models as {name: model}."""
    models = {}
    for name in MODEL_FILES:
        m = _load_model(name)
        if m is not None:
            models[name] = m
    return models


def invalidate_model_cache() -> None:
    _load_model.cache_clear()


def _model_feature_count(model: Any) -> int | None:
    count = getattr(model, "n_features_in_", None)
    if count is not None:
        return int(count)
    named_steps = getattr(model, "named_steps", None)
    if named_steps:
        for step in reversed(list(named_steps.values())):
            count = getattr(step, "n_features_in_", None)
            if count is not None:
                return int(count)
    return None


def _features_for_model(model: Any, fv: FeatureVector) -> np.ndarray:
    X = fv.features.reshape(1, -1)
    expected = _model_feature_count(model)
    if expected is None or expected == X.shape[1]:
        return X
    if expected < X.shape[1]:
        logger.warning(
            "Model expects %s features but feature vector has %s; using leading features for compatibility",
            expected,
            X.shape[1],
        )
        return X[:, :expected]
    logger.warning(
        "Model expects %s features but feature vector has %s; padding with zeros",
        expected,
        X.shape[1],
    )
    padded = np.zeros((1, expected), dtype=X.dtype)
    padded[:, :X.shape[1]] = X
    return padded


def predict_with_model(name: str, fv: FeatureVector) -> Optional[Dict[str, float]]:
    """Predict outcome probabilities from a single model.

    Returns {home_win, draw, away_win} or None if model unavailable.
    """
    model = _load_model(name)
    if model is None:
        return None

    X = _features_for_model(model, fv)
    try:
        proba = model.predict_proba(X)[0]
        # Classes: 0=away_win, 1=draw, 2=home_win
        return {
            "home_win": float(proba[2]),
            "draw": float(proba[1]),
            "away_win": float(proba[0]),
        }
    except Exception as e:
        logger.error("Prediction failed for model %s: %s", name, e)
        return None


def predict_all_models(fv: FeatureVector) -> Dict[str, Dict[str, float]]:
    """Run all loaded models on a feature vector.

    Returns {model_name: {home_win, draw, away_win}}.
    """
    results = {}
    for name in MODEL_FILES:
        pred = predict_with_model(name, fv)
        if pred is not None:
            results[name] = pred
    return results
