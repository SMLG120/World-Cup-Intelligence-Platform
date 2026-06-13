"""Validate feature vectors used by training and inference."""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ml.features import FEATURE_NAMES, N_FEATURES, build_feature_matrix_from_db, build_feature_vector  # noqa: E402


@dataclass
class FeatureCheck:
    name: str
    status: str
    message: str
    details: dict = field(default_factory=dict)


def validate_features(sample_home: str = "France", sample_away: str = "Brazil") -> dict:
    checks: list[FeatureCheck] = []

    def add(status: str, name: str, message: str, **details) -> None:
        checks.append(FeatureCheck(name=name, status=status, message=message, details=details))

    if len(FEATURE_NAMES) == N_FEATURES and len(set(FEATURE_NAMES)) == len(FEATURE_NAMES):
        add("PASS", "feature_order", "Feature names are unique and match N_FEATURES.", count=N_FEATURES)
    else:
        add("FAIL", "feature_order", "Feature names are duplicated or mismatched.", count=len(FEATURE_NAMES))

    try:
        fv = build_feature_vector(sample_home, sample_away)
        _check_matrix(add, "current_inference_vector", fv.features.reshape(1, -1))
    except Exception as exc:  # noqa: BLE001
        add("FAIL", "current_inference_vector", "Could not build current inference vector.", error=str(exc))

    try:
        X, y, ids = build_feature_matrix_from_db(max_rows=5000)
        if X.size == 0:
            add("WARN", "training_matrix", "No training matrix rows are available.")
        else:
            _check_matrix(add, "training_matrix", X)
            if len(y) == len(X) == len(ids):
                add("PASS", "training_labels", "Training labels align with feature rows.", rows=len(X))
            else:
                add("FAIL", "training_labels", "Training labels do not align with feature rows.", rows=len(X), labels=len(y), ids=len(ids))
    except Exception as exc:  # noqa: BLE001
        add("FAIL", "training_matrix", "Could not build training matrix.", error=str(exc))

    status = "FAIL" if any(check.status == "FAIL" for check in checks) else "PASS"
    return {
        "status": status,
        "feature_count": N_FEATURES,
        "feature_names": FEATURE_NAMES,
        "checks": [check.__dict__ for check in checks],
    }


def _check_matrix(add, name: str, X: np.ndarray) -> None:
    if X.ndim != 2 or X.shape[1] != N_FEATURES:
        add("FAIL", name, "Feature matrix shape mismatch.", shape=list(X.shape), expected_features=N_FEATURES)
        return
    if np.isnan(X).any():
        add("FAIL", name, "Feature matrix contains NaN values.")
        return
    if np.isinf(X).any():
        add("FAIL", name, "Feature matrix contains infinite values.")
        return
    add("PASS", name, "Feature matrix is finite and shape-compatible.", shape=list(X.shape))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WCIP ML feature generation.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--home", default="France")
    parser.add_argument("--away", default="Brazil")
    args = parser.parse_args()

    report = validate_features(sample_home=args.home, sample_away=args.away)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Feature validation: {report['status']}")
        for check in report["checks"]:
            details = f" {json.dumps(check['details'], sort_keys=True)}" if check["details"] else ""
            print(f"[{check['status']}] {check['name']}: {check['message']}{details}")
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
