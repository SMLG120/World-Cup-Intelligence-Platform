# Real-Time Data Audit

Date: 2026-06-13

## Executive Summary

The platform already has the main building blocks for a real-time football intelligence system: FastAPI, SQLAlchemy, Celery, Redis cache fallback, versioned FIFA ranking snapshots, player and coach tables, an Elo engine, ML feature generation, and WC2026 prediction pages. The largest gap is that Elo is not versioned as a first-class external snapshot. The existing Elo refresh updates `teams.elo` directly and does not preserve a structured source log or per-snapshot rank table. Match result ingestion is idempotent, but it does not automatically update Elo ratings, refresh affected feature rows, invalidate prediction caches, or annotate predictions with the data snapshot used.

FIFA ranking ingestion is more mature: it fetches FIFA's official men's ranking page/API, stores immutable snapshots, writes provider-agnostic `team_rankings`, and updates `teams.fifa_rank` as a display cache. The official FIFA page observed on 2026-06-13 lists the latest men's ranking update as 2026-06-11 and the next official update as 2026-07-20. The local code still needs first-class freshness APIs, admin refresh endpoints, frontend freshness indicators, and consistent prediction metadata.

## Current Storage

### Elo Ratings

- Display values live on `teams.elo` in `app.models.team.Team`.
- Historical Elo values live in `elo_history` through `app.models.team.EloHistory`.
- `etl/extract/elo_ratings.py` fetches `https://www.eloratings.net/World.tsv`, caches it in `data/cache/elo_ratings.tsv`, and falls back to an embedded snapshot when the network fails.
- `etl/pipeline.py::run_elo_update()` fetches current Elo values and updates `teams.elo`.
- Missing: immutable external Elo snapshot tables, source logs, Elo rank storage, data versions, and a dedicated `etl/elo/` pipeline.

### FIFA Rankings

- Canonical snapshot models are `FifaRankingSnapshot` and `FifaRankingEntry`.
- Provider-agnostic ranking rows are stored in `team_rankings`.
- Source logs are stored in `ranking_source_logs`.
- `etl/extract/fifa_rankings.py` fetches FIFA's official ranking page and ranking API payload.
- `etl/load/ranking_loader.py` stores immutable snapshots and updates `teams.fifa_rank` only as a current display cache.
- `etl/monitoring/ranking_monitor.py` detects material changes and can trigger retraining.
- Missing: requested `etl/fifa_rankings/` package layout, `GET /rankings/fifa/history/{team_id}`, and global freshness metadata API.

### Match Results

- Historical match results live in `match_results`.
- `etl/load/db_loader.py::load_match_results()` upserts by `(home_team, away_team, match_date)` and skips duplicates.
- Match insert/update does not currently call a rating update service.
- Missing: idempotent `update_ratings_after_match(match_id)` flow, group standings update hook, cache invalidation, and affected feature refresh.

### Players And Coaches

- Player and coach data live in `players` and `coaches`.
- Legal CSV rating import exists in `etl/player_ratings/csv_import.py`.
- WC2026 seed ETL exists separately from generic ETL in `etl/world_cup_2026/`.
- Missing: requested `etl/players/` package, generated player profile/description field in API output, and a player availability refresh task.

## Feature Engineering And ML Freshness

- `ml/features.py` builds 33 features using Elo, FIFA ranking, recent results, squad values, player strength, availability, coach impact, form, and tournament experience.
- Historical FIFA ranking lookup uses the latest `FifaRankingSnapshot` on or before the match date, which prevents current-ranking leakage when snapshots exist.
- Historical Elo lookup uses `elo_history` on or before the match date and falls back to neutral `1500.0` for historical rows.
- Current/future predictions use the current display values from `teams.elo` and `teams.fifa_rank` when no as-of snapshot is selected.
- Missing: feature validation script focused on no NaN/infinity/order mismatch, snapshot metadata attached to prediction output, and recalibration decision workflow.

## Prediction Recalculation

- `app/services/winner_predictions.py` computes WC2026 title probabilities from current Elo, FIFA rank, player strength, form, and coach data.
- `ml/ensemble.py` returns statistical, ML, ensemble, model weights, and feature values.
- Prediction cache invalidation is not tied to data refresh jobs.
- Prediction responses do not currently expose Elo rating used, FIFA ranking used, snapshot timestamp, player data freshness timestamp, model version, or data version.

## Frontend Freshness

- Frontend pages consume teams, predictions, ML models, WC2026 teams/groups, and simulations through `lib/api.ts` and `lib/queries.ts`.
- Save simulation buttons already exist on `/simulate`, `/tournament`, `/wc2026`, and `/predict`.
- `/models` shows model training metrics.
- Missing: visible freshness indicators on `/`, `/wc2026`, `/predict`, `/simulate`, `/tournament`, `/teams`, `/team/[id]`, `/player/[id]`, and `/models`.
- Missing: admin-only manual refresh controls exposed through the frontend.

## Hardcoding And Staleness Risks

- Elo fallback data in `etl/extract/elo_ratings.py` is manually embedded and can drift.
- WC2026 seed data can populate team/player/coach defaults, but external refreshes do not yet reconcile every snapshot into the feature store.
- `teams.elo` and `teams.fifa_rank` are display caches and should not be treated as historical truth.
- Root prediction services can still operate when model files are absent, but data freshness is not surfaced to the user.

## Files That Need Modification

- `app/models/team.py`
- `app/models/player.py`
- `app/models/__init__.py`
- `app/db/init_db.py`
- `alembic/versions/*`
- `etl/pipeline.py`
- `etl/elo/*`
- `etl/fifa_rankings/*`
- `etl/players/*`
- `etl/schedulers/celery_tasks.py`
- `app/workers/celery_app.py`
- `app/workers/tasks.py`
- `app/services/rating_update_service.py`
- `app/services/data_refresh_service.py`
- `app/api/v1/ratings.py`
- `app/api/v1/data.py`
- `app/api/v1/admin_data.py`
- `app/api/v1/rankings.py`
- `app/api/v1/world_cup.py`
- `app/api/v1/ml.py`
- `ml/features.py`
- `ml/validate_features.py`
- `ml/retrain_if_needed.py`
- `wcip-frontend/lib/api.ts`
- `wcip-frontend/lib/types.ts`
- `wcip-frontend/lib/queries.ts`
- `wcip-frontend/components/data-freshness.tsx`
- Frontend pages listed in the task
- `README.md`, `MEMORY.md`, `REPO_CHECKLIST.md`, `docs/DATA_PIPELINE.md`, `docs/MODEL_CARD.md`

## Implementation Direction

Extend the existing architecture by adding immutable Elo snapshot tables and services alongside the existing `elo_history` timeseries. Keep `teams.elo` and `teams.fifa_rank` as fast display caches. Add structured refresh tasks that log status, preserve historical records, refresh current caches, invalidate prediction cache keys, and expose a single `/data/freshness` contract for the frontend. Keep external fetchers cache-aware and testable without network access.
