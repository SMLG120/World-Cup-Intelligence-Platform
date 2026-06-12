# World Cup Intelligence Platform — Repository Checklist

Status legend: ✅ Complete · 🔄 In Progress · 📋 Planned

---

## Data Layer

### ETL Infrastructure
- ✅ `etl/pipeline.py` — orchestrator with ETL state file for incremental runs
- ✅ `etl/extract/international_results.py` — martj42 CSV download + caching + parse (49K rows)
- ✅ `etl/extract/elo_ratings.py` — eloratings.net TSV fetch + embedded fallback snapshot
- ✅ `etl/extract/football_data.py` — football-data.org API client (rate-limited 6.5s)
- ✅ `etl/extract/fifa_rankings.py` — official FIFA ranking snapshot fetch + validation
- ✅ `etl/load/ranking_loader.py` — historical ranking snapshot loader
- ✅ `etl/monitoring/ranking_monitor.py` — ranking change detection + retraining trigger
- ✅ `etl/transform/normalize.py` — canonical name normalization (60+ variant spellings)
- ✅ `etl/validation/schema.py` — ValidatedMatch dataclass, business-rule checks
- ✅ `etl/load/db_loader.py` — idempotent upsert loaders (batch 500, in-run dedup)
- ✅ `etl/schedulers/celery_tasks.py` — daily results, weekly Elo, daily FIFA ranking Celery tasks

### Database Tables (19 total)
- ✅ `users` — accounts, roles, refresh tokens
- ✅ `audit_logs` — admin audit trail
- ✅ `teams` — team metadata, Elo, FIFA rank, confederation
- ✅ `elo_history` — Elo rating timeseries per team
- ✅ `simulations` — saved tournament simulation records
- ✅ `simulation_runs` — per-run results (async Celery runs)
- ✅ `saved_scenarios` — user-saved scenario configurations
- ✅ `players` — 25-field squad data (xG, xGA, injuries, caps, fitness)
- ✅ `coaches` — formation, win%, tournament experience, impact score
- ✅ `match_results` — 49,306 local historical international match rows (1872–2026)
- ✅ `match_features` — pre-computed 17-feature vectors
- ✅ `ml_models` — model registry with metrics + ensemble weights
- ✅ `qualified_teams` — WC2026 qualification tracker (48/48, official groups loaded)
- ✅ `fifa_ranking_snapshots` — immutable FIFA ranking publications
- ✅ `fifa_ranking_entries` — team ranks, points, and movement per snapshot
- ✅ `team_rankings` — provider-agnostic ranking records per snapshot
- ✅ `ranking_source_logs` — ranking fetch/load audit trail
- ✅ `player_rating_imports` — legal-source rating import batches
- ✅ `player_rating_records` — historical player-rating rows per import

### Data Quality
- ✅ Unique constraint on (home_team, away_team, match_date) — duplicates rejected at DB level
- ✅ NA/empty score filtering — scheduled/future matches skipped
- ✅ Team name normalization — 60+ variants mapped to canonical names
- ✅ Incremental ETL with 7-day overlap window to catch late corrections
- ✅ WC2026 validation script for official teams, groups, roster placeholders,
  coaches, prediction readiness, and tournament placement
- ✅ FIFA ranking versioning / snapshot tagging
- ✅ Ranking source logging for fetch/load traceability
- ✅ Legal CSV player-rating import with validation and versioning
- 📋 Historical FIFA ranking backfill before first snapshot ingestion date
- 📋 Broader data versioning for non-ranking external sources
- 📋 StatsBomb Open Data integration (xG, shot-level data)

---

## ML Layer

### Feature Store
- ✅ `ml/features.py` — 33-feature engineering pipeline (v2; v1-compatible prefix)
- ✅ All features as (home − away) differentials for sign-consistent interpretation
- ✅ `build_feature_vector()` — real-time feature computation for any match
- ✅ `build_feature_matrix_from_db()` — batch matrix for training (25K+ samples from 2000+)
- ✅ `persist_features()` — saves computed vector to `match_features` table
- ✅ Point-in-time FIFA ranking lookup prevents current-rank leakage into historical rows
- ✅ Point-in-time Elo lookup uses `elo_history` or neutral fallback for historical rows
- ✅ Player rating, unit strength, squad depth, form, availability, caps, goals, and weighted player-strength features

### Models
- ✅ Logistic Regression — Pipeline(StandardScaler + LogisticRegression); acc 57.68%, ll 0.923
- ✅ Random Forest — 300 trees, max_depth 8; acc 57.85%, ll 0.922
- ✅ XGBoost — 300 estimators, multi-class softprob; acc 57.23%, ll 0.928
- ✅ LightGBM — 300 estimators, multiclass; acc 57.29%, ll 0.931
- ✅ CatBoost — 300 iterations, MultiClass; acc 57.92%, ll 0.920

### Training Infrastructure
- ✅ `ml/train.py` — time-series CV (5-fold expanding window), model registry
- ✅ `ml/evaluate.py` — cross-validation + calibration reports
- ✅ `ml/predict.py` — `lru_cache` model loading, per-model inference
- ✅ `ml/retrain.py` — incremental retrain + cache invalidation
- ✅ Model versioning (`v{YYYYMMDD}`) + `is_active` flag in registry
- ✅ Ensemble weight auto-update on each retrain (inverse log-loss, normalised)

### Ensemble Engine
- ✅ `ml/ensemble.py` — 30% statistical + 70% ML (DB-weighted)
- ✅ Graceful fallback to statistical-only when no models are trained
- ✅ `HybridPrediction` dataclass with `to_dict()` serialization

### SHAP Explainability
- ✅ `shap.TreeExplainer` for RF / XGBoost / LightGBM / CatBoost
- ✅ `shap.LinearExplainer` for Logistic Regression (extracts `clf` from Pipeline)
- ✅ `top_positive` / `top_negative` factor lists with display names
- ✅ Human-readable narrative sentence generation
- ✅ Feature-magnitude fallback when model unavailable

### Model Registry
- ✅ `MLModelRecord` ORM — accuracy, F1, Brier, log-loss, calibration, ensemble_weight, training_samples, feature_version
- ✅ Historical model versions retained with `is_active` flag
- 📋 Experiment tracking integration (MLflow / W&B)

---

## Statistical Prediction Layer (Phase 1 — preserved)

- ✅ `wcip/engine/elo.py` — World-Football-Elo variant (K scaling, G goal-diff multiplier)
- ✅ `wcip/engine/scoreline.py` — Independent Poisson model, full P[i,j] matrix
- ✅ `wcip/engine/montecarlo.py` — Parallel Monte Carlo, Wilson CI, extra time + penalties
- ✅ `wcip/data/teams_2022.py` — 2022 WC seed data
- ✅ `app/services/prediction.py` — statistical engine bridge for API/Celery

---

## Prediction Layer (Hybrid)

- ✅ `predict_hybrid()` — single entry point returning all three layers + SHAP
- ✅ `MatchOutcome` + `HybridPrediction` + `PredictionExplanation` dataclasses
- ✅ Match-level confidence score (based on cross-model standard deviation)
- ✅ Model agreement score
- ✅ Expected scoreline from Poisson λ values
- ✅ xG per team in every response

---

## World Cup 2026

- ✅ `wcip/data/wc2026.py` — 48-team format constants, confederation slots, host nations
- ✅ `CONFIRMED_QUALIFIERS` — 48 official teams with FIFA group labels
- ✅ `get_qualified_teams_from_db()` — DB-first with stale-data fallback to official seed
- ✅ `build_2026_groups_from_db()` — official groups when draw is complete
- ✅ `_provisional_groups_by_elo()` — serpentine Elo-seeded provisional groups
- ✅ `build_2026_bracket()` — R32 → R16 → QF → SF → Final bracket
- ✅ Dedicated WC2026 seed ETL with placeholder-safe player/coach records
- ✅ Historical WC support (2010, 2014, 2018, 2022)
- 📋 Automatic group draw import from official FIFA feed

---

## API Layer

### Authentication
- ✅ `POST /auth/register` — account creation
- ✅ `POST /auth/login` — OAuth2 password flow → access + refresh JWT
- ✅ `POST /auth/refresh` — token refresh
- ✅ `GET /auth/me` — current user

### Teams
- ✅ `GET /teams` — list with confederation filter (cached)
- ✅ `GET /teams/{id}` — team detail
- ✅ `GET /teams/{id}/stats` — aggregated statistics
- ✅ `GET /teams/{id}/elo-history` — Elo timeseries
- ✅ `GET /players` — registry with team/search filters
- ✅ `GET /players/{id}` — player detail

### Statistical Predictions
- ✅ `POST /match/simulate` — Elo + Poisson + explanation
- ✅ `POST /tournament/simulate` — Monte Carlo (≤ 2,000 sync)
- ✅ `POST /scenario/compare` — 2–3 scenario comparison
- ✅ `GET /editions` — tournament editions

### Simulation Persistence
- ✅ `POST /simulations` — save (async above threshold)
- ✅ `GET /simulations` — paginated list
- ✅ `GET /simulations/{id}` — fetch
- ✅ `GET /simulations/public/{token}` — public share
- ✅ `PATCH /simulations/{id}` — rename / toggle public
- ✅ `POST /simulations/{id}/duplicate` — clone
- ✅ `DELETE /simulations/{id}` — remove

### ML Predictions
- ✅ `POST /ml/predict` — hybrid prediction (stat + ML + ensemble + SHAP)
- ✅ `POST /ml/train` — trigger training (admin, async)
- ✅ `POST /ml/retrain` — incremental retrain (admin, async)
- ✅ `GET /ml/models` — registered models + metrics
- ✅ `GET /ml/features` — feature vector for a match
- ✅ `GET /ml/feature-names` — feature name list
- ✅ `GET /ml/explanations` — SHAP explanation
- ✅ `POST /ml/etl/run` — trigger ETL (admin, async)
- ✅ `GET /world-cup/2026/winner-predictions` — ranked WC2026 winner predictions
- ✅ `GET /rankings/fifa/latest` — current stored FIFA ranking snapshot
- ✅ `GET /rankings/fifa/snapshots` — list stored ranking snapshots
- ✅ `GET /rankings/fifa/snapshots/{ranking_id}` — historical ranking snapshot
- ✅ `POST /rankings/fifa/refresh` — admin refresh + optional retraining trigger

### World Cup 2026
- ✅ `GET /world-cup/qualified-teams` — qualification list
- ✅ `GET /world-cup/groups` — draw status + groups
- ✅ `GET /world-cup/bracket` — knockout bracket
- ✅ `POST /world-cup/simulate` — WC2026 Monte Carlo
- ✅ `GET /world-cup/schedule` — tournament schedule
- ✅ `GET /world-cup/teams/{team_name}` — team detail + squad + coach
- ✅ `GET /world-cup/players/{team_name}` — squad list

### Admin
- ✅ `GET /admin/analytics` — usage metrics
- ✅ `GET /health` — liveness probe

---

## Frontend Layer

### Foundation
- ✅ Next.js 14 App Router + TypeScript + Tailwind CSS
- ✅ `lib/types.ts` — all interfaces (stat + ML + WC2026 types)
- ✅ `lib/api.ts` — typed fetch client with JWT token handling
- ✅ `lib/auth-context.tsx` — JWT auth provider (login/register/refresh/logout)
- ✅ `lib/queries.ts` — React Query hooks for all endpoints
- ✅ `middleware.ts` — auth route protection

### UI Primitives
- ✅ button, card, input, select, slider, skeleton, badge

### Shared Components
- ✅ `components/nav.tsx` — 10-route top navigation
- ✅ `components/probability-bar.tsx` — W/D/L split bar
- ✅ `components/match-predictor.tsx` — team pickers + modifiers
- ✅ `components/champion-chart.tsx` — champion probability chart (Recharts)
- ✅ `components/bracket.tsx` — animated knockout bracket

### Pages
- ✅ `/dashboard` — overview, top contenders, recent simulations
- ✅ `/wc2026` — qualified teams, official groups, Monte Carlo simulation
- ✅ `components/winner-predictions-section.tsx` — winner prediction table and charts
- ✅ Winner prediction sections on `/dashboard`, `/wc2026`, `/world-cup`, `/tournament`, `/predict`
- ✅ `/compare` — statistical vs all 5 ML models vs ensemble, side-by-side
- ✅ `/player-lab` — load squads, toggle injuries/suspensions, override form/coach
- ✅ `/models` — model metrics, ensemble weights, feature vector explorer
- ✅ `/simulate` — statistical single-match predictor
- ✅ `/tournament` — Monte Carlo tournament runner + bracket
- ✅ `/scenarios` — 2–3 scenario comparison
- ✅ `/teams` — sortable team table
- ✅ `/team/[id]` — team detail + Elo trend
- ✅ `/saved` — user simulation history (rename, share, duplicate, delete)
- ✅ `/history` — activity timeline
- ✅ `/profile` — account settings
- ✅ `/admin` — analytics (admin-gated)
- ✅ `/login` · `/register` — auth pages

---

## Infrastructure

- ✅ Dockerfile + docker-compose.yml (api + worker + beat + postgres + redis)
- ✅ render.yaml — Render deployment blueprint
- ✅ alembic/ — database migrations
- ✅ `.env.example` with all required config keys documented
- 📋 GitHub Actions CI (backend pytest + frontend typecheck on push)
- 📋 Frontend Jest / RTL unit tests
- 📋 Playwright E2E tests

---

## Notes

- The root `.venv` and `wcip-backend/.venv` are separate environments. ML packages
  (scikit-learn 1.9, XGBoost 3.2, LightGBM 4.6, CatBoost 1.2, SHAP 0.52) must be
  installed into the backend venv used by uvicorn.
- Player and coach tables are schema-complete. Fresh local databases receive one
  `world_cup_2026_placeholder` player and coach per WC2026 team; verified roster
  imports replace those placeholders team by team.
- WC2026 official groups are loaded locally. The knockout bracket remains a
  placeholder structure until FIFA-published fixture slots are imported.
