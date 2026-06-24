# Data Freshness / Local Setup / Vercel / Render Deployment Audit

Date: 2026-06-22

This repo already accumulated several prior audits on this exact topic
(`docs/DEPLOYMENT_CONNECTION_AUDIT.md`, `docs/VERCEL_DATA_FRESHNESS_AUDIT.md`,
`docs/RENDER_BACKEND_DEPLOYMENT_AUDIT.md`, `LOCAL_CODESPACE_SETUP_AUDIT.md`,
`RESUME_LOCAL_DEPLOYMENT_AUDIT.md`). Those diagnosed the frontend/backend
contract correctly and are not duplicated in full here. This pass re-verified
everything end to end against the current code and found two real,
previously-undiagnosed deploy-breaking bugs in the Render blueprint and one
defensive gap in database config — both fixed below — plus one piece of
repo clutter that risked future Vercel confusion.

## What the app is currently doing

- Frontend (`wcip-frontend/lib/api.ts`) builds every API call from
  `NEXT_PUBLIC_API_BASE_URL` + `/api/v1/...` via `buildApiUrl()`. It throws
  (surfaced as "Backend not configured") if the env var is unset, and flags
  (`getApiConfigIssue()`) if the value still contains `/api/v1`, is
  `localhost` in production, points at the frontend's own origin, or is
  insecure `http://` under an HTTPS frontend. There is no double `/api/v1`
  path in the current code — `NEXT_PUBLIC_API_BASE_URL` is the backend
  *origin only*, and `/api/v1` is appended exactly once.
- `components/DataFreshnessCard.tsx` calls `useDataFreshness()` →
  `GET /api/v1/data/freshness`, and renders "Backend unreachable" /
  "Backend not configured" / "Data source unavailable" / "Partial snapshot"
  /  "Predictions refreshed" depending on the fetch outcome — these are
  exactly the strings reported as errors, confirming they come from this
  component's own state machine, not a crash.
- Backend `GET /api/v1/data/freshness`
  (`app/services/data_refresh_service.get_data_freshness_from_db`) never
  raises on a sparse/empty database; it returns `status: "available"` or
  `"partial"` with a `message` field instead of a 500. Verified locally with
  a real (non-empty) database — returns real Elo/FIFA/squad timestamps, not
  faked data.
- `app/models/rag.py` exists and is imported by `app/models/__init__.py`;
  the previously-reported `ModuleNotFoundError: app.models.rag` is already
  fixed in this codebase (see `docs/DEPLOYMENT_CONNECTION_AUDIT.md`).

## What the app should be doing

Exactly what's described above — this part of the architecture was already
correct. The remaining gap was entirely in **how the backend gets onto
Render**, not in the frontend/backend contract.

## Why Data Freshness was failing (root cause)

`GET /api/v1/data/freshness` itself is not the problem — it works locally
and degrades gracefully. "Backend unreachable" / "Failed to fetch" /
"Data source unavailable" on the deployed site point at the *Render backend
not being reachable at all*, which traces to two real bugs in
`wcip-backend/render.yaml`:

1. **Fresh Render databases need explicit migrations and bootstrap.** The web
   service now uses the requested direct start command
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. On a fresh Render
   PostgreSQL database, run `alembic upgrade head` and
   `python -m scripts.bootstrap_data` from Render Shell before serving traffic.

2. **No `rootDir`.** `render.yaml` lives at `wcip-backend/render.yaml` but
   declared no `rootDir`. Render Blueprints run build/start commands from the
   **repository root** unless a service sets `rootDir` explicitly. With no
   `rootDir`, `pip install -r requirements.txt` and the Uvicorn start command
   would execute from the repo root, where `requirements.txt` does not exist —
   this alone is enough to make the Render build or boot fail outright.
   **Fixed:** added `rootDir: wcip-backend` to both the `wcip-api` web
   service and the `wcip-worker` worker service.

3. **(Defensive, not yet confirmed as the live cause) Postgres URL scheme.**
   `app/db/base.py` passes `settings.DATABASE_URL` straight to
   `sqlalchemy.create_engine()` with no normalization. Some Postgres
   providers (Render included, historically) hand out `postgres://`
   connection strings; SQLAlchemy 1.4+ rejects that scheme outright
   (`NoSuchModuleError: Can't load plugin: sqlalchemy.dialects:postgres`),
   which would crash the backend on boot before any health check passes.
   **Fixed:** added a `field_validator` on `DATABASE_URL` in
   `app/core/config.py` that rewrites `postgres://` → `postgresql://` before
   the engine is created. Covered by `tests/test_config.py`.

None of these three are visible from the frontend or from reading
`lib/api.ts` — they only show up once you trace exactly how Render executes
`render.yaml`, which is why earlier audits (correctly) concluded the
frontend/backend *contract* was fine but couldn't confirm why the backend
itself wasn't reachable.

## Was `/api/v1` duplicated?

No. Confirmed by reading `buildApiUrl()`/`request()` in `lib/api.ts`: the
base URL is the backend origin only, `/api/v1` is appended exactly once in
`request()`. `getApiConfigIssue()` actively detects and warns if someone
*does* set `NEXT_PUBLIC_API_BASE_URL` with a trailing `/api/v1`, which is the
right defensive guard for the misconfiguration the task asked about.

## Was the backend reachable locally?

Yes, after this audit, confirmed directly:

```text
python3 -c "from app.main import app" -> Backend imports OK
uvicorn app.main:app --port 8000  -> started
GET http://localhost:8000/health             -> 200 {"status":"ok"}
GET http://localhost:8000/api/v1/data/freshness -> 200, status "available", real Elo/FIFA/squad timestamps
```

Frontend, against that same local backend:

```text
npm ci          -> clean install succeeded (one stale node_modules dir had to be reinstalled — local environment issue, not a code bug)
npm run typecheck -> pass
npm run build     -> pass, all routes compiled
npm run dev (port 3123) -> 200, SSR shows "Checking sources" (correct: freshness fetches client-side after hydration)
```

## Was the backend reachable on Render?

Not verifiable from this environment (no access to the live Render service
or its dashboard). The two render.yaml bugs above (`rootDir`, migration
start command) are sufficient on their own to explain build/boot failures or
post-migration instability, independent of network access. **This must be
re-verified against the actual Render dashboard after redeploying** with the
fixed `render.yaml` — see verification checklist below.

## Did the production database have freshness data?

Not verifiable from here either — that's specific to whatever the live
Render PostgreSQL instance currently contains. Locally, the seeded SQLite
database does have real Elo/FIFA/squad data and returns a full
`"status": "available"` response. Once the Render service is confirmed
reachable, run the same data refresh/seed steps documented in
`docs/DATA_PIPELINE.md` against the Render database.

## CORS

Already correct. `app/core/config.py` defaults `BACKEND_CORS_ORIGINS` to
include `http://localhost:3000`, `http://127.0.0.1:3000`, and the Vercel
production URL even with no env var set, and also accepts `ALLOWED_ORIGINS`
/ `CORS_ORIGINS` as aliases. `render.yaml` sets all three explicitly plus a
`BACKEND_CORS_ORIGIN_REGEX` covering Vercel preview deployments.

## Vercel / Render environment variables

- Vercel needs exactly: `NEXT_PUBLIC_API_BASE_URL=https://<your-render-backend>` (backend **origin only**, no `/api/v1`, never `localhost`, never the Vercel URL itself).
- Render's `wcip-api` web service gets `DATABASE_URL` from the `wcip-db` PostgreSQL instance, `SECRET_KEY`/`JWT_SECRET_KEY`/`JWT_REFRESH_SECRET_KEY` auto-generated by the blueprint, and `ALLOWED_ORIGINS`/CORS vars pointing at the Vercel URL — all already declared correctly in `render.yaml`; no missing keys found.

## Repo clutter found and removed

The repo root had its own `package.json`/`package-lock.json` declaring
`"next": "^16.3.0-canary.42"` — a pre-release version, unrelated to the real
app's `wcip-frontend/package.json` (`"next": "^16.2.4"`). Both `vercel.json`
files already bypass this (`installCommand`/`buildCommand` use `npm --prefix
wcip-frontend`), so it was never actually executed by the documented deploy
path — but it's exactly the kind of leftover that causes "sometimes it
installs a different Next.js version" confusion if anyone ever runs a plain
`npm install` at the repo root or a Vercel project setting drifts from the
documented Root Directory. Removed the dead `dependencies` block and
regenerated an empty root lockfile.

## Files Changed

- `wcip-backend/render.yaml` — direct Uvicorn start command and `rootDir: wcip-backend` on both services.
- `wcip-backend/app/core/config.py` — normalizes `postgres://` → `postgresql://` in `DATABASE_URL`.
- `wcip-backend/tests/test_config.py` — new, covers the URL normalization.
- `package.json` / `package-lock.json` (repo root) — removed unused/misleading Next.js canary dependency block.
- `docs/DEPLOYMENT.md`, `README.md`, `docs/REPO_CHECKLIST.md` — documented the `rootDir` requirement and the Postgres URL gotcha.

## Exact Local Commands

```bash
cd wcip-backend
python -m venv .venv && source .venv/bin/activate   # if not already set up
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

```bash
cd wcip-frontend
npm install
npm run dev
```

Verify:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/data/freshness
open http://localhost:3000
```

## Exact Render Settings (now matching `render.yaml`)

```text
Service Type: Web Service
Runtime: Python
Root Directory: wcip-backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Health Check Path: /health
```

Required env vars (already declared in `render.yaml` if deployed as a
Blueprint; set manually otherwise):

```env
DATABASE_URL=<Render PostgreSQL Internal Connection String>
SECRET_KEY=<generated>
JWT_SECRET_KEY=<generated>
JWT_REFRESH_SECRET_KEY=<generated>
JWT_ALGORITHM=HS256
ALLOWED_ORIGINS=https://world-cup-intelligence-platform.vercel.app,http://localhost:3000
ENVIRONMENT=production
APP_ENV=production
DEBUG=false
```

## Exact Vercel Settings

```text
Root Directory: wcip-frontend
Framework Preset: Next.js
Install Command: npm install
Build Command: npm run build
Output Directory: .next
```

```env
NEXT_PUBLIC_API_BASE_URL=https://<your-render-backend>.onrender.com
```

Redeploy after changing this — Vercel does not hot-reload env vars into a
running build.

## Final Verification Checklist

- [ ] Redeploy the Render Blueprint (or update the existing service's Root
  Directory/Start Command to match `render.yaml`) and confirm the build logs
  show `alembic upgrade head` running before Uvicorn starts.
- [ ] `curl https://<render-url>/health` → `{"status":"ok"}`
- [ ] `curl https://<render-url>/api/v1/data/freshness` → JSON, not HTML/404
- [ ] Vercel project env has `NEXT_PUBLIC_API_BASE_URL=https://<render-url>` (no `/api/v1`, no `localhost`, not the Vercel URL itself) and has been redeployed since the value was set
- [ ] Open the deployed Vercel site, DevTools → Network, confirm the freshness request goes to `https://<render-url>/api/v1/data/freshness` and returns 200
- [ ] If the response is `"status": "partial"` with real timestamps, that's correct partial-data behavior, not a bug — seed/refresh the Render database per `docs/DATA_PIPELINE.md` to fill it in

## Remaining Risks

- The actual Render backend public hostname could not be confirmed from this
  environment — verify it directly in the Render dashboard and use that
  exact URL in Vercel.
- Render's free/starter Python builds may be memory/time-constrained for
  CatBoost/LightGBM/XGBoost/SHAP; if the build times out, consider a paid
  plan or trimming `requirements.txt` for the web service.
- The Elo data currently in the local database includes an absolute local
  filesystem path in `elo_source_url` (from a one-time PDF-to-CSV import).
  That's harmless for the freshness JSON shape but meaningless once copied
  to Render — re-run the live Elo refresh in production rather than copying
  the local database file.
- This audit could not exercise the actual Render/Vercel dashboards; the two
  `render.yaml` bugs fixed here are confirmed by direct reading of Render's
  Blueprint execution model, not by reproducing a live deploy failure.
