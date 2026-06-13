# Startup Debug Audit

Date: 2026-06-13

## Commands And Working Directories

- Backend working directory: `wcip-backend`
- Backend startup command: `.venv/bin/uvicorn app.main:app --reload --log-level debug`
- Frontend working directory: `wcip-frontend`
- Frontend startup command: `npm run dev`
- Backend expected URL: `http://localhost:8000`
- Frontend expected URL: `http://localhost:3000`

## Runtime Versions

- Python: `Python 3.14.3` from `wcip-backend/.venv/bin/python`
- Node: `v24.13.0`
- npm: `11.6.2`

## Virtual Environment And Env Files

- Backend virtualenv: present at `wcip-backend/.venv`
- Backend `.env`: present
- Backend `.env.example`: present
- Frontend `.env.local`: present
- Frontend `.env.local.example`: present

Sanitized backend env values from `wcip-backend/.env`:

- `DEBUG=true`
- `DATABASE_URL=sqlite:///./wcip.db`
- `JWT_SECRET_KEY=<set>`
- `JWT_REFRESH_SECRET_KEY=<set>`
- `CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000`

Sanitized frontend env values:

- `NEXT_PUBLIC_API_BASE=/backend/api/v1`

## Root Environment Conflict

The active shell environment contains `DEBUG=release`. Pydantic settings read process
environment variables before `.env`, so this overrides `wcip-backend/.env` and causes
backend imports, Alembic, and Uvicorn startup to fail:

```text
pydantic_core._pydantic_core.ValidationError: DEBUG
Input should be a valid boolean, unable to interpret input
input_value='release'
```

With `DEBUG=false` explicitly passed, `from app.main import app` succeeds and reports
65 registered routes. Redis is unavailable in the sandbox, but the backend falls back
to the in-memory cache as expected.

## Database And Migration Status

- Configured database URL: `sqlite:///./wcip.db`
- Resolved SQLite path: `wcip-backend/wcip.db`
- Database file exists: yes
- Database size observed: 11,968,512 bytes
- Current local table counts with `DEBUG=false`:
  - `teams=57`
  - `players=48`
  - `qualified_teams=48`

`alembic current` fails under the raw environment because of `DEBUG=release`.
With `DEBUG=false`, Alembic loads, but the current command did not print an applied
revision in the captured output. `alembic heads` reports `a1c9e8d4f602` as the
current head revision.

## Frontend Validation Status

- `npm run build` passes using `next build --webpack`.
- `npm run typecheck` can fail before a fresh build because `tsconfig.json` includes
  generated `.next/types/**/*.ts` files and stale incremental metadata can point to
  missing generated route type files.
- Previous lint-script issue was fixed to use `eslint .`; lint passes after source
  cleanup.

## Port Status

`lsof` reported listeners on both expected ports:

- Port 8000: Python processes were listed.
- Port 3000: a Node process was listed.

However, `curl -I http://localhost:8000/docs` and `curl -I http://localhost:3000`
could not connect during the audit, so the listed processes were not serving the
expected apps reliably. If this repeats locally, stop the listed process IDs from
`lsof -i :8000` or `lsof -i :3000`, then restart the apps from the correct folders.

## API Proxy / Base URL

The frontend API client defaults to `/backend/api/v1` and `next.config.mjs` rewrites
`/backend/:path*` to `http://localhost:8000/:path*`. This is a valid local-dev setup
when the frontend is served by Next. Direct `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
would also work for browser calls if CORS is configured.

## Proposed Fixes

1. Make backend `DEBUG` parsing tolerant of common deployment strings such as
   `release`, `production`, and `development`.
2. Add startup diagnostics that log sanitized database URL, resolved SQLite path,
   Alembic revision status, and row counts for teams, players, and qualified teams.
3. Make frontend `typecheck` independent of generated `.next/types` files so it
   passes before `npm run build`.
4. Re-run backend and frontend validation plus API smoke checks.
