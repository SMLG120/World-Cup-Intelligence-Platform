# Code Cleanup Audit

Date: 2026-06-13  
Scope: FastAPI backend, SQLAlchemy database, Celery/Redis runtime, ML/ETL
artifacts, Next.js frontend, Docker/Render/Vercel configuration.

## Executive Summary

The repository needs safety cleanup before the next commit. The root
`.gitignore` already ignores many sensitive/generated paths, but multiple
generated files are already tracked by Git, so ignore rules alone will not
protect the repository. The most important cleanup is to remove tracked
bytecode, local SQLite databases, model pickle files, CatBoost training logs,
ETL cache files, zip archives, and local build output from the Git index without
deleting local copies.

No real production secret was found in the source scan. The matches were
placeholders, test credentials, documentation examples, or ordinary auth field
names. The backend currently uses `SECRET_KEY`; the requested template names
`JWT_SECRET_KEY` and `JWT_REFRESH_SECRET_KEY` are not yet represented cleanly in
configuration. The frontend currently reads `NEXT_PUBLIC_API_BASE`, while the
requested environment template uses `NEXT_PUBLIC_API_BASE_URL`.

## Files Safe To Remove From Tracking

Remove these from Git tracking with `git rm --cached` or `git rm -r --cached`.
Do not delete local copies if they are useful for local development.

- `wcip-backend/app/**/__pycache__/*.pyc`
- `wcip-backend/etl/**/__pycache__/*.pyc`
- `wcip-backend/ml/**/__pycache__/*.pyc`
- `wcip-backend/tests/**/__pycache__/*.pyc`
- `wcip-backend/wcip/**/__pycache__/*.pyc`
- `wcip-backend/wcip.db`
- `wcip.db`
- `wcip-backend/data/cache/elo_ratings.tsv`
- `wcip-backend/data/cache/fifa_rankings.json`
- `wcip-backend/data/cache/results.csv`
- `wcip-backend/etl/data/etl_state.json`
- `wcip-backend/models/*.pkl`
- `wcip-backend/catboost_info/*`
- `wcip-backend.zip`
- `wcip-frontend.zip`
- `.DS_Store`

These are generated, local, or binary artifacts. They should be reproducible
from ETL/training/build commands or maintained outside the repository.

## Files That Must Stay

- Source code under `wcip-backend/app`, `wcip-backend/etl`,
  `wcip-backend/ml`, `wcip-backend/wcip`, and `wcip-frontend/app`,
  `wcip-frontend/components`, `wcip-frontend/lib`
- Alembic migrations and database schema code
- `README.md`, `API.md`, `DATA_PIPELINE.md`, `MODEL_CARD.md`,
  `REPO_CHECKLIST.md`, `ARCHITECTURE.md`
- `.env.example` files and `.env.local.example` templates
- `requirements.txt`, `package.json`, `package-lock.json`
- Dockerfiles, `docker-compose.yml`, `render.yaml`, `vercel.json`
- `.gitkeep` files used to preserve empty artifact directories
- Validation, migration, ETL, and training scripts under `wcip-backend/scripts`,
  `wcip-backend/etl`, and `wcip-backend/ml`

## Files And Paths That Should Be Ignored

Required ignore coverage:

- Environment files: `.env`, `.env.*`, except committed examples
- Python generated files: `__pycache__/`, `*.py[cod]`, `.pytest_cache/`,
  `.mypy_cache/`, `.ruff_cache/`, coverage output
- Virtual environments: `.venv/`, `venv/`, `env/`
- SQLite/local DB files: `*.db`, `*.sqlite`, `*.sqlite3`, journal files
- Node/Next files: `node_modules/`, `.next/`, `out/`, `dist/`, `build/`,
  `coverage/`, `*.tsbuildinfo`
- Logs: `*.log`, `logs/`
- ML artifacts: `*.pkl`, `*.joblib`, `*.onnx`, `mlruns/`, `wandb/`,
  `artifacts/`, `models/generated/`, `catboost_info/`
- Docker local state: `docker-data/`, `redis-data/`, `postgres-data/`
- Archives and OS/editor noise: `*.zip`, `.DS_Store`, `.idea/`, `.vscode/`
- Credential material: `*.pem`, `*.key`, `*.p12`, `*.pfx`, private key names,
  token/secret/credential JSON files

## Suspicious Secrets Scan

Patterns scanned included:

- `sk-`
- `api_key=`
- `SECRET_KEY=`
- `password=`
- `BEGIN PRIVATE KEY`
- `AWS_SECRET_ACCESS_KEY`
- common GitHub, Slack, Google, and AWS token prefixes

Findings:

- No real production secret was found.
- `README.md` and `wcip-backend/.env.example` contain placeholder secret values.
- Tests contain dummy passwords such as `password123`.
- Auth code contains normal field names such as `password`, `access_token`, and
  `refresh_token`.

## Dependency Issues

- Root `package.json` and root `package-lock.json` appear to duplicate frontend
  Next/React dependencies while the real frontend project lives in
  `wcip-frontend`. This can confuse Next.js root inference during builds.
- Root `node_modules/` exists locally and should never be committed.
- `wcip-frontend/package.json` is the active frontend dependency manifest.
- Backend dependencies are managed in `wcip-backend/requirements.txt`.

## Import And Debug Issues

- No immediate broken imports were identified during static inspection.
- CLI scripts intentionally use `print()` for command output:
  `scripts/validate_world_cup_2026.py`, `scripts/migrate_wc2026_teams.py`,
  `ml/train.py`, and `etl/validate_training_data.py`.
- `app/db/init_db.py` prints a startup message only when run as a script.
- `wcip/wcip/demo.py` is a demonstration script and should remain unless the
  project decides to remove examples.

## Environment Variable Issues

- Backend config currently uses `SECRET_KEY` and `ALGORITHM`; requested
  templates call for `JWT_SECRET_KEY`, `JWT_REFRESH_SECRET_KEY`, and
  `JWT_ALGORITHM`.
- Refresh tokens currently use the same secret as access tokens. This is
  acceptable for local development but should be split for safer production
  rotation.
- Backend CORS config is named `BACKEND_CORS_ORIGINS`; requested examples use
  `CORS_ORIGINS`.
- Frontend API client uses `NEXT_PUBLIC_API_BASE`; requested examples use
  `NEXT_PUBLIC_API_BASE_URL`.
- Docker Compose contains default Postgres credentials for local development.
  They should be environment-variable driven and documented as local-only.
- Render config generates `SECRET_KEY` but does not yet mention split JWT
  refresh secrets.

## Recommended Cleanup Order

1. Update root and service-level `.gitignore` files.
2. Add safe placeholder `.env.example` templates.
3. Add local env generation script that never prints secrets.
4. Add repo safety scanner and `make safety-check`.
5. Update config to accept safe env aliases without breaking existing variables.
6. Update Docker/deploy docs and templates.
7. Remove tracked generated artifacts from Git index with documented commands.
8. Run backend tests, frontend typecheck/build, and safety scan.
