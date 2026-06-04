"""Retrain script — incremental retraining on new data since last training run."""
from __future__ import annotations

import argparse
import logging

logger = logging.getLogger(__name__)


def run_retrain(model_filter: str = "all") -> dict:
    """Retrain models on the full updated dataset.

    Invalidates the model cache after saving.
    """
    from ml.train import run_training
    from ml.predict import invalidate_model_cache

    logger.info("Starting retrain (model_filter=%s)", model_filter)
    results = run_training(model_filter=model_filter, full_refresh=False)
    invalidate_model_cache()
    logger.info("Retrain complete. Trained %d model(s).", len(results))
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description="Retrain WCIP ML models")
    parser.add_argument("--model", default="all")
    args = parser.parse_args()
    run_retrain(model_filter=args.model)
