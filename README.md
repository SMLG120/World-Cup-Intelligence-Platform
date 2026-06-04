# World Cup Intelligence Platform

A football analytics platform that predicts FIFA World Cup matches and simulates
entire tournaments using Elo ratings, a Poisson scoreline model, and Monte Carlo
simulation — wrapped in a FastAPI backend and a Next.js frontend.

> **All output is statistical simulation for education and analysis. This project
> does not provide betting advice and does not encourage gambling.**

---

## What's in the box

The project is three independent-but-connected packages:

| Package | Stack | Role |
|---|---|---|
| `world-cup-intelligence-core` | Python · NumPy · SciPy | The prediction engine (Elo, Poisson, Monte Carlo). Runs offline, fully tested. |
| `wcip-backend` | FastAPI · SQLAlchemy · Celery · Redis | REST API, auth, persistence, async simulations. |
| `wcip-frontend` | Next.js 15 · React 19 · TypeScript · Tailwind | Web client: match predictor, tournament runner, scenario lab, dashboards. |

```
┌──────────────────────── Frontend (Next.js / React) ─────────────────────────┐
│  dashboard · match · tournament · scenarios · teams · saved · history · admin │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                     │  REST (typed client, JWT)
┌───────────────────────────────────▼──────────────────────────────────────────┐
│  Backend (FastAPI)  —  auth · rate-limit · OpenAPI · caching                   │
│     small runs: inline        large runs: Celery worker                        │
├───────────────────────────────────┬──────────────────────────────────────────┤
│  Engine (wcip/*)  —  Elo · Poisson · Monte Carlo · explainability              │
├──────────────┬──────────────────┬─────────────────────────────────────────────┤
│ PostgreSQL   │ Redis (cache +   │ Celery worker (10k–50k-run simulations,       │
│ (or SQLite)  │ Celery broker)   │ scheduled data-refresh hook)                  │
└──────────────┴──────────────────┴─────────────────────────────────────────────┘
```

---

## Algorithms

This is the heart of the project. Everything is classical sports statistics and
simulation — chosen because, for tournament forecasting, well-calibrated
statistical models are more robust and interpretable than a black-box learner.

### 1. Elo rating system
A World-Football-Elo variant. Each team has a strength rating; the expected
result of a match is the logistic function of the rating gap:

```
E_A = 1 / (1 + 10 ^ ((R_B − R_A) / 400))
```

After a match the rating moves toward the observed result:

```
R' = R + K · G · (S − E)
```

where `S ∈ {1, 0.5, 0}`, `K` scales with match importance (friendly →
World Cup final), and `G` is a goal-difference multiplier so blowouts move
ratings more. The engine supports historical recalculation (replaying a match
list) and per-team rating trends.

### 2. Poisson scoreline model
The Elo gap is converted into an **expected-goals supremacy**, producing a goal
rate (λ) for each side. Goals are modelled as two **independent Poisson
distributions**, giving a full scoreline probability matrix `P[i, j]`. From it:

- **Win/Draw/Loss** = sum of the lower triangle / diagonal / upper triangle.
- **Expected goals (xG)** per team = the λ values.

Form, injuries, morale, fatigue, squad chemistry, and coaching enter as
multipliers on the goal rates, which is how scenario adjustments propagate.

### 3. Match simulation
Concrete scorelines are sampled from those Poisson rates. Knockout matches that
finish level go to **extra time** (goal rates scaled by 30/90) and then, if still
level, an **Elo-weighted penalty shootout** (a Bernoulli trial nudged by the
rating gap).

### 4. Tournament engine
Group stage is a round-robin ranked by FIFA tie-breakers
(points → goal difference → goals for). The knockout stage is a **data-driven
bracket** (the official 2022 template, extensible to other formats) resolved by
advancing winners round by round.

### 5. Monte Carlo simulation
The whole tournament is replayed thousands of times (1k–50k) **in parallel**
across CPU cores (seeded `SeedSequence` per worker for reproducibility). The runs
are aggregated into per-stage probabilities (Round of 16 → Champion). Uncertainty
is reported with a **Wilson score confidence interval** on each champion
probability, and an **expected finishing position** weighted by elimination round.

### 6. Explainable predictions
Each prediction is decomposed into the factors that produced it — Elo gap, xG
supremacy, recent form, squad availability, morale — ranked by magnitude and
rendered into plain language ("France is favoured because its Elo rating is 138
points higher and its xG supremacy is +0.6…").

### Probability & statistics used
Logistic (sigmoid) function · Poisson distribution · Bernoulli trials ·
the Monte Carlo method · Wilson score interval for binomial proportions.

---

## Does it use machine learning?

**No — not in the trained-model sense, and the project is explicit about that.**

- There are **no trained ML models**: no XGBoost, Random Forest, Logistic
  Regression, LightGBM, or neural networks are fit on a dataset or used at
  inference. Predictions come entirely from the Elo + Poisson + Monte Carlo
  pipeline above.
- The Elo update rule is a simple **online learning** rule (it adjusts ratings
  from observed results), but that is statistical estimation, not ML.
- Explanations are a **transparent factor decomposition**, not SHAP or
  permutation importance.

The codebase is **architected** so a supervised ML ensemble could be added later
as an additional probability source blended with the Elo/Poisson model, with
SHAP attached for explanations — see *Roadmap*. Until that exists, calling the
platform "ML-powered" would be inaccurate, so we don't.

---

## Tech stack

**Engine** Python 3.12 · NumPy · SciPy
**Backend** FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL/SQLite · Redis ·
Celery · PyJWT · bcrypt
**Frontend** Next.js 15 (App Router) · React 19 · TypeScript · TailwindCSS ·
TanStack Query · Recharts · Framer Motion · React Hook Form + Zod
**Infra** Docker · Docker Compose · Render · Vercel

---

## Repository layout

```
world-cup-intelligence-core/   prediction engine + 15 tests
wcip-backend/                   FastAPI service + 18 tests + Docker/Render
  app/{core,db,models,schemas,repositories,services,api,workers}
  wcip/                         (vendored engine)
  alembic/                      migrations
wcip-frontend/                  Next.js app (16 routes)
  app/                          pages
  lib/                          api client, auth, query hooks, types
  components/                   ui primitives + charts + bracket
```

---

## Quick start

```bash
# 1. Backend (SQLite + in-memory cache; no external services needed)
cd wcip-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000/docs

# 2. Frontend (in a second terminal)
cd wcip-frontend
npm install
cp .env.local.example .env.local
npm run dev                            # http://localhost:3000
```

The Next.js config proxies `/backend/*` → `http://localhost:8000`, so the two
talk to each other without CORS configuration in development.

Full stack with Docker (Postgres + Redis + worker):

```bash
cd wcip-backend && docker compose up --build
```

---

## Testing

```bash
# Engine — 15 tests
cd world-cup-intelligence-core && pip install -r requirements.txt && pytest -q

# Backend — 18 tests (auto-configures temp SQLite + eager Celery)
cd wcip-backend && pytest -q
pytest --cov=app --cov-report=term-missing      # coverage

# Frontend — typecheck + production build
cd wcip-frontend && npm run typecheck && npm run build
```

A dedicated frontend unit/E2E suite (Jest/RTL/Playwright) and a CI workflow are
not yet included — see *Roadmap*.

---

## Data

The engine ships with the real 2022 World Cup field: 32 nations, official groups,
the official knockout bracket, and an approximate published Elo snapshot
(eloratings.net, Nov 2022) as the seed. The engine recomputes ratings from match
results once an ETL feed is connected.

A scheduled `refresh_data` Celery task is stubbed as the integration point.
Legitimately usable sources to wire it to: **Football-Data.org** (free API),
**StatsBomb Open Data** (CC-licensed), and public international-results / Elo
datasets. Note that FotMob, Opta, SofaScore, and Transfermarkt are proprietary
and prohibit scraping — the platform does not use them.

---

## Security

JWT access/refresh tokens (distinguished by a `type` claim), bcrypt password
hashing, role-based admin authorization, per-IP rate limiting, CORS allow-list,
Pydantic validation on every payload, ORM-only queries (no string SQL), and
baseline security headers via Next.js middleware.

---

## Roadmap

- **ML ensemble layer** — train XGBoost / Random Forest / Logistic Regression on
  ETL-derived features, blend with the Elo/Poisson probabilities, and attach SHAP
  for explanations. (The architecture reserves a slot for this.)
- **Live data pipeline** — connect `refresh_data` to Football-Data.org / StatsBomb
  so Elo and form update from real results.
- **Remaining UX** — PDF/CSV report export, OAuth (Google/GitHub) via NextAuth.
- **Test & CI** — frontend Jest/RTL + Playwright E2E, GitHub Actions running all
  suites on push.

---

## License & disclaimer

For educational and analytical use. Predictions are probabilistic simulations,
not forecasts of certainty and not betting guidance.
