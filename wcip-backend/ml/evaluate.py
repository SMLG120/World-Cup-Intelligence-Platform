"""Model evaluation and cross-validation utilities."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

logger = logging.getLogger(__name__)


def cross_validate_model(
    name: str,
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    n_splits: int = 5,
) -> Dict[str, Any]:
    """Full cross-validation report for a model.

    Returns per-fold metrics plus mean and std.
    """
    from ml.train import evaluate_model, time_series_cv_split

    splits = time_series_cv_split(X, n_splits=n_splits)
    if not splits:
        return {"error": "insufficient data for cross-validation"}

    fold_results: List[Dict[str, float]] = []
    for i, (train_idx, test_idx) in enumerate(splits):
        # Clone to avoid cross-contamination between folds
        import pickle
        model_copy = pickle.loads(pickle.dumps(model))
        model_copy.fit(X[train_idx], y[train_idx])
        metrics = evaluate_model(model_copy, X[train_idx], y[train_idx], X[test_idx], y[test_idx])
        fold_results.append(metrics)
        logger.info("[%s] fold %d acc=%.3f f1=%.3f", name, i, metrics["accuracy"], metrics["f1_score"])

    # Aggregate
    keys = fold_results[0].keys()
    summary: Dict[str, Any] = {
        "model": name,
        "n_folds": len(fold_results),
        "per_fold": fold_results,
    }
    for k in keys:
        vals = [m[k] for m in fold_results]
        summary[f"{k}_mean"] = float(np.mean(vals))
        summary[f"{k}_std"] = float(np.std(vals))

    return summary


def compare_models(X: np.ndarray, y: np.ndarray) -> List[Dict[str, Any]]:
    """Compare all active models on the provided dataset."""
    from ml.predict import load_all_models
    models = load_all_models()

    results = []
    for name, model in models.items():
        report = cross_validate_model(name, model, X, y)
        results.append(report)

    # Sort by brier_score_mean (lower = better)
    results.sort(key=lambda r: r.get("brier_score_mean", 999))
    return results


def calibration_report(model: Any, X_test: np.ndarray, y_test: np.ndarray) -> Dict[str, Any]:
    """Generate a calibration report showing reliability diagram data."""
    from sklearn.calibration import calibration_curve

    y_prob = model.predict_proba(X_test)
    classes = ["away_win", "draw", "home_win"]
    curves = {}
    for c_idx, c_name in enumerate(classes):
        y_binary = (y_test == c_idx).astype(int)
        prob_true, prob_pred = calibration_curve(y_binary, y_prob[:, c_idx], n_bins=10)
        curves[c_name] = {
            "prob_true": prob_true.tolist(),
            "prob_pred": prob_pred.tolist(),
        }
    return {"calibration_curves": curves}
