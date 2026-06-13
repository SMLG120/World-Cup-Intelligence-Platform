# Project Memory

## Security Cleanup Status

- Root and service-level ignore rules are intended to block `.env`, local DBs,
  Python bytecode, Node/Next build output, ETL cache files, ML artifacts,
  CatBoost logs, private keys, credential JSON, and zip exports.
- `.env.example` files must remain placeholder-only and committed.
- Real `.env` and `.env.local` files must never be committed.
- Local env files should be generated with:

```bash
cd wcip-backend
python scripts/generate_local_env.py
```

- Repository safety checks should be run with:

```bash
make safety-check
```

## Tracked Artifact Risk

The cleanup audit found generated files already tracked by Git, including
Python bytecode, SQLite databases, ETL cache files, model pickle files,
CatBoost training logs, and zip exports. `.gitignore` does not protect files
that are already tracked.

Before committing cleanup, remove those files from the Git index without
deleting local copies using the commands documented in `SECURITY_CLEANUP.md`.

## Environment Configuration

- Backend accepts both old and new env names:
  - `SECRET_KEY` or `JWT_SECRET_KEY`
  - `ALGORITHM` or `JWT_ALGORITHM`
  - `BACKEND_CORS_ORIGINS` or `CORS_ORIGINS`
  - `ENVIRONMENT` or `APP_ENV`
- Refresh tokens can use `JWT_REFRESH_SECRET_KEY`; if absent, local development
  falls back to the access-token secret.
- Frontend accepts both:
  - `NEXT_PUBLIC_API_BASE_URL=http://localhost:8000`
  - `NEXT_PUBLIC_API_BASE=/backend/api/v1`

## Production Secrets

Production secrets must be generated outside the repo and configured through
Render, Vercel, or another secret manager. Do not reuse generated local secrets
in production.

