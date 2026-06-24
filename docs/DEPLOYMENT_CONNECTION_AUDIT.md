# Deployment Connection Audit

Date: 2026-06-22

## Target Production Chain

```text
Vercel frontend
-> NEXT_PUBLIC_API_BASE_URL
-> Render FastAPI backend
-> DATABASE_URL
-> Render PostgreSQL database
```

## Short Verdict

The source code is now configured for the intended production architecture, but
the live deployment is not fully connected yet.

- The frontend API client reads `NEXT_PUBLIC_API_BASE_URL`.
- The backend reads `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`,
  `JWT_REFRESH_SECRET_KEY`, `ALLOWED_ORIGINS`, and `ENVIRONMENT`.
- Render config exists for a Python FastAPI backend and PostgreSQL database.
- Vercel config exists for the Next.js frontend.
- Local backend import, migration, health, and freshness checks pass.
- Local frontend typecheck/build pass after reinstalling dependencies with
  `npm ci`.
- Live Vercel is reachable, but the backend freshness path is not returning
  backend JSON yet. Vercel still needs `NEXT_PUBLIC_API_BASE_URL` set to the
  real Render backend public URL and redeployed.

## Repository Structure

- Frontend root: `wcip-frontend`
- Backend root: `wcip-backend`
- Frontend package: `wcip-frontend/package.json`
- Backend requirements: `wcip-backend/requirements.txt`
- FastAPI entrypoint: `wcip-backend/app/main.py`
- FastAPI import path: `app.main:app`
- Backend database config: `wcip-backend/app/db/base.py`
- Backend env loader: `wcip-backend/app/core/config.py`
- Backend CORS config: `wcip-backend/app/core/config.py`,
  `wcip-backend/app/main.py`
- Frontend API client: `wcip-frontend/lib/api.ts`
- Frontend freshness UI: `wcip-frontend/components/DataFreshnessCard.tsx`
- Root env template: `.env.example`
- Backend env template: `wcip-backend/.env.example`
- Render config: `wcip-backend/render.yaml`
- Vercel configs: `vercel.json`, `wcip-frontend/vercel.json`
- Docker files: `wcip-backend/Dockerfile`, `wcip-backend/docker-compose.yml`,
  `wcip-frontend/Dockerfile`

## Frontend API Connection

Status: code is correct, dashboard must be checked.

`wcip-frontend/lib/api.ts` resolves the API base in this order:

```text
NEXT_PUBLIC_API_BASE_URL
NEXT_PUBLIC_API_BASE
/backend/api/v1 fallback
```

It appends `/api/v1` when the configured base is a backend origin such as:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-backend.onrender.com
```

It rejects unsafe production config:

- missing `NEXT_PUBLIC_API_BASE_URL`
- `localhost` or `127.0.0.1`
- the Vercel frontend origin
- insecure `http://` from an HTTPS frontend

The data freshness call is:

```text
GET <NEXT_PUBLIC_API_BASE_URL>/api/v1/data/freshness
```

The codebase does not hardcode the Vercel frontend URL as the backend API. Local
development examples use `localhost`, which is correct for local-only use.

## Backend Environment And Database

Status: code is correct for Render/PostgreSQL.

`wcip-backend/app/core/config.py` reads:

```env
DATABASE_URL
SECRET_KEY
JWT_SECRET_KEY
JWT_REFRESH_SECRET_KEY
ALLOWED_ORIGINS
ENVIRONMENT
APP_ENV
```

`wcip-backend/app/db/base.py` creates the SQLAlchemy engine from
`settings.DATABASE_URL`. Local defaults may use SQLite, but production must set
Render's PostgreSQL Internal Database URL.

Alembic reads the same `DATABASE_URL` in `wcip-backend/alembic/env.py`.

## Render Backend Setup

Use these Render settings:

```text
Service Type: Web Service
Runtime: Python
Root Directory: wcip-backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Run migrations and bootstrap data separately from Render Shell before serving a
fresh production database:

```bash
alembic upgrade head
python -m scripts.bootstrap_data
```

Web start command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required Render backend env vars:

```env
DATABASE_URL=<Render PostgreSQL Internal Database URL>
SECRET_KEY=<generated production secret>
JWT_SECRET_KEY=<generated production jwt secret>
JWT_REFRESH_SECRET_KEY=<generated production refresh jwt secret>
ALLOWED_ORIGINS=https://world-cup-intelligence-platform.vercel.app,http://localhost:3000
ENVIRONMENT=production
APP_ENV=production
DEBUG=false
```

Optional worker/cache env vars:

```env
REDIS_URL=<Render Key Value Internal URL>
CELERY_BROKER_URL=<Render Key Value Internal URL>
CELERY_RESULT_BACKEND=<Render Key Value Internal URL>
```

Generate each secret locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Do not commit these values.

## Vercel Frontend Setup

Use these Vercel settings:

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Required Vercel env var:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-backend.onrender.com
```

Do not set this to:

```text
http://localhost:8000
https://world-cup-intelligence-platform.vercel.app
undefined
```

Do not put `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, or
`JWT_REFRESH_SECRET_KEY` in Vercel. Redeploy Vercel after changing environment
variables.

## CORS

Status: code allows Vercel.

Backend CORS accepts `ALLOWED_ORIGINS`, `CORS_ORIGINS`, or
`BACKEND_CORS_ORIGINS`. Defaults include:

```text
http://localhost:3000
http://127.0.0.1:3000
https://world-cup-intelligence-platform.vercel.app
```

It also supports a constrained Vercel preview regex.

## Data Freshness Endpoint

Status: endpoint exists and handles sparse data.

Endpoint:

```text
GET /api/v1/data/freshness
```

The response includes fields such as:

- `generated_at`
- `data_snapshot_timestamp`
- `last_elo_update`
- `last_fifa_ranking_update`
- `last_player_data_update`
- `model_trained_at`
- `data_snapshot_version`
- `using_latest_cached_snapshot`
- `source_status`

Sparse database behavior is covered by tests:

- full/current freshness response works
- empty freshness tables return `none`/`not_loaded` fields
- partial data returns available fields without crashing

## RAG And Model Imports

Status: valid.

`wcip-backend/app/models/rag.py` is tracked and defines:

- `RagDocument`
- `RagChunk`
- `RagEmbedding`
- `RagQuery`
- `RagAnswer`

`wcip-backend/app/models/__init__.py` imports those models, and
`wcip-backend/alembic/versions/c1d2e3f4a5b6_add_rag_tables.py` creates the
matching tables.

## Docker

Docker is optional for production because Render can use the Python runtime and
Vercel builds Next.js directly.

Docker is useful for local full-stack development:

```text
api container -> db container
worker container -> db/redis containers
```

`wcip-backend/docker-compose.yml` correctly uses the `db` service name in
`DATABASE_URL`, not `localhost`.

For local browser-based frontend development, the frontend may call:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

That is local-only and must not be used in Vercel Production.

## Verification Results

Local backend:

```text
python -c "from app.main import app; print('Backend imports OK')" -> failed locally because `python` is not on PATH
./.venv/bin/python -c "from app.main import app; print('Backend imports OK')" -> Backend imports OK
./.venv/bin/python -m alembic upgrade head -> success
./.venv/bin/python -m pytest -q tests/test_realtime_data.py -> 8 passed
./.venv/bin/python -m pytest -q tests/test_rag_edge_cases.py -> 5 passed
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 -> started successfully
GET http://127.0.0.1:8000/health -> 200 {"status":"ok"}
GET http://127.0.0.1:8000/api/v1/data/freshness -> 200 JSON
```

Local frontend:

```text
npm ci -> success; 2 npm audit findings remain
npm run typecheck -> success
npm run build -> success
```

Live checks:

```text
GET https://world-cup-intelligence-platform.vercel.app/ -> 200
GET https://world-cup-intelligence-platform.vercel.app/backend/api/v1/data/freshness -> 404 HTML frontend page
GET https://wcip-api.onrender.com/health -> 404 Not Found
GET https://wcip-api.onrender.com/api/v1/data/freshness -> 404 Not Found
```

`https://wcip-api.onrender.com` was checked only because `render.yaml` names the
service `wcip-api`; Render may assign or use a different public URL. Use the
actual Render backend URL from the Render dashboard.

## Manual Action Checklist

### A. Workspace

```bash
cd wcip-backend
./.venv/bin/python -c "from app.main import app; print('Backend imports OK')"
./.venv/bin/python -m alembic upgrade head
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

In another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/data/freshness
```

Frontend:

```bash
cd wcip-frontend
npm ci
npm run typecheck
npm run build
```

### B. Render

1. Create a PostgreSQL database.
2. Copy its Internal Database URL.
3. Create a Web Service from the repo.
4. Set Root Directory to `wcip-backend`.
5. Set Runtime to `Python`.
6. Set Build Command to `pip install -r requirements.txt`.
7. Set Start Command to `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
8. Add the required backend env vars listed above.
9. Deploy.
10. Test:

```text
https://YOUR_RENDER_BACKEND_URL/health
https://YOUR_RENDER_BACKEND_URL/api/v1/data/freshness
```

### C. Vercel

1. Open the frontend project settings.
2. Set Root Directory to `wcip-frontend`.
3. Set Build Command to `npm run build`.
4. Set:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_RENDER_BACKEND_URL
```

5. Redeploy.
6. Open DevTools Network on:

```text
https://world-cup-intelligence-platform.vercel.app
```

7. Confirm the freshness request goes to:

```text
https://YOUR_RENDER_BACKEND_URL/api/v1/data/freshness
```

## Remaining Risks

- The actual Render public backend URL is not committed in the repo and could
  not be confirmed from local code alone.
- The live Vercel deployment is not yet visibly connected to Render freshness
  JSON.
- Frontend dependencies had to be reinstalled locally with `npm ci`; keep using
  clean installs in CI/Render/Vercel rather than relying on a stale
  `node_modules`.
- `npm audit` reports 2 vulnerabilities. Review them separately before
  production hardening.
- Render Python builds may need enough memory/time for ML packages such as
  CatBoost, LightGBM, XGBoost, and SHAP.
