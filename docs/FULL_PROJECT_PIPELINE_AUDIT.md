# Full Project Pipeline Audit
**World Cup Intelligence Platform (WCIP)**
**Date:** 2026-06-13
**Auditor:** Principal Engineering Review

---

## 1. Project Structure

```
World cup Predictor/
├── wcip-backend/           FastAPI backend (Python 3.14, SQLite/PostgreSQL)
│   ├── app/                FastAPI application
│   │   ├── api/v1/         API endpoints
│   │   ├── core/           Config, cache, security
│   │   ├── db/             SQLAlchemy session/base
│   │   ├── models/         ORM models
│   │   ├── repositories/   Data access layer
│   │   ├── schemas/        Pydantic schemas
│   │   ├── services/       Business logic
│   │   └── workers/        Celery tasks
│   ├── etl/                Extract-Transform-Load pipelines
│   │   ├── elo/            Elo ETL (extract/transform/load/validate)
│   │   ├── fifa_rankings/  FIFA ranking ETL
│   │   ├── players/        Player data ETL
│   │   ├── schedulers/     Celery-scheduled ETL tasks
│   │   └── world_cup_2026/ WC2026 seed data ingest
│   ├── ml/                 Machine learning pipeline
│   │   ├── features.py     Feature engineering (33-feature vector)
│   │   ├── train.py        Training pipeline (5 models + CV)
│   │   ├── evaluate.py     Model evaluation metrics
│   │   ├── ensemble.py     Ensemble weighting
│   │   ├── predict.py      Inference
│   │   ├── retrain.py      Full retraining
│   │   ├── retrain_if_needed.py  Threshold-based retrain check
│   │   └── validate_features.py  Feature validation
│   ├── wcip/               Core engine
│   │   ├── engine/         Match + tournament simulation
│   │   │   ├── elo.py      Elo calculation
│   │   │   ├── match.py    Match simulator
│   │   │   ├── montecarlo.py  Monte Carlo engine
│   │   │   ├── scoreline.py   Poisson scoreline model
│   │   │   └── tournament.py  Tournament bracket engine
│   │   └── data/           Static seed data (teams, 2026 qualifiers)
│   └── models/             Saved ML model pickles (5 models)
└── wcip-frontend/          Next.js 14 (App Router) frontend
    ├── app/                Pages (App Router)
    ├── components/         Shared components
    └── lib/                API client, queries, types
```

---

## 2. Backend Audit

### 2.1 Backend Startup
**Status: WORKING**
- `app/main.py` has a clean `lifespan` startup that calls `init_db()` and logs diagnostics.
- Error handlers cover HTTP, validation, and unhandled exceptions.
- CORS, rate limiting, and request ID middleware are in place.
- SQLite and PostgreSQL supported via `DATABASE_URL`.

### 2.2 Database Models
**Status: WORKING**

| Model | Table | Notes |
|-------|-------|-------|
| Team | teams | Stores elo, fifa_rank, attack, defence, chemistry, coach_quality |
| EloHistory | elo_history | Per-match Elo history (in-game Elo tracking) |
| EloRatingSnapshot | elo_rating_snapshots | Versioned Elo ingestion snapshots |
| TeamEloRating | team_elo_ratings | Per-team rating within a snapshot |
| EloSourceLog | elo_source_logs | Fetch/load audit trail |
| FifaRankingSnapshot | fifa_ranking_snapshots | Versioned FIFA ranking snapshots |
| FifaRankingEntry | fifa_ranking_entries | Per-team entry in a FIFA snapshot |
| TeamRanking | team_rankings | Provider-agnostic ranking compat table |
| RankingSourceLog | ranking_source_logs | Fetch/load audit trail |
| Player | players | Squad members with stats, ratings, injury status |
| Coach | coaches | Team coach metadata |
| MatchResult | match_results | Historical match outcomes for training |
| QualifiedTeam | qualified_teams | 2026 qualifiers with group assignment |
| MLModelRecord | ml_model_records | Trained model versions and metrics |
| MatchFeatures | match_features | Persisted feature vectors |

### 2.3 Alembic Migrations
**Status: WORKING**
- 4 migrations present: initial schema, FIFA ranking snapshots, prediction data quality tables, real-time Elo and refresh metadata.
- `init_db()` uses SQLAlchemy `create_all` for dev + idempotency.

### 2.4 Elo Rating Pipeline
**Status: WORKING (ETL), PARTIALLY BROKEN (frontend visibility)**

**What works:**
- `etl/elo/extract_elo.py` fetches from `eloratings.net/World.tsv` (TSV fallback) with HTML parser for the WC2026 page.
- `etl/elo/load_elo.py` persists `EloRatingSnapshot` + `TeamEloRating` records.
- `_update_team_display_elo()` updates `team.elo` field when a new snapshot becomes current.
- `EloSourceLog` records fetch/load audit trail.
- Celery beat schedule: `refresh-elo-ratings-daily` runs every 24h.
- `/ratings/elo/latest` returns the current snapshot correctly.
- `/ratings/elo/history/{team_id}` returns per-team history.

**What is broken:**
- The `/world-cup/qualified-teams` endpoint returns `QualifiedTeam` objects which do NOT include `elo_rating` or `fifa_rank`.
- The `/world-cup` page uses `useWC2026Teams()` which calls this endpoint — so Elo is NEVER shown in the teams tab.
- The `DataFreshnessStrip` shows last Elo update timestamp, but individual team Elo values are invisible in team listings.

**Root cause:** The API for qualified teams was designed as a qualification-status endpoint, not a ratings endpoint. It was never wired to merge the current Elo snapshot.

### 2.5 FIFA Ranking Pipeline
**Status: WORKING (ETL), PARTIALLY BROKEN (frontend)**

**What works:**
- `etl/fifa_rankings/` has extract/transform/load/validate modules.
- Snapshot versioning and source logs in place.
- Celery beat: `check-fifa-rankings-daily` runs every 24h.
- `get_data_freshness()` reports `last_fifa_ranking_date`.

**What is broken:**
- Same as Elo: `QualifiedTeam` response doesn't include `fifa_rank`.
- The FIFA ranking source requires HTTP parsing; robot restrictions may block automated fetches in production.

### 2.6 Player Data Pipeline
**Status: INCOMPLETE**

**What exists:**
- `etl/players/csv_import.py` — can import players from a CSV.
- `etl/player_ratings/csv_import.py` — imports player ratings from a CSV.
- `etl/players/profiles.py` — player profile management.
- Celery beat: `refresh-player-availability-daily` runs daily.
- `ml/features.py` has 16 player-derived features (positions, ratings, form, etc.).

**What is missing/broken:**
- No real player data is imported. The `players` table is empty for most teams.
- All player features default to neutral values (70.0 ratings, 0 caps, etc.).
- No automated source — the CSV import requires a file to be placed manually.
- The player features have zero effect on predictions because all teams default to the same neutral values.

**Recommended fix:** Import player data via StatsBomb Open Data, FIFA API, or place a seeded CSV.

### 2.7 Match Results Data
**Status: WORKING (ETL exists), DATA SPARSE**

- `etl/extract/international_results.py` ingests historical results.
- `etl/extract/football_data.py` fetches from Football-Data.org if API key present.
- Data sparsity: the DB may have few or no training rows without running the full ETL.

### 2.8 ML Feature Engineering
**Status: WORKING (code), LIMITED (by missing data)**

- `ml/features.py` computes 33 features: elo_diff, fifa_rank_diff, xg, form, squad stats, coach, chemistry, travel, 16 player features.
- Feature vector is deterministic for a given snapshot.
- Missing data is handled with logged fallbacks.
- Historical point-in-time Elo and FIFA rankings are used for training rows to prevent data leakage.

**Limitation:** Player features default to neutral (70.0) for all teams since no player data is imported. This means features 17–32 contribute no real signal.

### 2.9 ML Training
**Status: WORKING (code), STALE (models)**

- `ml/train.py` trains Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost.
- Time-series CV (expanding window, 5 splits) prevents data leakage.
- Metrics: accuracy, F1, Brier score, log loss, ECE.
- Models saved as pickle files in `models/` directory.
- `MLModelRecord` in DB tracks version, metrics, ensemble weight, calibration status.
- `_update_ensemble_weights()` normalizes weights via inverse log-loss.

**Not working:**
- Retraining is not automatically triggered after ETL updates (manual only).

### 2.10 ML Inference and Ensemble
**Status: WORKING**

- `ml/predict.py` runs inference with all trained models.
- `ml/ensemble.py` combines predictions using DB-stored weights.
- `/ml/predict` endpoint returns statistical + individual ML + ensemble predictions.
- `/ml/models` endpoint returns all model records with metrics.

### 2.11 Automated ML Retraining
**Status: PARTIALLY IMPLEMENTED**

- `ml/retrain_if_needed.py` evaluates retraining thresholds (≥5 FIFA changes → recalibrate; ≥100 player changes → retrain).
- **NOT wired:** Celery ETL tasks do not call `retrain_if_needed` after completing. The threshold check is only run manually.

### 2.12 Tournament Simulator
**Status: WORKING**

- `wcip/engine/tournament.py` — `TournamentEngine` handles group stage (48 teams, 12 groups, FIFA rules for best 3rd place) and full knockout bracket.
- `wcip/engine/montecarlo.py` — `MonteCarloEngine` runs N parallel simulations and aggregates per-team probabilities with Wilson CIs.
- `wcip/engine/match.py` + `wcip/engine/scoreline.py` — Poisson match model parameterized by Elo.
- Returns: champion, final, semi, quarter, r16, r32 probabilities + expected finish.

**Original gap found during audit:**
- Simulated group tables (P/W/D/L/GF/GA/GD per group) were not returned.
- Group qualification probability per team per group was not shown.
- A concrete replayable knockout bracket and third-place match were not exposed.

**Post-audit implementation:**
- `POST /world-cup/simulate` and `POST /world_cup/2026/simulate` now return
  aggregate probabilities plus a replayable tournament path with group tables,
  best third-place standings, knockout matches, champion, runner-up, and third
  place.

### 2.13 World Cup 2026 API
**Status: WORKING**

- `GET /world-cup/qualified-teams` — returns confirmed qualifiers.
- `GET /world-cup/groups` — group draw status and assignments.
- `GET /world-cup/bracket` — bracket slot assignments.
- `POST /world-cup/simulate` — full Monte Carlo simulation.
- `GET /world-cup/2026/winner-predictions` — ranked winner predictions.
- `GET /world-cup/2026/predictions` — full prediction bundle with freshness.
- `GET /world-cup/schedule` — fixture/schedule metadata.
- `GET /world-cup/teams/{team_name}` — team detail with squad stats.

### 2.14 Data Freshness API
**Status: WORKING**

- `GET /data/freshness` returns timestamps for all data sources.
- Used by `DataFreshnessStrip` component in frontend.

### 2.15 Saved Simulations
**Status: WORKING**

- `POST /simulations`, `GET /simulations`, `GET /simulations/{id}`, `DELETE /simulations/{id}`, `POST /simulations/{id}/duplicate`, `POST /simulations/{id}/compare` all implemented.
- Per-user access control enforced.

### 2.16 Admin Endpoints
**Status: WORKING**

- `POST /admin/data/refresh-all` → triggers all ETL.
- `POST /admin/data/refresh-elo` → triggers Elo ETL.
- `POST /admin/data/refresh-fifa-rankings` → triggers FIFA ETL.
- Admin-only via `require_admin` dependency.

---

## 3. Frontend Audit

### 3.1 Frontend Routes

| Route | File | Status | Notes |
|-------|------|--------|-------|
| `/` | app/page.tsx | Working | Home/landing |
| `/world-cup` | app/world-cup/page.tsx | **BEST** | Full WC2026 dashboard — teams, groups, simulation |
| `/wc2026` | app/wc2026/page.tsx | **DUPLICATE** | Older WC2026 page — same features, less polished. Should redirect. |
| `/simulate` | app/simulate/page.tsx | **DUPLICATE** | WC2026 simulation only — duplicates `/world-cup` simulation tab |
| `/tournament` | app/tournament/page.tsx | **LEGACY** | Runs 2022 edition. Should be WC2026 or redirected. |
| `/predict` | app/predict/page.tsx | Working | Single-match predictor with stat + ML + ensemble |
| `/compare` | app/compare/page.tsx | Unknown | Scenario compare |
| `/scenarios` | app/scenarios/page.tsx | Unknown | Scenario lab |
| `/explain` | app/explain/page.tsx | Unknown | Match explanation |
| `/models` | app/models/page.tsx | Working | ML model dashboard |
| `/player-lab` | app/player-lab/page.tsx | Working | Player impact lab |
| `/teams` | app/teams/page.tsx | Working | Team listing |
| `/team/[id]` | app/team/[id]/page.tsx | Working | Team detail |
| `/player/[id]` | app/player/[id]/page.tsx | Working | Player detail |
| `/saved` | app/saved/page.tsx | Working | Saved simulations |
| `/admin` | app/admin/page.tsx | Working | Admin dashboard |

### 3.2 Frontend API Hooks
**Status: WORKING**

- `lib/queries.ts` uses TanStack Query with typed hooks for all backend endpoints.
- `lib/api.ts` has a clean typed `request()` function with token refresh, error handling, and `ApiError` class.
- All major endpoints have typed wrappers: teams, players, simulations, ML, WC2026, ratings, rankings.

### 3.3 Navigation
**Status: PARTIALLY BROKEN**

Current nav links:
```
WC 2026  → /world-cup    ✓ (best WC2026 page)
Predict  → /predict       ✓
Compare  → /compare       ✓
Simulate → /simulate      ✗ (duplicates /world-cup simulation tab)
Scenarios→ /scenarios     ✓
Explain  → /explain       ✓
Models   → /models        ✓
Lab      → /player-lab    ✓
Teams    → /teams         ✓
Saved    → /saved         ✓
```

Problem: "Simulate" in the nav points to `/simulate` which is a duplicate of the simulation tab in `/world-cup`. Users are confused about where to find the main simulation.

### 3.4 Simulation Pages (Duplication Analysis)
**Status: DUPLICATED**

Three pages do the same WC2026 simulation:

1. `/world-cup` (`world-cup/page.tsx`) — **BEST**: Has Champion chart, Round advancement chart, full probability table, teams tab, groups tab.
2. `/simulate` (`simulate/page.tsx`) — **GOOD**: Has Rankings list, Champion histogram, Bracket funnel.
3. `/wc2026` (`wc2026/page.tsx`) — **OLDER**: Simple card-based layout, less polished.
4. `/tournament` (`tournament/page.tsx`) — **LEGACY**: Runs 2022 world cup simulation using old `/tournament/simulate` endpoint.

**Recommendation:** `/world-cup` is the primary experience. `/simulate` should redirect to `/world-cup`. `/wc2026` should redirect to `/world-cup`. `/tournament` should be updated to WC2026 or removed.

### 3.5 Elo Ratings in Frontend
**Status: BROKEN (root cause identified)**

The Elo ratings DO exist in the backend and ARE fetchable via `/ratings/elo/latest`. The problem is that:

1. The team listing on `/world-cup` uses `useWC2026Teams()` which fetches `QualifiedTeam[]`.
2. `QualifiedTeam` only has: `team_name, team_code, confederation, group_label, pot, host_nation, confirmed, qualification_path`.
3. Elo is NOT in `QualifiedTeam`.
4. No page merges the Elo snapshot data with the qualified teams data.

**Fix:** Either (a) add `elo_rating` and `fifa_rank` to the `/world-cup/qualified-teams` response by joining against the current snapshot, or (b) fetch `/ratings/elo/latest` in parallel and merge client-side.

### 3.6 Data Freshness Component
**Status: WORKING**

`DataFreshnessStrip` shows last Elo update, FIFA update, match results, players, model version, and feature version. Admin users see a "Refresh Data" button. This is correctly wired to `useDataFreshness()` which hits `/data/freshness`.

### 3.7 ML Model Dashboard
**Status: WORKING**

`/models` shows active model records, weights, training dates, and metrics.

### 3.8 Bracket Component
**Status: LIMITED**

`components/bracket.tsx` shows an "advancement funnel" probability table, not a true visual bracket. No round-by-round bracket structure is shown. Users cannot see which teams would meet in which round.

---

## 4. What Is Working

- ✅ Backend startup and diagnostics
- ✅ Elo ETL (fetch, parse TSV/HTML, snapshot versioning, team.elo update)
- ✅ FIFA ranking ETL (snapshot versioning, source logs)
- ✅ Tournament simulation engine (48 teams, 12 groups, full knockout)
- ✅ Monte Carlo engine with Wilson CIs and multiprocessing
- ✅ ML training pipeline with time-series CV
- ✅ Ensemble weighting via inverse log-loss
- ✅ Feature engineering pipeline (33 features, point-in-time safe)
- ✅ Data freshness API and frontend strip
- ✅ Saved simulations (CRUD, per-user, duplication, comparison)
- ✅ Single-match prediction (/predict) with stat + ML + ensemble
- ✅ Admin data refresh endpoints
- ✅ Celery beat schedule for ETL tasks
- ✅ Type-safe API client with TanStack Query hooks
- ✅ Auth (JWT, refresh tokens)

---

## 5. What Is Broken

- ❌ Elo ratings not shown in `/world-cup` teams tab (API gap)
- ❌ FIFA rankings not shown in `/world-cup` teams tab (API gap)
- ❌ `/tournament` page runs 2022 simulation, not 2026
- ❌ `/wc2026` page is a stale duplicate of `/world-cup`
- ❌ `/simulate` page duplicates `/world-cup` simulation tab
- ❌ "Simulate" nav link creates confusion (should go to world-cup)
- ❌ ML retraining NOT automatically triggered after ETL updates
- ❌ Player data not imported — all 16 player features use neutral defaults
- ✅ Group stage tables now returned in WC2026 simulation output.
- ✅ Full knockout replay payload now includes R32, R16, QF, SF, third-place match, and final.
- ✅ Group qualification output is visible through group tables and advancement probabilities.
- 🔄 Bracket match-detail modal remains planned.

---

## 6. What Is Duplicated

| Feature | Canonical Location | Duplicate |
|---------|-------------------|-----------|
| WC2026 team listing | `/world-cup` | `/wc2026` |
| WC2026 groups | `/world-cup` | `/wc2026` |
| WC2026 simulation | `/world-cup` | `/simulate`, `/wc2026` |
| WC2026 tournament results | `/world-cup` | `/tournament` (wrong edition) |
| Simulation tab embedding | `/world-cup` | `/simulate` (standalone) |

---

## 7. What Is Stale / Missing Data

- **Player data:** Empty for all teams. No automated ingestion. All player features = neutral defaults.
- **Match results:** May be sparse depending on last ETL run. Training data quality depends on this.
- **Elo:** Fresh from ETL but not visible in teams tab (UI bug, not data bug).
- **FIFA rankings:** Same as Elo — fresh in DB but not surfaced in teams tab.
- **ML models:** May be trained on sparse data (if ETL hasn't run). Model performance on empty DB = minimal.

---

## 8. Root Causes

### Root Cause 1: Elo not in frontend teams display
The `GET /world-cup/qualified-teams` endpoint returns a `QualifiedTeam` schema that was designed for qualification tracking only. It never joins against the Elo or FIFA ranking snapshots. The frontend never fetches `/ratings/elo/latest` in the team listing page and merges it.

**Fix:** Add `elo_rating` and `fifa_rank` to the qualified-teams response from the current snapshot.

### Root Cause 2: Duplicate simulation pages
Historical development added `/simulate`, `/wc2026`, and `/tournament` as separate pages before `/world-cup` became the canonical dashboard. They were never cleaned up.

**Fix:** Redirect `/wc2026` and `/tournament` to `/world-cup`. Remove `Simulate` from the top-level nav.

### Root Cause 3: ML retraining not automated
`ml/retrain_if_needed.py` exists and works, but the Celery ETL tasks in `etl/schedulers/celery_tasks.py` complete without calling it. The `retrain_if_needed` function requires external caller to pass `material_ranking_changes`, `material_elo_changes`, etc.

**Fix:** After each Elo/FIFA/results ETL task completes, call `evaluate_retraining_need(apply=True)` with appropriate counts.

### Root Cause 4: Player data not ingested
`etl/players/csv_import.py` exists but requires a CSV file at a configured path. No default CSV is provided and no automated download is wired. The `refresh_player_availability` Celery task calls `run_player_rating_import()` from `etl/pipeline.py` but this function likely finds no file and exits silently.

**Fix:** Import StatsBomb Open Data player stats (legally available) or use a seeded reference CSV.

### Root Cause 5: Group tables missing from simulation output
The `MonteCarloEngine._run_chunk` only tracks elimination round reach counts, not group-stage standings. The frontend can only show champion/final/semi/quarter/r16 probabilities — not group standings.

**Fix implemented:** WC2026 simulation now runs one replayable tournament in
addition to Monte Carlo aggregation and serializes `group_tables`,
`best_third_place`, `knockout_bracket`, `matches`, `champion`, `runner_up`, and
`third_place`.

---

## 9. What Causes Predictions to Be Inaccurate

1. **Neutral player features:** All 16 player-derived features default to 70.0 for all teams → zero differentiation signal from player quality.
2. **Sparse training data:** Without a full match results ETL run, the training set is small and models overfit.
3. **Model staleness:** Models may not have been retrained after the latest Elo/FIFA updates.
4. **Neutral coach data:** Coach records are empty/neutral for most teams, contributing no signal.
5. **Travel/rest features:** Always zero (not wired to actual fixture schedule).

---

## 10. What Should Not Change

- Core tournament engine (`wcip/engine/`) — already correct for 48-team format.
- Alembic migration structure — versioned snapshots are correct design.
- Feature vector structure and `FEATURE_VERSION` — changing order breaks saved models.
- Saved simulations API — per-user access control is correct.
- Authentication system — JWT + refresh is correct.
- `DataFreshnessStrip` component — works correctly.
- `data_refresh_service.py` — clean orchestration layer.

---

## 11. What Needs to Change

### Backend
1. `app/api/v1/world_cup.py`: Add `elo_rating` and `fifa_rank` to `/world-cup/qualified-teams` response.
2. `app/api/v1/world_cup.py`: Add `/world_cup/2026/simulate`, `/world_cup/2026/groups`, and `/world_cup/2026/bracket` aliases.
3. `wcip/engine/tournament.py`: Add third-place match, best third-place rows, and serializable replay payload support.
4. `etl/schedulers/celery_tasks.py`: Call `retrain_if_needed` after Elo/FIFA/results/player ETL tasks complete.
5. `app/workers/celery_app.py`: Add `retrain_if_needed` beat schedule.
6. `ml/validate_player_features.py`: Add player data and player-feature validation command.
7. `app/api/v1/ml.py`: Add `POST /admin/ml/retrain-if-needed`.

### Frontend
1. `components/nav.tsx`: Remove duplicate Simulate entry and keep WC2026 as the primary flow.
2. `app/wc2026/page.tsx`: Redirect legacy page to `/world-cup`.
3. `app/tournament/page.tsx`: Redirect legacy tournament page to `/world-cup`.
4. `app/world-cup/page.tsx`: Add Elo/FIFA display, full group tables, best third-place table, bracket tab, and save button.
5. `components/data-freshness.tsx`: Add admin actions for Elo, FIFA, players, all data, retraining check, and retrain.
6. `lib/types.ts`: Add Elo/FIFA team fields and WC2026 group/bracket response types.
7. `app/wc2026/simulate/page.tsx`: Load the canonical World Cup dashboard for the explicit simulator route.

---

## 12. Known Risks

- **eloratings.net** changes its page structure frequently; HTML parser may break. TSV fallback is more stable.
- **FIFA ranking** official page uses JavaScript rendering; HTTP-only scraping may fail. Cached data is used as fallback.
- **Player data** has no legal free-tier automated source for all 48 WC teams. Manual CSV import is the current approach.
- **SQLite in production** limits concurrent write throughput. Use PostgreSQL for production.
- **Pickle models** are not portable across Python versions. If Python is upgraded, retrain from scratch.

---

## 13. Implemented / In Progress / Planned

### Implemented
- [x] Elo ETL with snapshot versioning
- [x] FIFA ranking ETL with snapshot versioning
- [x] 33-feature ML pipeline (including 16 player features)
- [x] Time-series CV training (5 models)
- [x] 48-team Monte Carlo tournament simulation
- [x] Data freshness API and frontend strip
- [x] Saved simulations with per-user access
- [x] Admin data refresh endpoints
- [x] Celery beat schedule for ETL

### Completed In This Session
- [x] Add Elo/FIFA rank to qualified-teams API response
- [x] Show Elo/FIFA values in `/world-cup` teams tab
- [x] Redirect `/wc2026`, `/simulate`, and `/tournament` duplicate pages
- [x] Wire `retrain_if_needed` after ETL tasks and add scheduled/admin hooks
- [x] Simplify nav around the WC2026 center
- [x] Return and display WC2026 group tables, best third-place standings, and knockout replay bracket
- [x] Add `ml.validate_player_features`

### Planned
- [ ] Player data import (StatsBomb Open Data / seeded CSV)
- [ ] True bracket visualization (round-by-round)
- [ ] Group stage table simulation output
- [ ] Match detail modal in simulation
- [ ] Player impact on specific simulation runs
