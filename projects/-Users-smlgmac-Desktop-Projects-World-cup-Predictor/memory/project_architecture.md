---
name: project-architecture
description: Full architecture of the World Cup Intelligence Platform — what's built, where files live, and how systems connect
metadata:
  type: project
---

## Stack

- Backend: FastAPI + SQLAlchemy 2.0 + SQLite (dev) / PostgreSQL (prod), Celery + Redis
- Frontend: Next.js 14 App Router + Tailwind CSS, TypeScript, React Query, Recharts
- ML: scikit-learn 1.9, XGBoost 3.2, LightGBM 4.6, CatBoost 1.2, SHAP 0.52
- ETL: custom pipeline in `etl/` using martj42 CSV + eloratings.net + football-data.org API

## Phase 1 (existing, DO NOT replace)

- `wcip/engine/elo.py` — Elo rating engine (World-Football-Elo variant)
- `wcip/engine/scoreline.py` — Independent Poisson scoreline model
- `wcip/engine/montecarlo.py` — Monte Carlo tournament simulator (parallel, seeded)
- `wcip/data/teams_2022.py` — 2022 WC seed data
- `app/services/prediction.py` — Statistical prediction bridge

## Phase 2 (added June 2025)

### Backend new files
- `app/models/player.py` — Player (25 fields) + Coach (13 fields) SQLAlchemy ORM
- `app/models/match_result.py` — MatchResult, MatchFeatures, MLModelRecord, QualifiedTeam
- `etl/` — Full ETL pipeline (extract/transform/validate/load) + Celery schedulers
- `wcip/data/wc2026.py` — Dynamic WC2026 module (DB-first, 43/48 confirmed, no hardcoded list)
- `ml/features.py` — 17-feature engineering pipeline (v1)
- `ml/train.py` — Training: time-series CV, 5 models, model registry + ensemble weights
- `ml/predict.py` — lru_cache model loading + inference per model
- `ml/ensemble.py` — predict_hybrid(): stat 30% + ML 70% + SHAP explanations
- `ml/evaluate.py` — cross-validation + calibration reports
- `ml/retrain.py` — incremental retrain entry point
- `app/api/v1/ml.py` — 8 ML API endpoints
- `app/api/v1/world_cup.py` — 7 WC2026 API endpoints

### Frontend new pages
- `app/wc2026/page.tsx` — WC2026 Dashboard (teams, groups, simulation)
- `app/compare/page.tsx` — Prediction Comparison (statistical vs 5 ML models vs ensemble)
- `app/player-lab/page.tsx` — Player Impact Lab (toggle injuries/suspensions, override form)
- `app/models/page.tsx` — Model Dashboard (metrics, ensemble weights, feature explorer)

## Database (13 tables)

users, audit_logs, teams (57 rows — +12 after WC2026 migration), elo_history, simulations,
simulation_runs, saved_scenarios, players (0 — needs API key), coaches (0 — needs API key),
match_results (49,304 rows), match_features, ml_models (5 rows),
qualified_teams (52 rows — finalized WC2026 field, June 2026)

## API (35 total endpoints)

- auth (4), teams (4), matches/scenarios/editions (4), simulations (7)
- ml (8): /predict, /train, /retrain, /models, /features, /feature-names, /explanations, /etl/run
- world-cup (7): /qualified-teams, /groups, /bracket, /simulate, /schedule, /teams/{name}, /players/{name}
- admin (1), health (1)

## Key workflows

1. **Setup**: `init_db()` seeds 2022 teams + 43 WC2026 qualified teams on first start
2. **Load history**: `etl.pipeline.run_historical_results()` → 49,304 matches in DB
3. **Train ML**: `python -m ml.train` → 5 models in `models/`, registered in `ml_models`
4. **Predict**: `POST /api/v1/ml/predict` → statistical + per-model ML + ensemble + SHAP
5. **WC2026 sim**: `POST /api/v1/world-cup/simulate` → Monte Carlo (provisional groups until draw)

## WC2026 notes (updated June 2026)

- **52 teams confirmed** (finalized field; Italy/Poland/Denmark did not qualify)
- Group draw not yet held → `/world-cup/groups` returns `draw_complete: false`
- Simulation uses provisional Elo-seeded groups until official `group_label` values populated
- Removed: Italy, Poland, Denmark
- Added: Iraq (AFC); Algeria, Cape Verde, DR Congo (CAF); Curaçao, Haiti, Panama (CONCACAF);
         Paraguay (CONMEBOL); Bosnia and Herzegovina, Czechia, Norway, Sweden (UEFA)
- Canonical renames: "Czech Republic"→"Czechia", "Bosnia & Herzegovina"→"Bosnia and Herzegovina"
- Migration script: `wcip-backend/scripts/migrate_wc2026_teams.py` (idempotent)

## Bugs fixed during Phase 2 implementation

1. `multi_class="multinomial"` removed from LogisticRegression (sklearn 1.5+ dropped it)
2. ETL loader: added in-run dedup set to handle duplicate CSV rows
3. FastAPI: removed `= Depends()` default from `AdminUser` params (Annotated conflict)
4. CSV parser: explicit NA/empty score check before int() conversion

**Why:** Production World Cup prediction platform. ML ensemble gives better-calibrated probabilities than pure Elo/Poisson for upset prediction and international form effects.
