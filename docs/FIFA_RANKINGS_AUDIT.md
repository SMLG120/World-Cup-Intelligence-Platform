# FIFA Rankings Audit

Audit date: 2026-06-08

## Official Ranking Status

Official FIFA sources checked:

- FIFA men's ranking page: `https://inside.fifa.com/fifa-world-ranking/men`
- FIFA April 2026 ranking article:
  `https://inside.fifa.com/fifa-world-ranking/men/news/france-1st-fifa-coca-cola-world-ranking-april-2026`

Latest official status observed during the audit:

- Latest published men's ranking update: **2026-04-01**
- Next listed update: **2026-06-11**
- Official #1: **France**
- Other explicitly verified official positions from FIFA's April 2026 article:
  Spain #2, Argentina #3, Portugal #5, Brazil #6

## Local Ranking Discrepancies

The local application had multiple ranking states before this fix.

### Local Database

Query:

```sql
SELECT name, fifa_rank FROM teams ORDER BY fifa_rank LIMIT 15;
```

Observed top rows:

| Local DB Rank | Team |
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

### Local Cache

File: `wcip-backend/data/cache/fifa_rankings.json`

Observed top rows:

| Cache Rank | Team |
|---:|---|
| 1 | Argentina |
| 2 | France |
| 3 | England |
| 4 | Belgium |
| 5 | Brazil |
| 6 | Portugal |
| 7 | Netherlands |
| 8 | Spain |
| 9 | Italy |
| 10 | Croatia |

### Discrepancy Table

| Team | Official FIFA Rank | Local DB Rank | Local Cache Rank | Status |
|---|---:|---:|---:|---|
| France | 1 | 4 | 2 | DB and cache stale |
| Spain | 2 | 7 | 8 | DB and cache stale |
| Argentina | 3 | 3 | 1 | Cache stale |
| Portugal | 5 | 9 | 6 | DB and cache stale |
| Brazil | 6 | 1 | 5 | DB and cache stale; app incorrectly showed Brazil #1 |

Conclusion: the application could not trust `teams.fifa_rank` or the cached JSON
as the source of truth. Rankings were manually maintained/stale and inconsistent.

## Root Cause

Before this audit, ranking ingestion was not production-grade:

- `teams.fifa_rank` acted as both current UI field and historical feature source.
- The ranking cache could disagree with the database.
- Historical training generated `fifa_rank_diff` from current team rows, which
  risked leaking current ranking information into old matches.
- Ranking updates overwrote current values rather than preserving publication
  snapshots.

## Architecture Changes Implemented

### Versioned Ranking Storage

Added migration:

- `wcip-backend/alembic/versions/3f8b9d9c2a11_add_fifa_ranking_snapshots.py`

New tables:

- `fifa_ranking_snapshots`
- `fifa_ranking_entries`

Each snapshot preserves:

- FIFA ranking schedule id
- ranking date
- published timestamp
- next update timestamp
- source URL
- source hash
- current snapshot flag
- per-team rank, previous rank, movement, points, previous points, and raw source
  payload fragment

Older snapshots are preserved. The latest snapshot refreshes `teams.fifa_rank`
only as a display/API cache.

### ETL Changes

Files:

- `wcip-backend/etl/extract/fifa_rankings.py`
- `wcip-backend/etl/load/ranking_loader.py`
- `wcip-backend/etl/pipeline.py`

The new ETL flow:

1. Read FIFA ranking page metadata.
2. Resolve the latest men's ranking schedule id.
3. Fetch the schedule-specific ranking payload.
4. Normalize team names.
5. Validate snapshot quality.
6. Store the ranking as an immutable snapshot.
7. Update `teams.fifa_rank` for current display only.

Manual command:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"
```

### Monitoring And Retraining Trigger

Files:

- `wcip-backend/etl/monitoring/ranking_monitor.py`
- `wcip-backend/etl/schedulers/celery_tasks.py`
- `wcip-backend/app/workers/celery_app.py`

The monitor checks official rankings, stores changed snapshots, logs movement,
and marks updates as material when any of these thresholds are crossed:

- top-10 movement
- rank delta of at least 5 inside the top 50
- points delta of at least 25

Material ranking changes can trigger:

```python
ml.retrain.run_retrain(model_filter="all")
```

### API Changes

Files:

- `wcip-backend/app/api/v1/rankings.py`
- `wcip-backend/app/api/v1/router.py`
- `API.md`

New endpoints:

- `GET /api/v1/rankings/fifa/latest`
- `GET /api/v1/rankings/fifa/snapshots`
- `GET /api/v1/rankings/fifa/snapshots/{ranking_id}`
- `POST /api/v1/rankings/fifa/refresh`

### ML And Feature Engineering Changes

Files:

- `wcip-backend/ml/features.py`
- `wcip-backend/app/api/v1/ml.py`
- `wcip-backend/tests/test_fifa_rankings.py`

Implemented safeguards:

- `fifa_rank_diff` now uses the latest stored ranking snapshot with
  `ranking_date <= match_date`.
- Historical Elo now uses `elo_history.recorded_at <= match_date`.
- If a historical FIFA ranking or Elo snapshot is missing, the feature uses a
  neutral value rather than today's value.
- API overrides now allow `fifa_rank` for explicit scenario testing.
- Tests cover snapshot storage, API exposure, historical ranking lookup, and
  future-ranking leakage prevention.

## Prediction Impact

The local Brazil-vs-France current ranking feature changed materially:

| Source | Brazil Rank | France Rank | Brazil Home `fifa_rank_diff` |
|---|---:|---:|---:|
| Local DB before fix | 1 | 4 | +3 |
| Official FIFA April 2026 | 6 | 1 | -5 |

That is an 8-rank swing and a sign flip. Any ML model that uses
`fifa_rank_diff` can shift probabilities once official snapshots are loaded and
the model is retrained.

### Sample Prediction Delta

Local command run against `wcip-backend/wcip.db`:

```bash
env DEBUG=false DATABASE_URL=sqlite:///./wcip.db /usr/local/bin/python3 - <<'PY'
from ml.ensemble import predict_hybrid

base = predict_hybrid("Brazil", "France", include_shap=False)
official = predict_hybrid(
    "Brazil",
    "France",
    home_overrides={"fifa_rank": 6},
    away_overrides={"fifa_rank": 1},
    include_shap=False,
)
print(base.to_dict()["ensemble"])
print(official.to_dict()["ensemble"])
PY
```

Observed output:

| Scenario | Home Win | Draw | Away Win | xG | Expected Scoreline |
|---|---:|---:|---:|---|---|
| Local stale DB ranking | 56.41% | 23.73% | 19.86% | Brazil 1.719, France 0.981 | Brazil 2 - 1 France |
| Official rank override | 54.37% | 24.27% | 21.35% | Brazil 1.719, France 0.981 | Brazil 2 - 1 France |
| Delta | -2.04 pp | +0.54 pp | +1.49 pp | unchanged | unchanged |

Interpretation: FIFA rank changes affect ML/ensemble inputs. The statistical
scoreline layer and expected goals did not change in this sample because that
layer uses Elo/Poisson inputs, not FIFA rank. This local run loaded Logistic
Regression and Random Forest; XGBoost, LightGBM, and CatBoost were unavailable
in the shell used for the audit, and sklearn emitted pickle-version warnings.
Use this as a directional impact check, not as a final recalibration result.

Local persistence status during the audit:

- `match_features`: 0 persisted rows in the local DB
- `match_results`: 49,306 local rows observed in the current DB
- `ml_models`: 5 active model records trained on 2026-06-04
- Training matrix after leakage guardrail: 25,245 rows, 17 features
- `fifa_rank_diff` in the regenerated historical matrix was neutral because no
  historical FIFA ranking snapshots had been loaded locally yet

Champion probabilities and full tournament simulations were not recalibrated in
this audit because the environment did not complete a live official snapshot
load and all-model retraining run. The code path is now in place; the next
production step is to ingest official snapshots, backfill historical ranking
snapshots where possible, install the full ML dependency set, and run:

```bash
cd wcip-backend
python -m ml.train --model all --full-refresh
```

## Files Modified Or Added

Source and migrations:

- `wcip-backend/app/models/ranking.py`
- `wcip-backend/app/models/__init__.py`
- `wcip-backend/alembic/versions/3f8b9d9c2a11_add_fifa_ranking_snapshots.py`
- `wcip-backend/etl/extract/fifa_rankings.py`
- `wcip-backend/etl/load/ranking_loader.py`
- `wcip-backend/etl/monitoring/__init__.py`
- `wcip-backend/etl/monitoring/ranking_monitor.py`
- `wcip-backend/etl/pipeline.py`
- `wcip-backend/etl/schedulers/celery_tasks.py`
- `wcip-backend/app/workers/celery_app.py`
- `wcip-backend/app/api/v1/rankings.py`
- `wcip-backend/app/api/v1/router.py`
- `wcip-backend/ml/features.py`
- `wcip-backend/app/api/v1/ml.py`
- `wcip-backend/tests/test_fifa_rankings.py`

Documentation:

- `README.md`
- `DATA_PIPELINE.md`
- `MODEL_CARD.md`
- `REPO_CHECKLIST.md`
- `ARCHITECTURE.md`
- `API.md`
- `FIFA_RANKINGS_AUDIT.md`
- `projects/-Users-smlgmac-Desktop-Projects-World-cup-Predictor/memory/MEMORY.md`
- `projects/-Users-smlgmac-Desktop-Projects-World-cup-Predictor/memory/etl_data_sources.md`
- `projects/-Users-smlgmac-Desktop-Projects-World-cup-Predictor/memory/project_architecture.md`
- `projects/-Users-smlgmac-Desktop-Projects-World-cup-Predictor/memory/ml_model_registry.md`

## Verification

Targeted tests:

```bash
cd wcip-backend
env DEBUG=false pytest -q tests/test_fifa_rankings.py tests/test_api.py
```

Result: 18 passed.

Full backend test suite:

```bash
cd wcip-backend
env DEBUG=false pytest -q
```

Result: 26 passed.

## Remaining Risks

- Historical FIFA ranking snapshots still need to be backfilled. Until then,
  older training rows use neutral ranking values by design.
- Elo history also needs a complete backfill for fully point-in-time Elo
  training features.
- The current local `teams.fifa_rank` values remain stale until the first
  official snapshot refresh is run against the target database.
- The existing `v20260604` model records are baseline models and should be
  retrained after official ranking snapshots are loaded.
- The FIFA page payload structure can change. The extractor validates snapshots,
  but production monitoring should alert on repeated fetch or validation failures.
