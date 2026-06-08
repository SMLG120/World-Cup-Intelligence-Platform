# World Cup Intelligence Platform

A full-stack football prediction app for international tournaments. The backend
combines statistical simulation, machine-learning predictions, explainability,
user accounts, saved simulations, and a tournament-aware data pipeline. The
frontend turns those APIs into dashboards, match tools, tournament simulations,
team pages, and model views.

> Predictions are probabilistic analysis for education and exploration. They are
> not betting advice.

## What Is In The App

The platform has four main layers:

1. **FastAPI backend** in `wcip-backend/app`
2. **Prediction engine** in `wcip-backend/wcip` and `wcip-backend/ml`
3. **ETL/data layer** in `wcip-backend/etl`
4. **Next.js frontend** in `wcip-frontend`

The important flow is:

```text
Raw football data
  -> ETL extract/transform/validate/load
  -> SQLite or Postgres tables
  -> feature engineering
  -> statistical engine + ML models
  -> FastAPI endpoints
  -> Next.js interface
```

## How The Code Works

### 1. Startup And Database Seeding

When the backend starts, `app/main.py` runs the app lifespan hook. That calls
`app/db/init_db.py`.

Step by step:

1. `create_tables()` creates any missing SQLAlchemy tables.
2. `seed_teams()` inserts the 2022 baseline team registry.
3. `seed_qualified_teams_2026()` inserts the WC2026 qualified-team tracker.
4. `seed_2026_teams_into_team_table()` ensures all WC2026 teams exist in the
   main team table.
5. `seed_world_cup_2026_registry()` runs the dedicated WC2026 seed ETL.

The startup seed is lightweight and idempotent. It loads the official 48
WC2026 teams and group labels, then creates one clearly marked placeholder
player and coach per team when no verified roster snapshot has been imported.
Real roster imports use a different `data_source` and replace those placeholder
rows team by team.

### 2. Generic ETL Pipeline

The generic ETL orchestrator lives in `wcip-backend/etl/pipeline.py`.

Step by step:

1. `run_historical_results()` downloads or reads cached international results.
2. `etl/transform/normalize.py` canonicalizes team names.
3. `etl/validation/schema.py` rejects malformed matches.
4. `etl/load/db_loader.py` upserts rows into `match_results`.
5. `run_elo_update()` refreshes `teams.elo`.
6. `run_full_pipeline()` runs historical results, Elo update, and the WC2026 seed.

Useful commands:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_historical_results; run_historical_results()"
python -c "from etl.pipeline import run_elo_update; print(run_elo_update())"
python -c "from etl.pipeline import run_full_pipeline; print(run_full_pipeline())"
```

### 3. WC2026 Seed ETL

The World Cup 2026 seed pipeline is isolated from the generic football-data ETL.
That makes tournament roster updates easier and keeps API-Football snapshots from
leaking into unrelated ingestion code.

Key files:

- `wcip-backend/etl/world_cup_2026/seed_data.py`
- `wcip-backend/etl/world_cup_2026/ingest.py`
- `wcip-backend/etl/world_cup_2026_seed.py`

Step by step:

1. `seed_data.py` provides WC2026 metadata, official group labels, and explicit
   placeholder roster/coach rows for local startup.
2. `ingest.py` accepts either a Python payload or a JSON file.
3. Teams are normalized into `TeamSeedRecord`.
4. Players are normalized into `PlayerSeedRecord`.
5. Coaches are normalized into `CoachSeedRecord`.
6. The loader upserts:
   - `teams`
   - `qualified_teams`
   - `players`
   - `coaches`
7. Existing records are updated by stable keys:
   - team name for teams
   - `external_id + data_source`, then `name + team_name`, for players
   - `team_name` for coaches

Run with the built-in team fallback:

```bash
cd wcip-backend
python -c "from etl.world_cup_2026.ingest import run_wc2026_seed; print(run_wc2026_seed())"
```

The built-in fallback writes placeholder roster records with
`data_source="world_cup_2026_placeholder"`. These records are not real squad or
coach data; they exist so `/players`, `/world-cup/players/{team_name}`, and team
pages remain stable until a verified source snapshot is loaded.

Run from a source snapshot:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_wc2026_seed; print(run_wc2026_seed('data/wc2026_snapshot.json'))"
```

Expected payload shape:

```json
{
  "tournament_year": 2026,
  "teams": [
    {
      "team": {"name": "Czech Republic", "code": "CZE"},
      "confederation": "UEFA",
      "elo": 1700,
      "fifa_rank": 20,
      "group_label": "A",
      "pot": 2
    }
  ],
  "players": [
    {
      "player": {"id": 999001, "name": "Example Player", "age": 28},
      "statistics": [
        {
          "team": {"name": "Czech Republic"},
          "games": {"position": "Goalkeeper", "minutes": 90},
          "goals": {"total": 0, "assists": 1}
        }
      ]
    }
  ],
  "coaches": [
    {
      "name": "Example Coach",
      "team_name": "Czech Republic",
      "nationality": "Czechia",
      "preferred_formation": "4-2-3-1",
      "impact_score": 1.08
    }
  ]
}
```

The normalizer maps known variants such as `Czech Republic` to `Czechia`, so the
database stays consistent across historical results, API payloads, and frontend
selectors.

### 4. Feature Engineering And ML

Feature generation lives in `wcip-backend/ml/features.py`.

The feature layer builds home-minus-away differentials such as:

- Elo difference
- FIFA rank difference
- recent form
- squad market value
- injury burden
- coach impact
- average age
- tournament experience
- starting XI and bench strength

Training uses `wcip-backend/ml/train.py`. Model records are stored in the
`ml_models` table and model files are written under `wcip-backend/models`.

Commands:

```bash
cd wcip-backend
python -m ml.train --model all
python -m ml.train --model catboost
python -m ml.train --model all --full-refresh
```

### 5. Prediction Runtime

The service bridge is `wcip-backend/app/services/prediction.py`.

For a match prediction:

1. The API receives home team, away team, and optional modifiers.
2. The service loads the tournament edition data.
3. The scoreline model estimates expected goals.
4. Win/draw/loss probabilities are calculated.
5. The response includes probabilities, xG, and explanation factors.

For tournament simulation:

1. The API receives an edition and run count.
2. `MonteCarloEngine` replays the tournament many times.
3. Knockouts resolve tied matches through extra-time and penalty logic.
4. Results aggregate into stage probabilities and champion odds.

For hybrid ML prediction:

1. The ML endpoint builds the feature vector.
2. Available trained models produce outcome probabilities.
3. The ensemble combines model outputs with the statistical layer.
4. SHAP or fallback feature explanations describe the result.

## How The Interface Works

The frontend is a Next.js app in `wcip-frontend`.

### Frontend Request Flow

1. Pages and components call React Query hooks in `wcip-frontend/lib/queries.ts`.
2. Hooks use the typed client in `wcip-frontend/lib/api.ts`.
3. `api.ts` sends requests to the FastAPI backend.
4. Authenticated routes use `wcip-frontend/lib/auth-context.tsx` for JWT storage
   and token refresh.
5. Shared UI components in `wcip-frontend/components` render charts, forms,
   probability bars, brackets, and controls.

### Main Screens

- `/dashboard` gives the user an overview of teams and predictions.
- `/predict` and `/simulate` provide single-match tools.
- `/tournament` runs Monte Carlo tournament simulations.
- `/wc2026` and `/world-cup` expose World Cup 2026 views.
- `/teams` lists teams and links to team detail pages.
- `/team/[id]` shows one team.
- `/player/[id]` shows one player.
- `/compare` compares teams or prediction outputs.
- `/scenarios` compares two or three what-if simulations.
- `/models` shows model metrics and feature information.
- `/saved` and `/history` show user simulation history.
- `/login`, `/register`, and `/profile` handle user accounts.

### Interface Step By Step

1. Start the backend at `http://localhost:8000`.
2. Start the frontend at `http://localhost:3000`.
3. Open the frontend.
4. Use the navigation bar to choose a workflow.
5. Pick teams from selectors populated by `GET /api/v1/teams`.
6. Adjust sliders or scenario controls when available.
7. Submit the form.
8. The frontend calls the relevant backend endpoint.
9. Results render as probabilities, cards, charts, or bracket views.
10. If logged in, users can save simulations and revisit them later.

## API Map

All backend API routes use the `/api/v1` prefix.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/teams` | List teams |
| `GET` | `/teams/{id}` | Team detail |
| `GET` | `/teams/{id}/stats` | Team model inputs |
| `GET` | `/teams/{id}/elo-history` | Elo history |
| `GET` | `/players` | Player registry with team/search filters |
| `GET` | `/players/{id}` | Player detail |
| `POST` | `/match/simulate` | Single-match statistical prediction |
| `POST` | `/tournament/simulate` | Monte Carlo tournament simulation |
| `POST` | `/scenario/compare` | Compare 2-3 scenarios |
| `GET` | `/editions` | Available tournament editions |
| `POST` | `/simulations` | Create saved simulation |
| `GET` | `/simulations` | List saved simulations |
| `GET` | `/simulations/{id}` | Fetch saved simulation |
| `PATCH` | `/simulations/{id}` | Rename or publish simulation |
| `DELETE` | `/simulations/{id}` | Delete saved simulation |
| `POST` | `/auth/register` | Create account |
| `POST` | `/auth/login` | Login and receive JWTs |
| `POST` | `/auth/refresh` | Refresh access token |
| `GET` | `/auth/me` | Current user |
| `GET` | `/ml/models` | Model registry |
| `GET` | `/ml/features` | Feature vector for a match |
| `GET` | `/ml/feature-names` | Feature names for the current feature version |
| `GET` | `/ml/explanations` | SHAP or feature-importance explanation |
| `POST` | `/ml/predict` | Hybrid statistical + ML prediction |
| `POST` | `/ml/train` | Trigger model training |
| `POST` | `/ml/retrain` | Trigger retraining |
| `POST` | `/ml/etl/run` | Trigger the ETL pipeline |
| `GET` | `/world-cup/qualified-teams` | WC2026 qualified-team list |
| `GET` | `/world-cup/groups` | WC2026 groups or pending draw status |
| `GET` | `/world-cup/bracket` | WC2026 knockout bracket |
| `POST` | `/world-cup/simulate` | WC2026 tournament simulation |
| `GET` | `/world-cup/schedule` | WC2026 schedule metadata |
| `GET` | `/world-cup/teams/{team_name}` | WC2026 team, squad, and coach detail |
| `GET` | `/world-cup/players/{team_name}` | WC2026 squad list |
| `GET` | `/health` | Backend health check |

Interactive API docs are available at `http://localhost:8000/docs` when the
backend is running.

## Local Setup

### Backend

```bash
cd wcip-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The backend defaults to SQLite at `wcip-backend/wcip.db`, in-memory cache, and no
external services.

Useful environment variables:

```bash
DATABASE_URL=sqlite:///./wcip.db
SECRET_KEY=change-me
BACKEND_CORS_ORIGINS=http://localhost:3000
ETL_AUTO_RUN_ON_STARTUP=false
FOOTBALL_DATA_API_KEY=
```

`ETL_AUTO_RUN_ON_STARTUP` is reserved for heavier external refresh jobs. The
startup-safe WC2026 registry seed runs regardless, because it uses local data
and placeholder records only.

### Frontend

```bash
cd wcip-frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:3000`.

### Full Stack With Docker

```bash
cd wcip-backend
docker compose up --build
```

This starts the backend, worker, beat scheduler, Postgres, and Redis.

## Common Workflows

### Refresh Historical Results

```bash
cd wcip-backend
python -c "from etl.pipeline import run_historical_results; print(run_historical_results())"
```

### Refresh Elo Ratings

```bash
cd wcip-backend
python -c "from etl.pipeline import run_elo_update; print(run_elo_update())"
```

### Seed WC2026 Teams, Players, And Coaches

```bash
cd wcip-backend
python -c "from etl.world_cup_2026.ingest import run_wc2026_seed; print(run_wc2026_seed())"
```

With a JSON source snapshot:

```bash
cd wcip-backend
python -c "from etl.world_cup_2026.ingest import run_wc2026_seed; print(run_wc2026_seed(source_path='data/wc2026_snapshot.json'))"
```

### Run A Match Prediction

```bash
curl -X POST http://localhost:8000/api/v1/match/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "home": "Argentina",
    "away": "France",
    "knockout": false
  }'
```

### Run A Tournament Simulation

```bash
curl -X POST http://localhost:8000/api/v1/tournament/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "edition": "2022",
    "runs": 1000
  }'
```

## Repository Layout

```text
.
├── README.md
├── DATA_PIPELINE.md
├── MODEL_CARD.md
├── ARCHITECTURE.md
├── world_cup_2026_audit.md
├── wcip-backend
│   ├── app
│   │   ├── api/v1
│   │   ├── core
│   │   ├── db
│   │   ├── models
│   │   ├── repositories
│   │   ├── schemas
│   │   └── services
│   ├── etl
│   │   ├── extract
│   │   ├── load
│   │   ├── transform
│   │   ├── validation
│   │   ├── world_cup_2026
│   │   ├── world_cup_2026_seed.py
│   │   └── pipeline.py
│   ├── ml
│   ├── tests
│   └── wcip
└── wcip-frontend
    ├── app
    ├── components
    └── lib
```

## Testing

Backend:

```bash
cd wcip-backend
env DEBUG=false pytest -q
```

Focused WC2026 seed ETL test:

```bash
cd wcip-backend
env DEBUG=false pytest -q tests/test_wc2026_seed.py
```

Frontend:

```bash
cd wcip-frontend
npm run typecheck
npm run build
```

Note: in restricted sandboxes, the Monte Carlo tests may fail because
`ProcessPoolExecutor` checks OS semaphore limits. Run the backend test command
outside the sandbox if you see `PermissionError: Operation not permitted` from
`os.sysconf("SC_SEM_NSEMS_MAX")`.

## Data Sources

- International match results: `martj42/international_results`
- Elo ratings: `eloratings.net`
- Official WC2026 teams/groups: FIFA standings reference
- WC2026 live/squad/team data: API-Football / API-SPORTS, `league=1`,
  `season=2026`
- Local fallback: `wcip-backend/wcip/data/wc2026.py`
- Placeholder roster/coach records: `data_source="world_cup_2026_placeholder"`
  until a verified source snapshot is loaded

## Deployment Notes

- Set a strong `SECRET_KEY` in production.
- Use Postgres for production `DATABASE_URL`.
- Use Redis for cache and Celery broker/result backend.
- Set `BACKEND_CORS_ORIGINS` to the deployed frontend origin.
- Set frontend API configuration to point at the deployed backend.
- Run Alembic migrations before serving production traffic.
- Run WC2026 seed ETL from a vetted source snapshot when tournament rosters are
  updated.

## License And Disclaimer

Use for educational and analytical purposes only. Predictions are uncertain
probabilistic outputs, not guarantees. Respect the licenses and terms of the data
providers used by your deployment.
