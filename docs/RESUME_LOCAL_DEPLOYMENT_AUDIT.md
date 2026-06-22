# Resume Local Deployment Audit

Generated: 2026-06-22

## Current Architecture

Local development should run:

```text
Next.js frontend -> local FastAPI backend -> local SQLite database
```

Production should run:

```text
Vercel frontend -> Render FastAPI backend -> Render PostgreSQL database
```

The frontend must know only the backend origin through
`NEXT_PUBLIC_API_BASE_URL`. The frontend API client appends `/api/v1` in code.

## Audit Answers

- Frontend API env: uses `NEXT_PUBLIC_API_BASE_URL` as the public backend origin.
- Duplicated `/api/v1`: fixed. The local env examples use `http://localhost:8000`; the API client appends `/api/v1`.
- Backend database env: `wcip-backend/app/core/config.py` reads `DATABASE_URL`; Alembic also reads the same setting in `wcip-backend/alembic/env.py`.
- FastAPI entrypoint: `wcip-backend/app/main.py` defines `app = FastAPI(...)`.
- Backend local command: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`.
- Render backend command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
- Missing RAG import: fixed. `wcip-backend/app/models/rag.py` exists and `wcip-backend/app/models/__init__.py` imports `RagDocument`, `RagChunk`, and `RagEmbedding`.
- Data freshness endpoint: exists at `/api/v1/data/freshness` through `wcip-backend/app/api/v1/data.py`.
- Empty local DB behavior: fixed. Data freshness returns a partial/unavailable status and message instead of an unhandled 500 when local data is missing.
- CORS: backend allows localhost origins and the production Vercel frontend through settings aliases: `ALLOWED_ORIGINS`, `CORS_ORIGINS`, and `BACKEND_CORS_ORIGINS`.
- Local vs production env: separated in examples and docs. Local uses SQLite and localhost. Production should use Render PostgreSQL and a Render backend URL.
- Auth/JWT config: backend accepts `JWT_SECRET_KEY` or `SECRET_KEY`; production validation rejects known unsafe default secrets.
- Vercel config: frontend should use Root Directory `wcip-frontend`, framework Next.js, build command `npm run build`, output `.next`.
- Render config: backend blueprint exists in `wcip-backend/render.yaml` and now uses the requested direct Uvicorn start command.

## Frontend API Contract

Local:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Production:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_RENDER_BACKEND_URL
```

Expected freshness request:

```text
http://localhost:8000/api/v1/data/freshness
```

Invalid values:

```text
undefined/api/v1/data/freshness
http://localhost:8000/api/v1/api/v1/data/freshness
https://world-cup-intelligence-platform.vercel.app/api/v1/data/freshness
```

## What Was Broken Or Risky

- The frontend API client still carried legacy `NEXT_PUBLIC_API_BASE` and `/backend/api/v1` fallback behavior.
- That legacy logic could mask missing environment variables and made local vs production behavior harder to reason about.
- If someone configured `NEXT_PUBLIC_API_BASE_URL` with `/api/v1`, the app could build duplicate API prefixes.
- The Render deployment docs and blueprint were not fully aligned with the requested direct Uvicorn start command.
- Clean local examples were needed so `.env` and `.env.local` do not drift into production settings.
- Clean `npm ci` exposed a Recharts/Victory dependency issue and missing Recharts TypeScript declarations.

## What Must Be Fixed Before Deployment

- Create the Render PostgreSQL database and set `DATABASE_URL` on the Render backend only.
- Generate strong production `SECRET_KEY`, `JWT_SECRET_KEY`, and `JWT_REFRESH_SECRET_KEY`.
- Set Render `ALLOWED_ORIGINS` to include the Vercel frontend URL.
- Set Vercel `NEXT_PUBLIC_API_BASE_URL` to the Render backend origin, not the Vercel frontend URL.
- Run backend migrations against the production database.
- Redeploy Vercel after environment variables are set.
- Verify browser Network requests hit `https://YOUR_RENDER_BACKEND_URL/api/v1/...`.

## Local Commands

Backend:

```bash
cd wcip-backend
./.venv/bin/python -m alembic upgrade head
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd wcip-frontend
npm install
npm run dev
```

If port `3000` is occupied, stop the old process or temporarily run:

```bash
npm run dev -- -H 0.0.0.0 -p 3001
```

## Verification Targets

Backend:

```text
http://localhost:8000/
http://localhost:8000/health
http://localhost:8000/docs
http://localhost:8000/api/v1/data/freshness
```

Frontend:

```text
http://localhost:3000/
http://localhost:3000/wc2026
http://localhost:3000/teams
http://localhost:3000/predict
```

## Verification Status

Completed successfully:

```bash
cd wcip-backend
./.venv/bin/python -c "from app.main import app; print('Backend imports OK')"
./.venv/bin/python -m alembic upgrade head
./.venv/bin/python -m pytest -q tests/test_realtime_data.py tests/test_rag_edge_cases.py
git diff --check
```

Observed result:

```text
Backend imports OK
Alembic upgrade completed
13 backend tests passed
Whitespace check passed
```

Frontend verification is currently blocked by local dependency-tree corruption,
not by the source code changes in this audit. `npm run typecheck` failed because
`wcip-frontend/node_modules` was incomplete and TypeScript resolved packages
from the repo root instead. Attempts to run `npm ci` then failed with:

```text
ENOTEMPTY: directory not empty, rename .../wcip-frontend/node_modules/resolve
```

Root cause found during verification: stale frontend processes were still
running and using `wcip-frontend/node_modules` while npm tried to reinstall.
Those processes were stopped, but the final clean reinstall was blocked by the
execution environment approval/usage limit before it could complete.

Recovery command for the local machine:

```bash
cd wcip-frontend
mv node_modules node_modules_corrupt_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
rm -rf .next
npm ci
npm run typecheck
npm run build
```

Then start the stack and smoke-test:

```bash
cd ../wcip-backend
./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

cd ../wcip-frontend
npm run dev
```

