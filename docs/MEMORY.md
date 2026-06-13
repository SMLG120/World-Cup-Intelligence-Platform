# Project Memory

## Security Cleanup Status

- Root and service-level ignore rules are intended to block `.env`, local DBs,
  Python bytecode, Node/Next build output, ETL cache files, ML artifacts,
  CatBoost logs, private keys, credential JSON, and zip exports.
- `.env.example` files must remain placeholder-only and committed.
- Real `.env` and `.env.local` files must never be committed.
- Local env files should be generated with:

```bash
cd wcip-backend
python scripts/generate_local_env.py
```

- Repository safety checks should be run with:

```bash
make safety-check
```

## Tracked Artifact Risk

The cleanup audit found generated files already tracked by Git, including
Python bytecode, SQLite databases, ETL cache files, model pickle files,
CatBoost training logs, and zip exports. `.gitignore` does not protect files
that are already tracked.

Before committing cleanup, remove those files from the Git index without
deleting local copies using the commands documented in `SECURITY_CLEANUP.md`.

## Environment Configuration

- Backend accepts both old and new env names:
  - `SECRET_KEY` or `JWT_SECRET_KEY`
  - `ALGORITHM` or `JWT_ALGORITHM`
  - `BACKEND_CORS_ORIGINS` or `CORS_ORIGINS`
  - `ENVIRONMENT` or `APP_ENV`
- Refresh tokens can use `JWT_REFRESH_SECRET_KEY`; if absent, local development
  falls back to the access-token secret.
- Frontend accepts both:
  - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
  - `NEXT_PUBLIC_API_BASE=/backend/api/v1`

## Production Secrets

Production secrets must be generated outside the repo and configured through
Render, Vercel, or another secret manager. Do not reuse generated local secrets
in production.

## Real-Time Data Pipeline

- Elo is versioned through `elo_rating_snapshots`, `team_elo_ratings`, and
  `elo_source_logs`. `teams.elo` remains only a current display/cache value.
- FIFA rankings remain versioned through `fifa_ranking_snapshots`,
  `fifa_ranking_entries`, `team_rankings`, and `ranking_source_logs`.
  `teams.fifa_rank` remains only a current display/cache value.
- Public freshness metadata is served by `GET /api/v1/data/freshness`.
- Public Elo APIs are:
  - `GET /api/v1/ratings/elo/latest`
  - `GET /api/v1/ratings/elo/history/{team_id}`
- Admin refresh APIs are:
  - `POST /api/v1/admin/data/refresh-elo`
  - `POST /api/v1/admin/data/refresh-fifa-rankings`
  - `POST /api/v1/admin/data/refresh-players`
  - `POST /api/v1/admin/data/refresh-all`
  - `POST /api/v1/admin/ml/retrain-if-needed`
- Player profiles are generated only from stored fields. Sparse rows must be
  labelled incomplete rather than filled with unsupported scouting claims.
- FIFA WC2026 squad-list PDF ingestion lives in
  `etl/players/fifa_squad_pdf.py`. It writes
  `data/external/fifa_wc2026_squad_players.csv` and can import rows with
  `source_name="fifa_wc2026_squad_pdf"`.
- FIFA squad-list data contains factual roster fields only. The generated
  `player_rating` values are conservative `fifa_roster_proxy_v1` features
  derived from age, position, caps, goals, and height; they are not official
  FIFA or scouting ratings.
- `ml.validate_features` checks feature count/order and NaN/inf safety.
- `ml.validate_player_features` checks player coverage, duplicate rows, rating
  ranges, position mapping, null-heavy fields, feature-order compatibility, and
  player-feature NaN/inf safety.
- `ml.retrain_if_needed` marks active model registry rows for recalibration only
  when data changes cross configured thresholds.

## WC2026 Simulation UX

- `/world-cup` is the canonical World Cup 2026 intelligence center.
- `/wc2026/simulate` loads the same full tournament simulator for the explicit
  route contract.
- `/wc2026/bracket` is the dedicated full-bracket route. It should show group
  tables and group fixtures first, then Round of 32, Round of 16,
  Quarter-finals, Semi-finals, Third-place Match, Final, and Champion.
- `/simulate`, `/tournament`, and `/wc2026` are legacy/duplicate entry points
  that route users back to the canonical World Cup experience.
- `POST /api/v1/world_cup/2026/simulate` accepts `prediction_mode` values
  `statistical`, `ml`, and `ensemble`. The mode changes the displayed
  match-level probability layer while aggregate tournament odds still come from
  Monte Carlo output.
- `POST /api/v1/world_cup/2026/simulate` returns aggregate probabilities plus a
  replayable bracket payload: group tables, group-stage fixtures, 32 qualified
  teams, best third-place teams, knockout rounds, match results, champion,
  runner-up, third place, seed, freshness, and match-level prediction layers.
- Every serialized WC2026 match should expose statistical, ML, ensemble, and
  selected probabilities, winner probability, expected scoreline, team codes,
  and an advancement reason.
- Knockout serialization must preserve elimination integrity. A losing knockout
  team cannot appear in later rounds except that both semi-final losers must
  appear in the third-place match.
