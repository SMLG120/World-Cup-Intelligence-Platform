# World Cup Intelligence Platform

A hybrid AI and statistical prediction platform for international football. Combines
an Elo + Poisson + Monte Carlo statistical engine with a trained five-model ML ensemble
and SHAP explainability, wrapped in a FastAPI backend and a Next.js frontend.

> **All output is probabilistic simulation for education and analysis. This platform
> does not provide betting advice and does not encourage gambling.**

---

## Platform Overview

The platform produces three independent prediction layers for every match and surfaces
all three to users so they can compare them directly.

```
┌─────────────────── Statistical Layer ───────────────────┐
│  Elo Rating Engine → Poisson Scoreline → Monte Carlo Sim │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   ML Prediction Layer                    │
│  Logistic · Random Forest · XGBoost · LightGBM · CatBoost│
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                   Ensemble Layer                         │
│  30% Statistical + 70% ML (inverse log-loss weighted)    │
│  + SHAP explainability + narrative                       │
└─────────────────────────────────────────────────────────┘
```

### Statistical Prediction Engine (Phase 1)

**Elo Ratings** — A World-Football-Elo variant where each team's rating encodes its
historical strength. The expected match outcome is the logistic function of the
rating difference:

```
E_A = 1 / (1 + 10 ^ ((R_B − R_A) / 400))
R'  = R + K · G · (S − E)
```

`K` scales with match importance (friendly → World Cup final). `G` is a goal-difference
multiplier. The platform refreshes ratings from eloratings.net via the ETL pipeline.

**Poisson Scoreline Model** — The Elo gap converts to per-team goal rates (λ). Goals
are modelled as two independent Poisson distributions, producing a full scoreline
probability matrix `P[i, j]`. Win/draw/loss come from summing triangles. xG values
are the λ parameters directly. Form, injury burden, coach impact, squad chemistry,
and fatigue enter as multipliers on the goal rates.

**Monte Carlo Tournament Simulation** — The full tournament is replayed up to 50,000
times in parallel (seeded `SeedSequence` per worker for reproducibility). Knockout
matches that are level go to extra time (goal rates × 30/90) and then an Elo-weighted
penalty shootout (Bernoulli trial nudged by rating gap). Results aggregate into
per-stage champion probabilities with Wilson score confidence intervals.

### Machine Learning Prediction Engine (Phase 2)

Five models trained on 25,243 international matches (from 2000 onward) using a
17-feature engineering pipeline. All models predict three-class outcome probabilities
(home win / draw / away win).

| Model | Accuracy | F1 | Brier | Log-Loss | Ensemble Weight |
|---|---|---|---|---|---|
| CatBoost | 57.92% | 0.5007 | 0.181 | 0.9196 | 20.11% |
| Random Forest | 57.85% | 0.4970 | 0.181 | 0.9221 | 20.06% |
| Logistic Regression | 57.68% | 0.4954 | 0.182 | 0.9229 | 20.04% |
| LightGBM | 57.29% | 0.5037 | 0.183 | 0.9306 | 19.87% |
| XGBoost | 57.23% | 0.5021 | 0.183 | 0.9282 | 19.92% |

*Metrics from 5-fold time-series cross-validation on 2000–2026 data. Training date: 2026-06-04.*

### Ensemble Layer

The ensemble combines statistical and ML outputs in a weighted sum. Weights are
derived from validation log-loss (lower log-loss → higher weight), re-normalised
each time a model is retrained:

```
ensemble_weight_i = (1 / log_loss_i) / Σ(1 / log_loss_j)
final = 0.30 × statistical + 0.70 × Σ(w_i × ML_i)
```

When no trained models are available the ensemble falls back to statistical-only
output, so the platform works before the first training run.

---

## Data Sources

### International Football Results Dataset
- **Maintainer:** Mart Jürisoo (martj42) on GitHub
- **URL:** `https://github.com/martj42/international_results`
- **License:** CC BY-SA 4.0 — attribution required
- **Coverage:** All international results since November 1872
- **Current DB rows:** 49,304 matches (1872-11-30 to 2026-06-03) from 327 teams
- **Fields used:** date, home_team, away_team, home_score, away_score, tournament, city, country, neutral
- **Update frequency:** CSV updated daily by the maintainer; ETL runs incrementally with a 7-day look-back overlap
- **Pipeline entry:** `etl/extract/international_results.py` → normalise → validate → `match_results` table
- **Limitation:** Scheduled/future matches appear with "NA" scores — the ETL skips these rows

### World Football Elo Ratings
- **Source:** eloratings.net
- **URL:** `https://www.eloratings.net/World.tsv`
- **License:** Public data, attribution requested; no commercial restriction documented
- **Coverage:** Current Elo ratings for all FIFA-affiliated national teams
- **Fields used:** team name, current Elo rating
- **Update frequency:** Weekly ETL task; embedded fallback snapshot (~Jan 2025 top 50) used if fetch fails
- **Pipeline entry:** `etl/extract/elo_ratings.py` → `teams.elo` column

### Football-Data.org API
- **URL:** `https://api.football-data.org/v4`
- **License:** Free tier (rate-limited to 10 req/min); commercial tiers available
- **Fields used:** competition teams, match results, squad rosters, standings
- **Update frequency:** On-demand via ETL; requires `FOOTBALL_DATA_API_KEY` in `.env`
- **Pipeline entry:** `etl/extract/football_data.py` → player records, team stats
- **Limitation:** Free tier excludes some competitions; squad depth limited to registered players

### FIFA Rankings
- **Source:** Embedded snapshot (June 2025 approximate)
- **Fields used:** team name, FIFA world ranking position
- **Update frequency:** Updated quarterly via ETL; embedded fallback in `etl/extract/fifa_rankings.py`
- **Pipeline entry:** `teams.fifa_rank` column; `fifa_rank_diff` feature

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Frontend (Next.js 14 App Router)             │
│  /dashboard  /wc2026  /compare  /player-lab  /models           │
│  /simulate   /tournament  /scenarios  /teams  /saved  /history │
└──────────────────────────┬──────────────────────────────────────┘
                           │  REST + JWT (typed client)
┌──────────────────────────▼──────────────────────────────────────┐
│                    Backend (FastAPI)                            │
│  35 endpoints · CORS · rate-limit · JWT auth · OpenAPI         │
│  auth · teams · matches · simulations · scenarios ·            │
│  ml · world-cup · admin                                        │
└──────┬──────────────┬──────────────────┬────────────────────────┘
       │              │                  │
┌──────▼──────┐ ┌─────▼──────┐ ┌────────▼───────────────────────┐
│ Statistical │ │ ML Layer   │ │ Data Layer                     │
│ Engine      │ │ ml/        │ │ ETL Pipeline   etl/            │
│ wcip/engine │ │ features   │ │ ↓                              │
│ elo.py      │ │ train      │ │ extract (CSV/API/eloratings)   │
│ scoreline.py│ │ predict    │ │ transform (name normalisation) │
│ montecarlo  │ │ ensemble   │ │ validate (schema + business)   │
└──────┬──────┘ │ evaluate   │ │ load (upsert, batch 500)       │
       │        │ retrain    │ └────────────┬───────────────────┘
       └────────┴────────────┘             │
                     │              ┌──────▼──────────────────────┐
              ┌──────▼──────┐      │ Database (SQLite/PostgreSQL) │
              │ Ensemble    │      │ 13 tables · 49K+ matches     │
              │ Layer       │      │ 5 models · 43 WC2026 teams   │
              └─────────────┘      └─────────────────────────────┘
                                   ┌─────────────────────────────┐
                                   │ Cache / Queue               │
                                   │ Redis + Celery              │
                                   │ daily results · weekly elo  │
                                   └─────────────────────────────┘
```

---

## Data Pipeline

```
Raw CSV / API response
         │
         ▼  extract/
   fetch_results_csv()         — downloads & caches CSV
   fetch_elo_ratings()         — eloratings.net TSV or fallback snapshot
   fetch_competition_matches() — football-data.org API (rate-limited 6.5s)
         │
         ▼  transform/
   canonical(name)             — 60+ team name variants → canonical form
   normalize_match(raw)        — field mapping, type coercion
   compute_outcome(hg, ag)     — 0=away win, 1=draw, 2=home win
   is_competitive(tournament)  — filters friendlies for training
         │
         ▼  validation/
   validate_match()            — required fields, ¬negative goals, max score 30, future date skip
   validate_player()           — numeric field coercion, name/team checks
         │
         ▼  load/
   load_match_results()        — upsert with in-run dedup (49K → 39.8K unique)
   load_players()              — upsert by external_id or name+team
   load_qualified_teams()      — upsert WC2026 qualification data
         │
         ▼  ml/
   build_feature_matrix_from_db() — 17 features × N matches since 2000-01-01
         │
         ▼
   time_series_cv_split()      — expanding window, 5 folds, no leakage
   train_model()               — fit + CV metrics per model
   save_model()                — pickle to models/{name}.pkl
   register_model()            — upsert MLModelRecord, update ensemble_weight
         │
         ▼
   _update_ensemble_weights()  — normalise weights to sum to 1
         │
         ▼  prediction
   predict_hybrid()            — stat + all ML + weighted ensemble + SHAP
         │
         ▼
   MonteCarloEngine             — parallelised tournament simulation
         │
         ▼
   API Response / Frontend
```

---

## Feature Engineering

All 17 features are expressed as (home − away) differentials. A positive value favours the home team.

| # | Feature | Calculation | Source |
|---|---|---|---|
| 0 | `elo_diff` | home Elo − away Elo | `teams.elo` |
| 1 | `fifa_rank_diff` | away rank − home rank (inverted so positive = better) | `teams.fifa_rank` |
| 2 | `xg_diff` | mean xG last 10 matches (home − away) | `match_results` aggregation |
| 3 | `xga_diff` | mean xGA last 10 (home − away; negative = better defence) | `match_results` aggregation |
| 4 | `goals_scored_diff` | mean goals scored last 10 (home − away) | `match_results` aggregation |
| 5 | `goals_conceded_diff` | mean goals conceded last 10 (home − away) | `match_results` aggregation |
| 6 | `form_diff` | points from last 5 competitive matches (home − away) | `match_results` aggregation |
| 7 | `avg_age_diff` | mean squad age (home − away) | `players.age` |
| 8 | `market_value_diff` | log10(home market value) − log10(away market value) | `players.market_value_eur` |
| 9 | `injury_burden_diff` | injured/suspended starters ratio (home − away) | `players.injured / .suspended` |
| 10 | `coach_impact_diff` | coach impact score (home − away) | `coaches.impact_score` |
| 11 | `squad_chemistry_diff` | proportion of players from same club (home − away) | `players.club` |
| 12 | `travel_distance_km` | absolute km for home team travel to venue | geolocation estimate |
| 13 | `rest_days` | home team rest days since last match | `match_results` date diff |
| 14 | `tournament_exp_diff` | World Cup appearances (home − away) | `teams` metadata |
| 15 | `starting_xi_strength_diff` | mean Elo contribution of starting XI (home − away) | `players` stats |
| 16 | `bench_strength_diff` | mean Elo contribution of bench (home − away) | `players` stats |

Feature version: `v1`. Stored in `match_features` table for reuse. Version is recorded
alongside every trained model in `ml_models.feature_version`.

---

## Machine Learning

### Training

```bash
# Load historical data (run once, or when refreshing)
cd wcip-backend
python -c "from etl.pipeline import run_historical_results; run_historical_results()"

# Train all models (~2–5 min on CPU)
python -m ml.train --model all

# Train a single model
python -m ml.train --model catboost

# Force re-use of all history (ignore incremental state)
python -m ml.train --model all --full-refresh
```

### Cross-Validation Strategy

Time-series aware expanding window: training data for fold `k` covers all matches
from 2000-01-01 up to the fold's cut-off, test data covers the next 10% of the
timeline. This prevents future data leakage — a model trained at fold `k` has never
seen the matches it predicts.

```
Fold 0: train [2000 ─── cut0) → test [cut0 ─ cut0+10%]
Fold 1: train [2000 ─── cut1) → test [cut1 ─ cut1+10%]
...
Fold 4: train [2000 ─── cut4) → test [cut4 ─ end]
```

### Model Selection

Logistic Regression is wrapped in a `sklearn.Pipeline` with `StandardScaler`.
All tree models (RF, XGBoost, LightGBM, CatBoost) operate on raw features.
Ensemble weights are proportional to `1 / log_loss` from cross-validation and
are re-normalised to sum to 1.

### Retraining

```bash
# API-triggered retrain (admin token required)
curl -X POST /api/v1/ml/retrain \
  -H "Authorization: Bearer <token>" \
  -d '{"model": "all"}'

# Celery scheduled retrain
# Weekly task in etl/schedulers/celery_tasks.py
```

Models are versioned by training date (`v20260604`). Old records are kept in
`ml_models` with `is_active=false` for auditability.

---

## Explainability

Every hybrid prediction includes a SHAP-based explanation.

**SHAP method selection:**
- `LogisticRegression` inside a Pipeline: `shap.LinearExplainer` on the `clf` step
- Tree models (RF, XGBoost, LightGBM, CatBoost): `shap.TreeExplainer`

**Output structure:**
- `top_positive` — features most favouring the home team
- `top_negative` — features most favouring the away team
- `shap_values` — raw SHAP values for all 17 features
- `narrative` — human-readable sentence generated from the top two factors

**Example output — Argentina vs France:**
```json
{
  "top_positive": [
    {"name": "elo_diff", "display_name": "Elo Rating Difference",
     "value": 133.0, "impact": 0.312}
  ],
  "top_negative": [
    {"name": "xga_diff", "display_name": "Expected Goals Against Difference",
     "value": -0.7, "impact": -0.108}
  ],
  "narrative": "Argentina is favoured due to Elo Rating Difference (+133.0). France benefits from Expected Goals Against Difference (-0.7)."
}
```

When a model file is unavailable, the system falls back to feature-magnitude ranking
(largest absolute feature value) with an explicit `fallback: true` flag in the response.

---

## World Cup 2026

### Format

FIFA World Cup 2026 uses an expanded 48-team format for the first time.

| Stage | Teams | Format |
|---|---|---|
| Group Stage | 48 | 12 groups of 4, round-robin |
| Round of 32 | 32 | Top 2 from each group (24) + 8 best third-place |
| Round of 16 | 16 | Single elimination |
| Quarter-finals | 8 | Single elimination |
| Semi-finals | 4 | Single elimination |
| Final | 2 | Single elimination |

### Qualification

- **Total slots:** 48
- **Confederation allocations:** UEFA 16, CAF 9, AFC 8, CONCACAF 6 (incl. 3 hosts), CONMEBOL 6, OFC 1, Playoff 2
- **Confirmed as of June 2025:** 43 teams (5 slots remain via inter-confederation playoffs)
- **Host nations:** United States, Canada, Mexico (auto-qualified)
- **Data model:** `qualified_teams` table — `confirmed=true/false`, `group_label` populated after official draw

### Group Draw

The group draw has not yet been held as of June 2025. The platform responds to this as follows:

- `GET /api/v1/world-cup/groups` returns `{"draw_complete": false, "groups": {}}`
- `POST /api/v1/world-cup/simulate` uses provisional Elo-seeded groups (serpentine sort by Elo into 12 groups of 4) until official groups are loaded into `qualified_teams.group_label`

Once FIFA announces the draw, update `qualified_teams.group_label` for all 48 teams
and the platform automatically uses the official groups.

### Tournament Simulation

The WC2026 simulation path:
1. Load qualified teams from `qualified_teams` table (DB-first, CONFIRMED_QUALIFIERS fallback)
2. Build groups — official if `draw_complete`, provisional Elo-seeded if not
3. Run `MonteCarloEngine` with 2026 bracket template (R32 included)
4. Return per-team probabilities for each stage up to Champion

---

## Prediction API Usage

### Hybrid Prediction
```bash
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "home_team": "Argentina",
    "away_team": "France",
    "match_date": "2026-07-19",
    "include_shap": true
  }'
```

Response includes `statistical`, `ml_predictions` (one per model), `ensemble`,
`home_xg`, `away_xg`, `expected_scoreline`, `confidence_score`, `model_agreement`,
and `explanation` with `narrative`.

### Feature Vector
```bash
curl "http://localhost:8000/api/v1/ml/features?home_team=Argentina&away_team=France"
```

### Statistical Match Prediction (legacy)
```bash
curl -X POST http://localhost:8000/api/v1/match/simulate \
  -d '{"home_team": "Argentina", "away_team": "France", "n_simulations": 1000}'
```

---

## Complete API Reference (prefix `/api/v1`)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | – | Create account |
| POST | `/auth/login` | – | OAuth2 password flow → access + refresh tokens |
| POST | `/auth/refresh` | – | Exchange refresh token |
| GET | `/auth/me` | JWT | Current user |
| GET | `/teams` | – | List teams (cached, `?confederation=`) |
| GET | `/teams/{id}` | – | Team detail |
| GET | `/teams/{id}/stats` | – | Aggregated stats |
| GET | `/teams/{id}/elo-history` | – | Elo trend data |
| POST | `/match/simulate` | – | Statistical single-match prediction |
| POST | `/tournament/simulate` | – | Statistical Monte Carlo tournament (≤ 2,000 runs sync) |
| POST | `/scenario/compare` | – | Compare 2–3 scenarios |
| GET | `/editions` | – | Available tournament editions |
| POST | `/simulations` | JWT | Save simulation (async above threshold) |
| GET | `/simulations` | JWT | Paginated history |
| GET | `/simulations/{id}` | JWT | Fetch by ID |
| GET | `/simulations/public/{token}` | – | Shared public view |
| PATCH | `/simulations/{id}` | JWT | Rename / toggle public |
| POST | `/simulations/{id}/duplicate` | JWT | Clone |
| DELETE | `/simulations/{id}` | JWT | Remove |
| GET | `/admin/analytics` | Admin | Usage metrics |
| GET | `/health` | – | Liveness |
| POST | `/ml/predict` | – | Hybrid prediction (stat + ML + ensemble + SHAP) |
| POST | `/ml/train` | Admin | Trigger training (async) |
| POST | `/ml/retrain` | Admin | Incremental retrain (async) |
| GET | `/ml/models` | – | Registered models + metrics |
| GET | `/ml/features` | – | Feature vector for a match |
| GET | `/ml/feature-names` | – | Feature name list (v1) |
| GET | `/ml/explanations` | – | SHAP explanation for a match |
| POST | `/ml/etl/run` | Admin | Trigger ETL pipeline (async) |
| GET | `/world-cup/qualified-teams` | – | WC2026 qualified teams |
| GET | `/world-cup/groups` | – | Group draw (or pending status) |
| GET | `/world-cup/bracket` | – | Knockout bracket |
| POST | `/world-cup/simulate` | – | WC2026 Monte Carlo simulation |
| GET | `/world-cup/schedule` | – | Tournament schedule (June 11 – July 19, 2026) |
| GET | `/world-cup/teams/{team_name}` | – | Team detail with squad/coach/injury count |
| GET | `/world-cup/players/{team_name}` | – | Full squad list |

---

## Repository Layout

```
world-cup-predictor/
├── README.md                    this file
├── REPO_CHECKLIST.md            feature completion tracker
├── MODEL_CARD.md                model documentation and limitations
│
├── wcip-backend/
│   ├── app/
│   │   ├── main.py              FastAPI app, middleware, lifespan
│   │   ├── core/                config, security, deps, cache, rate-limit
│   │   ├── db/                  engine, session, init_db (seed)
│   │   ├── models/              SQLAlchemy ORM (13 tables)
│   │   │   ├── user.py          users, audit_logs
│   │   │   ├── team.py          teams, elo_history
│   │   │   ├── simulation.py    simulations, simulation_runs, saved_scenarios
│   │   │   ├── player.py        players, coaches
│   │   │   └── match_result.py  match_results, match_features, ml_models, qualified_teams
│   │   ├── schemas/             Pydantic v2 request/response models
│   │   ├── repositories/        typed data-access layer
│   │   ├── services/            prediction bridge
│   │   └── api/v1/              auth, teams, matches, simulations, scenarios,
│   │                            ml, world_cup, router
│   ├── wcip/                    vendored statistical engine
│   │   ├── engine/
│   │   │   ├── elo.py           Elo rating system
│   │   │   ├── scoreline.py     Poisson scoreline model
│   │   │   └── montecarlo.py    Monte Carlo simulator
│   │   └── data/
│   │       ├── teams_2022.py    2022 WC seed data
│   │       └── wc2026.py        WC2026 format + qualified teams
│   ├── ml/
│   │   ├── features.py          17-feature engineering pipeline
│   │   ├── train.py             training + time-series CV + model registry
│   │   ├── predict.py           model loading (lru_cache) + inference
│   │   ├── ensemble.py          hybrid prediction + SHAP explanations
│   │   ├── evaluate.py          cross-validation + calibration reports
│   │   └── retrain.py           incremental retrain entry point
│   ├── etl/
│   │   ├── extract/             international_results.py, elo_ratings.py,
│   │   │                        football_data.py, fifa_rankings.py
│   │   ├── transform/           normalize.py (60+ name variants)
│   │   ├── validation/          schema.py (ValidatedMatch, validate_match)
│   │   ├── load/                db_loader.py (upsert, batch 500)
│   │   ├── schedulers/          celery_tasks.py
│   │   └── pipeline.py          orchestrator + ETL state file
│   ├── models/                  trained model pickles (*.pkl, gitignored)
│   ├── data/cache/              downloaded CSVs + TSVs (gitignored)
│   ├── tests/                   pytest suite (18 tests)
│   ├── alembic/                 migrations
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
│
└── wcip-frontend/
    ├── app/
    │   ├── wc2026/              WC2026 dashboard (teams, groups, simulation)
    │   ├── compare/             Prediction comparison (stat vs ML vs ensemble)
    │   ├── player-lab/          Player Impact Lab (toggle injuries, overrides)
    │   ├── models/              Model dashboard (metrics, ensemble weights, features)
    │   ├── dashboard/           Overview, top contenders, recent simulations
    │   ├── simulate/            Statistical single-match predictor
    │   ├── tournament/          Monte Carlo tournament runner + bracket
    │   ├── scenarios/           2–3 scenario comparison
    │   ├── teams/               Team table + detail pages
    │   └── saved/ history/      User simulation history
    ├── components/
    │   ├── nav.tsx              Top navigation (all 10 routes)
    │   ├── match-predictor.tsx  Team pickers + modifiers + result display
    │   ├── probability-bar.tsx  W/D/L split bar
    │   ├── bracket.tsx          Animated knockout bracket
    │   ├── champion-chart.tsx   Champion probability bar chart
    │   └── ui/                  button, card, input, select, slider, skeleton, badge
    └── lib/
        ├── types.ts             All TypeScript interfaces (stat + ML + WC2026)
        ├── api.ts               Typed fetch client + token handling
        ├── auth-context.tsx     JWT auth provider
        └── queries.ts           React Query hooks
```

---

## Quick Start

```bash
# Backend (SQLite + in-memory cache — no external services needed)
cd wcip-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                    # edit FOOTBALL_DATA_API_KEY if desired
uvicorn app.main:app --reload           # http://localhost:8000/docs

# Load historical match data and train ML models (run once after setup)
python -c "from etl.pipeline import run_historical_results; run_historical_results()"
python -m ml.train --model all

# Frontend (separate terminal)
cd wcip-frontend
npm install
cp .env.local.example .env.local
npm run dev                             # http://localhost:3000
```

Full stack with Docker (Postgres + Redis + Celery worker):
```bash
cd wcip-backend && docker compose up --build
```

---

## Data Freshness and Scheduled Jobs

| Job | Schedule | Description |
|---|---|---|
| `daily_results_update` | Daily | Incremental load of new international match results |
| `weekly_elo_update` | Weekly | Refresh team Elo ratings from eloratings.net |
| `full_pipeline` | On-demand | Full ETL + Elo update (admin API or Celery) |
| ML retrain | On-demand | Admin API `POST /ml/retrain` or `python -m ml.train` |

ETL state is persisted in `etl/data/etl_state.json`. The `last_results_date` field
controls incremental loading — deleted to force a full refresh.

Downloaded CSVs are cached in `data/cache/` and reused until `force_refresh=True`.

---

## Reproducibility

| Concern | Implementation |
|---|---|
| Random seeds | `np.random.SeedSequence` per Celery worker; `random_state=42` for all sklearn/XGBoost/LightGBM models |
| Dataset versioning | ETL state file records load date; `match_results.created_at` timestamps each row |
| Feature versioning | `FEATURE_VERSION = "v1"` constant; stored in `ml_models.feature_version` |
| Model versioning | Models keyed by `{name}_v{YYYYMMDD}`; all versions retained in `ml_models` with `is_active` flag |
| Training data | `--full-refresh` re-reads all history; default uses incremental window |

---

## Security

JWT access/refresh tokens with distinct `type` claims · bcrypt password hashing ·
role-based admin guard (`require_admin` dependency) · per-IP fixed-window rate
limiting · CORS allow-list · Pydantic validation on every payload · ORM-only queries
(no string SQL) · baseline security headers via Next.js middleware.

---

## Deployment

**Render:** `render.yaml` provisions web + worker + Postgres + Redis.
Set `BACKEND_CORS_ORIGINS` to your Vercel domain and `SECRET_KEY` to a 32+ byte secret.

**Docker:** `docker compose up --build` — runs api, worker, beat, postgres, redis.

**Vercel:** `cd wcip-frontend && vercel deploy`. Set `NEXT_PUBLIC_API_URL` to your Render URL.

---

## Testing

```bash
# Backend — 18 tests (isolated SQLite, eager Celery)
cd wcip-backend && pytest -q
pytest --cov=app --cov-report=term-missing

# Frontend — typecheck + build
cd wcip-frontend && npm run typecheck && npm run build
```

---

## License and Disclaimer

For educational and analytical use only. Predictions are probabilistic simulations
and should not be interpreted as certainty. This platform does not provide betting
advice and does not encourage gambling.

Data sources used under their respective licenses — see the Data Sources section
above for attribution and license details.
