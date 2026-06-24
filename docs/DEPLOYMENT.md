# Deployment

This repository is a monorepo:

```text
repo-root/
  wcip-backend/    FastAPI backend
  wcip-frontend/   Next.js frontend
```

The frontend and backend deploy separately.

## Local Codespace Setup

Before Render/Vercel deployment, verify the local chain:

```text
local frontend -> local FastAPI backend -> local SQLite database
```

Backend:

```bash
cd wcip-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Frontend:

```bash
cd wcip-frontend
npm install
npm run dev
```

Local frontend env:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Production frontend env:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-render-backend.onrender.com
```

In Codespaces, forward ports `8000` and `3000`. If the browser cannot reach
`localhost:8000`, use the forwarded 8000 URL as `NEXT_PUBLIC_API_BASE_URL` and
restart the frontend dev server.

## Frontend: Vercel

The real Next.js app root is `wcip-frontend/`. It contains:

- `wcip-frontend/package.json`
- `wcip-frontend/app/`
- `wcip-frontend/next.config.mjs`
- `wcip-frontend/vercel.json`

Use these Vercel project settings:

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Required Vercel environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_BACKEND_URL
NEXT_PUBLIC_APP_NAME=World Cup Intelligence Platform
NEXT_PUBLIC_ENABLE_ML=true
NEXT_PUBLIC_ENABLE_SCENARIOS=true
NEXT_PUBLIC_ENABLE_EXPLAINABILITY=true
```

Do not set `NEXT_PUBLIC_API_BASE_URL` to `localhost` in production.

## Backend: Separate Python Host

Do not deploy `wcip-backend/` to Vercel as a normal Next.js app. Deploy the
FastAPI backend separately, for example on:

- Render
- Railway
- Fly.io
- AWS
- A Docker host

The Vercel frontend calls the deployed backend through
`NEXT_PUBLIC_API_BASE_URL`.

### Render Backend Settings

Use these Render settings for the FastAPI backend:

```text
Service Type: Web Service
Runtime: Python
Root Directory: wcip-backend
Build Command: pip install -r requirements.txt
Start Command: bash scripts/start_render.sh
Health Check Path: /health
```

The backend app path is:

```text
app.main:app
```

`scripts/start_render.sh` runs `alembic upgrade head`, then
`python -m scripts.bootstrap_data`, then starts Uvicorn. If using
`render.yaml` as a Blueprint, both services must set `rootDir: wcip-backend`
since the blueprint file lives inside that subdirectory, not at the repo root —
without it, Render runs `pip install -r requirements.txt` from the repo root,
where `requirements.txt` doesn't exist, and the build fails.

Required Render environment variables:

```env
DATABASE_URL=Render PostgreSQL Internal Database URL
SECRET_KEY=generated secret
JWT_SECRET_KEY=generated jwt secret
JWT_REFRESH_SECRET_KEY=generated refresh jwt secret
ALLOWED_ORIGINS=https://world-cup-intelligence-platform.vercel.app,http://localhost:3000
ENVIRONMENT=production
APP_ENV=production
DEBUG=false
```

`DATABASE_URL` may arrive as `postgres://...` from some providers;
`app/core/config.py` normalizes that to `postgresql://...` automatically, so
either scheme works.

Generate each secret locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

`DATABASE_URL` comes from Render PostgreSQL. Create a Render PostgreSQL
database, copy its Internal Database URL, and set it only on the Render backend
service. Do not put backend secrets or database URLs in Vercel.

After Render gives you a backend URL, set this in Vercel and redeploy:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_RENDER_BACKEND_URL
```

Verify:

```text
https://YOUR_RENDER_BACKEND_URL/
https://YOUR_RENDER_BACKEND_URL/health
https://YOUR_RENDER_BACKEND_URL/docs
https://YOUR_RENDER_BACKEND_URL/api/v1/data/freshness
```

## Local Build Verification

```bash
cd wcip-frontend
npm install
npm run typecheck
npm run build
```

Expected result:

- `.next/` is created
- no missing `app` directory error
- no TypeScript errors
- no backend process required during build

## Common Vercel Error

If Vercel says:

```text
Couldn't find any `pages` or `app` directory
```

Vercel is building from the wrong folder. Set the Vercel Root Directory to:

```text
wcip-frontend
```

The repository root includes a defensive `vercel.json` and `vercel-build`
script that delegate to `wcip-frontend`, but the preferred fix is still to set
the Vercel project root correctly.
