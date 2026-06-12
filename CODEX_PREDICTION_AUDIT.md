# Codex Prediction Audit

Audit date: 2026-06-12

Scope: backend API routes, database models, migrations, ETL, FIFA ranking
ingestion, team/player/coach ingestion, ML features, model loading, ensemble
logic, tournament simulation, frontend API client/hooks/pages, and chart
components.

## Executive Summary

The platform can already return team lists, WC2026 groups, WC2026 tournament
simulation output, statistical match predictions, and hybrid ML match
predictions. It does not yet provide the requested ranked
World Cup 2026 winner-prediction endpoint with statistical/ML/ensemble
probability breakdown, explanation, group, FIFA rank, and normalized champion
probabilities.

The largest data-quality risks are:

- FIFA ranking snapshot tables exist but are empty in the local database.
- `teams.fifa_rank` still contains stale display-cache values; Brazil is stored
  as rank #1 locally.
- FIFA's official ranking page was checked during this audit and says the men's
  ranking was just updated on 2026-06-11, with the next official update on
  2026-07-20.
- All 48 WC2026 teams have exactly one player and one coach row, but all are
  `world_cup_2026_placeholder` records.
- Player ratings are not stored in the schema, and there is no legal CSV import
  interface for EA Sports FC or other licensed player-rating data.
- `match_features` has 0 rows; training computes features on demand.
- Existing models are active but trained on feature version `v1` before the
  requested player-rating feature expansion.

## Current Database State

Local SQLite database: `wcip-backend/wcip.db`

| Table | Rows | Audit Finding |
|---|---:|---|
| `teams` | 57 | Present; includes stale current rank cache |
| `qualified_teams` | 48 | WC2026 teams present |
| `players` | 48 | One placeholder row per WC2026 team |
| `coaches` | 48 | One placeholder row per WC2026 team |
| `match_results` | 49,306 | Historical results present |
| `match_features` | 0 | Persisted feature store empty |
| `ml_models` | 5 | Active v20260604 model registry records |
| `fifa_ranking_snapshots` | 0 | Snapshot ingestion has not populated DB |
| `fifa_ranking_entries` | 0 | Snapshot entries absent |

## Endpoint Audit

Tested with FastAPI `TestClient`.

| Endpoint | Status | Finding |
|---|---:|---|
| `GET /health` | 200 | Works outside `/api/v1` |
| `GET /api/v1/health` | 404 | Not mounted under v1 despite README/API-map expectation in some docs |
| `GET /api/v1/teams` | 200 | Returns 57 teams |
| `GET /api/v1/world-cup/qualified-teams` | 200 | Returns 48 teams |
| `GET /api/v1/world-cup/groups?year=2026` | 200 | Returns groups and qualification status |
| `GET /api/v1/world-cup/bracket?year=2026` | 200 | Returns bracket metadata |
| `POST /api/v1/world-cup/simulate` | 200 | Returns stage probabilities, but not requested winner-prediction contract |
| `POST /api/v1/tournament/simulate` | 200 | Works and proxies WC2026 when edition is 2026 |
| `POST /api/v1/match/simulate` | 200 | Works for Brazil vs France |
| `GET /api/v1/ml/models` | 200 | Returns 5 registry records |
| `GET /api/v1/ml/features` | 200 | Returns v1 features |
| `POST /api/v1/ml/predict` | 200 | Returns hybrid prediction; optional model packages may be missing in shell |
| `GET /api/v1/rankings/fifa/latest` | 404 | Expected until a ranking snapshot is loaded |
| `GET /api/v1/rankings/fifa/snapshots` | 200 | Route exists; DB is empty |
| `POST /api/v1/rankings/fifa/refresh` | protected | Admin route exists |

Missing requested endpoint:

- `GET /api/v1/world-cup/2026/winner-predictions`

## Ranking Data Audit

Official source checked:

- `https://inside.fifa.com/fifa-world-ranking/men`

Official page status observed during this audit:

- Just updated: 2026-06-11
- Next official update: 2026-07-20

Local top rankings in `teams`:

| Stored Rank | Team |
|---:|---|
| 1 | Brazil |
| 2 | Belgium |
| 3 | Argentina |
| 4 | France |
| 5 | England |
| 7 | Spain |
| 8 | Netherlands |
| 9 | Portugal |
| 9 | Italy |
| 10 | Denmark |

Findings:

- No WC2026 team has `teams.fifa_rank <= 0`, but the values are stale.
- `fifa_ranking_snapshots` and `fifa_ranking_entries` are empty.
- The code has `FifaRankingSnapshot` and `FifaRankingEntry`, but not the exact
  requested `team_rankings` or `ranking_source_logs` tables.
- Ranking source traceability is partial: snapshots store source URL/hash, but
  there is no separate source log for fetch attempts, failures, or validation
  outcomes.

## Team, Player, And Coach Data Audit

All 48 WC2026 teams have a team row, one player row, and one coach row.

However:

- `players.data_source = world_cup_2026_placeholder` for all 48 player rows.
- `coaches.data_source = world_cup_2026_placeholder` for all 48 coach rows.
- Every player row has `age IS NULL`.
- Every player row has `market_value_eur IS NULL`.
- Every player row has missing `club`.
- No player rating field exists.
- No rating source, rating version, or rating import timestamp exists.
- No `data/external/ea_player_ratings.csv` import path exists.

Teams with sparse current strength metadata:

- Several WC2026 teams have neutral Elo `1500.0`, including Austria, Colombia,
  Egypt, Ivory Coast, Jordan, New Zealand, Scotland, South Africa, Turkey, and
  Uzbekistan.

## Feature Engineering Audit

Current ML feature version: `v1`

Current feature count: 17

Existing player-related feature coverage:

- `avg_age_diff`
- `market_value_diff`
- `injury_burden_diff`
- `squad_chemistry_diff`
- `starting_xi_strength_diff`
- `bench_strength_diff`

Missing requested player-level features:

- `average_starting_xi_rating`
- `average_squad_rating`
- `top_5_player_rating_avg`
- `goalkeeper_rating`
- `defensive_unit_rating`
- `midfield_unit_rating`
- `attacking_unit_rating`
- `squad_depth_score`
- `star_player_score`
- `player_form_score`
- `player_availability_score`
- `international_experience_score`
- `average_caps`
- `total_international_goals`
- `weighted_player_strength`

Current safety behavior:

- Missing player data falls back to neutral defaults.
- Historical FIFA rank lookup uses ranking snapshots if available.
- Historical Elo lookup uses `elo_history` if available.
- Missing historical ranking/Elo uses neutral fallback to avoid leakage.

Current weakness:

- Placeholder player rows make squad-derived features mostly neutral or
  low-information.
- `match_features` is empty, so feature reproducibility depends on live
  recomputation.
- Existing model files expect 17 features, so expanding feature count requires
  model retraining or prediction-time compatibility handling.

## Model Loading And Ensemble Audit

Registry:

- `logistic`, `random_forest`, `xgboost`, `lightgbm`, and `catboost` are active.
- All are version `20260604`.
- All are feature version `v1`.
- All report 25,243 training samples.

Model files exist in `wcip-backend/models/`.

Observed local shell behavior:

- Logistic Regression and Random Forest loaded.
- XGBoost, LightGBM, and CatBoost failed to import in the shell used for the
  endpoint probe because the packages were unavailable to that interpreter.
- sklearn emitted pickle-version warnings: model files were created with
  scikit-learn 1.9.0 while the shell had scikit-learn 1.8.0.

Risk:

- Ensemble output can silently use fewer than five ML models if optional packages
  are missing.
- Expanded features will break old pickles unless prediction code gates by
  feature version or models are retrained.

## Tournament Simulation Audit

Current WC2026 simulation:

- Uses `get_qualified_teams_from_db()`.
- Builds official groups if present.
- Builds a R32 bracket.
- Runs `MonteCarloEngine`.
- Returns `champion`, `final`, `semi`, `quarter`, `round_of_16`,
  `expected_finish`, and champion confidence interval.

Limitations:

- Output is not explicitly normalized for champion probability sum in the API
  response.
- No winner-prediction explanation field.
- No statistical/ML/ensemble probability breakdown.
- No `team_id`, `fifa_code`, `group`, `confederation`, or `fifa_rank` in the
  simulation result.
- Monte Carlo multiprocessing can fall back to one worker in restricted
  environments; this is handled with a warning.

## Frontend Audit

Files inspected:

- `wcip-frontend/lib/api.ts`
- `wcip-frontend/lib/types.ts`
- `wcip-frontend/lib/queries.ts`
- `wcip-frontend/app/wc2026/page.tsx`
- `wcip-frontend/app/world-cup/page.tsx`
- `wcip-frontend/app/tournament/page.tsx`
- `wcip-frontend/app/predict/page.tsx`
- `wcip-frontend/app/dashboard/page.tsx`
- `wcip-frontend/components/champion-chart.tsx`
- `wcip-frontend/components/bracket.tsx`

Working frontend data paths:

- `wc2026Teams()`
- `wc2026Groups()`
- `wc2026Simulate()`
- `simulateTournament()`
- `simulateMatch()`
- `mlPredict()`
- `mlModels()`
- `mlFeatures()`

Missing frontend pieces:

- No API client method for winner predictions.
- No TanStack Query hook for winner predictions.
- No `WorldCupWinnerPrediction` TypeScript type.
- `/wc2026`, `/world-cup`, `/tournament`, `/predict`, and `/dashboard` do not
  display the requested winner-prediction contract.
- Existing charts show champion/round probabilities from simulation, but not
  model comparison, confederation breakdown, top 10 favorites, or dark horses
  from a dedicated winner-prediction endpoint.
- `/dashboard` still says “32 nations,” stale for WC2026.

Frontend error handling:

- Basic error strings exist on prediction pages.
- Retry buttons are missing for the requested winner-prediction flow.
- Technical details are not consistently restricted to development mode.

## 500 Error Risk Audit

Potential unhandled or weakly handled errors:

- Missing ranking snapshot returns 404 for latest ranking, but frontend has no
  ranking-specific empty state.
- `ml_predict` catches all prediction errors and returns a plain 500 string.
- Global backend exception handler returns only `{"detail": "Internal server error"}`.
- Error payloads do not include `status_code`, `error_code`, `message`,
  `detail`, and `request_id`.
- Ranking refresh failures are logged by background tasks but not exposed through
  a source log table.
- Missing optional ML packages reduce model coverage and may surprise users.
- Invalid or empty WC2026 dataset raises 503 in simulation.
- Very high simulation counts are constrained by schema, but worker/sandbox
  process limits can still force fallback behavior.

## Implementation Priorities

1. Add source-log/ranking compatibility tables without replacing the existing
   `fifa_ranking_snapshots` architecture.
2. Add legal CSV-based player rating ingestion with version/source tracking.
3. Expand player-strength feature generation with safe fallback behavior and a
   new feature version.
4. Add a winner-prediction service and endpoint that enriches Monte Carlo output
   with team metadata, FIFA ranks, model/stat/ensemble fields, normalized
   probabilities, confidence intervals, and explanation text.
5. Add structured error responses with request IDs.
6. Add frontend API types/hooks and winner-prediction sections to requested
   pages.
7. Update documentation and tests.

## Post-Remediation Addendum

Updated after implementation on 2026-06-12.

### Official FIFA Ranking Status

Official source:

- `https://inside.fifa.com/fifa-world-ranking/men`
- FIFA page status observed: just updated on 2026-06-11; next official update
  2026-07-20.
- Official FIFA API snapshot fetched through the project extractor:
  `FRS_Male_Football_20260401`, ranking date `2026-06-11`, 211 entries.

Official top 10 loaded from FIFA:

| Official Rank | Team | Points |
|---:|---|---:|
| 1 | Argentina | 1877.27 |
| 2 | Spain | 1874.71 |
| 3 | France | 1870.70 |
| 4 | England | 1828.02 |
| 5 | Portugal | 1767.85 |
| 6 | Brazil | 1765.86 |
| 7 | Morocco | 1755.10 |
| 8 | Netherlands | 1753.57 |
| 9 | Belgium | 1742.24 |
| 10 | Germany | 1735.77 |

### Discrepancies Resolved

Before remediation, the local `teams.fifa_rank` display cache showed Brazil as
rank #1 and the versioned ranking tables were empty. After loading the official
snapshot:

| Store | Before | After |
|---|---:|---:|
| `fifa_ranking_snapshots` | 0 | 1 |
| `fifa_ranking_entries` | 0 | 211 |
| `team_rankings` | 0 | 211 |
| `ranking_source_logs` | 0 | 1 |
| Brazil rank in `teams` | 1 | 6 |
| Argentina rank in `teams` | 3 | 1 |

The current local top 10 now matches the official snapshot:

1. Argentina
2. Spain
3. France
4. England
5. Portugal
6. Brazil
7. Morocco
8. Netherlands
9. Belgium
10. Germany

### Implementation Completed

- Added Alembic migration
  `wcip-backend/alembic/versions/73b2e6b46c21_add_prediction_data_quality_tables.py`.
- Added `team_rankings` and `ranking_source_logs`.
- Added player-rating import tables and player rating fields.
- Added CSV-only legal player-rating ingestion in
  `wcip-backend/etl/player_ratings/csv_import.py`.
- Expanded active feature generation to v2 with 33 features and v1 model
  compatibility slicing.
- Added `GET /api/v1/world-cup/2026/winner-predictions` and compatibility alias
  `GET /api/v1/world_cup/2026/winner-predictions`.
- Added frontend API types, query hook, and `WinnerPredictionsSection` on
  dashboard, tournament, predict, WC2026, and world-cup pages.
- Added structured backend error envelopes with request IDs.
- Removed the frontend production-build dependency on Google Fonts fetches by
  using local system font variables.

### Prediction Impact Check

After ranking refresh, the winner-prediction endpoint returns Brazil with
`fifa_rank: 6`, no longer #1. A 100-run smoke test with seed `7` returned 48
teams, champion probabilities summing to 100%, and this top five:

| Rank | Team | Champion % | FIFA Rank |
|---:|---|---:|---:|
| 1 | Brazil | 20.04 | 6 |
| 2 | Argentina | 12.50 | 1 |
| 3 | Spain | 7.89 | 2 |
| 4 | Netherlands | 6.13 | 8 |
| 5 | Portugal | 5.01 | 5 |

Brazil remains a tournament favorite in that smoke test because the tournament
model also uses Elo, group/bracket path, and Monte Carlo outcomes. That is now a
model result, not a stale FIFA-rank display bug.

### Remaining Risks

- Legal player-rating CSV data is not yet present at
  `wcip-backend/data/external/ea_player_ratings.csv`, so v2 player-rating
  features use neutral fallbacks.
- Full model retraining was not run after the schema/feature expansion; existing
  v1 model pickles remain active through compatibility slicing until a retrain
  is executed with official snapshots and player-rating data loaded.
- Historical FIFA ranking backfill before the latest snapshot is still needed
  for complete point-in-time training coverage.
- Next.js still warns about multiple lockfiles and the deprecated middleware
  convention, though production build passes.
