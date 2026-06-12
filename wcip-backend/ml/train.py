"""ML training pipeline.

Trains 5 models on historical international match data.
Uses time-series aware cross-validation to prevent data leakage.

Usage:
    python -m ml.train [--full-refresh] [--model logistic|rf|xgb|lgbm|catboost|all]
"""
from __future__ import annotations

import argparse
import logging
import os
import pickle
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parents[1] / "models"
MODELS_DIR.mkdir(exist_ok=True)

# Minimum training samples required
MIN_SAMPLES = 200


def _import_models() -> Dict[str, Any]:
    """Import all ML estimators (lazy import to avoid slow startup)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    models: Dict[str, Any] = {
        "logistic": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(
                max_iter=1000,
                C=1.0,
                solver="lbfgs",
                random_state=42,
            )),
        ]),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            max_depth=8,
            min_samples_leaf=10,
            n_jobs=-1,
            random_state=42,
        ),
    }

    try:
        from xgboost import XGBClassifier
        models["xgboost"] = XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            use_label_encoder=False,
            eval_metric="mlogloss",
            random_state=42,
            n_jobs=-1,
        )
    except ImportError:
        logger.warning("xgboost not installed; skipping XGBClassifier")

    try:
        import lightgbm as lgb
        models["lightgbm"] = lgb.LGBMClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1,
        )
    except ImportError:
        logger.warning("lightgbm not installed; skipping LGBMClassifier")

    try:
        from catboost import CatBoostClassifier
        models["catboost"] = CatBoostClassifier(
            iterations=300,
            depth=5,
            learning_rate=0.05,
            random_seed=42,
            verbose=0,
        )
    except ImportError:
        logger.warning("catboost not installed; skipping CatBoostClassifier")

    return models


def load_training_data(full_refresh: bool = False) -> Tuple[np.ndarray, np.ndarray, List]:
    """Load feature matrix and labels from DB."""
    from ml.features import build_feature_matrix_from_db

    # Only use matches from 2000+ for cleaner features
    since = date(2000, 1, 1)
    logger.info("Building feature matrix since %s...", since)
    X, y, ids = build_feature_matrix_from_db(since_date=since, max_rows=60_000)
    logger.info("Dataset: %d samples, %d features", len(X), X.shape[1] if len(X) else 0)
    return X, y, ids


def time_series_cv_split(
    X: np.ndarray,
    n_splits: int = 5,
    test_size: float = 0.1,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """Expanding window time-series cross-validation splits.

    Data must be chronologically ordered (already guaranteed by build_feature_matrix_from_db).
    Each fold expands the training window and uses a fixed-size test window.
    """
    n = len(X)
    test_n = max(1, int(n * test_size))
    splits = []
    for i in range(n_splits):
        # Test window slides forward
        test_end = n - (n_splits - 1 - i) * test_n
        test_start = test_end - test_n
        if test_start <= MIN_SAMPLES:
            continue
        train_idx = np.arange(0, test_start)
        test_idx = np.arange(test_start, test_end)
        splits.append((train_idx, test_idx))
    return splits


def evaluate_model(
    model: Any,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
) -> Dict[str, float]:
    """Compute all evaluation metrics for a fitted model."""
    from sklearn.metrics import accuracy_score, brier_score_loss, f1_score, log_loss

    y_pred = model.predict(X_test)
    y_prob = model.predict_proba(X_test)

    acc = accuracy_score(y_test, y_pred)
    f1 = f1_score(y_test, y_pred, average="weighted")

    # Brier score (multi-class: mean over classes)
    brier = 0.0
    for c in range(3):
        y_binary = (y_test == c).astype(int)
        brier += brier_score_loss(y_binary, y_prob[:, c])
    brier /= 3.0

    ll = log_loss(y_test, y_prob)

    # Calibration (expected calibration error approximation)
    ece = _expected_calibration_error(y_test, y_prob)

    return {
        "accuracy": float(acc),
        "f1_score": float(f1),
        "brier_score": float(brier),
        "log_loss": float(ll),
        "calibration_score": float(1 - ece),  # higher = better calibrated
    }


def _expected_calibration_error(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    """Simplified ECE for multi-class (mean over classes)."""
    ece = 0.0
    for c in range(y_prob.shape[1]):
        probs = y_prob[:, c]
        labels = (y_true == c).astype(float)
        bins = np.linspace(0, 1, n_bins + 1)
        total = 0.0
        for b in range(n_bins):
            mask = (probs >= bins[b]) & (probs < bins[b + 1])
            if mask.sum() == 0:
                continue
            total += mask.sum() * abs(labels[mask].mean() - probs[mask].mean())
        ece += total / len(y_true)
    return ece / y_prob.shape[1]


def train_model(
    name: str,
    model: Any,
    X: np.ndarray,
    y: np.ndarray,
    version: str = "latest",
) -> Tuple[Any, Dict[str, float]]:
    """Train a single model with time-series CV and return (fitted_model, metrics)."""
    if len(X) < MIN_SAMPLES:
        logger.warning("Insufficient training data (%d < %d). Skipping %s.", len(X), MIN_SAMPLES, name)
        return model, {}

    splits = time_series_cv_split(X)
    if not splits:
        logger.warning("No valid CV splits for %s; falling back to 80/20 split.", name)
        split_at = int(0.8 * len(X))
        splits = [(np.arange(split_at), np.arange(split_at, len(X)))]

    cv_metrics: List[Dict[str, float]] = []
    for fold, (train_idx, test_idx) in enumerate(splits):
        model.fit(X[train_idx], y[train_idx])
        fold_metrics = evaluate_model(model, X[train_idx], y[train_idx], X[test_idx], y[test_idx])
        cv_metrics.append(fold_metrics)
        logger.info("  Fold %d: acc=%.3f f1=%.3f bs=%.3f ll=%.3f",
                    fold, fold_metrics["accuracy"], fold_metrics["f1_score"],
                    fold_metrics["brier_score"], fold_metrics["log_loss"])

    # Final fit on all data
    model.fit(X, y)

    # Average CV metrics
    avg_metrics: Dict[str, float] = {}
    for k in cv_metrics[0]:
        avg_metrics[k] = float(np.mean([m[k] for m in cv_metrics]))

    avg_metrics["training_samples"] = len(X)
    logger.info("Model %s trained. Avg acc=%.3f, f1=%.3f, brier=%.3f, ll=%.3f",
                name, avg_metrics["accuracy"], avg_metrics["f1_score"],
                avg_metrics["brier_score"], avg_metrics["log_loss"])
    return model, avg_metrics


def save_model(name: str, model: Any, version: str = "latest") -> Path:
    path = MODELS_DIR / f"{name}.pkl"
    with open(path, "wb") as f:
        pickle.dump(model, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Saved model %s -> %s", name, path)
    return path


def register_model(
    name: str,
    version: str,
    file_path: Path,
    metrics: Dict[str, float],
    feature_version: str | None = None,
) -> None:
    """Record model metadata in the database."""
    try:
        from ml.features import FEATURE_VERSION
        from app.db.base import SessionLocal
        from app.models.match_result import MLModelRecord
        from sqlalchemy import select

        db = SessionLocal()
        try:
            existing = db.scalar(
                select(MLModelRecord).where(
                    MLModelRecord.model_name == name,
                    MLModelRecord.version == version,
                )
            )
            if existing:
                record = existing
            else:
                record = MLModelRecord(model_name=name, version=version)
                db.add(record)

            record.file_path = str(file_path)
            record.accuracy = metrics.get("accuracy")
            record.f1_score = metrics.get("f1_score")
            record.brier_score = metrics.get("brier_score")
            record.log_loss = metrics.get("log_loss")
            record.calibration_score = metrics.get("calibration_score")
            record.training_samples = int(metrics.get("training_samples", 0))
            record.feature_version = feature_version or FEATURE_VERSION
            record.is_active = True

            # Auto-calibrate ensemble weight from inverse log-loss
            ll = metrics.get("log_loss", 1.1)
            record.ensemble_weight = max(0.1, 1.0 / max(ll, 0.01))

            db.commit()
            logger.info("Registered model %s v%s in DB", name, version)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not register model in DB: %s", e)


def run_training(model_filter: str = "all", full_refresh: bool = False) -> Dict[str, Dict]:
    """Main training entry point. Returns {model_name: metrics}."""
    logging.basicConfig(level=logging.INFO)
    X, y, _ = load_training_data(full_refresh=full_refresh)

    if len(X) < MIN_SAMPLES:
        logger.error("Not enough training data (%d samples). Run ETL first.", len(X))
        return {}

    all_models = _import_models()
    to_train = (
        all_models
        if model_filter == "all"
        else {k: v for k, v in all_models.items() if k == model_filter}
    )

    results: Dict[str, Dict] = {}
    version = date.today().strftime("%Y%m%d")

    for name, model in to_train.items():
        logger.info("Training: %s", name)
        fitted, metrics = train_model(name, model, X, y, version=version)
        if metrics:
            path = save_model(name, fitted, version=version)
            register_model(name, version, path, metrics)
            results[name] = metrics

    # Compute ensemble weights (normalized inverse log-loss)
    if results:
        _update_ensemble_weights(results)

    return results


def _update_ensemble_weights(results: Dict[str, Dict]) -> None:
    """Normalize ensemble weights so they sum to 1.0."""
    try:
        from app.db.base import SessionLocal
        from app.models.match_result import MLModelRecord
        from sqlalchemy import select

        db = SessionLocal()
        try:
            records = db.scalars(
                select(MLModelRecord).where(MLModelRecord.is_active == True)
            ).all()

            total_weight = sum(r.ensemble_weight for r in records)
            if total_weight > 0:
                for r in records:
                    r.ensemble_weight = r.ensemble_weight / total_weight
            db.commit()
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not update ensemble weights: %s", e)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train WCIP ML models")
    parser.add_argument("--model", default="all",
                        choices=["all", "logistic", "random_forest", "xgboost", "lightgbm", "catboost"])
    parser.add_argument("--full-refresh", action="store_true")
    args = parser.parse_args()

    results = run_training(model_filter=args.model, full_refresh=args.full_refresh)
    for name, metrics in results.items():
        print(f"\n{name}:")
        for k, v in metrics.items():
            print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")
