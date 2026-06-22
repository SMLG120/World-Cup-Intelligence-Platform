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
  -> versioned Elo rating snapshots
  -> versioned FIFA ranking snapshots
  -> SQLite or Postgres tables
  -> feature engineering
  -> statistical engine + ML models
  -> FastAPI endpoints
  -> Next.js interface
```

The homepage explains the prediction stack in user-facing football terms:
Elo ratings, official FIFA rankings, FIFA squad PDF data, five ML models
(Logistic Regression, Random Forest, XGBoost, LightGBM, CatBoost), Poisson score
modeling, Monte Carlo simulation, and the complete WC2026 bracket path from
groups through champion.

Data-source boundaries matter:

- Elo comes from World Football Elo sources such as `eloratings.net`, with an
  embedded Elo fallback only when live sources are unavailable.
- The static World Football Elo PDF snapshot dated 2026-06-21 can be converted
  with `python -m scripts.convert_elo_pdf_to_csv` and loaded with
  `python -m etl.elo.load_elo_csv`. The generated CSV is
  `wcip-backend/data/processed/world_football_elo_ratings_2026_06_21.csv`;
  validation requires 244 teams in the current extract and top rows Spain 2129,
  Argentina 2128, France 2084, England 2055, Colombia 1998, Brazil 1986.
- FIFA rankings come from the official FIFA men's ranking source.
- Squad/player facts come from the FIFA WC2026 squad PDF and feed player/squad
  features. The PDF is not used as an Elo or FIFA ranking source.

Probability API fields use fraction units internally and over the wire:
`0.14232` means `14.2%`. Frontend display helpers multiply by 100 once and
defensively normalize legacy percent-unit responses.

`GET /api/v1/data/freshness` exposes the frontend freshness fields: Elo updated,
FIFA ranking updated, squad data updated, latest results updated, model trained,
feature version, and prediction data snapshot version.

Local test login:

```bash
cd wcip-backend
python -m scripts.seed_test_user
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testtest"}'
```

The login route also accepts the OAuth2 form shape (`username` + `password`) for
Swagger and older clients. The seed command is development/test-only and is
idempotent.

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
rows team by team. Startup skips those placeholders once real PDF players or
coaches exist, so verified squad data is not overwritten on app boot.

### 2. Generic ETL Pipeline

The generic ETL orchestrator lives in `wcip-backend/etl/pipeline.py`.

Step by step:

1. `run_historical_results()` downloads or reads cached international results.
2. `etl/transform/normalize.py` canonicalizes team names.
3. `etl/validation/schema.py` rejects malformed matches.
4. `etl/load/db_loader.py` upserts rows into `match_results`.
5. `run_elo_update()` fetches World Football Elo data, stores an immutable
   snapshot in `elo_rating_snapshots` / `team_elo_ratings`, appends compatible
   `elo_history` rows, and refreshes `teams.elo` as a display cache.
6. `run_fifa_rankings_update()` fetches the latest official FIFA ranking
   publication, validates it, stores it as a timestamped snapshot, and refreshes
   `teams.fifa_rank` as a display cache.
7. `run_full_pipeline()` runs historical results, Elo update, FIFA ranking
   snapshot ingestion, and the WC2026 seed.

Useful commands:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_historical_results; run_historical_results()"
python -c "from etl.pipeline import run_elo_update; print(run_elo_update())"
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"
python -c "from etl.pipeline import run_full_pipeline; print(run_full_pipeline())"
```

### 3. FIFA Ranking Snapshot ETL

FIFA rankings are no longer manually maintained. The ranking pipeline lives in
`wcip-backend/etl/extract/fifa_rankings.py`,
`wcip-backend/etl/load/ranking_loader.py`, and
`wcip-backend/etl/monitoring/ranking_monitor.py`.

Step by step:

1. The extractor reads the official FIFA ranking page metadata.
2. It resolves the latest men’s ranking schedule id.
3. It downloads the corresponding FIFA ranking payload.
4. It normalizes team names through the same canonical-name layer used by match
   results.
5. It validates that ranks and teams are unique and that the snapshot has enough
   entries to be credible.
6. The loader writes one row to `fifa_ranking_snapshots` and one row per team to
   `fifa_ranking_entries`.
7. Older snapshots remain in the database for reproducible feature generation,
   backtesting, Elo recalibration, tournament simulations, and ML training.
8. The newest snapshot updates `teams.fifa_rank` only as a current UI/API cache.

Run a ranking refresh:

```bash
cd wcip-backend
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"
```

Check for changes and optionally trigger retraining:

```bash
cd wcip-backend
python -c "from etl.monitoring.ranking_monitor import check_fifa_ranking_update; print(check_fifa_ranking_update(force_refresh=True, trigger_retraining=True))"
```

The Celery beat scheduler also runs `etl.refresh_fifa_rankings` daily. Material
changes are defined as top-10 movement, a rank delta of at least 5 inside the top
50, or a points delta of at least 25.

### 4. Real-Time Elo, FIFA, Match, And Player Refresh

Real-time refresh code extends the existing ETL architecture instead of replacing
it.

Key files:

- `wcip-backend/etl/elo/` — World Football Elo extract, transform, validate, load
- `wcip-backend/etl/fifa_rankings/` — dedicated FIFA ranking ETL package wrappers
- `wcip-backend/etl/players/` — legal CSV player import/profile helpers
- `wcip-backend/app/services/data_refresh_service.py` — refresh orchestration
- `wcip-backend/app/services/rating_update_service.py` — idempotent Elo update after match result changes
- `wcip-backend/ml/validate_features.py` — feature shape/NaN/inf validation
- `wcip-backend/ml/validate_player_features.py` — player-data coverage and player-feature validation
- `wcip-backend/ml/retrain_if_needed.py` — recalibration trigger decision script

Step by step:

1. Elo refresh tries `https://www.eloratings.net/2026_World_Cup`, then
   `https://www.eloratings.net/World.tsv`, then the local embedded fallback.
2. The loader stores each Elo ingest as an immutable `elo_rating_snapshots` row
   and one `team_elo_ratings` row per team.
3. FIFA ranking refresh keeps using the official FIFA men's ranking source and
   stores immutable snapshots.
4. Match result ingestion triggers `update_ratings_after_match(match_id)` for
   2026 World Cup result rows. Reprocessing the same match result is idempotent.
5. Player data is imported from legal/manual CSV sources only. Generated player
   profile text is based only on stored fields and labels incomplete records.
6. `/api/v1/data/freshness` exposes the latest Elo, FIFA, match, player, model,
   feature, and snapshot metadata.
7. Admin users can call:
   - `POST /api/v1/admin/data/refresh-elo`
   - `POST /api/v1/admin/data/refresh-fifa-rankings`
   - `POST /api/v1/admin/data/refresh-players`
   - `POST /api/v1/admin/data/refresh-all`
   - `POST /api/v1/admin/ml/retrain-if-needed`
8. The frontend displays freshness indicators and admin refresh controls on the
   main prediction, simulation, team, player, and model pages.

Scheduled Celery tasks:

```text
etl.refresh_elo_ratings
etl.refresh_fifa_rankings
etl.refresh_world_cup_results
etl.refresh_player_availability
etl.refresh_prediction_cache
etl.retrain_if_needed
```

Manual validation:

```bash
cd wcip-backend
python -m ml.validate_features
python -m ml.validate_player_features
python -m ml.retrain_if_needed --material-ranking-changes 5 --apply
curl http://localhost:8000/api/v1/data/freshness
curl http://localhost:8000/api/v1/ratings/elo/latest?limit=10
curl http://localhost:8000/api/v1/rankings/fifa/latest?limit=10
```

### 5. WC2026 Seed ETL

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

### 6. Feature Engineering And ML

Feature generation lives in `wcip-backend/ml/features.py`.

The feature layer builds home-minus-away differentials such as:

- Elo difference
- FIFA rank difference from the latest ranking snapshot on or before the match
  date
- recent form
- squad market value
- injury burden
- coach impact
- average age
- tournament experience
- starting XI and bench strength

Historical feature generation uses point-in-time FIFA ranking snapshots and Elo
history when available. It does not use today’s rankings for old matches. If a
historical snapshot is missing, ranking/Elo features fall back to neutral values
instead of leaking current data into training.

Training uses `wcip-backend/ml/train.py`. Model records are stored in the
`ml_models` table and model files are written under `wcip-backend/models`.

Commands:

```bash
cd wcip-backend
python -m ml.train --model all
python -m ml.train --model catboost
python -m ml.train --model all --full-refresh
```

### 6. RAG Explanations

RAG is an explanation layer, not a prediction engine. It indexes safe factual
records from teams, players, coaches, WC2026 groups, and model metadata. It
never reads `.env` files, tokens, local secrets, private keys, or model weights.

Step by step:

1. `rag/sources.py` turns public database records into indexable text.
2. `rag/indexer.py` chunks those documents and stores TF-IDF terms.
3. `rag/retriever.py` retrieves matching chunks, including aliases such as
   `BIH` for `Bosnia and Herzegovina`.
4. `rag/generator.py` assembles a factual answer and warns when data is missing.
5. Prediction or bracket questions are redirected back to `/predict`,
   `/wc2026/bracket`, or the simulation APIs because RAG does not choose winners.

Commands:

```bash
cd wcip-backend
python -m rag.indexer
pytest -q tests/test_rag_edge_cases.py
```

### 7. Prediction Runtime

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
4. WC2026 responses include one replayable tournament path with group tables,
   best third-place standings, knockout matches, final, third-place match, and
   champion.
5. Results also aggregate into stage probabilities and champion odds.

For the full 2026 bracket simulation:

1. `POST /api/v1/world_cup/2026/simulate` accepts `runs`, optional `seed`,
   `deterministic`, and `prediction_mode` (`statistical`, `ml`, or
   `ensemble`).
2. The backend loads the 48 WC2026 teams and groups from the database. If a
   draw is missing, it creates provisional Elo-seeded groups.
3. The tournament engine simulates all 72 group-stage fixtures and ranks each
   group by points, goal difference, and goals for.
4. The top two teams in each group advance automatically.
5. The eight best third-place teams advance by the same table tiebreakers.
6. The Round of 32 bracket resolves winners through Round of 16,
   quarter-finals, semi-finals, third-place match, final, and champion.
7. Each serialized match includes team codes, simulated score, xG, expected
   scoreline, statistical prediction, ML prediction, ensemble prediction,
   selected prediction mode, winner probability, champion probability, and an
   advancement reason.
8. The aggregate `teams` list still comes from Monte Carlo runs, while the
   `group_stage_matches` and `knockout_bracket` fields show one replayable path.

Important response fields:

```json
{
  "year": 2026,
  "runs": 10000,
  "prediction_mode": "ensemble",
  "groups": { "A": ["Mexico", "South Africa", "South Korea", "Czechia"] },
  "group_tables": { "A": [{ "team": "Mexico", "points": 7, "qualified": true }] },
  "group_stage_matches": { "A": [{ "home": "Mexico", "away": "South Africa" }] },
  "qualified_teams": [{ "team": "Mexico", "qualification_type": "automatic" }],
  "best_third_place": [{ "team": "Canada", "rank": 1 }],
  "knockout_bracket": [
    {
      "round": "Round of 32",
      "matches": [
        {
          "home": "Mexico",
          "away": "Canada",
          "scoreline": "2-1",
          "selected_prediction": { "home_win": 0.45, "draw": 0.25, "away_win": 0.30 },
          "winner_probability": 0.45,
          "advancing_team": "Mexico"
        }
      ]
    }
  ],
  "champion": "France",
  "champion_probability": 0.13
}
```

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

- Final navigation: `WC 2026 | BRACKET | PREDICT | SCENARIOS | EXPLAIN | MODELS | TEAMS | SAVED`.
- `/dashboard` gives the user an overview of teams and predictions.
- `/wc2026` is the World Cup 2026 intelligence center. It shows a compact
  overview: top champion probabilities, most likely final, dark horses,
  freshness dates, group snapshot, and a CTA into the bracket simulator.
- `/world-cup` redirects to `/wc2026` for compatibility.
- `/wc2026/bracket` is the only full tournament simulation screen. It shows
  group tables, group fixtures, best third-place ranking, Round of 32 through
  champion, and save controls.
- `/predict` is the single-match prediction page. It compares statistical, ML,
  and ensemble outputs in one place, so `/compare` redirects here.
- `/scenarios` is the what-if lab. It supports tournament scenario comparison
  and player availability changes moved from the old Lab page, so `/player-lab`
  redirects here.
- `/teams` lists WC2026 nations with FIFA code, group, confederation, Elo, FIFA
  ranking, coach, squad count, and team-detail links.
- `/team/[id]` shows one team, its coach, strength summary, and full database
  squad with position, club, height, caps, goals, assists, and friendly
  incomplete-data states.
- `/player/[id]` shows one player.
- `/explain` explains feature impacts and SHAP/factor output.
- `/models` shows model metrics and feature information.
- `/saved` shows saved simulations for the logged-in user. `/history` remains a
  legacy history route.
- `/login`, `/register`, and `/profile` handle user accounts.

### Interface Step By Step

1. Start the backend at `http://localhost:8000`.
2. Start the frontend at `http://localhost:3000`.
3. Open the frontend.
4. Use the navigation bar to choose a workflow.
5. Check the freshness strip for last Elo, FIFA ranking, match, player, model,
   feature, and snapshot updates.
6. Pick teams from selectors populated by `GET /api/v1/teams`.
7. Adjust sliders or scenario controls when available.
8. Submit the form.
9. The frontend calls the relevant backend endpoint.
10. Results render as probabilities, cards, charts, or bracket views.
11. Admin users can refresh Elo, FIFA rankings, player data, all data, check
    retraining thresholds, or trigger retraining from the freshness strip.
12. After a WC2026 simulation finishes, logged-in users can save the full group
    table, bracket, match list, champion probabilities, seed, and data snapshot.

## API Map

All backend API routes use the `/api/v1` prefix.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/teams` | List WC2026 teams by default with group, code, coach, ranking, Elo, and squad count; pass `world_cup_only=false` for every historical team |
| `GET` | `/teams/{id}` | Team detail with the same enriched contract |
| `GET` | `/teams/{id}/stats` | Team model inputs |
| `GET` | `/teams/{id}/elo-history` | Elo history |
| `GET` | `/teams/{id}/players` | Full database squad rows for a team |
| `GET` | `/teams/{id}/squad` | Team, coach, squad count, and full squad payload |
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
| `POST` | `/admin/ml/retrain-if-needed` | Admin retraining threshold check |
| `POST` | `/rag/ask` | Factual RAG explanation from indexed public records |
| `GET` | `/rag/status` | RAG index counts and last indexed timestamp |
| `GET` | `/rag/documents` | Indexed RAG document summaries |
| `POST` | `/admin/rag/index` | Admin-only RAG index rebuild |
| `GET` | `/ratings/elo/latest` | Current stored Elo snapshot |
| `GET` | `/ratings/elo/history/{team_id}` | Versioned Elo history for one team |
| `GET` | `/rankings/fifa/latest` | Current stored FIFA ranking snapshot |
| `GET` | `/rankings/fifa/history/{team_id}` | Versioned FIFA ranking history for one team |
| `GET` | `/rankings/fifa/snapshots` | List stored FIFA ranking snapshots |
| `GET` | `/rankings/fifa/snapshots/{ranking_id}` | Fetch one historical ranking snapshot |
| `POST` | `/rankings/fifa/refresh` | Admin ranking refresh and optional retrain trigger |
| `GET` | `/data/freshness` | Elo, FIFA, match, player, model, and feature freshness |
| `POST` | `/admin/data/refresh-elo` | Admin-only Elo refresh |
| `POST` | `/admin/data/refresh-fifa-rankings` | Admin-only FIFA ranking refresh |
| `POST` | `/admin/data/refresh-players` | Admin-only legal player-data refresh |
| `POST` | `/admin/data/refresh-all` | Admin-only global refresh |
| `GET` | `/world-cup/qualified-teams` | WC2026 qualified-team list with Elo/FIFA display values |
| `GET` | `/world-cup/groups` | WC2026 groups or pending draw status |
| `GET` | `/world-cup/bracket` | WC2026 knockout bracket |
| `POST` | `/world-cup/simulate` | WC2026 tournament simulation with full replayable bracket |
| `POST` | `/world_cup/2026/simulate` | Explicit WC2026 simulation alias with `prediction_mode` |
| `GET` | `/world_cup/2026/groups` | Explicit WC2026 groups alias |
| `GET` | `/world_cup/2026/bracket` | Explicit WC2026 bracket alias |
| `GET` | `/world-cup/schedule` | WC2026 schedule metadata |
| `GET` | `/world-cup/teams/{team_name}` | WC2026 team, squad, and coach detail |
| `GET` | `/world-cup/players/{team_name}` | WC2026 squad list |
| `GET` | `/world-cup/2026/predictions` | WC2026 prediction bundle with freshness |
| `GET` | `/world_cup/2026/winner-predictions` | Underscore alias for winner predictions |
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
python scripts/generate_local_env.py
uvicorn app.main:app --reload
```

The backend defaults to SQLite at `wcip-backend/wcip.db`, in-memory cache, and no
external services.

Useful environment variables are documented in `wcip-backend/.env.example`.
Use placeholders only in committed examples. Generate local-only secrets with
`python scripts/generate_local_env.py`.

Common backend variables:

```bash
APP_ENV=development
DATABASE_URL=sqlite:///./wcip.db
JWT_SECRET_KEY=replace-with-generated-local-secret
JWT_REFRESH_SECRET_KEY=replace-with-generated-local-refresh-secret
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ETL_AUTO_RUN_ON_STARTUP=false
FOOTBALL_DATA_API_KEY=
FIFA_RANKING_SOURCE_URL=https://inside.fifa.com/fifa-world-ranking/men
ELO_RATING_SOURCE_URL=https://www.eloratings.net/2026_World_Cup
ELO_RATING_TSV_URL=https://www.eloratings.net/World.tsv
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
Frontend public variables are documented in
`wcip-frontend/.env.local.example`. The API client accepts both
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8000` and the older
`NEXT_PUBLIC_API_BASE=/backend/api/v1` proxy form.

### Frontend Deployment On Vercel

This repository is a monorepo. The actual Next.js app is not at the repository
root; it lives in `wcip-frontend/`.

Use these Vercel settings:

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Set these Vercel environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_BACKEND_URL
NEXT_PUBLIC_APP_NAME=World Cup Intelligence Platform
NEXT_PUBLIC_ENABLE_ML=true
NEXT_PUBLIC_ENABLE_SCENARIOS=true
NEXT_PUBLIC_ENABLE_EXPLAINABILITY=true
```

The frontend build must not start or deploy the FastAPI backend. Deploy the
backend separately on Render, Railway, Fly.io, AWS, or another Python/Docker
host, then point `NEXT_PUBLIC_API_BASE_URL` at that deployed backend.
Do not point `NEXT_PUBLIC_API_BASE_URL` at the Vercel frontend URL.

The homepage Data Freshness card reads:

```text
GET <NEXT_PUBLIC_API_BASE_URL>/api/v1/data/freshness
```

If the deployed card says `Backend not configured` or `Freshness unavailable`,
check Vercel's Production environment for `NEXT_PUBLIC_API_BASE_URL`, redeploy
the frontend after changing it, and confirm the backend allows
`https://world-cup-intelligence-platform.vercel.app` through CORS. A response
from `/backend/api/v1/data/freshness` with `DNS_HOSTNAME_RESOLVED_PRIVATE`
means Vercel is still using the local proxy fallback instead of the deployed
FastAPI backend.

If Vercel says:

```text
Couldn't find any `pages` or `app` directory
```

then Vercel is building from the wrong folder. Set the Vercel Root Directory to
`wcip-frontend`. Do not create a fake root-level `app/` directory.

### Full Stack With Docker

```bash
cd wcip-backend
python scripts/generate_local_env.py
docker compose up --build
```

This starts the backend, worker, beat scheduler, Postgres, and Redis.
Docker Compose reads local env values from `wcip-backend/.env`. Do not use these
generated local secrets in production.

## Security And Cleanup

Repository safety docs:

- `CODE_CLEANUP_AUDIT.md` — cleanup audit and tracked artifact findings
- `SECURITY_CLEANUP.md` — cleanup commands, secret rotation, and local setup
- `.env.example`, `wcip-backend/.env.example`, and
  `wcip-frontend/.env.local.example` — placeholder-only templates

Generate local env files:

```bash
cd wcip-backend
python scripts/generate_local_env.py
```

Run the safety check:

```bash
make safety-check
```

Never commit:

- `.env` or `.env.local`
- local databases such as `wcip.db`
- Python bytecode and `__pycache__`
- `node_modules`, `.next`, and build output
- ETL cache files
- model artifacts such as `*.pkl`, `*.joblib`, or `*.onnx`
- private keys, tokens, service-account files, or real API keys

If a real secret is leaked, rotate it at the provider immediately, update
Render/Vercel or your secret manager, remove the file from Git tracking, and run
`make safety-check`.

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

### Refresh FIFA Ranking Snapshots

```bash
cd wcip-backend
python -c "from etl.pipeline import run_fifa_rankings_update; print(run_fifa_rankings_update(force_refresh=True))"
```

Inspect the current stored snapshot:

```bash
curl http://localhost:8000/api/v1/rankings/fifa/latest?limit=10
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

### Build FIFA Squad CSV For Teams, Scenarios, And ML

The official FIFA squad-list PDF can be loaded directly into the database or
converted into an importer-ready CSV. The PDF fields are factual roster fields,
not official player ratings. The converter derives conservative
`fifa_roster_proxy_v1` ratings from position, age, caps, goals, and height so
the existing player-strength feature pipeline has non-neutral squad signal.

Install requirements first so PDF extraction is available:

```bash
cd wcip-backend
source .venv/bin/activate
pip install -r requirements.txt
```

Load the PDF directly into `players` and `coaches`:

```bash
cd wcip-backend
python -m etl.players.load_squad_pdf \
  --source-pdf data/external/fifa_wc2026_squad_lists_english.pdf
python -m scripts.validate_squad_ingestion
```

Build the CSV directly from the FIFA source and import it into the database:

```bash
cd wcip-backend
python -m etl.players.fifa_squad_pdf --download --import-db
```

If the environment cannot download external files, download the PDF manually to:

```text
wcip-backend/data/external/fifa_wc2026_squad_lists_english.pdf
```

Then run:

```bash
cd wcip-backend
python -m etl.players.fifa_squad_pdf \
  --source-pdf data/external/fifa_wc2026_squad_lists_english.pdf \
  --import-db
python -m scripts.validate_squad_ingestion
```

Generated CSV:

```text
wcip-backend/data/external/fifa_wc2026_squad_players.csv
```

The validator checks 48 WC2026 teams, player coverage for every team, Bosnia and
Herzegovina aliases (`BIH`, `Bosnia And Herzegovina`, `Bosnia-Herzegovina`,
`Bosnia & Herzegovina`), Bosnia coach coverage, duplicate squad rows, valid
positions, valid team mapping, and nonnegative numeric fields.

After import:

1. `/api/v1/world-cup/players/{team_name}` returns the real squad rows.
2. `/api/v1/teams/{team_id}/players` and `/api/v1/teams/{team_id}/squad`
   return team-id based squad payloads for the Teams page and team detail page.
3. `/teams` shows squad counts and `/team/[id]` shows the full roster with
   position, club, height, caps, goals, and coach context.
4. `/scenarios` loads the same squad rows for player availability what-ifs.
5. `/predict` uses the same team registry for single-match prediction setup.
6. `ml/features.py` uses the imported player ratings for squad depth,
   positional-unit strength, top-five player strength, availability, caps,
   goals, and weighted player-strength features.

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

### Run A Full WC2026 Simulation

```bash
curl -X POST http://localhost:8000/api/v1/world_cup/2026/simulate \
  -H "Content-Type: application/json" \
  -d '{
    "runs": 1000,
    "seed": null,
    "deterministic": false,
    "prediction_mode": "ensemble"
  }'
```

The response includes aggregate probabilities plus `group_tables`,
`group_stage_matches`, `qualified_teams`, `best_third_place`,
`knockout_bracket`, `matches`, `champion`, `runner_up`, `third_place`, and the
selected prediction layers for every serialized match.

### Test The Full WC2026 Bracket Locally

1. Start the backend:

```bash
cd wcip-backend
source .venv/bin/activate
uvicorn app.main:app --reload
```

2. Start the frontend:

```bash
cd wcip-frontend
npm run dev
```

3. Open `http://localhost:3000/wc2026`.
4. Confirm the top nav only shows `WC 2026`, `BRACKET`, `PREDICT`,
   `SCENARIOS`, `EXPLAIN`, `MODELS`, `TEAMS`, and `SAVED`.
5. Open `http://localhost:3000/wc2026/bracket`.
6. Pick a simulation count.
7. Pick `Ensemble`, `Statistical`, or `ML` mode.
8. Click `Run`.
9. Confirm group tables render before the bracket.
10. Confirm the bracket shows Round of 32, Round of 16, Quarter-finals,
   Semi-finals, Third-place Match, Final, and Champion.
11. Click `Random run` or `Rerun` to generate a different unseeded path.
12. Open `http://localhost:3000/teams` and confirm teams, groups, coaches,
    rankings, Elo values, squad counts, and team-detail links render.
13. Open any `/team/[id]` page and confirm the full squad table renders.
14. Open `http://localhost:3000/scenarios`, load squads, toggle player
    availability, and run the match delta.
15. Sign in and click `Save Simulation` to persist the full bracket to your
    account.

## Repository Layout

```text
.
├── README.md
├── docs
│   ├── DATA_PIPELINE.md
│   └── MODEL_CARD.md
├── ARCHITECTURE.md
├── API.md
├── CODE_CLEANUP_AUDIT.md
├── SECURITY_CLEANUP.md
├── FIFA_RANKINGS_AUDIT.md
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
alembic upgrade head
python -m scripts.validate_squad_ingestion
python -m ml.validate_features
python -m rag.indexer
pytest -q tests/test_rag_edge_cases.py
env DEBUG=false pytest -q
python -m ml.validate_player_features
python -m ml.retrain_if_needed
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
npm run lint
```

Safety:

```bash
python3 scripts/check_repo_safety.py
git status --ignored
```

Note: in restricted sandboxes, the Monte Carlo tests may fail because
`ProcessPoolExecutor` checks OS semaphore limits. Run the backend test command
outside the sandbox if you see `PermissionError: Operation not permitted` from
`os.sysconf("SC_SEM_NSEMS_MAX")`.

Hydration note: browser password managers can inject attributes such as
`data-dashlane-rid` into input/button markup before React hydrates. If a
hydration warning points at the analyst search input but disappears in an
extension-free/incognito browser, the warning is caused by extension injection,
not server/client app state. The app still avoids `Date.now()`, `Math.random()`,
browser storage, and locale-dependent formatting in SSR-critical initial render
paths.

## Data Sources

- International match results: `martj42/international_results`
- Elo ratings: `eloratings.net`
- FIFA men’s rankings: official FIFA ranking page and ranking schedule payload,
  stored as immutable snapshots in `fifa_ranking_snapshots` and
  `fifa_ranking_entries`
- Official WC2026 teams/groups: FIFA standings reference
- WC2026 squad/player/coach data: official FIFA squad-list PDF loaded from
  `wcip-backend/data/external/fifa_wc2026_squad_lists_english.pdf`
- Local fallback: `wcip-backend/wcip/data/wc2026.py`
- Placeholder roster/coach records: `data_source="world_cup_2026_placeholder"`
  until a verified source snapshot is loaded

## Deployment Notes

- Deploy the backend as a separate Render Python web service from
  `wcip-backend`.
- Render backend build command: `pip install -r requirements.txt`.
- Render backend start command: `bash scripts/start_render.sh`.
- The FastAPI app path is `app.main:app`; the direct Uvicorn command is
  `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- `DATABASE_URL` comes from the Render PostgreSQL Internal Database URL.
- Generate strong production `SECRET_KEY`, `JWT_SECRET_KEY`, and
  `JWT_REFRESH_SECRET_KEY` values with
  `python -c "import secrets; print(secrets.token_urlsafe(64))"`.
- Do not reuse local development secrets in production.
- Never commit production `.env` files.
- Use Postgres for production `DATABASE_URL`.
- Use Redis for cache and Celery broker/result backend.
- Set `ALLOWED_ORIGINS`, `CORS_ORIGINS`, or `BACKEND_CORS_ORIGINS` to the
  deployed frontend origin.
- Set Vercel `NEXT_PUBLIC_API_BASE_URL` to the deployed Render backend origin.
- In Vercel, set the frontend Root Directory to `wcip-frontend`; the repository
  root is not the Next.js app.
- Run Alembic migrations before serving production traffic.
- Run WC2026 seed ETL from a vetted source snapshot when tournament rosters are
  updated.

## License And Disclaimer

Use for educational and analytical purposes only. Predictions are uncertain
probabilistic outputs, not guarantees. Respect the licenses and terms of the data
providers used by your deployment.
