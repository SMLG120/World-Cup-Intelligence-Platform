# Cleanup Report

Generated: 2026-06-22

## Cleanup Scope

The cleanup pass focused on files that are unsafe or useless to track:

```text
.env
.env.local
*.db
*.sqlite
__pycache__/
.pytest_cache/
.next/
node_modules/
dist/
build/
coverage/
*.log
.DS_Store
```

## Files Removed From Git Tracking

None. A tracked-file audit found no tracked `.env`, `.env.local`, local database,
cache, dependency, build, coverage, log, or `.DS_Store` files.

## Files Kept

- Source code in `wcip-backend/` and `wcip-frontend/`.
- Alembic migrations and data/ETL scripts.
- Valid RAG code and models.
- Frontend components and pages.
- Documentation and deployment templates.
- Local ignored artifacts such as virtual environments, dependency folders, and SQLite files were left on disk when useful for local verification.

## Ignore Rules Confirmed

The root, backend, and frontend `.gitignore` files cover:

```gitignore
.env
.env.*
!.env.example
!.env.local.example
*.db
*.sqlite
__pycache__/
.pytest_cache/
.next/
node_modules/
dist/
build/
coverage/
*.log
.DS_Store
```

Backend `.env` and frontend `.env.local` are ignored and should remain local-only.

## Secrets Protected

- No production secrets were added to tracked files.
- `.env` and `.env.local` remain ignored.
- Example files contain placeholders only.
- Render secrets belong in Render environment variables.
- Vercel should only receive public frontend variables such as `NEXT_PUBLIC_API_BASE_URL`.

## Risks Avoided

- Did not delete source files, migrations, ETL code, ML code, RAG code, or frontend pages.
- Did not remove local dependency folders needed for fast verification.
- Did not commit local database files.
- Did not commit private credentials, tokens, or generated secrets.

## Local Dependency Note

During verification, `wcip-frontend/node_modules` was found to be corrupt after
stale local Next/npm processes held the dependency tree during reinstall. This
folder is ignored and should not be committed. Quarantine or delete it locally,
then run `npm ci` before frontend typecheck/build:

```bash
cd wcip-frontend
mv node_modules node_modules_corrupt_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true
rm -rf .next
npm ci
```
