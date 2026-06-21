# Deployment

This repository is a monorepo:

```text
repo-root/
  wcip-backend/    FastAPI backend
  wcip-frontend/   Next.js frontend
```

The frontend and backend deploy separately.

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
