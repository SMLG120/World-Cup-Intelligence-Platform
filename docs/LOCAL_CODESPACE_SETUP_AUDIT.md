# Local Codespace Setup Audit

Date: 2026-06-22

## Goal

```text
local frontend -> local FastAPI backend -> local SQLite database
```

This audit focuses on local GitHub Codespaces development before Render/Vercel
deployment.

## Project Layout

- Frontend folder: `wcip-frontend`
- Backend folder: `wcip-backend`
- Frontend API client: `wcip-frontend/lib/api.ts`
- Frontend local env template: `wcip-frontend/.env.local.example`
- Frontend local env file: `wcip-frontend/.env.local` (ignored by Git)
- Backend env template: `wcip-backend/.env.example`
- Backend local env file: `wcip-backend/.env` (ignored by Git)
- FastAPI entrypoint: `wcip-backend/app/main.py`
- FastAPI import path: `app.main:app`
- Database config: `wcip-backend/app/db/base.py`
- CORS config: `wcip-backend/app/core/config.py`,
  `wcip-backend/app/main.py`
- Data freshness endpoint: `GET /api/v1/data/freshness`
- Docker files: `wcip-backend/Dockerfile`, `wcip-backend/docker-compose.yml`,
  `wcip-frontend/Dockerfile`

## Local API Base

Use one clean frontend API base:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The frontend API client appends `/api/v1` automatically, so the final local
freshness request is:

```text
http://localhost:8000/api/v1/data/freshness
```

Do not set local `NEXT_PUBLIC_API_BASE_URL` to:

```text
http://localhost:8000/api/v1
```

The client currently avoids duplicate `/api/v1` if someone accidentally adds it,
but the local env file should still use the backend origin only.

## Backend Local Env

Use `wcip-backend/.env` for local-only values:

```env
DATABASE_URL=sqlite:///./wcip.db
SECRET_KEY=local_dev_secret
JWT_SECRET_KEY=local_dev_jwt_secret
JWT_REFRESH_SECRET_KEY=local_dev_refresh_secret
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
ENVIRONMENT=development
```

`wcip-backend/.env` is ignored by Git. Do not commit real secrets or local
database files.

## Backend Commands

```bash
cd wcip-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -c "from app.main import app; print('Backend imports OK')"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

If plain `python` is not available in the environment, use:

```bash
./.venv/bin/python -c "from app.main import app; print('Backend imports OK')"
./.venv/bin/python -m alembic upgrade head
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Backend Endpoint Checks

With the backend running:

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/docs
http://localhost:8000/api/v1/data/freshness
```

`/api/v1/data/freshness` returns JSON. If the local SQLite database has not been
seeded, the response includes:

```json
{
  "status": "partial",
  "message": "Freshness data is unavailable because local database is not seeded."
}
```

plus the normal freshness fields with `none` / `not_loaded` values.

## Optional Local Data Checks

These scripts are useful after installing dependencies and running migrations:

```bash
cd wcip-backend
./.venv/bin/python -m scripts.validate_squad_ingestion
./.venv/bin/python -m scripts.validate_elo_csv
./.venv/bin/python -m ml.validate_features
```

If a script reports missing data, restore the referenced file under
`wcip-backend/data/` or run the documented import for that source. Render
PostgreSQL is not required for local Codespace development.

## Frontend Local Env

Use `wcip-frontend/.env.local`:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=World Cup Intelligence Platform
NEXT_PUBLIC_ENABLE_ML=true
NEXT_PUBLIC_ENABLE_SCENARIOS=true
NEXT_PUBLIC_ENABLE_EXPLAINABILITY=true
```

`wcip-frontend/.env.local` is ignored by Git.

## Frontend Commands

In a second terminal:

```bash
cd wcip-frontend
npm ci
npm run dev
```

Open the forwarded port 3000 URL from the Codespaces Ports tab.

If port 3000 is already in use, stop the old frontend process or temporarily
run:

```bash
npm run dev -- -H 0.0.0.0 -p 3001
```

## Codespaces Port Forwarding

Forward both ports:

```text
8000 -> FastAPI backend
3000 -> Next.js frontend
```

If the browser running the frontend cannot call `http://localhost:8000`, copy
the forwarded backend URL for port 8000 from the Codespaces Ports tab and set:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR-CODESPACE-NAME-8000.app.github.dev
```

Then restart the frontend dev server because Next.js reads public environment
variables at startup.

## Local Verification Checklist

- Backend imports correctly.
- Backend starts on port 8000.
- `/health` returns `{"status":"ok"}`.
- `/docs` loads.
- `/api/v1/data/freshness` returns JSON.
- Frontend starts on port 3000.
- Data Freshness card does not show backend unreachable.
- API base does not duplicate `/api/v1`.
- Local frontend env does not use a Render or Vercel URL.

## Verification Run

Commands run in this workspace:

```text
./.venv/bin/python -m alembic upgrade head -> success
./.venv/bin/python -c "from app.main import app; print('Backend imports OK')" -> success
./.venv/bin/python -m pytest -q tests/test_realtime_data.py tests/test_rag_edge_cases.py -> 13 passed
./.venv/bin/python -m scripts.validate_squad_ingestion -> PASS
./.venv/bin/python -m scripts.validate_elo_csv -> PASS
./.venv/bin/python -m ml.validate_features -> PASS
npm ci -> success
npm run typecheck -> success
npm run build -> success
```

Runtime checks:

```text
GET http://127.0.0.1:8000/ -> 200
GET http://127.0.0.1:8000/health -> 200
GET http://127.0.0.1:8000/docs -> 200
GET http://127.0.0.1:8000/api/v1/data/freshness -> 200
GET http://127.0.0.1:3000/ -> 200 from an existing frontend process
GET http://127.0.0.1:3001/ -> 200 from the current frontend process
GET http://127.0.0.1:3001/wc2026 -> 200
```

Port 3000 was already occupied by a Node process during this run, so the
current frontend was also checked on port 3001. In a fresh Codespace, use port
3000 normally.

Frontend dependency note:

`recharts@2` needs a compatible `victory-vendor` package. The frontend now pins
`victory-vendor@36.6.8`, because `36.9.2` installed without the CommonJS files
that Recharts expects during `next build`.

## Later Render/Vercel Work

After local Codespace works:

```env
Production NEXT_PUBLIC_API_BASE_URL=https://your-render-backend.onrender.com
```

Set that in Vercel only after the Render backend URL is live and
`https://your-render-backend.onrender.com/api/v1/data/freshness` returns JSON.
