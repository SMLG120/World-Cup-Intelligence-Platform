# Vercel Deployment Audit

Date: 2026-06-21

## Repository Structure

- Repository root: monorepo containing `wcip-backend/` and `wcip-frontend/`.
- Backend folder: `wcip-backend/` (FastAPI, not a Vercel Next.js app).
- Frontend folder: `wcip-frontend/`.
- Actual Next.js project root: `wcip-frontend/`.
- Frontend package file: `wcip-frontend/package.json`.
- Frontend App Router directory: `wcip-frontend/app/` exists.
- Frontend Next config: `wcip-frontend/next.config.mjs`.
- Frontend Vercel config: `wcip-frontend/vercel.json`.
- Root package file: `package.json` exists, but the repository root has no
  `app/` or `pages/` directory.

## Root Cause

The Vercel error:

```text
Couldn't find any `pages` or `app` directory
```

means Vercel is building from the repository root or another non-frontend
folder. The Next.js app lives in `wcip-frontend/`, so Vercel must use
`wcip-frontend` as the project root. Creating a fake root-level `app/` directory
would hide the configuration problem and is not the right fix.

## Current Deployment Assumption

Vercel appears to be running a build command from the repository root. That root
contains `package.json`, but it does not contain the frontend `app/` directory.
The existing `wcip-frontend/vercel.json` is only picked up if the Vercel Root
Directory is set to `wcip-frontend`.

## Correct Vercel Settings

Use these settings in the Vercel dashboard:

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

`npm run vercel-build` is also available inside `wcip-frontend` and delegates to
`next build --webpack`. The explicit webpack flag avoids the local Next 16
Turbopack CSS panic seen in the sandbox while preserving a normal Next.js
production build for Vercel.

## Required Frontend Environment Variables

Set these in the Vercel project environment:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_BACKEND_URL
NEXT_PUBLIC_APP_NAME=World Cup Intelligence Platform
NEXT_PUBLIC_ENABLE_ML=true
NEXT_PUBLIC_ENABLE_SCENARIOS=true
NEXT_PUBLIC_ENABLE_EXPLAINABILITY=true
```

Do not set production `NEXT_PUBLIC_API_BASE_URL` to `localhost`. The FastAPI
backend must be deployed separately and the frontend should call that deployed
backend URL.

## Backend Deployment Boundary

`wcip-backend/` should not be deployed to Vercel as a normal Next.js app. Deploy
it separately on Render, Railway, Fly.io, AWS, or another Python/Docker host,
then point `NEXT_PUBLIC_API_BASE_URL` at that backend.
