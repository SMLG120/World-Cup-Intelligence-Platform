# Data Migration And Import Audit

Generated: 2026-06-24

## Executive Summary

The local SQLite database is populated and the backend can serve the main data
surfaces. The main production risk found during the audit was that the Alembic
migration chain was not safe for a fresh production database. A clean
`alembic upgrade head` against an empty database failed because revision
`73b2e6b46c21_add_prediction_data_quality_tables.py` altered `players` before
any migration created `players`, `coaches`, `match_results`, `match_features`,
`ml_models`, or `qualified_teams`.

Local startup hides this because `app.db.init_db.create_tables()` calls
`Base.metadata.create_all()`. Render/PostgreSQL should not rely on startup table
creation; it needs migrations plus an explicit bootstrap/import command.

The player-rating warnings for Mexico, South Africa, and South Korea are not
frontend bugs by themselves. They mean the active database has player rows
without `player_rating` values for those teams. Locally that data is present;
production likely has WC2026 teams but has not run the squad/player-rating
bootstrap.

## Implemented Repairs

- Added Alembic revision
  `4a6f2d8b9c01_create_prediction_base_tables.py` before
  `73b2e6b46c21_add_prediction_data_quality_tables.py`.
- Verified a fresh empty SQLite database can run `alembic upgrade head` and
  create the required prediction, player, coach, model, ranking, Elo, RAG, user,
  and simulation tables.
- Added idempotent `python -m scripts.bootstrap_data` to run migrations, seed
  WC2026 teams, import the FIFA squad PDF, import labeled player-rating proxy
  rows, load local Elo CSV data, refresh/cache FIFA rankings when available, and
  register existing model artifacts.
- Added `python -m scripts.validate_player_ratings` to report WC2026 rating
  coverage and whether neutral defaults are being used.
- Expanded `/api/v1/data/freshness` to return `status`, `message`, `warnings`,
  and structured `sources` while preserving the legacy flat fields.
- Updated frontend freshness types and UI to trust top-level backend status and
  display warnings such as missing player ratings / neutral defaults.
- Unignored the required bundled source artifacts so Render can receive them:
  `data/cache/results.csv`, `data/cache/fifa_rankings.json`,
  `data/external/fifa_wc2026_squad_lists_english.pdf`,
  `data/external/fifa_wc2026_squad_players.csv`, and the checked model `.pkl`
  artifacts under `wcip-backend/models/`.

## Current Local Database Snapshot

Local DB URL checked: `sqlite:///./wcip.db`

| Table | Local row count |
|---|---:|
| teams | 57 |
| qualified_teams | 48 |
| players | 1253 |
| coaches | 48 |
| match_results | 49306 |
| match_features | 0 |
| elo_rating_snapshots | 3 |
| team_elo_ratings | 549 |
| elo_source_logs | 7 |
| fifa_ranking_snapshots | 1 |
| fifa_ranking_entries | 211 |
| team_rankings | 211 |
| ranking_source_logs | 3 |
| player_rating_imports | 6 |
| player_rating_records | 7488 |
| ml_models | 15 |
| simulations | 4 |
| simulation_runs | 0 |
| saved_scenarios | 0 |
| rag_documents | 1365 |
| rag_chunks | 2730 |
| rag_embeddings | 2730 |
| rag_queries | 30 |
| rag_answers | 30 |

All 48 local WC2026 teams have at least one player row with `player_rating`.

## Required Tables And Frontend Dependencies

| Frontend feature | Backend endpoint | Required tables |
|---|---|---|
| Data Freshness card | `GET /api/v1/data/freshness` | `elo_rating_snapshots`, `fifa_ranking_snapshots`, `match_results`, `players`, `player_rating_imports`, `ml_models`, `elo_source_logs`, `ranking_source_logs` |
| Teams page | `GET /api/v1/teams?world_cup_only=true` | `teams`, `qualified_teams`, `players`, `coaches` |
| Team detail/squad | `GET /api/v1/teams/{id}`, `/players`, `/squad` | `teams`, `players`, `coaches`, `qualified_teams` |
| Models page | `GET /api/v1/ml/models`, `/api/v1/ml/features` | `ml_models`, `teams`, `players`, `elo_rating_snapshots`, `team_elo_ratings`, `fifa_ranking_snapshots`, `fifa_ranking_entries` |
| Prediction page | `POST /api/v1/match/simulate`, `POST /api/v1/ml/predict` | `teams`, `players`, `coaches`, `match_results`, `elo_rating_snapshots`, `team_elo_ratings`, `fifa_ranking_snapshots`, `fifa_ranking_entries`, `ml_models` |
| WC2026 bracket/simulation | `POST /api/v1/world_cup/2026/simulate`, `GET /api/v1/world_cup/2026/groups` | `qualified_teams`, `teams`, `players`, `coaches`, rating/ranking snapshots, ML models |
| RAG Ask Analyst | `/api/v1/rag/*` | `rag_documents`, `rag_chunks`, `rag_embeddings`, `rag_queries`, `rag_answers` |
| Saved simulations | `/api/v1/simulations/*` | `users`, `simulations`, `simulation_runs`, `saved_scenarios` |

## Migration Coverage

| Migration | Creates or updates |
|---|---|
| `0964b8fff254_initial_schema.py` | `teams`, `users`, `audit_logs`, `elo_history`, `saved_scenarios`, `simulations`, `simulation_runs` |
| `3f8b9d9c2a11_add_fifa_ranking_snapshots.py` | `fifa_ranking_snapshots`, `fifa_ranking_entries` |
| `73b2e6b46c21_add_prediction_data_quality_tables.py` | `ranking_source_logs`, `team_rankings`, `player_rating_imports`, `player_rating_records`; alters `players` and `match_features` |
| `a1c9e8d4f602_add_realtime_elo_and_refresh_metadata.py` | `elo_rating_snapshots`, `team_elo_ratings`, `elo_source_logs`; alters `players` and `ml_models` |
| `b5c7a9e1d3f2_add_player_squad_fields_and_coach_team.py` | adds FIFA squad fields to `players` and `coaches` |
| `c1d2e3f4a5b6_add_rag_tables.py` | `rag_documents`, `rag_chunks`, `rag_embeddings`, `rag_queries`, `rag_answers` |

Migration problem found:

```text
sqlite3.OperationalError: no such table: players
```

This happens on a brand-new database during `alembic upgrade head`.

## SQLAlchemy Metadata Imports

`wcip-backend/app/models/__init__.py` imports all active ORM models, including:

- `Team`, `EloHistory`, `EloRatingSnapshot`, `TeamEloRating`, `EloSourceLog`
- `Player`, `Coach`, `PlayerRatingImport`, `PlayerRatingRecord`
- `FifaRankingSnapshot`, `FifaRankingEntry`, `TeamRanking`, `RankingSourceLog`
- `MatchResult`, `MatchFeatures`, `MLModelRecord`, `QualifiedTeam`
- `Simulation`, `SimulationRun`, `SavedScenario`
- `User`, `AuditLog`
- `RagDocument`, `RagChunk`, `RagEmbedding`, `RagQuery`, `RagAnswer`

The previous `app.models.rag` crash is fixed in the current codebase.

## Import And Seed Sources

| Data | Script/module | Source |
|---|---|---|
| WC2026 teams/groups/placeholders | `etl.world_cup_2026.ingest.run_wc2026_seed` | `etl/world_cup_2026/seed_data.py` |
| Official squad/player/coach data | `etl.players.load_squad_pdf.load_squad_from_pdf` | `data/external/fifa_wc2026_squad_lists_english.pdf` |
| Player-rating proxy rows | `etl.player_ratings.csv_import.import_player_ratings_csv` | `data/external/fifa_wc2026_squad_players.csv` or optional `ea_player_ratings.csv` |
| Elo ratings | `etl.elo.load_elo_csv.load_elo_csv` | `data/processed/world_football_elo_ratings_2026_06_21.csv` |
| FIFA rankings | `etl.load.ranking_loader.load_latest_fifa_ranking_snapshot` | FIFA ranking fetch/cache |
| Match results | `etl.pipeline.run_historical_results` | `data/cache/results.csv` / martj42 source |
| ML model metadata | `ml.train` / existing `ml_models` table | trained model registry |
| RAG index | `rag.indexer` / admin RAG endpoint | database-derived docs |

`data/external/ea_player_ratings.csv` is not present locally. That is okay if
the official squad PDF-derived proxy ratings are imported and labeled as such.

Before this repair, `.gitignore` hid the local squad PDF/CSV, cached FIFA
rankings, cached historical results, and model artifacts from Git. That meant a
Render deployment could have working Python code and a live API but no source
files for production bootstrap to import. Those files are now allow-listed by
name; they still need to be committed with the code.

## Why Player Ratings Are Missing In Production

The warning:

```text
No player ratings for Mexico; using neutral rating defaults
```

comes from `ml/features.py` when a team has no players with `player_rating`.
Local data does not reproduce this for WC2026 teams, so the most likely
production root cause is:

1. Render database migrations did not fully create the schema from Alembic alone.
2. Render deployment did not include the bundled source files needed by the
   bootstrap command.
3. Render database has teams/qualified teams but has not run the full squad and
   player-rating bootstrap.
4. Production startup may run lightweight table creation/seeding but not the
   complete data imports.
5. Frontend receives `200 OK` payloads but the payloads are partial.

## Frontend Contract Check

The frontend API client uses `NEXT_PUBLIC_API_BASE_URL` and appends `/api/v1`
in code. The local env example correctly uses:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The frontend `DataFreshness` type now includes richer `warnings` and `sources`
objects. The Data Freshness component trusts the top-level backend `status` and
still falls back to legacy flat fields for mixed deployments during rollout.

## Freshness Behavior

Current backend freshness returns `200 OK`, the legacy flat fields, and richer
source metadata with:

- `status`
- `message`
- `warnings`
- `sources`
- timestamps
- source URLs/versions
- `source_status`

It can distinguish available/partial/unavailable locally so the frontend can
clearly show:

```text
Data partially available
Player ratings missing for some teams; neutral defaults are used.
```

## Production Difference From Local

Local DB is already seeded and imported. Production needs an explicit,
idempotent bootstrap after migrations:

```bash
alembic upgrade head
python -m scripts.bootstrap_data
python -m scripts.validate_player_ratings
python -m ml.validate_features
```

Do not run destructive imports automatically on every request.
