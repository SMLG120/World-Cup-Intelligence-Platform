"""Out-of-sample evaluation of the live prediction pipeline.

Scores the exact probabilities ``POST /api/v1/match/predict`` returns on
matches played *after* a cutoff (default: the date the shipped model artifacts
were trained), with features built as of each match date. Compares the
pipeline with and without selected models so ensemble changes are evaluated
before they ship.

    python -m scripts.evaluate_holdout --since 2026-06-25 --out report.json

Metrics: multi-class log loss, Brier score (sum over 3 outcomes), accuracy,
expected calibration error (top-class, 10 bins). Lower is better except
accuracy.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402

OUTCOMES = ("home_win", "draw", "away_win")
EPS = 1e-12


def _actual(home_goals: int, away_goals: int) -> str:
    if home_goals > away_goals:
        return "home_win"
    if home_goals < away_goals:
        return "away_win"
    return "draw"


def score(rows: list[tuple[dict[str, float], str]]) -> dict[str, float]:
    n = len(rows)
    if not n:
        return {"n": 0}
    log_loss = brier = correct = 0.0
    bins = [[0, 0.0, 0.0] for _ in range(10)]
    for probs, actual in rows:
        total = sum(probs[o] for o in OUTCOMES) or 1.0
        p = {o: probs[o] / total for o in OUTCOMES}
        log_loss -= math.log(max(p[actual], EPS))
        brier += sum((p[o] - (1.0 if o == actual else 0.0)) ** 2 for o in OUTCOMES)
        top = max(OUTCOMES, key=lambda o: p[o])
        hit = top == actual
        correct += hit
        b = bins[min(int(p[top] * 10), 9)]
        b[0] += 1
        b[1] += p[top]
        b[2] += hit
    ece = sum(abs(b[1] / b[0] - b[2] / b[0]) * b[0] / n for b in bins if b[0])
    return {
        "n": n,
        "log_loss": round(log_loss / n, 4),
        "brier": round(brier / n, 4),
        "accuracy": round(correct / n, 4),
        "ece": round(ece, 4),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", default="2026-06-25", help="first match date (exclusive of training data)")
    parser.add_argument("--until", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()
    logging.disable(logging.WARNING)

    import ml.predict as mp
    from app.db.base import SessionLocal
    from app.models.match_result import MatchResult
    from app.services.head_to_head_prediction import predict_head_to_head

    since = date.fromisoformat(args.since)
    until = date.fromisoformat(args.until) if args.until else date.today()
    with SessionLocal() as db:
        matches = db.execute(
            select(
                MatchResult.home_team, MatchResult.away_team, MatchResult.match_date,
                MatchResult.home_goals, MatchResult.away_goals,
            )
            .where(MatchResult.match_date >= since, MatchResult.match_date <= until)
            .order_by(MatchResult.match_date)
        ).all()
        train_rows = db.execute(
            select(MatchResult.home_goals, MatchResult.away_goals).where(MatchResult.match_date < since)
        ).all()

    # Base-rate baseline: outcome frequencies from data before the holdout.
    counts = {o: 0 for o in OUTCOMES}
    for hg, ag in train_rows:
        counts[_actual(hg, ag)] += 1
    base = {o: counts[o] / max(len(train_rows), 1) for o in OUTCOMES}

    all_models = dict(mp.MODEL_FILES)
    variants = {
        "pipeline_without_catboost (current prod)": {k: v for k, v in all_models.items() if k != "catboost"},
        "pipeline_with_catboost (fixed)": all_models,
    }
    results: dict[str, list] = {name: [] for name in variants}
    # Components of the user-facing blend (elo, fifa, player_strength,
    # statistical, ml) as returned in method_breakdown.
    per_model: dict[str, list] = {}
    baseline_rows = []
    failures = 0
    started = time.perf_counter()

    for home, away, match_date, hg, ag in matches:
        actual = _actual(hg, ag)
        baseline_rows.append((base, actual))
        for name, model_files in variants.items():
            mp.MODEL_FILES = model_files
            try:
                pred = predict_head_to_head(home, away, match_date=match_date)
            except Exception:  # noqa: BLE001
                failures += 1
                continue
            results[name].append((pred["probabilities"], actual))
            if model_files is all_models:
                for component, probs in (pred.get("method_breakdown") or {}).items():
                    per_model.setdefault(component, []).append((probs, actual))
    mp.MODEL_FILES = all_models

    report = {
        "holdout": {"since": str(since), "until": str(until), "matches": len(matches)},
        "seconds": round(time.perf_counter() - started, 1),
        "failures": failures,
        "base_rate": {k: round(v, 4) for k, v in base.items()},
        "baseline_base_rate": score(baseline_rows),
        "variants": {name: score(rows) for name, rows in results.items()},
        "components_with_catboost": {name: score(rows) for name, rows in per_model.items() if rows},
    }
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
