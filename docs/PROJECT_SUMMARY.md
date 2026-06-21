# World Cup Intelligence Platform — Project Summary

> Statistical simulation and prediction platform for FIFA World Cup 2026.
> Educational analysis only — not betting advice.

---

## Project Goal

The World Cup Intelligence Platform (WCIP) simulates every possible outcome of the 2026 FIFA World Cup using Elo ratings, expected-goals (xG) models, FIFA rankings, Monte Carlo simulation, and a multi-model machine learning ensemble. It provides recruiters, engineers, and football analysts with a working example of a production-grade data pipeline feeding a live prediction system.

---

## Architecture Overview

```
Raw Sources (eloratings.net · FIFA · martj42 CSV · Wikipedia)
         │
         ▼
   ETL Pipeline  ──────────────────────────────────────────────────┐
   (extract → transform → validate → load)                         │
         │                                                         │
         ▼                                                         │
   Versioned Snapshots                                             │
   (EloRatingSnapshot · FifaRankingSnapshot · MatchResult)        │
         │                                                         │
         ▼                                                         │
   Feature Engineering  (33 differential features, v2)            │
         │                                                         │
         ▼                                                         │
   ML Ensemble  (XGBoost · CatBoost · LightGBM · Logistic)       │
         │                           ▲                             │
         ▼                           │ retraining trigger          │
   FastAPI REST API  ◄───────────────┘                             │
   (14 sub-routers, JWT auth, rate limiting)                       │
         │                                                         │
         ▼                                                         │
   Next.js Frontend                                                │
   (React Query · TailwindCSS · Framer Motion · Recharts)  ───────┘
```

---

## Backend Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| API | FastAPI (Python 3.12+) | REST API, JWT auth, request validation |
| ORM | SQLAlchemy 2.0 | Typed models, declarative mapping |
| Migrations | Alembic | Schema versioning |
| Task Queue | Celery + Redis | Async ETL, scheduled refreshes |
| Cache | Redis (or in-process dict) | Prediction caching, cache invalidation |
| Engine | Custom Elo + Poisson | Match outcome probabilities |
| Simulation | Monte Carlo | Tournament path probabilities (up to 50 K runs) |
| ML | scikit-learn / XGBoost / CatBoost / LightGBM | Ensemble match prediction |
| SHAP | shap | Model explainability |

**Key files:**
```
wcip-backend/
├── app/
│   ├── api/v1/          # 14 route modules
│   ├── core/            # config, deps, security, cache, rate limit
│   ├── db/              # engine, session, init_db
│   ├── models/          # SQLAlchemy ORM models
│   ├── repositories/    # database query layer
│   ├── schemas/         # Pydantic request/response schemas
│   ├── services/        # orchestration (predictions, refresh, ratings)
│   └── workers/         # Celery app
├── etl/
│   ├── elo/             # Elo extract → transform → load → validate
│   ├── extract/         # data source fetchers
│   ├── fifa_rankings/   # FIFA ranking pipeline
│   ├── players/         # squad ingestion (PDF + CSV)
│   ├── schedulers/      # Celery tasks
│   └── pipeline.py      # master ETL orchestrator
├── ml/
│   ├── features.py      # 33-feature engineering (v2)
│   ├── train.py         # model training
│   ├── ensemble.py      # ensemble weighting
│   ├── predict.py       # inference layer
│   ├── retrain_if_needed.py  # smart recalibration logic
│   └── validate_features.py  # NaN/inf/shape checks
├── scripts/
│   ├── validate_world_cup_data.py   # match & standings integrity
│   ├── validate_rankings.py         # Elo & FIFA coverage checks
│   ├── validate_world_cup_2026.py   # team/player/coach audit
│   └── validate_squad_ingestion.py  # squad PDF audit
└── wcip/engine/
    ├── elo.py           # Elo update formulas
    ├── montecarlo.py    # parallel tournament simulation
    ├── poisson.py       # goal distribution model
    └── tournament.py    # group stage + knockout simulation
```

---

## Frontend Architecture

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Framework | Next.js 15 (App Router) | SSR + client components |
| Language | TypeScript | End-to-end type safety |
| State | React Query (TanStack) | Server state, caching, mutations |
| Styling | TailwindCSS + CSS vars | Consistent design tokens |
| Animation | Framer Motion | Page/bracket transitions |
| Charts | Recharts | Champion probability bars |
| Auth | JWT (localStorage) | Client-side token storage |

**Key pages:**
```
wcip-frontend/app/
├── page.tsx             # Landing / hero
├── wc2026/bracket/      # Visual knockout bracket (SVG connectors)
├── world-cup/           # Group tables + simulation
├── predict/             # Single match predictor
├── teams/               # Team list + Elo history
├── models/              # ML model dashboard
├── saved/               # Saved simulations
├── admin/               # Admin controls (auth-gated)
└── scenarios/           # Scenario comparison
```

---

## Database Architecture

**Engine:** SQLite (development) → PostgreSQL (production)

**Core tables:**

| Table | Purpose |
|-------|---------|
| `teams` | 48 qualified nations with Elo, FIFA rank, feature multipliers |
| `elo_history` | Point-in-time Elo after each match |
| `elo_rating_snapshots` | Immutable ingestion snapshots (eloratings.net / Wikipedia) |
| `team_elo_ratings` | Per-team rows within each snapshot |
| `elo_source_logs` | Fetch/load audit trail |
| `fifa_ranking_snapshots` | Immutable FIFA publication snapshots |
| `fifa_ranking_entries` | Per-team rank within a snapshot |
| `match_results` | 50,000+ historical international results |
| `match_features` | Pre-computed 33-feature vectors |
| `players` | Squad players with FIFA PDF fields |
| `coaches` | Head coaches per team |
| `qualified_teams` | WC2026 confirmed qualifiers with group assignments |
| `ml_model_records` | Trained model metadata and metrics |
| `simulations` | Saved simulation results (user-linked) |

**Key design decisions:**
- Elo and FIFA ranking snapshots are **immutable** (never overwritten, versioned by ID)
- `is_current = True` flags the latest valid snapshot for fast queries
- Alembic manages all schema migrations (5 migration files)
- Historical training rows use **point-in-time** feature values to prevent data leakage

---

## Data Pipeline Architecture

```
Sources                    Frequency        Handler
──────────────────────────────────────────────────────
martj42 international CSV  Daily            etl/extract/international_results.py
eloratings.net/2026        Weekly           etl/elo/extract_elo.py
Wikipedia Elo ratings      Weekly (backup)  etl/elo/wikipedia_elo.py
FIFA ranking page          Monthly          etl/extract/fifa_rankings.py
FIFA squad PDF             Once (pre-WC)    etl/players/load_squad_pdf.py
Player rating CSV          On-demand        etl/player_ratings/csv_import.py
```

**Refresh order:**
1. `refresh_world_cup_results()` — latest match data
2. `refresh_elo_ratings()` — Elo snapshot with source fallback chain
3. `refresh_fifa_rankings()` — official FIFA rank snapshot
4. `refresh_player_availability()` — player CSV if present
5. `refresh_prediction_cache()` — invalidate stale prediction cache
6. `evaluate_retraining_need()` — trigger ML refresh if thresholds exceeded

All steps are individually fault-tolerant: one failure does not block the others.

---

## ML Pipeline Architecture

**Feature engineering (v2 — 33 features):**
- Elo differential, FIFA rank differential
- xG / xGA history, form (points-per-game last N matches)
- Squad age, market value, injury burden, chemistry, coach quality
- Player rating features (GK, DEF, MID, FWD, bench depth)
- International caps / goals (squad-level)
- Tournament experience, rest days, travel distance

**Ensemble models:**
- XGBoost (gradient boosting)
- CatBoost (categorical boosting)
- LightGBM (fast gradient boosting)
- Logistic Regression (calibrated baseline)
- Weighted ensemble with SHAP explanations

**Prediction modes:**
| Mode | Description |
|------|------------|
| `statistical` | Elo + Poisson model only |
| `ml` | ML ensemble only |
| `ensemble` | Weighted combination (default) |

**Retraining thresholds:**
| Trigger | Threshold | Action |
|---------|-----------|--------|
| New match results | ≥ 1 match | Refresh features + cache |
| FIFA rank changes | ≥ 5 material changes | Recalibration |
| Elo changes | ≥ 10 material changes | Recalibration |
| Player data changes | ≥ 100 records | Full retraining |

---

## WC2026 Simulation Features

- **48 teams** across 12 groups (A–L), 4 teams per group
- Group stage: 3 matches per team, full round-robin
- Advancement: top 2 per group + 8 best third-place teams
- Knockout: Round of 32 → R16 → QF → SF → Final + 3rd-place match
- Sequential bracket pairing (M49+M50 → M65, etc., matching FIFA draw)
- Monte Carlo: up to 50,000 parallel runs
- Per-team probabilities: champion, finalist, semi, QF, R16, R32
- Wilson 95% confidence intervals on all champion probabilities
- Group tables, match fixtures, best-third ranking all returned per simulation

---

## Current Limitations

- **Live score ingestion** not implemented — match results come from the martj42 archive CSV (updated with a day or two lag)
- **Bracket seeding** uses sequential pairing; actual WC seeding schedule may differ post-draw
- **Squad PDF parsing** requires the FIFA PDF file to be present locally; no auto-download in production
- **No WebSocket** — frontend polls or requires manual refresh for live tournament data
- **SQLite in dev** does not support concurrent writes; switch to PostgreSQL for production load
- **ML models** are serialized as `.pkl` files locally; no remote model registry configured
- **Wikipedia Elo** is a secondary source only; used when eloratings.net is unreachable

---

## Local Startup Commands

```bash
# 1. Clone and set up environment
cp wcip-backend/.env.example wcip-backend/.env   # fill in secrets
cp wcip-frontend/.env.example wcip-frontend/.env.local

# 2. Backend
cd wcip-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python app/db/init_db.py          # seed WC2026 teams
uvicorn app.main:app --reload     # http://localhost:8000

# 3. Frontend
cd ../wcip-frontend
npm install
npm run dev                       # http://localhost:3000

# 4. Seed data and run ETL
cd wcip-backend
python -m etl.pipeline            # full pipeline
python -m ml.train                # train ML models
python -m ml.validate_features    # verify no NaN/inf
python -m scripts.validate_world_cup_2026

# 5. Tests
pytest -q
cd ../wcip-frontend && npm run typecheck && npm run build
```

---

## Production Deployment Assumptions

| Concern | Approach |
|---------|---------|
| Database | PostgreSQL 15+ with connection pooling (PgBouncer) |
| Secret management | Environment variables injected by secrets manager |
| Task queue | Celery + Redis; Beat scheduler for cron jobs |
| Model storage | S3/GCS bucket mounted at `ML_MODELS_DIR` |
| Frontend | Vercel or static export behind CDN |
| Backend | Docker container on Railway / Fly.io / ECS |
| Cache | Redis Cluster or Elasticache |
| Monitoring | Structured JSON logs → Datadog / Grafana Loki |
| Auth | JWT HS256; upgrade to RS256 for multi-service |

---

---

## RAG System

The RAG layer provides natural language explanation and retrieval over tournament data.
It is an explanation-only layer — it never determines match outcomes.

| Component | Location | Purpose |
|-----------|----------|---------|
| Data sources | `rag/sources.py` | Fetches teams, players, coaches, groups, model metadata |
| Chunking | `rag/chunking.py` | 200-token overlapping text chunks |
| Indexer | `rag/indexer.py` | TF-IDF keyword index; run via `POST /admin/rag/index` |
| Retriever | `rag/retriever.py` | TF-IDF cosine-like scoring + context filters |
| Generator | `rag/generator.py` | Template-based answer assembly with educational disclaimer |
| Service | `rag/service.py` | `answer_question()` orchestrator + query/answer audit log |
| API | `app/api/v1/rag.py` | `/rag/ask`, `/rag/status`, `/rag/documents`, `/admin/rag/index` |
| DB Tables | `rag_documents`, `rag_chunks`, `rag_embeddings`, `rag_queries`, `rag_answers` | |
| Frontend | `AskAnalystBox`, `RagAnswerCard`, `RagSourcesList`, `PredictionExplanationPanel` | |

*Updated: 2026-06-21 | Feature version: v2 | Simulation engine: Monte Carlo + Elo/Poisson | ML: XGBoost/CatBoost/LightGBM ensemble | RAG: TF-IDF keyword retrieval*
