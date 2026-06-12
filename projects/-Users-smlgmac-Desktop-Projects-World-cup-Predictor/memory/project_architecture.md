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
- ETL: custom pipeline in `etl/` using martj42 CSV + eloratings.net + official FIFA ranking snapshots + football-data.org API

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
- `app/models/ranking.py` — versioned FIFA ranking snapshots and entries
- `app/models/player.py` — player rating import/history tables in addition to Player/Coach
- `etl/load/ranking_loader.py` — historical FIFA ranking snapshot storage
- `etl/monitoring/ranking_monitor.py` — ranking update checks + retraining trigger
- `etl/player_ratings/` — legal CSV player-rating ingestion
- `wcip/data/wc2026.py` — Dynamic WC2026 module (DB-first, official 48-team/group fallback)
- `etl/world_cup_2026/` — Dedicated WC2026 seed ETL for teams, players, and coaches
- `ml/features.py` — 33-feature engineering pipeline (v2, v1-compatible prefix)
- `ml/train.py` — Training: time-series CV, 5 models, model registry + ensemble weights
- `ml/predict.py` — lru_cache model loading + inference per model
- `ml/ensemble.py` — predict_hybrid(): stat 30% + ML 70% + SHAP explanations
- `ml/evaluate.py` — cross-validation + calibration reports
- `ml/retrain.py` — incremental retrain entry point
- `app/api/v1/ml.py` — 8 ML API endpoints
- `app/api/v1/rankings.py` — 4 FIFA ranking snapshot endpoints
- `app/api/v1/world_cup.py` — 7 WC2026 API endpoints
- `app/services/winner_predictions.py` — ranked WC2026 winner prediction service

### Frontend new pages
- `app/wc2026/page.tsx` — WC2026 Dashboard (teams, groups, simulation)
- `app/compare/page.tsx` — Prediction Comparison (statistical vs 5 ML models vs ensemble)
- `app/player-lab/page.tsx` — Player Impact Lab (toggle injuries/suspensions, override form)
- `app/models/page.tsx` — Model Dashboard (metrics, ensemble weights, feature explorer)
- `components/winner-predictions-section.tsx` — ranked winner table and charts reused on dashboard/WC pages

## Database (19 tables)

users, audit_logs, teams (57 rows — +12 after WC2026 migration), elo_history, simulations,
simulation_runs, saved_scenarios, players (placeholder rows until verified import),
coaches (placeholder rows until verified import),
match_results (49,306 local rows observed during audit), match_features, ml_models (5 rows),
qualified_teams (48 rows — official WC2026 field and groups, June 2026),
fifa_ranking_snapshots, fifa_ranking_entries, team_rankings,
ranking_source_logs, player_rating_imports, player_rating_records

## API

- auth (4), teams (4), players (2), matches/scenarios/editions (4), simulations (7)
- ml (8): /predict, /train, /retrain, /models, /features, /feature-names, /explanations, /etl/run
- rankings (4): /fifa/latest, /fifa/snapshots, /fifa/snapshots/{ranking_id}, /fifa/refresh
- world-cup (8): /qualified-teams, /groups, /bracket, /simulate, /2026/winner-predictions, /schedule, /teams/{name}, /players/{name}
- admin (1), health (1)

## Key workflows

1. **Setup**: `init_db()` seeds 2022 teams, official WC2026 teams/groups, and placeholder roster/coach rows on first start
2. **Load history**: `etl.pipeline.run_historical_results()` → 49,306 local matches observed during audit
3. **Load FIFA rankings**: `etl.pipeline.run_fifa_rankings_update(force_refresh=True)` → versioned snapshot tables
4. **Import ratings**: `etl.pipeline.run_player_rating_import('data/external/ea_player_ratings.csv')` → player rating columns/history
5. **Train ML**: `python -m ml.train` → 5 models in `models/`, registered in `ml_models`
6. **Predict**: `POST /api/v1/ml/predict` → statistical + per-model ML + ensemble + SHAP
7. **WC2026 sim**: `POST /api/v1/world-cup/simulate` → Monte Carlo using official groups and placeholder knockout slots
8. **Winner predictions**: `GET /api/v1/world-cup/2026/winner-predictions` → normalized ranked champion probabilities

## WC2026 notes (updated June 2026)

- **48 teams confirmed** with official Group A-L labels
- `/world-cup/groups` returns `draw_complete: true` when the local seed/DB is current
- Simulation uses official groups; R32 bracket slots remain placeholders until fixture pairings are imported
- Removed from stale local data: Italy, Poland, Denmark, Nigeria, Cameroon, Serbia, Venezuela
- Startup roster rows use `data_source="world_cup_2026_placeholder"` until a verified squad/coach snapshot is imported
- Canonical renames: "Czech Republic"→"Czechia", "Bosnia & Herzegovina"→"Bosnia and Herzegovina"
- Migration script: `wcip-backend/scripts/migrate_wc2026_teams.py` (idempotent)

## Bugs fixed during Phase 2 implementation

1. `multi_class="multinomial"` removed from LogisticRegression (sklearn 1.5+ dropped it)
2. ETL loader: added in-run dedup set to handle duplicate CSV rows
3. FastAPI: removed `= Depends()` default from `AdminUser` params (Annotated conflict)
4. CSV parser: explicit NA/empty score check before int() conversion
5. FIFA rank leakage: historical feature generation now uses ranking snapshots
   with `ranking_date <= match_date` or neutral fallback instead of current
   `teams.fifa_rank`

**Why:** Production World Cup prediction platform. ML ensemble gives better-calibrated probabilities than pure Elo/Poisson for upset prediction and international form effects.
