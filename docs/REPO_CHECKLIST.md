# World Cup Intelligence Platform — Repository Checklist

Status legend: ✅ Complete · 🔄 In Progress · 📋 Planned

---

## Data Layer

### ETL Infrastructure
- ✅ `etl/pipeline.py` — orchestrator with ETL state file for incremental runs
- ✅ `etl/extract/international_results.py` — martj42 CSV download + caching + parse (49K rows)
- ✅ `etl/extract/elo_ratings.py` — eloratings.net TSV fetch + embedded fallback snapshot
- ✅ `etl/elo/` — versioned World Football Elo snapshots, validation, loader, source logs
- ✅ `scripts/convert_elo_pdf_to_csv.py` / `scripts/validate_elo_csv.py` /
  `etl/elo/load_elo_csv.py` — static 2026-06-21 World Football Elo PDF CSV
  workflow with top-six validation and immutable snapshot loading
- ✅ `etl/extract/football_data.py` — football-data.org API client (rate-limited 6.5s)
- ✅ `etl/extract/fifa_rankings.py` — official FIFA ranking snapshot fetch + validation
- ✅ `etl/fifa_rankings/` — dedicated FIFA ranking ETL package around the canonical official snapshot loader
- ✅ `etl/players/` — legal CSV player import wrapper + generated profile text
- ✅ `etl/players/fifa_squad_pdf.py` — official FIFA squad PDF to player CSV converter with conservative proxy ratings
- ✅ `etl/load/ranking_loader.py` — historical ranking snapshot loader
- ✅ `etl/monitoring/ranking_monitor.py` — ranking change detection + retraining trigger
- ✅ `etl/transform/normalize.py` — canonical name normalization (60+ variant spellings)
- ✅ `etl/validation/schema.py` — ValidatedMatch dataclass, business-rule checks
- ✅ `etl/load/db_loader.py` — idempotent upsert loaders (batch 500, in-run dedup)
- ✅ `etl/schedulers/celery_tasks.py` — scheduled Elo, FIFA, results, player availability, and cache refresh tasks
- ✅ `etl.retrain_if_needed` — scheduled retraining threshold monitor

### Database Tables (19 total)
- ✅ `users` — accounts, roles, refresh tokens
- ✅ `audit_logs` — admin audit trail
- ✅ `teams` — team metadata, Elo, FIFA rank, confederation
- ✅ `elo_history` — Elo rating timeseries per team
- ✅ `elo_rating_snapshots` — immutable World Football Elo ingestion snapshots
- ✅ `team_elo_ratings` — team Elo rating/rank rows per snapshot
- ✅ `elo_source_logs` — Elo fetch/load audit trail
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
- ✅ `rag_documents` — indexed text documents for RAG retrieval (teams, players, coaches, model metadata)
- ✅ `rag_chunks` — overlapping 200-token text chunks from each document
- ✅ `rag_embeddings` — TF-IDF term weights per chunk (keyword retrieval)
- ✅ `rag_queries` — query audit log with latency tracking
- ✅ `rag_answers` — generated answer log with confidence and citations

### Data Quality
- ✅ Unique constraint on (home_team, away_team, match_date) — duplicates rejected at DB level
- ✅ NA/empty score filtering — scheduled/future matches skipped
- ✅ Team name normalization — 60+ variants mapped to canonical names
- ✅ Incremental ETL with 7-day overlap window to catch late corrections
- ✅ WC2026 validation script for official teams, groups, roster placeholders,
  coaches, prediction readiness, and tournament placement
- ✅ FIFA ranking versioning / snapshot tagging
- ✅ Ranking source logging for fetch/load traceability
- ✅ Elo source logging for fetch/load traceability
- ✅ Static Elo PDF CSV snapshot loaded as `elo-pdf-2026-06-21-960500577039`
  with 244 rows, 57 local team matches, and PDF top-six validation
- ✅ Prediction probability contract: backend JSON uses fractions `0.0` to
  `1.0`; frontend formatting multiplies by 100 once and guards legacy values
- ✅ Legal CSV player-rating import with validation and versioning
- ✅ Official FIFA squad-list CSV generation for Teams, Scenarios, and player-strength ML features
- ✅ Official FIFA squad PDF ingestion validation: local DB currently validates with 1,254 players and 48 coaches
- ✅ Generated player profiles from supported fields only; incomplete rows labelled
- ✅ Player-derived feature validator for sparse squads, duplicates, rating ranges, position mapping, and NaN/inf safety
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
- ✅ Point-in-time Elo lookup uses `team_elo_ratings`, then `elo_history`, then neutral fallback for historical rows
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
- ✅ `ml/validate_features.py` — feature order/shape/NaN/inf validation report
- ✅ `ml/validate_player_features.py` — player-data and player-feature validation report
- ✅ `ml/retrain_if_needed.py` — data-change threshold workflow for recalibration decisions
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
- ✅ `MLModelRecord` ORM — accuracy, F1, Brier, log-loss, calibration, ensemble_weight, training_samples, feature_version, data_snapshot_version, recalibration status
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
- ✅ `build_2026_bracket()` — R32 → R16 → QF → SF → third-place/final replay payload
- ✅ Dedicated WC2026 seed ETL with placeholder-safe player/coach records
- ✅ Full WC2026 simulation response with group tables, group-stage fixtures,
  qualified teams, best third-place table, knockout matches, champion,
  runner-up, third place, and champion probability
- ✅ Match-level WC2026 bracket payload includes team codes, scoreline, xG,
  expected scoreline, statistical/ML/ensemble probabilities, selected
  prediction mode, winner probability, and advancement reason
- ✅ WC2026 knockout elimination integrity covered by tests, including
  semi-final losers appearing only in the third-place match
- ✅ Historical WC support (2010, 2014, 2018, 2022)
- 📋 Automatic group draw import from official FIFA feed

---

## API Layer

### Authentication
- ✅ `POST /auth/register` — account creation
- ✅ `POST /auth/login` — JSON email/password and OAuth2 password form → access + refresh JWT
- ✅ `POST /auth/refresh` — token refresh
- ✅ `GET /auth/me` — current user

### Teams
- ✅ `GET /teams` — enriched WC2026 list by default with confederation filter, FIFA code, WC group, coach, squad count, Elo, and FIFA rank; `world_cup_only=false` returns every historical team
- ✅ `GET /teams/{id}` — enriched team detail
- ✅ `GET /teams/{id}/stats` — aggregated statistics
- ✅ `GET /teams/{id}/elo-history` — Elo timeseries
- ✅ `GET /teams/{id}/players` — full squad rows for a team
- ✅ `GET /teams/{id}/squad` — team, coach, squad count, and squad payload
- ✅ `GET /ratings/elo/latest` — current versioned Elo snapshot
- ✅ `GET /ratings/elo/history/{team_id}` — versioned Elo records for a team
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
- ✅ `POST /admin/ml/retrain-if-needed` — evaluate retraining thresholds and mark active models
- ✅ `GET /world-cup/2026/winner-predictions` — ranked WC2026 winner predictions
- ✅ `GET /world-cup/2026/predictions` — prediction bundle with freshness metadata
- ✅ `/world_cup/2026/*` — underscore compatibility aliases
- ✅ `GET /rankings/fifa/latest` — current stored FIFA ranking snapshot
- ✅ `GET /rankings/fifa/history/{team_id}` — FIFA ranking history for a team
- ✅ `GET /rankings/fifa/snapshots` — list stored ranking snapshots
- ✅ `GET /rankings/fifa/snapshots/{ranking_id}` — historical ranking snapshot
- ✅ `POST /rankings/fifa/refresh` — admin refresh + optional retraining trigger
- ✅ `GET /data/freshness` — current data/model/feature freshness metadata

### World Cup 2026
- ✅ `GET /world-cup/qualified-teams` — qualification list with current Elo/FIFA display values
- ✅ `GET /world-cup/groups` — draw status + groups
- ✅ `GET /world-cup/bracket` — knockout bracket
- ✅ `POST /world-cup/simulate` — WC2026 Monte Carlo + replayable bracket payload
- ✅ `POST /world_cup/2026/simulate` — explicit WC2026 simulation alias with
  `prediction_mode` support (`statistical`, `ml`, `ensemble`)
- ✅ `GET /world_cup/2026/groups` — explicit WC2026 groups alias
- ✅ `GET /world_cup/2026/bracket` — explicit WC2026 bracket alias
- ✅ `GET /world-cup/schedule` — tournament schedule
- ✅ `GET /world-cup/teams/{team_name}` — team detail + squad + coach
- ✅ `GET /world-cup/players/{team_name}` — squad list

### Admin
- ✅ `GET /admin/analytics` — usage metrics
- ✅ `POST /admin/data/refresh-elo` — admin-only Elo refresh
- ✅ `POST /admin/data/refresh-fifa-rankings` — admin-only FIFA ranking refresh
- ✅ `POST /admin/data/refresh-players` — admin-only player-data refresh
- ✅ `POST /admin/data/refresh-all` — admin-only global refresh
- ✅ `POST /admin/ml/retrain-if-needed` — admin-only recalibration check
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
- ✅ `components/nav.tsx` — clean eight-tab navigation: WC 2026, BRACKET, PREDICT, SCENARIOS, EXPLAIN, MODELS, TEAMS, SAVED
- ✅ `components/probability-bar.tsx` — W/D/L split bar
- ✅ `components/match-predictor.tsx` — team pickers + modifiers
- ✅ `components/champion-chart.tsx` — champion probability chart (Recharts)
- ✅ `components/bracket.tsx` — animated knockout bracket
- ✅ `components/DataFreshnessCard.tsx` — deterministic freshness card with Elo, FIFA, squad, results, model, snapshot fields and admin refresh controls
- ✅ `components/data-freshness.tsx` — compatibility re-export for existing freshness strip imports

### Pages
- ✅ `/dashboard` — overview, top contenders, recent simulations
- ✅ `/wc2026` — canonical WC2026 overview with top probabilities, most likely final, dark horses, freshness, group snapshot, and bracket CTA
- ✅ `/world-cup` — compatibility redirect to `/wc2026`
- ✅ `/wc2026/simulate` — explicit simulator compatibility route redirected to `/wc2026/bracket`
- ✅ `/wc2026/bracket` — dedicated bracket simulator with group tables,
  group fixtures, full knockout columns, mode controls, random rerun, save, and
  retry/error states
- ✅ `/compare` — compatibility redirect to `/predict`; comparison charts live inside Predict
- ✅ `/player-lab` — compatibility redirect to `/scenarios`; player availability controls live inside Scenarios
- ✅ `components/winner-predictions-section.tsx` — winner prediction table and charts
- ✅ Winner prediction sections on `/dashboard`, `/wc2026`, `/predict`
- ✅ Freshness indicators on `/`, `/dashboard`, `/wc2026`, `/predict`, `/simulate`, `/tournament`, `/teams`, `/team/[id]`, `/player/[id]`, `/models`
- ✅ `/` — explanatory homepage for Elo, FIFA rankings, squad PDF data, ML models, Poisson/Monte Carlo simulation, and full bracket projection links
- ✅ `/models` — model metrics, ensemble weights, feature vector explorer
- ✅ `/simulate` — legacy simulation route redirected to `/wc2026/bracket`
- ✅ `/tournament` — legacy tournament route redirected to `/wc2026/bracket`
- ✅ `/scenarios` — WC2026 scenario comparison plus squad loading, player availability toggles, and before/after match delta
- ✅ `/teams` — sortable WC2026 table with group, code, confederation, Elo, FIFA rank, coach, squad count, and team links
- ✅ `/team/[id]` — team detail + Elo trend + full squad table
- ✅ `/saved` — user simulation history (rename, share, duplicate, delete)
- ✅ `/history` — activity timeline
- ✅ `/profile` — account settings
- ✅ `/admin` — analytics (admin-gated)
- ✅ `/login` · `/register` — auth pages

---

## Infrastructure

- ✅ Dockerfile + docker-compose.yml (api + worker + beat + postgres + redis)
- ✅ render.yaml — Render Python deployment blueprint; both services set
  `rootDir: wcip-backend` and `startCommand: bash scripts/start_render.sh`
  (runs Alembic migrations before Uvicorn starts)
- ✅ `wcip-backend/scripts/start_render.sh` — Alembic + Uvicorn start script, required (not optional) as the Render start command
- ✅ `app/core/config.py` normalizes `postgres://` `DATABASE_URL` values to `postgresql://` for SQLAlchemy compatibility
- ✅ `RENDER_BACKEND_DEPLOYMENT_AUDIT.md` — FastAPI backend Render checklist
- ✅ `vercel.json` — root-level defensive Vercel config delegates builds to `wcip-frontend`
- ✅ `wcip-frontend/vercel.json` — Next.js Vercel config for the correct frontend project root
- ✅ `VERCEL_DATA_FRESHNESS_AUDIT.md` — deployed freshness diagnosis and env/CORS checklist
- ✅ alembic/ — database migrations
- ✅ `.env.example` with all required config keys documented
- ✅ `wcip-backend/.env.example` — backend placeholder-only local template
- ✅ `wcip-frontend/.env.local.example` — frontend placeholder-only local template
- ✅ `wcip-backend/scripts/generate_local_env.py` — secure local env generator
- ✅ `wcip-backend/scripts/seed_test_user.py` — development/test-only seed for `test@example.com / testtest`
- ✅ `scripts/check_repo_safety.py` + `make safety-check` — tracked artifact and secret scanner
- ✅ `SECURITY_CLEANUP.md` — cleanup commands, secret rotation, and never-commit policy
- 📋 GitHub Actions CI (backend pytest + frontend typecheck on push)
- 📋 Frontend Jest / RTL unit tests
- 📋 Playwright E2E tests

---

## RAG System

- ✅ `wcip-backend/rag/` — RAG module (explanation/retrieval only, never predicts winners)
  - `sources.py` — fetches team, player, coach, group, model metadata; never reads secrets
  - `chunking.py` — 200-token overlapping text chunker
  - `indexer.py` — TF-IDF indexer, persists to `rag_documents/chunks/embeddings`
  - `retriever.py` — keyword + TF-IDF retrieval with doc-type and team-id filtering
  - `generator.py` — template-based answer assembly with disclaimer
  - `service.py` — `answer_question()` orchestrator with query/answer audit logging
  - `schemas.py` — `RagAnswer`, `RagAskRequest`, `RagIndexStatus`, `RagDocumentSummary`
- ✅ `app/api/v1/rag.py` — `POST /rag/ask`, `GET /rag/status`, `GET /rag/documents`, `POST /admin/rag/index`
- ✅ `app/models/rag.py` — ORM models for the 5 RAG tables
- ✅ `alembic/versions/c1d2e3f4a5b6_add_rag_tables.py` — migration applied
- ✅ `RagExplanation` field on `MatchPrediction` and `TeamProbabilityOut` schemas
- ✅ Frontend components: `AskAnalystBox`, `RagAnswerCard`, `RagSourcesList`, `PredictionExplanationPanel`
- ✅ RAG integrated into `/wc2026`, `/teams`, and `/team/[id]` pages
- ✅ RAG API client in `lib/api.ts` (`ragApi.ask`, `ragApi.status`, `ragApi.documents`, `ragApi.adminIndex`)
- ✅ RAG types in `lib/types.ts`

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
- The current tracked-file audit found no tracked `.env`, local database,
  dependency, build, cache, coverage, log, or `.DS_Store` files in the unsafe
  patterns checked by `CLEANUP_REPORT.md`.
