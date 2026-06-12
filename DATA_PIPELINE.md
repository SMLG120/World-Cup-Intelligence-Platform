# Data Pipeline — World Cup Intelligence Platform

---

## Overview

The ETL pipeline transforms raw international football data from four source
families into clean, deduplicated, validated tables that power the statistical
prediction engine, feature engineering, and ML training pipeline.

```
Data Sources
     │
     ├─ martj42 CSV      (49K+ matches since 1872)
     ├─ eloratings.net   (current team Elo ratings)
     ├─ FIFA rankings    (versioned men’s ranking snapshots)
     ├─ player ratings   (legal-source CSV, optional)
     └─ football-data.org API  (squad data, optional)
     │
     ▼
Extract  ──── data/cache/  (local disk cache)
     │
     ▼
Transform  (name normalisation + outcome labels)
     │
     ▼
Validate   (schema + business rules)
     │
     ▼
Load  ──── match_results (49,306 local rows observed during audit)
      │    teams.elo (updated)
      │    fifa_ranking_snapshots / fifa_ranking_entries (historical)
      │    team_rankings / ranking_source_logs (traceability)
      │    teams.fifa_rank (current display cache)
      │    qualified_teams (48 WC2026 teams)
      │    players / coaches / player_rating_* (when source data is set)
      │
      ▼
Feature Engineering  ──── match_features (pre-computed)
      │                    or real-time in build_feature_vector()
      ▼
ML Training
      │
      ├─ v2 feature matrix (33 features, 25K+ rows from 2000+)
      ├─ Time-series cross-validation (5 folds)
      ├─ 5 models trained + evaluated
      └─ models/*.pkl + ml_models registry
      │
      ▼
Prediction Service
      │
      ├─ Statistical (Elo + Poisson)
      ├─ ML (5 models, lru_cache loaded)
      └─ Ensemble (30/70 weighted)
      │
      ▼
Tournament Simulator  (Monte Carlo, parallel)
      │
      ▼
API Response / Frontend
```

---

## Source 1: International Football Results (martj42)

### Source Details
- **URL:** `https://raw.githubusercontent.com/martj42/international_results/master/results.csv`
- **License:** CC BY-SA 4.0 — attribution required, share-alike on derivative datasets
- **Coverage:** All international results since 30 November 1872
- **Size:** ~49,000+ completed matches as of mid-2026
- **Format:** CSV with header row

### CSV Schema
```
date,home_team,away_team,home_score,away_score,tournament,city,country,neutral
1872-11-30,Scotland,England,0,4,Friendly,Glasgow,Scotland,FALSE
...
```

`neutral=TRUE` means neither team is the official host (played at a third country or
explicitly neutral venue).

Future/scheduled matches appear with `home_score=NA, away_score=NA` — the ETL skips
these rows.

### Extract Step
**File:** `etl/extract/international_results.py`

```python
fetch_results_csv(force_refresh=False)
```

1. Check `data/cache/results.csv` — return cached if `force_refresh=False`
2. `httpx.get(RESULTS_URL, timeout=60)` with 3 retries
3. On all retries failing, fall back to cached copy if available
4. Write downloaded content to cache file

```python
parse_results(csv_text, since=None)
```

Generator that yields one dict per completed match:
1. Parse ISO date — skip malformed rows
2. Filter `match_date < since` for incremental runs
3. Check `home_score`/`away_score` for NA/empty — skip scheduled matches
4. `int()` conversion with try/except — skip non-numeric scores
5. Yield normalised dict: `{match_date, home_team, away_team, home_goals, away_goals, tournament, city, country, neutral}`

### Transform Step
**File:** `etl/transform/normalize.py`

```python
canonical(name) -> str
```

Maps 60+ team name variants to a single canonical name. Examples:
```
"USA"             → "United States"
"Ivory Coast"     → "Ivory Coast"   (not Côte d'Ivoire)
"Republic of Ireland" → "Ireland"
"South Korea"     → "South Korea"
"Iran"            → "Iran"          (not "IR Iran")
```

```python
normalize_match(raw) -> dict
```

Applies `canonical()` to both team names, strips whitespace, converts `neutral` to bool.

```python
compute_outcome(home_goals, away_goals) -> int
```

Returns: `0` (away win), `1` (draw), `2` (home win).

### Validation Step
**File:** `etl/validation/schema.py`

```python
validate_match(normalized) -> ValidatedMatch
```

Raises `ValidationError` (skips the row) if:
- `home_team` or `away_team` is empty
- `home_goals` or `away_goals` is negative
- Either score exceeds 30 (data integrity check)
- `match_date` is in the future (not yet played)

Up to 10 validation failures are logged at DEBUG level; the pipeline continues.

### Load Step
**File:** `etl/load/db_loader.py`

```python
load_match_results(records, batch_size=500) -> int
```

Idempotent upsert logic:
1. Maintain in-memory `seen` set of `(home_team, away_team, match_date)` tuples
   — prevents duplicate inserts from duplicate CSV rows within the same run
2. For each record: `SELECT EXISTS` from `match_results` on unique constraint
   `(home_team, away_team, match_date)` — skip if already loaded
3. Accumulate `MatchResult` ORM objects; `db.add_all(batch)` + `db.commit()` every 500

**Current local result during the ranking audit:** 49,306 match rows in
`match_results`. Earlier pipeline runs documented 49,304 unique rows after
deduplicating 2 duplicate source rows; always verify with the target database
before publishing model metrics.

### Outcome Distribution in DB
```
home_win:  24,162  (48.2%)
draw:      11,208  (22.3%)
away_win:  13,934  (27.8%)
```

---

## Source 2: World Football Elo Ratings

### Source Details
- **URL:** `https://www.eloratings.net/World.tsv`
- **License:** Public data; attribution appreciated
- **Coverage:** All FIFA-affiliated national teams, current ratings
- **Format:** TSV (tab-separated)

### Extract Step
**File:** `etl/extract/elo_ratings.py`

```python
fetch_elo_ratings(force_refresh=False) -> dict[str, float]
```

1. HTTP fetch from `ELO_URL`
2. Parse TSV using regex fallback if standard tabular parse fails
3. On failure: return `_ELO_FALLBACK` — embedded snapshot of top ~50 teams
   (Argentina 2141, France 2028, England 1977, etc.)
4. Cache to `data/cache/elo_ratings.tsv`

### Load Step
**File:** `etl/pipeline.py :: run_elo_update()`

1. Fetch ratings dict
2. `SELECT * FROM teams`
3. For each team: `canonical(team.name)` lookup in ratings dict
4. Update `team.elo` in place
5. `db.commit()`

---

## Source 3: FIFA Men's World Ranking Snapshots

### Source Details
- **Official page:** `https://inside.fifa.com/fifa-world-ranking/men`
- **Ranking schedule payload:** resolved from FIFA page metadata, then fetched from
  FIFA's ranking schedule API by `rankingScheduleId`
- **Latest verified publication during this audit:** 01 April 2026
- **Next listed FIFA update during this audit:** 11 June 2026
- **Coverage:** FIFA men's national teams, ranks, previous ranks, points, and
  publication metadata

### Extract Step
**File:** `etl/extract/fifa_rankings.py`

```python
fetch_fifa_ranking_snapshot(force_refresh=False) -> RankingSnapshot
```

1. Read the official FIFA ranking page metadata.
2. Resolve the latest men’s ranking schedule id.
3. Fetch the ranking payload for that schedule id.
4. Normalize team names through `canonical()`.
5. Preserve raw FIFA payload fragments in each entry for auditability.
6. Validate minimum entry count, unique ranks, and unique teams.
7. Cache the normalized snapshot at `data/cache/fifa_rankings.json`.

The compatibility wrapper remains available:

```python
fetch_fifa_rankings(force_refresh=False) -> dict[str, int]
```

That wrapper returns `{team_name: rank}` for older call sites, but new code should
use the snapshot function so publication date and source hash are preserved.

### Load Step
**File:** `etl/load/ranking_loader.py`

```python
load_latest_fifa_ranking_snapshot(force_refresh=False) -> dict
load_fifa_ranking_snapshot(snapshot) -> dict
```

1. Upsert one row in `fifa_ranking_snapshots` keyed by FIFA `ranking_id`.
2. Insert one row per team in `fifa_ranking_entries`.
3. Mirror rows into `team_rankings` for provider-agnostic downstream queries.
4. Keep prior ranking publications instead of overwriting them.
5. Mark only the newest snapshot as `is_current=true`.
6. Refresh `teams.fifa_rank` from the newest snapshot as a display/API cache.
7. Write `ranking_source_logs` rows for fetch/load traceability.

`teams.fifa_rank` is not a historical feature source. Historical training and
backtests read `fifa_ranking_entries` through the latest snapshot with
`ranking_date <= match_date`.

### Monitoring Step
**File:** `etl/monitoring/ranking_monitor.py`

```python
check_fifa_ranking_update(force_refresh=True, trigger_retraining=False) -> dict
```

The monitor fetches the official snapshot, compares it to the current stored
snapshot, writes a new historical version if needed, and flags retraining when
ranking changes are material:

- any top-10 movement
- rank delta of at least 5 inside the top 50
- points delta of at least 25

When `trigger_retraining=True`, material ranking updates call
`ml.retrain.run_retrain(model_filter="all")`.

### API Exposure

- `GET /api/v1/rankings/fifa/latest`
- `GET /api/v1/rankings/fifa/snapshots`
- `GET /api/v1/rankings/fifa/snapshots/{ranking_id}`
- `POST /api/v1/rankings/fifa/refresh` (admin)

---

## Source 4: Player Ratings And Form CSV

### Source Details
- **Default path:** `wcip-backend/data/external/ea_player_ratings.csv`
- **Allowed sources:** licensed APIs, public datasets, manually maintained CSV
  files with attribution, or other data you have permission to use
- **Disallowed by policy:** scraping proprietary pages whose terms prohibit it,
  including FotMob, SofaScore, Transfermarkt, Opta, or EA pages unless you have a
  legal data source

### CSV Schema

Supported columns:

```text
player_name,team_name,position,club,age,international_caps,
international_goals,recent_form_score,injured,suspended,minutes_played,
goals,assists,xg,xa,market_value_eur,player_rating,ea_fc_rating
```

### Extract/Load Step
**File:** `etl/player_ratings/csv_import.py`

```python
import_player_ratings_csv(source_path, source_name, source_version)
```

1. Read a CSV file using `csv.DictReader`.
2. Validate required player/team names.
3. Normalize team names through `canonical()`.
4. Validate ratings are in the 0–100 range.
5. Upsert `players` by `team_name + player_name`.
6. Store import metadata in `player_rating_imports`.
7. Store historical row-level values in `player_rating_records`.
8. Remove startup placeholder player rows for teams that receive real imported
   player ratings.

Manual import:

```bash
cd wcip-backend
python -c "from etl.player_ratings import import_player_ratings_csv; print(import_player_ratings_csv('data/external/ea_player_ratings.csv', source_name='manual_csv', source_version='2026-06'))"
```

Pipeline wrapper:

```bash
python -c "from etl.pipeline import run_player_rating_import; print(run_player_rating_import())"
```

If the default file is missing, the wrapper returns a skipped status and leaves
placeholder player records untouched.

---

## Source 5: Football-Data.org API

### Source Details
- **Base URL:** `https://api.football-data.org/v4`
- **License:** Free tier (10 req/min); set `FOOTBALL_DATA_API_KEY` in `.env`
- **Coverage:** Club competitions, international fixtures, squad rosters

### Extract Step
**File:** `etl/extract/football_data.py`

```python
fetch_competition_teams(competition_id) -> list[dict]
fetch_competition_matches(competition_id, season) -> list[dict]
fetch_team_squad(team_id) -> list[dict]
fetch_standings(competition_id) -> dict
```

All functions sleep 6.5s between requests to respect the free-tier rate limit.
3-retry logic with exponential backoff.

### Load Step

```python
load_players(records, team_name, data_source) -> int
```

Upsert by `external_id` (football-data.org team ID) or `(name, team_name)` fallback.
Updates: position, club, age, goals, assists, xG, xAG, minutes_played, key_passes,
progressive passes/carries, tackles, interceptions, cards, injury/suspension status,
market value, international caps/goals, fitness score.

---

## Incremental Loading

### State File
`etl/data/etl_state.json` persists the ETL run history:

```json
{
  "last_results_date": "2026-06-04"
}
```

On incremental runs: `since = last_results_date - 7 days` (7-day overlap catches
retroactive result corrections). On first run or `force_refresh=True`: `since=None`
(full history).

### Triggering

```bash
# Manual incremental
python -c "from etl.pipeline import run_historical_results; run_historical_results()"

# Manual full refresh
python -c "from etl.pipeline import run_historical_results; run_historical_results(force_refresh=True)"

# Full pipeline (results + Elo + rankings + WC2026 seed + optional player ratings)
python -c "from etl.pipeline import run_full_pipeline; run_full_pipeline()"

# Manual FIFA ranking snapshot refresh
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"

# Ranking monitor with optional retraining trigger
python -c "from etl.monitoring.ranking_monitor import check_fifa_ranking_update; print(check_fifa_ranking_update(force_refresh=True, trigger_retraining=True))"

# Admin API (async, admin token required)
curl -X POST /api/v1/ml/etl/run -H "Authorization: Bearer <token>"
```

### Celery Scheduled Jobs
**File:** `etl/schedulers/celery_tasks.py`

| Task | Schedule | Action |
|---|---|---|
| `daily_results_update` | Daily | `run_historical_results()` incremental |
| `weekly_elo_update` | Weekly | `run_elo_update()` from eloratings.net |
| `fifa_rankings_update` | Daily | `check_fifa_ranking_update()` against official FIFA rankings |
| `full_pipeline` | On-demand | `run_full_pipeline()` |

---

## Feature Engineering Pipeline

**File:** `ml/features.py`

Active feature version: `v2`

`v2` keeps the original 17 features first for compatibility with existing
`v1` model files, then appends 16 player-level strength features:

- `average_starting_xi_rating_diff`
- `average_squad_rating_diff`
- `top_5_player_rating_avg_diff`
- `goalkeeper_rating_diff`
- `defensive_unit_rating_diff`
- `midfield_unit_rating_diff`
- `attacking_unit_rating_diff`
- `squad_depth_score_diff`
- `star_player_score_diff`
- `injury_burden_score_diff`
- `player_form_score_diff`
- `player_availability_score_diff`
- `international_experience_score_diff`
- `average_caps_diff`
- `total_international_goals_diff`
- `weighted_player_strength_diff`

### Real-Time (for prediction)

```python
build_feature_vector(home_team, away_team, match_date,
                     home_overrides=None, away_overrides=None) -> FeatureVector
```

Called for every prediction request. Queries the DB for the full 33-feature v2
vector and applies any overrides (from the Player Impact Lab or API request
body).

Override keys accepted: `elo`, `fifa_rank`, `form`, `injury_burden`,
`coach_impact`, `chemistry`, `fitness_score`.

For historical dates, `build_feature_vector()` reads:

- the latest `fifa_ranking_snapshots.ranking_date <= match_date`
- the latest `elo_history.recorded_at <= match_date`
- only match results before `match_date` for form and recent-score features

If a historical ranking or Elo snapshot is missing, the feature falls back to a
neutral value instead of using current data. This prevents current rankings from
leaking into old training rows.

### Batch (for training)

```python
build_feature_matrix_from_db(since_date, max_rows) -> (X, y, match_ids)
```

Queries `match_results` joined with `match_features` (pre-computed) or computes
features on-the-fly for rows not yet in `match_features`. On-the-fly computation
passes each historical match date into `build_feature_vector()` so ranking and
Elo lookups are point-in-time.

Returns:
- `X`: `np.ndarray` of shape `(N, 33)`
- `y`: `np.ndarray` of shape `(N,)` with values 0/1/2
- `match_ids`: list of `match_result.id` values

### Feature Storage

```python
persist_features(home_team, away_team, match_date, feature_vector) -> None
```

Saves the computed feature vector to `match_features` table linked to
`match_result.id`. The table now includes the v2 player feature columns as
well. Subsequent training runs can reuse stored vectors, avoiding recomputation
of historical features.

---

## ML Training Pipeline

**File:** `ml/train.py`

### Entry Point
```bash
python -m ml.train [--model all|logistic|random_forest|xgboost|lightgbm|catboost]
                   [--full-refresh]
```

### Steps

1. **Build matrix**
   ```python
   X, y, ids = build_feature_matrix_from_db(since_date=date(2000, 1, 1))
   # Result: X.shape = (25243, 17), y distribution: {0: 13934, 1: 11208, 2: 24162}
   ```

2. **Import models** (lazy import — avoids slow startup in production)
   ```python
   models = _import_models()
   # Gracefully skips unavailable packages (e.g., CatBoost not installed)
   ```

3. **For each model:**
   ```python
   train_model(name, model, X, y, version)
   ```
   - `time_series_cv_split(X, n_splits=5, test_size=0.1)` — expanding window
   - For each fold: fit on train slice, `predict_proba` on test slice
   - Compute: accuracy, F1 (macro), Brier score, log-loss, ECE calibration
   - Log per-fold metrics
   - Final fit on all data
   - `save_model(name, model, version)` → `models/{name}.pkl` (joblib pickle)
   - `register_model(name, model, metrics, version)` → `ml_models` upsert

4. **Update ensemble weights**
   ```python
   _update_ensemble_weights()
   ```
   Reads all `is_active=True` models from DB, computes `w_i = 1/ll_i`, normalises
   to sum to 1, writes back to `ml_models.ensemble_weight`.

### Time-Series CV Logic

```python
time_series_cv_split(X, n_splits=5, test_size=0.1)
```

Yields `(train_idx, test_idx)` pairs:
- Fold 0: train on [0, 80%), test on [80%, 90%)
- Fold 1: train on [0, 82%), test on [82%, 92%)
- Fold 2: train on [0, 84%), test on [84%, 94%)
- Fold 3: train on [0, 86%), test on [86%, 96%)
- Fold 4: train on [0, 88%), test on [88%, 100%)

Each test set is a strictly future slice of the training data. The model never
sees a match before training on it.

---

## Data Quality Controls

| Check | Where | Action |
|---|---|---|
| NA / empty scores | `parse_results()` | Skip row |
| Non-numeric scores | `parse_results()` | Skip row |
| Negative goals | `validate_match()` | Skip row, log |
| Score > 30 | `validate_match()` | Skip row, log |
| Future match date | `validate_match()` | Skip row |
| Duplicate (home, away, date) in same run | `load_match_results()` | Skip (in-memory set) |
| Duplicate (home, away, date) in DB | `load_match_results()` | Skip (SELECT EXISTS) |
| DB-level enforcement | `match_results` table | `UniqueConstraint("home_team","away_team","match_date")` |
| Team name variants | `canonical()` | Map to canonical (60+ variants) |
| FIFA ranking snapshot size | `validate_ranking_snapshot()` | Reject too-small snapshots |
| FIFA rank/team duplicates | `validate_ranking_snapshot()` | Reject duplicate rank or team keys |
| Historical ranking leakage | `build_feature_vector()` | Use snapshot date <= match date or neutral fallback |

---

## Data Lineage

```
results.csv (CC BY-SA 4.0)
    ↓  parse_results() + normalize_match() + validate_match()
    ↓  load_match_results()
match_results (49,306 local rows observed during audit)
    ↓  build_feature_matrix_from_db(since=2000-01-01)
fifa_ranking_snapshots / fifa_ranking_entries
    ↓  point-in-time ranking lookup
    ↓  [33 features × 25K+ rows from 2000+]
ML training (5 models)
    ↓  models/logistic.pkl
    ↓  models/random_forest.pkl
    ↓  models/xgboost.pkl
    ↓  models/lightgbm.pkl
    ↓  models/catboost.pkl
    ↓  ml_models registry (metrics + weights)
predict_hybrid(home, away)
    ↓  build_feature_vector()    → [17 floats]
    ↓  predict_all_models()      → {logistic: {...}, rf: {...}, ...}
    ↓  statistical layer         → Elo/Poisson probabilities
    ↓  ensemble calculation      → weighted blend
    ↓  SHAP explanation          → top factors + narrative
API response
```

### Winner Prediction Lineage

```
qualified_teams + teams + fifa_ranking snapshots + players/coaches
    ↓  app/services/winner_predictions.py
MonteCarloEngine  → statistical champion probability
player/ranking/Elo strength score → ML-style team strength probability
    ↓
normalized ensemble champion probability
    ↓
GET /api/v1/world-cup/2026/winner-predictions
    ↓
WinnerPredictionsSection charts and table
```

---

## Known Limitations

1. **xG proxy:** The `xg_diff` and `xga_diff` features are computed from actual goals
   scored/conceded in `match_results`, not from shot-level expected goals data.
   StatsBomb Open Data would provide true xG but is not yet integrated.

2. **Player table sparsity:** Without a `FOOTBALL_DATA_API_KEY`, features 7–11 and
   15–16 default to 0. This reduces signal for squad depth, injury burden, and
   market value dimensions.

3. **No intra-tournament form updates:** Once a tournament starts, ETL would need
   to run after each matchday to update form features for knockout-round predictions.
   Celery daily_results_update handles this if running.

4. **Name normalization completeness:** The `NAME_MAP` dict covers 60+ variants.
   Teams that appear in the CSV under an unrecognised spelling will be stored under
   their raw name rather than the canonical form. This is non-destructive but may
   split a team's history across two keys.

5. **Historical ranking backfill:** The snapshot pipeline preserves all new FIFA
   ranking publications going forward. Older FIFA ranking publications must still
   be backfilled if you want non-neutral `fifa_rank_diff` for pre-ingestion
   training periods.

6. **Elo history backfill:** `teams.elo` is current-state data. Historical feature
   generation reads `elo_history` when available and otherwise uses neutral Elo
   for past matches, so old rows are not contaminated by today’s ratings.
