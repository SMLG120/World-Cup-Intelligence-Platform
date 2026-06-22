# Vercel Data Freshness Audit

Date: 2026-06-22

## Production Symptom

Frontend:

```text
https://world-cup-intelligence-platform.vercel.app/
```

The homepage loads, but the Data Freshness card shows:

```text
Data source unavailable
Freshness unavailable
```

## Evidence

The deployed frontend route is live:

```text
GET https://world-cup-intelligence-platform.vercel.app/ -> 200
```

The deployed frontend proxy route for freshness fails:

```text
GET https://world-cup-intelligence-platform.vercel.app/backend/api/v1/data/freshness
-> 404
-> x-vercel-error: DNS_HOSTNAME_RESOLVED_PRIVATE
```

That error means the Vercel deployment is attempting to resolve a private/local
backend host through the frontend proxy. In this repo, `next.config.mjs`
previously defaulted `BACKEND_INTERNAL_URL` to `http://localhost:8000`, so a
production deployment without a real backend URL could still build but proxy
API calls to localhost from Vercel.

## Root Cause

The deployed frontend does not have a usable production backend API base. It is
falling back to `/backend/api/v1`, and the Vercel rewrite is resolving to a
private/local backend host. The fix is to set:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_DEPLOYED_FASTAPI_BACKEND
```

in Vercel for Production (and Preview/Development as needed), then redeploy.

## Required Vercel Frontend Settings

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

Required environment variables:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_DEPLOYED_FASTAPI_BACKEND
NEXT_PUBLIC_APP_NAME=World Cup Intelligence Platform
NEXT_PUBLIC_ENABLE_ML=true
NEXT_PUBLIC_ENABLE_SCENARIOS=true
NEXT_PUBLIC_ENABLE_EXPLAINABILITY=true
```

Do not use:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_API_BASE_URL=https://world-cup-intelligence-platform.vercel.app
```

## Backend CORS

The backend must allow:

```text
https://world-cup-intelligence-platform.vercel.app
```

The code now also supports a constrained Vercel preview regex:

```text
https://world-cup-intelligence-platform(?:-[a-z0-9-]+)?\.vercel\.app
```

## Backend Freshness Endpoint

The expected backend endpoint is:

```text
https://YOUR_DEPLOYED_FASTAPI_BACKEND/api/v1/data/freshness
```

No deployed backend URL is committed in the repo, so production backend
freshness cannot be verified from code alone. The local backend route should be
validated with:

```bash
cd wcip-backend
./.venv/bin/python -m pytest -q tests/test_realtime_data.py
```
