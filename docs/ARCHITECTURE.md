# Architecture — World Cup Intelligence Platform

---

## System Overview

The platform is three independent packages that communicate over REST:

```
┌──────────────────────────────────────────────────────────────────┐
│                  wcip-frontend (Next.js 14)                      │
│                                                                  │
│  /wc2026   /compare   /player-lab   /models                      │
│  /dashboard   /simulate   /tournament   /scenarios               │
│  /teams   /saved   /history   /profile   /admin                  │
└─────────────────────────┬────────────────────────────────────────┘
                          │  HTTPS REST + JWT
                          │  Typed client: wcip-frontend/lib/api.ts
                          │  React Query caching layer
                          │
┌─────────────────────────▼────────────────────────────────────────┐
│                  wcip-backend (FastAPI)                          │
│                                                                  │
│  Middleware stack:                                               │
│    CORS allow-list → per-IP rate limiting →                      │
│    JWT auth (Annotated deps) → request validation                │
│                                                                  │
│  Routers (app/api/v1/):                                          │
│    auth · teams · matches · simulations · scenarios              │
│    ml · rankings · world_cup · admin                             │
│                                                                  │
│  Versioned endpoint groups · OpenAPI at /docs                    │
└──────────┬──────────────┬──────────────────┬────────────────────┘
           │              │                  │
     ┌─────▼─────┐  ┌─────▼──────┐   ┌──────▼──────────────────┐
     │Statistical│  │ ML Layer   │   │ Database Layer          │
     │Engine     │  │            │   │                         │
     │wcip/engine│  │ml/         │   │ SQLAlchemy 2.0 ORM      │
     │           │  │  features  │   │ SQLite (dev)            │
     │elo.py     │  │  train     │   │ PostgreSQL (prod)       │
     │scoreline  │  │  predict   │   │                         │
     │montecarlo │  │  ensemble  │   │ 19 tables               │
     └─────┬─────┘  │  evaluate  │   │ 49,306 match records    │
           │        │  retrain   │   │ 48 WC2026 teams         │
           └────────┤            │   │ 5 trained models        │
                    └─────┬──────┘   └──────────────┬──────────┘
                          │                         │
                    ┌─────▼──────────────────────────▼──────────┐
                    │ Ensemble Layer                             │
                    │ ml/ensemble.py                            │
                    │ predict_hybrid() → HybridPrediction       │
                    │ 30% stat + 70% ML + SHAP narrative        │
                    └─────────────────────────────────────────┘
                                      │
                    ┌─────────────────▼─────────────────────────┐
                    │ Cache / Queue Layer                        │
                    │ Redis (cache + Celery broker)              │
                    │ Celery worker: run_simulation, ETL tasks   │
                    │ Celery beat: daily results, weekly Elo,    │
                    │ FIFA ranking monitor                      │
                    └───────────────────────────────────────────┘
```

---

## Backend Module Map

```
wcip-backend/
│
├── app/
│   ├── main.py                   FastAPI app factory; registers middleware,
│   │                             routers, lifespan (init_db on startup)
│   │
│   ├── core/
│   │   ├── config.py             Pydantic Settings — all env vars with defaults
│   │   ├── security.py           JWT encode/decode, bcrypt hash/verify
│   │   ├── deps.py               FastAPI Annotated deps:
│   │   │                           CurrentUser, AdminUser, get_db
│   │   ├── cache.py              Redis client with in-memory fallback
│   │   └── ratelimit.py          Per-IP fixed-window rate limiter
│   │
│   ├── db/
│   │   ├── base.py               SQLAlchemy engine + SessionLocal + Base
│   │   └── init_db.py            Table creation + seed:
│   │                               seed_teams_2022()
│   │                               seed_qualified_teams_2026()
│   │                               seed_2026_teams_into_team_table()
│   │                               SQLite dev guard for new runtime columns
│   │
│   ├── models/                   SQLAlchemy 2.0 ORM (mapped_column syntax)
│   │   ├── user.py               User, AuditLog
│   │   ├── team.py               Team, EloHistory
│   │   ├── simulation.py         Simulation, SimulationRun, SavedScenario
│   │   ├── player.py             Player, Coach, player-rating import history
│   │   ├── match_result.py       MatchResult, MatchFeatures,
│   │   │                         MLModelRecord, QualifiedTeam
│   │   └── ranking.py            FifaRankingSnapshot, FifaRankingEntry,
│   │                             TeamRanking, RankingSourceLog
│   │
│   ├── schemas/                  Pydantic v2 request/response models
│   │
│   ├── repositories/
│   │   └── repos.py              Typed data-access layer (no raw SQL)
│   │
│   ├── services/
│   │   ├── prediction.py         Bridge: API/Celery → wcip engine
│   │   └── winner_predictions.py WC2026 statistical + ML-style ensemble table
│   │
│   ├── api/v1/
│   │   ├── auth.py               register, login, refresh, me
│   │   ├── teams.py              teams list + detail + stats + elo-history
│   │   ├── matches.py            match simulate, tournament simulate, scenario
│   │   ├── simulations.py        CRUD + share + duplicate
│   │   ├── scenarios.py          scenario compare
│   │   ├── ml.py                 predict, train, retrain, models, features,
│   │   │                         explanations, etl/run
│   │   ├── rankings.py           FIFA ranking snapshots + admin refresh
│   │   ├── world_cup.py          qualified-teams, groups, bracket, simulate,
│   │   │                         schedule, teams/{name}, players/{name},
│   │   │                         2026/winner-predictions
│   │   └── router.py             api_router — includes all sub-routers
│   │
│   └── workers/
│       ├── celery_app.py         Celery instance + config
│       └── tasks.py              run_simulation, refresh_data (beat)
│
├── wcip/                         Vendored statistical engine (Phase 1)
│   ├── engine/
│   │   ├── elo.py                EloEngine: compute_expected, update_rating
│   │   ├── scoreline.py          PoissonModel: goal_rates, scoreline_matrix
│   │   └── montecarlo.py         MonteCarloEngine: run_simulation (parallel)
│   └── data/
│       ├── teams_2022.py         TEAMS_2022 seed dict
│       └── wc2026.py             WC2026 format + CONFIRMED_QUALIFIERS seed
│
├── ml/
│   ├── features.py               build_feature_vector(), FEATURE_NAMES (v2, 33)
│   │                             build_feature_matrix_from_db() for training
│   ├── train.py                  run_training(): time-series CV, save, register
│   │                             CLI: python -m ml.train [--model] [--full-refresh]
│   ├── predict.py                _load_model (lru_cache), predict_with_model,
│   │                             predict_all_models, invalidate_model_cache
│   ├── ensemble.py               predict_hybrid() → HybridPrediction
│   │                             _compute_shap(), _feature_importance_explanation()
│   ├── evaluate.py               cross_validate_model, compare_models,
│   │                             calibration_report
│   └── retrain.py                run_retrain() → run_training + invalidate cache
│
└── etl/
    ├── pipeline.py               run_historical_results(), run_elo_update(),
    │                             run_fifa_rankings_update(),
    │                             run_player_rating_import(),
    │                             run_full_pipeline() + ETL state file
    ├── extract/
    │   ├── international_results.py  martj42 CSV download + cache + parse
    │   ├── elo_ratings.py            eloratings.net TSV + fallback snapshot
    │   ├── football_data.py          football-data.org API client
    │   └── fifa_rankings.py          official FIFA ranking snapshots
    ├── transform/
    │   └── normalize.py          canonical(), normalize_match(), NAME_MAP (60+)
    ├── validation/
    │   └── schema.py             ValidatedMatch, validate_match(), validate_player()
    ├── load/
    │   ├── db_loader.py          load_match_results(), load_players(),
    │   │                         load_qualified_teams()
    │   └── ranking_loader.py     versioned FIFA ranking snapshot loader
    ├── player_ratings/
    │   └── csv_import.py         legal CSV player rating import + history
    ├── monitoring/
    │   └── ranking_monitor.py    ranking change detection + retrain trigger
    └── schedulers/
        └── celery_tasks.py       daily_results_update, weekly_elo_update,
                                  fifa_rankings_update, full_pipeline
```

---

## Frontend Module Map

```
wcip-frontend/
│
├── app/                          Next.js 14 App Router
│   ├── layout.tsx                Root layout — fonts, Providers wrapper
│   ├── providers.tsx             QueryClient + AuthContext + theme
│   ├── page.tsx                  Landing → redirect to /dashboard
│   │
│   ├── wc2026/page.tsx           WC2026 Dashboard
│   │                               Tab 1: Qualified teams (confederation filter)
│   │                               Tab 2: Groups (draw complete or pending)
│   │                               Tab 3: Monte Carlo simulation → champion %
│   │
│   ├── compare/page.tsx          Prediction Comparison
│   │                               Home/Away inputs → api.mlPredict()
│   │                               Rows: Statistical | Logistic | RF | XGB |
│   │                                     LightGBM | CatBoost | Ensemble
│   │                               OutcomeBar component (stacked %)
│   │                               ExplanationPanel (SHAP factors + narrative)
│   │
│   ├── player-lab/page.tsx       Player Impact Lab
│   │                               Team selector → api.wc2026Players()
│   │                               Side-by-side squads with:
│   │                                 OverrideSliders (form, injury, coach_impact)
│   │                                 Per-player Fit/Injured + OK/Suspended toggles
│   │                               computeInjuryBurden() → override injection
│   │                               Live recomputed prediction (3-column card)
│   │
│   ├── models/page.tsx           Model Dashboard
│   │                               ModelCard per model (metric bars)
│   │                               Ensemble weight distribution bar
│   │                               FeatureImportanceChart (33 features)
│   │                               Feature Vector Explorer
│   │
│   ├── dashboard/page.tsx        Overview + top contenders + recent sims
│   ├── simulate/page.tsx         Statistical single-match predictor
│   ├── tournament/page.tsx       Monte Carlo runner + winner probabilities
│   ├── scenarios/page.tsx        2–3 scenario comparison
│   ├── teams/page.tsx            Sortable team table
│   ├── team/[id]/page.tsx        Team detail + Elo trend chart
│   ├── saved/page.tsx            Simulation history management
│   ├── history/page.tsx          Activity timeline
│   ├── profile/page.tsx          Account settings
│   ├── admin/page.tsx            Usage analytics (admin-gated)
│   ├── login/page.tsx
│   └── register/page.tsx
│
├── components/
│   ├── nav.tsx                   Sticky top navigation (10 routes + auth state)
│   ├── match-predictor.tsx       Team pickers + stat/ML modifiers + result display
│   ├── probability-bar.tsx       Stacked W/D/L bar with percentages
│   ├── bracket.tsx               Animated knockout bracket (Framer Motion)
│   ├── champion-chart.tsx        Champion probability bar chart (Recharts)
│   ├── winner-predictions-section.tsx
│   │                             WC2026 champion charts, comparison, table
│   ├── require-auth.tsx          Route guard (auth + admin variants)
│   └── ui/                       button, card, input, select, slider,
│                                 skeleton, badge (shadcn-compatible)
│
└── lib/
    ├── types.ts                  TypeScript interfaces:
    │                               StatPrediction, Team, Simulation, Scenario
    │                               MLOutcome, HybridPrediction, PredictionExplanation
    │                               MLModel, FeatureVector
    │                               QualifiedTeam, WC2026Groups, WC2026Simulation
    │                               TeamDetail, Player, WorldCupWinnerPrediction
    ├── api.ts                    Typed fetch client:
    │                               predictMatch, simulateTournament, compareScenarios
    │                               mlPredict, mlModels, mlFeatures, mlExplanations
    │                               wc2026Teams, wc2026Groups, wc2026Simulate
    │                               wc2026TeamDetail, wc2026Players,
    │                               wc2026WinnerPredictions
    ├── auth-context.tsx          JWT AuthContext: login, register, refresh, logout
    ├── queries.ts                React Query hooks (useQuery / useMutation per endpoint)
    └── utils.ts                  cn() class merger, number formatters
```

---

## Database Schema

```
┌──────────────────┐   ┌─────────────────┐   ┌──────────────────────┐
│ users            │   │ teams            │   │ match_results        │
│──────────────────│   │─────────────────│   │──────────────────────│
│ id PK            │   │ id PK            │   │ id PK                │
│ email UNIQUE     │   │ name UNIQUE      │   │ match_date           │
│ hashed_password  │   │ confederation    │   │ home_team            │
│ role             │   │ elo              │   │ away_team            │
│ is_active        │   │ fifa_rank        │   │ home_goals           │
│ created_at       │   │ group_label      │   │ away_goals           │
│                  │   │ pot              │   │ tournament           │
└────────┬─────────┘   │ flag_url         │   │ neutral              │
         │             └──────────────────┘   │ outcome (0/1/2)      │
         │                                    │ data_source          │
┌────────▼─────────┐   ┌─────────────────┐   └──────────────────────┘
│ simulations      │   │ elo_history      │   UQ(home,away,date)
│──────────────────│   │─────────────────│
│ id PK            │   │ id PK            │   ┌──────────────────────┐
│ user_id FK       │   │ team_id FK       │   │ match_features       │
│ edition          │   │ rating           │   │──────────────────────│
│ status           │   │ recorded_at      │   │ id PK                │
│ result_json      │   └─────────────────┘   │ match_result_id      │
│ public_token     │                         │ home_team            │
│ created_at       │   ┌─────────────────┐   │ away_team            │
└──────────────────┘   │ players          │   │ match_date           │
                       │─────────────────│   │ elo_diff             │
┌──────────────────┐   │ id PK            │   │ fifa_rank_diff       │
│ qualified_teams  │   │ name             │   │ xg_diff              │
│──────────────────│   │ team_name        │   │ xga_diff             │
│ id PK            │   │ position         │   │ goals_scored_diff    │
│ team_name        │   │ club             │   │ goals_conceded_diff  │
│ team_code        │   │ age              │   │ form_diff            │
│ confederation    │   │ injured BOOL     │   │ avg_age_diff         │
│ tournament_year  │   │ suspended BOOL   │   │ market_value_diff    │
│ group_label      │   │ xg               │   │ injury_burden_diff   │
│ pot              │   │ xag              │   │ coach_impact_diff    │
│ host_nation BOOL │   │ minutes_played   │   │ squad_chemistry_diff │
│ confirmed BOOL   │   │ ratings/source   │   │ travel_distance_km   │
│ qualification    │   └─────────────────┘   │ rest_days            │
│   _path          │                         │ tournament_exp_diff  │
└──────────────────┘   ┌─────────────────┐   │ starting_xi_strength │
UQ(name, year)         │ coaches          │   │ bench_strength_diff  │
                       │─────────────────│   │ ... + v2 player cols │
                       │                 │   └──────────────────────┘
┌──────────────────┐   │ id PK            │
│ ml_models        │   │ name             │   ┌──────────────────────┐
│──────────────────│   │ team_name        │   │ audit_logs           │
│ id PK            │   │ nationality      │   │ saved_scenarios      │
│ model_name       │   │ preferred_form   │   │ simulation_runs      │
│ version          │   │   ation          │   └──────────────────────┘
│ accuracy         │   │ win_pct          │
│ f1_score         │   │ draw_pct         │
│ brier_score      │   │ loss_pct         │
│ log_loss         │   │ tournament_exp   │
│ calibration_score│   │ impact_score     │
│ ensemble_weight  │   └─────────────────┘
│ training_samples │
│ feature_version  │
│ is_active BOOL   │
│ trained_at       │
└──────────────────┘
```

Additional ranking tables:

- `fifa_ranking_snapshots` stores one immutable FIFA publication with
  `ranking_id`, `ranking_date`, `published_at`, `next_update_at`, `source_url`,
  `source_hash`, `team_count`, and `is_current`.
- `fifa_ranking_entries` stores team rank, previous rank, points, previous
  points, rank movement, source team code, and raw source payload per snapshot.
- `team_rankings` mirrors ranked records behind a provider-agnostic table name
  for point-in-time feature and analyst queries.
- `ranking_source_logs` records each ranking fetch/load attempt, source hash,
  status, row counts, and errors.

Additional player-rating tables:

- `player_rating_imports` stores one legal CSV/API import batch with source,
  version, status, and row counts.
- `player_rating_records` stores historical player rating rows for each import
  so model training and audits can reproduce old player-strength features.

`teams.fifa_rank` is a current display cache only. Historical training,
backtests, and tournament simulations should read ranking entries through the
latest snapshot with `ranking_date <= match_date`.

---

## Prediction Request Flow

```
Client
  │
  │  POST /api/v1/ml/predict
  │  { home_team, away_team, match_date, home_overrides, away_overrides }
  ▼
FastAPI router (app/api/v1/ml.py)
  │
  ├─ canonical(home_team), canonical(away_team)   ← name normalisation
  ├─ validate home != away
  │
  ▼
ml/ensemble.py :: predict_hybrid()
  │
  ├─ ml/features.py :: build_feature_vector()
  │     │
  │     ├─ _get_team_elo()           ← elo_history as-of date, teams cache for current
  │     ├─ _get_team_fifa_rank()     ← fifa_ranking_entries as-of date, teams cache for current
  │     ├─ _get_recent_match_stats() ← match_results aggregation (last 10)
  │     ├─ _get_form()               ← match_results aggregation (last 5 competitive)
  │     ├─ _get_squad_stats()        ← players table (defaults 0 if empty)
  │     ├─ _get_coach_impact()       ← coaches table (defaults 1.0 if empty)
  │     ├─ _get_team_chemistry()     ← players table (defaults 0 if empty)
  │     └─ _get_tournament_experience() ← match_results aggregation
  │
  ├─ app/services/prediction.py :: predict_match()    ← Statistical layer
  │     │
  │     ├─ EloEngine.compute_expected()
  │     └─ PoissonModel.goal_rates() → win/draw/loss probs + xG
  │
  ├─ ml/predict.py :: predict_all_models()            ← ML layer
  │     │
  │     ├─ _load_model("logistic")    ← lru_cache → models/logistic.pkl
  │     ├─ _load_model("random_forest")
  │     ├─ _load_model("xgboost")
  │     ├─ _load_model("lightgbm")
  │     └─ _load_model("catboost")
  │     Each returns {home_win, draw, away_win} or None if unavailable
  │
  ├─ Ensemble calculation
  │     weights = SELECT ensemble_weight FROM ml_models WHERE is_active=true
  │     ensemble = 0.30 × statistical + 0.70 × Σ(w_i × ML_i)
  │
  ├─ _compute_shap()                                 ← Explainability
  │     TreeExplainer for RF/XGB/LGBM/CatBoost
  │     LinearExplainer for Logistic (extracts clf from Pipeline)
  │
  └─ _feature_importance_explanation()
        → top_positive, top_negative, narrative sentence
        → HybridPrediction.to_dict()

Response
  {
    statistical: {home_win, draw, away_win},
    ml_predictions: {logistic: {...}, random_forest: {...}, ...},
    ensemble: {home_win, draw, away_win},
    home_xg, away_xg, expected_scoreline,
    confidence_score, model_agreement,
    explanation: {top_positive, top_negative, shap_values, narrative}
  }
```

---

## Tournament Simulation Flow

```
POST /api/v1/world-cup/simulate   (or /api/v1/tournament/simulate for 2022)
  │
  ├─ Load qualified teams from DB (qualified_teams table)
  │   or fall back to CONFIRMED_QUALIFIERS seed
  │
  ├─ Build groups
  │   ├─ Official: if qualified_teams.group_label is populated
  │   └─ Provisional: _provisional_groups_by_elo() — serpentine sort by Elo
  │
  ├─ Build bracket (build_2026_bracket)
  │   R32 template → R16 → QF → SF → Final
  │
  ├─ MonteCarloEngine(n_simulations=N, n_jobs=-1)
  │   ProcessPoolExecutor — one seeded SeedSequence per worker
  │   │
  │   For each simulation:
  │   ├─ Group stage: round-robin all groups
  │   │   PoissonModel.sample_scoreline() → W/D/L
  │   │   Rank by: points → GD → GF → head-to-head → Elo tiebreaker
  │   │   Advance: top 2 per group + 8 best third-place
  │   │
  │   └─ Knockout rounds:
  │       predict_match() → sample winner
  │       Level after 90min → extra time (λ × 30/90)
  │       Still level → Bernoulli penalty (nudged by Elo gap)
  │
  └─ Aggregate results
      Per team: P(R32), P(R16), P(QF), P(SF), P(Final), P(Champion)
      Wilson score CI on P(Champion)
      Expected finishing position (weighted by stage reached)

Response: {teams: [{team_name, confederation, champion_pct, ...stages...}]}
```

## Winner Prediction Flow

```
GET /api/v1/world-cup/2026/winner-predictions?runs=5000&seed=12345
  │
  ├─ Reuse WC2026 qualified teams, groups, and bracket
  ├─ Run MonteCarloEngine with deterministic seed for statistical stage odds
  ├─ Build an ML-style strength score from Elo, FIFA rank, player ratings,
  │   squad depth, availability, form, coach impact, and international experience
  ├─ Normalize statistical and ML-style champion probabilities
  └─ Return a ranked ensemble table with final/semi/quarter/group odds,
      confidence interval, model comparison values, and explanation text
```

---

## ETL Pipeline Flow

```
CLI / Admin API / Celery beat
  │
  ├─ run_historical_results(force_refresh)
  │   │
  │   ├─ _load_state() → last_results_date (incremental cutoff)
  │   │
  │   ├─ fetch_results_csv(force_refresh)
  │   │   ├─ Cache hit: read data/cache/results.csv
  │   │   └─ Cache miss: httpx.get(RESULTS_URL) → write cache
  │   │
  │   ├─ parse_results(csv_text, since)
  │   │   Skip: future/NA scores, dates before since
  │   │   Yield: {match_date, home_team, away_team, home_goals, ...}
  │   │
  │   ├─ normalize_match(raw)
  │   │   canonical(team_name) — 60+ NAME_MAP variants
  │   │   compute_outcome(hg, ag) → 0/1/2 label
  │   │
  │   ├─ validate_match(normalized)
  │   │   Checks: required fields, ¬negative, max_score 30, ¬future date
  │   │   Raises ValidationError → skip row (logged if ≤ 10 errors)
  │   │
  │   └─ load_match_results(validated_iterator, batch_size=500)
  │       Dedup set: skip (home, away, date) tuples seen in this run
  │       SELECT EXISTS → skip DB duplicates
  │       Batch commit every 500 rows
  │       Return: rows inserted
  │
  ├─ run_elo_update()
  │   fetch_elo_ratings() → {team_name: elo_float}
  │   UPDATE teams SET elo=... WHERE canonical(name) matches
  │
  ├─ run_fifa_rankings_update(force_refresh)
  │   fetch_fifa_ranking_snapshot() from official FIFA ranking metadata
  │   validate unique teams/ranks and minimum snapshot size
  │   INSERT/UPDATE fifa_ranking_snapshots by ranking_id
  │   INSERT fifa_ranking_entries for each ranked team
  │   MIRROR rows into team_rankings for provider-neutral queries
  │   WRITE ranking_source_logs for fetch/load traceability
  │   UPDATE teams.fifa_rank only for the current display cache
  │
  ├─ run_wc2026_seed()
  │   Upsert teams, qualified_teams, placeholder players, and coaches
  │
  └─ run_player_rating_import()
      Load licensed/manual CSV player ratings into players plus immutable
      player_rating_imports and player_rating_records history
```

---

## Caching Strategy

| Layer | Mechanism | TTL |
|---|---|---|
| HTTP responses (teams list) | Redis (in-memory fallback) | 300s |
| Downloaded CSV files | Local disk (`data/cache/`) | Until `force_refresh=True` |
| FIFA ranking snapshots | Local disk cache + database snapshots | Disk until `force_refresh=True`; DB permanent |
| Trained model objects | Python `lru_cache` (in-process) | Cleared by `invalidate_model_cache()` after retrain |
| React Query | Browser memory | Stale-while-revalidate; keys per endpoint + params |

---

## Security Architecture

```
Request
  │
  ├─ CORS middleware — allow-list from BACKEND_CORS_ORIGINS env var
  ├─ Rate limiting — per-IP fixed window (configurable in settings)
  │
  ├─ Public endpoints — no token required
  │   (teams, match/simulate, tournament/simulate, ml/predict, world-cup/*)
  │
  ├─ JWT-protected endpoints
  │   Authorization: Bearer <access_token>
  │   JWTBearer dep → decode → check type="access" + expiry
  │   → inject CurrentUser (User ORM object)
  │
  └─ Admin-protected endpoints
      AdminUser = Annotated[User, Depends(require_admin)]
      require_admin checks user.role == "admin"
      Applied to: /ml/train, /ml/retrain, /ml/etl/run, /admin/analytics

Token lifecycle:
  login → access_token (short-lived) + refresh_token (long-lived)
  POST /auth/refresh → new access_token (refresh_token validated by type claim)
  Passwords: bcrypt (72-byte safe), cost factor configurable
```

---

## Deployment Architecture

### Development
```
uvicorn app.main:app --reload    SQLite + in-memory cache + eager Celery
npm run dev                      Next.js dev server → proxies /backend/* to :8000
```

### Docker (local full stack)
```
docker compose up --build

Services:
  api      — uvicorn on :8000, mounts wcip-backend/
  worker   — celery worker (run_simulation tasks)
  beat     — celery beat (daily/weekly scheduled jobs)
  db       — postgres:15
  redis    — redis:7
```

### Production (Render + Vercel)
```
render.yaml provisions:
  web service    — uvicorn, auto-scales to 0
  worker service — celery worker
  PostgreSQL 15  — managed
  Redis 7        — managed
  Pre-deploy:    alembic upgrade head

Vercel:
  cd wcip-frontend && vercel deploy
  NEXT_PUBLIC_API_URL → Render web service URL
```

---

## Environment Variables

| Variable | Default | Required | Description |
|---|---|---|---|
| `SECRET_KEY` | (generated) | Prod | JWT signing key (≥ 32 bytes) |
| `DATABASE_URL` | sqlite:///./wcip.db | No | SQLite (dev) or PostgreSQL URL |
| `REDIS_URL` | redis://localhost:6379/0 | No | Redis for cache + Celery |
| `BACKEND_CORS_ORIGINS` | `["http://localhost:3000"]` | Prod | Frontend origin(s) |
| `FOOTBALL_DATA_API_KEY` | `""` | No | football-data.org free tier key |
| `ML_MODELS_DIR` | `models` | No | Directory for trained model pickles |
| `ML_MIN_TRAINING_SAMPLES` | `200` | No | Minimum rows before training |
| `ML_FEATURE_VERSION` | `v2` | No | Feature set version tag |
| `ETL_AUTO_RUN_ON_STARTUP` | `false` | No | Run ETL on every uvicorn start |
