---
name: ml-model-registry
description: Trained ML models, CV metrics, ensemble weights, feature version, and retraining notes
metadata:
  type: project
---

## Trained Models (version: v20260604)

All trained on 25,243 samples (2000-01-01 to 2026-06-04), 17 features (v1).
Time-series 5-fold expanding-window CV. Three-class: 0=away win, 1=draw, 2=home win.

| Model | Accuracy | F1 macro | Brier | Log-Loss | Ensemble Weight |
|-------|----------|----------|-------|----------|-----------------|
| catboost | 57.92% | 0.5007 | 0.181 | 0.9196 | 20.11% |
| random_forest | 57.85% | 0.4970 | 0.181 | 0.9221 | 20.06% |
| logistic | 57.68% | 0.4954 | 0.182 | 0.9229 | 20.04% |
| xgboost | 57.23% | 0.5021 | 0.183 | 0.9282 | 19.92% |
| lightgbm | 57.29% | 0.5037 | 0.183 | 0.9306 | 19.87% |

## Ensemble Formula

`ensemble = 0.30 × statistical + 0.70 × Σ(w_i × ML_i)`

Weights from `ml_models.ensemble_weight` in DB; auto-normalised to sum to 1.

## Feature Version v1 (17 features)

elo_diff, fifa_rank_diff, xg_diff, xga_diff, goals_scored_diff, goals_conceded_diff,
form_diff, avg_age_diff, market_value_diff, injury_burden_diff, coach_impact_diff,
squad_chemistry_diff, travel_distance_km, rest_days, tournament_exp_diff,
starting_xi_strength_diff, bench_strength_diff

Note: features 7–16 default to 0 when player/coach tables are empty.

## Model Files

`wcip-backend/models/logistic.pkl`, `random_forest.pkl`, `xgboost.pkl`, `lightgbm.pkl`, `catboost.pkl`

## Known Fix Applied

`multi_class="multinomial"` removed from LogisticRegression (dropped in sklearn 1.5+).
Current installed: sklearn 1.9.0, xgboost 3.2.0, lightgbm 4.6.0, catboost 1.2.10, shap 0.52.0.

## FIFA Ranking Audit Note

The active `v20260604` models predate the versioned FIFA ranking snapshot
pipeline and point-in-time ranking lookup. During the June 2026 audit, the local
DB had Brazil as FIFA rank #1 while the official FIFA men's ranking publication
showed France #1 and Brazil #6. Treat these models as the current baseline, but
retrain after:

- loading the latest official FIFA ranking snapshot
- backfilling historical FIFA ranking snapshots where possible
- backfilling Elo history where possible

The leakage guardrail now uses historical ranking snapshots with
`ranking_date <= match_date`; missing historical periods use neutral ranking
values instead of current ranks.

## Retraining

```bash
python -m ml.train --model all          # incremental
python -m ml.train --model all --full-refresh  # all history
```

Or admin API: `POST /api/v1/ml/retrain {"model": "all"}`
Ranking monitor trigger:
`check_fifa_ranking_update(force_refresh=True, trigger_retraining=True)`

**Why:** These are the production models. Weights are live in DB. If re-asked about model metrics, verify against DB rather than trusting this memory snapshot.
**How to apply:** When helping with prediction accuracy questions or ensemble configuration, use these as the baseline metrics.
