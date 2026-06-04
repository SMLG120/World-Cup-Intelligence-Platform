---
name: project-architecture
description: Full architecture of the World Cup Intelligence Platform — what's built, where files live, and how systems connect
metadata:
  type: project
---

## Stack
- Backend: FastAPI + SQLAlchemy + SQLite (dev) / PostgreSQL (prod), Celery workers
- Frontend: Next.js 14 App Router + Tailwind, TypeScript
- ML: scikit-learn, XGBoost, LightGBM, CatBoost, SHAP
- ETL: custom pipeline in `etl/` using martj42 international_results CSV + eloratings.net

## Phase 1 (existing, DO NOT replace)
- `wcip/engine/elo.py` — Elo rating engine
- `wcip/engine/scoreline.py` — Poisson scoreline model
- `wcip/engine/montecarlo.py` — Monte Carlo tournament simulator
- `wcip/data/teams_2022.py` — 2022 WC seed data
- `app/services/prediction.py` — Statistical prediction bridge

## Phase 2 (added in June 2025)
### Backend new files
- `app/models/player.py` — Player + Coach SQLAlchemy models
- `app/models/match_result.py` — MatchResult, MatchFeatures, MLModelRecord, QualifiedTeam models
- `etl/` — Full ETL pipeline: extract (football-data.org, int'l results CSV, elo ratings), transform (name normalization), load (upsert), validation, Celery schedulers
- `wcip/data/wc2026.py` — Dynamic WC2026 module (loads from DB, no hardcoded 48 teams)
- `ml/features.py` — 17-feature engineering pipeline (elo_diff, form, xG, injury_burden, coach_impact, etc.)
- `ml/train.py` — Training pipeline for 5 models (logistic, RF, XGBoost, LightGBM, CatBoost) with time-series CV
- `ml/predict.py` — Model loading + inference
- `ml/ensemble.py` — Hybrid prediction (statistical 30% + ML 70%), weighted by validation log-loss; SHAP explainability
- `ml/evaluate.py` — Cross-validation + calibration reports
- `ml/retrain.py` — Incremental retrain script
- `app/api/v1/ml.py` — ML API endpoints (/ml/predict, /ml/train, /ml/retrain, /ml/models, /ml/features, /ml/explanations)
- `app/api/v1/world_cup.py` — WC2026 endpoints (/world-cup/qualified-teams, /groups, /bracket, /simulate, /schedule, /teams/{name}, /players/{name})

### Frontend new pages
- `app/wc2026/page.tsx` — WC2026 Dashboard (teams, groups, simulation)
- `app/compare/page.tsx` — Prediction Comparison (statistical vs ML vs ensemble, side-by-side)
- `app/player-lab/page.tsx` — Player Impact Lab (modify injuries/suspensions/form, see recomputed predictions)
- `app/models/page.tsx` — Model Dashboard (metrics, ensemble weights, feature vector explorer)

## Key workflows
1. **First run**: `init_db()` seeds 2022 teams + 43 WC2026 qualified teams
2. **Load history**: `etl.pipeline.run_historical_results()` → loads 49K+ international matches
3. **Train ML**: `python -m ml.train` → trains 5 models, persists to `models/`, registers in `ml_models` table
4. **Predict**: `POST /api/v1/ml/predict` → returns statistical + per-model ML + ensemble probabilities + SHAP narrative
5. **WC2026 sim**: `POST /api/v1/world-cup/simulate` → Monte Carlo over qualified teams (provisional groups until draw)

## WC2026 notes
- 43/48 teams confirmed as of June 2025 (5 slots via playoff still TBD)
- Group draw not yet held → `/world-cup/groups` returns `draw_complete: false`
- Simulation uses provisional Elo-seeded groups until official draw

**Why:** This is a production World Cup prediction platform. The ML models give better-calibrated probabilities than pure Elo/Poisson, especially for upsets and international form effects.
