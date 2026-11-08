# WCIP production runbook

Vercel (frontend) → Render (API + data sync) → Supabase Postgres.

## Data flow

```
FIFA ranking page/API ┐
eloratings.net TSVs   ├─► Render cron `wcip-data-sync` (python -m scripts.sync_data, every 6 h)
martj42 results CSV   ┘        validate → versioned snapshots (never overwrite with partial data)
                                          │
                                          ▼
                               Supabase Postgres (authoritative store)
                                          │
                               Render web `wcip-api` (FastAPI; prediction cache keyed by data version)
                                          │
                               Vercel frontend (browser calls the API; never calls providers)
```

Only the cron job calls external providers. The FIFA step makes one page request per run and
downloads the ranking table only when FIFA has published a new release. A provider failure
leaves the stored data untouched, and the run exits non-zero so Render reports it as failed.

## Environment variables (names only — set values in each dashboard)

### Render `wcip-api` (web)
| Variable | Notes |
|---|---|
| `ENVIRONMENT`, `APP_ENV` | `production`. Production refuses weak JWT secrets and a SQLite `DATABASE_URL`. |
| `DEBUG` | `false` |
| `DATABASE_URL` | Supabase **Transaction pooler** string (port 6543), `sslmode=require`. |
| `SECRET_KEY`, `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY` | Long random values; never committed. |
| `JWT_ALGORITHM` | `HS256` |
| `ALLOWED_ORIGINS` | **Takes precedence over** `CORS_ORIGINS` / `BACKEND_CORS_ORIGINS`. Production Vercel origin only. |
| `BACKEND_CORS_ORIGIN_REGEX` | Vercel preview origins, if previews may call the API. |
| `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | From `wcip-redis`. |
| `RATE_LIMIT_PER_MINUTE` | Per client IP (requires the `--proxy-headers` start flags, already in `start_render.sh`). |
| `DB_POOL_SIZE`, `DB_MAX_OVERFLOW` | Optional; default 5 / 5. |
| `BOOTSTRAP_DATA_ON_START` | Default `true`; idempotent (~15–35 s on deploy). |
| `FIFA_RANKING_SOURCE_URL`, `ELO_RATING_SOURCE_URL`, `ELO_RATING_TSV_URL` | Public source URLs. |

### Render `wcip-data-sync` (cron) and `wcip-worker`
`ENVIRONMENT`, `APP_ENV`, `DEBUG`, `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`,
`JWT_REFRESH_SECRET_KEY`, source URLs (cron); plus Celery/Redis URLs (worker).

### Vercel
| Variable | Scope | Notes |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Production | Render API **origin** only (no `/api/v1`, no localhost — the UI flags both). |
| `NEXT_PUBLIC_API_BASE_URL` | Preview | Ideally a staging API. Pointing previews at production lets preview builds create real users and saved simulations. |
| `NEXT_PUBLIC_APP_NAME`, `NEXT_PUBLIC_ENABLE_*` | All | Public flags. |

Everything prefixed `NEXT_PUBLIC_` is visible in the browser. No Supabase key is used by the
frontend, and none should be added: the browser talks only to the API.

### Supabase
The API uses the Postgres connection string only. The service-role key and anon key are
unused by this codebase. Keep the database password out of Vercel entirely.

## Deploy order

1. **Database**: Render runs `alembic upgrade head` on start. Migrations must be backward-compatible
   with the currently running API (add or widen columns; never drop or rename in the same release).
2. **API** (`wcip-api`): deploy and wait for `/health` = 200, then check `/ready` returns
   `{"status":"ready","checks":{"database":true,"models":true}}`.
3. **Cron** (`wcip-data-sync`): trigger one manual run. Exit 0 means every source succeeded.
4. **Frontend** (Vercel): deploy after the API it depends on is live.

## Post-deploy smoke test

```bash
API=https://<render-api-host>
curl -fsS $API/health
curl -fsS $API/ready
curl -fsS $API/api/v1/data/freshness | jq '.status, .sources.fifa_rankings.version, .sources.fifa_rankings.status, .warnings'
curl -fsS -X POST $API/api/v1/match/predict -H 'content-type: application/json' \
     -d '{"home_team":"Spain","away_team":"Argentina"}' | jq '.probabilities'
# CORS from the production frontend origin:
curl -si -X OPTIONS $API/api/v1/match/predict -H "Origin: https://<vercel-domain>" \
     -H "Access-Control-Request-Method: POST" | grep -i access-control-allow-origin
```
Then open the Vercel site's Predict page and run a prediction.

## Rollback

* **Frontend**: Vercel → Deployments → previous deployment → *Promote to Production* (instant).
* **API / cron**: Render → service → Events → *Rollback* to the previous deploy.
* **Migrations**: every migration has a `downgrade`. Roll the code back first; downgrade only if
  the old code cannot run against the new schema (`alembic downgrade -1`). The
  `e7f8a9b0c1d2` downgrade refuses to run if any `players.external_id` is longer than 80 characters.
* **Bad data from a provider**: snapshots are versioned and never deleted. Set `is_current` back to
  the previous snapshot row (`fifa_ranking_snapshots` / `elo_rating_snapshots`). Prediction cache
  keys change automatically within about 30 s.

## Alerts worth configuring
* Render cron `wcip-data-sync` failed run (non-zero exit) → email.
* `/ready` non-200 for more than 2 minutes (external uptime monitor).
* `/api/v1/data/freshness` → `sources.fifa_rankings.status == "stale"` (sync has missed a FIFA release).
