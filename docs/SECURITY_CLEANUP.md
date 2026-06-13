# Security Cleanup Guide

This repository must not commit local secrets, databases, cache files, model
artifacts, virtual environments, or generated build outputs.

## Generate Local Development Env Files

From the backend directory:

```bash
cd wcip-backend
python scripts/generate_local_env.py
```

The script creates:

- `wcip-backend/.env`
- `wcip-frontend/.env.local`

It uses Python `secrets.token_urlsafe()` for local JWT and Postgres secrets,
does not print generated secret values, and will not overwrite existing env
files unless `--force` is passed.

Local secrets are for local development only. Generate production secrets in
Render, Vercel, or your external secret manager.

## Run Safety Checks

From the repository root:

```bash
make safety-check
```

Equivalent direct command:

```bash
python3 scripts/check_repo_safety.py
```

The safety check fails when Git tracks generated or sensitive files such as:

- `.env` files
- SQLite databases
- Python bytecode
- Next.js build output
- model pickle/joblib/ONNX artifacts
- ETL cache files
- CatBoost logs
- suspicious secret strings

## Files Never To Commit

- `.env`, `.env.local`, `.env.production`, or any real environment file
- local SQLite databases such as `wcip.db`
- `__pycache__/` and `*.pyc`
- `node_modules/`, `.next/`, `dist/`, `build/`, coverage output
- model artifacts such as `*.pkl`, `*.joblib`, `*.onnx`
- `catboost_info/`, `mlruns/`, `wandb/`, `artifacts/`
- `data/cache/*`
- private keys, service-account JSON, access tokens, API keys
- local zip exports

`.env.example` and `.env.local.example` files should stay committed and must
contain placeholders only.

## Remove Already-Tracked Generated Files

Run these commands from the repository root to remove generated files from Git
tracking without deleting local copies:

```bash
git rm -r --cached \
  wcip-backend/app/__pycache__ \
  wcip-backend/app/api/__pycache__ \
  wcip-backend/app/api/v1/__pycache__ \
  wcip-backend/app/core/__pycache__ \
  wcip-backend/app/db/__pycache__ \
  wcip-backend/app/models/__pycache__ \
  wcip-backend/app/repositories/__pycache__ \
  wcip-backend/app/schemas/__pycache__ \
  wcip-backend/app/services/__pycache__ \
  wcip-backend/etl/__pycache__ \
  wcip-backend/etl/extract/__pycache__ \
  wcip-backend/etl/load/__pycache__ \
  wcip-backend/etl/player_ratings/__pycache__ \
  wcip-backend/etl/transform/__pycache__ \
  wcip-backend/etl/validation/__pycache__ \
  wcip-backend/etl/world_cup_2026/__pycache__ \
  wcip-backend/ml/__pycache__ \
  wcip-backend/tests/__pycache__ \
  wcip-backend/wcip/__pycache__ \
  wcip-backend/wcip/data/__pycache__ \
  wcip-backend/wcip/engine/__pycache__
```

```bash
git rm --cached \
  .DS_Store \
  wcip.db \
  wcip-backend/wcip.db \
  wcip-backend.zip \
  wcip-frontend.zip
```

```bash
git rm --cached \
  wcip-backend/etl/data/etl_state.json \
  wcip-backend/data/cache/elo_ratings.tsv \
  wcip-backend/data/cache/fifa_rankings.json \
  wcip-backend/data/cache/results.csv
```

```bash
git rm --cached \
  wcip-backend/models/catboost.pkl \
  wcip-backend/models/lightgbm.pkl \
  wcip-backend/models/logistic.pkl \
  wcip-backend/models/random_forest.pkl \
  wcip-backend/models/xgboost.pkl
```

```bash
git rm -r --cached wcip-backend/catboost_info
```

After removing tracked artifacts:

```bash
make safety-check
git status --ignored
```

Commit the cleanup as its own commit so future application changes are easy to
review.

## Rotate Secrets If They Leak

If a real secret was committed or pushed:

1. Revoke or rotate the secret in the provider immediately.
2. Generate a new value outside the repository.
3. Update Render/Vercel/secret-manager dashboard values.
4. Remove the secret from the repo.
5. Run `make safety-check`.
6. If the repository was pushed publicly or shared externally, rewrite history
   with a vetted tool such as `git filter-repo` or the BFG Repo-Cleaner, then
   force-push after coordinating with collaborators.

Do not rely on deleting the current file alone; the secret remains in Git
history until rotated and purged.

## Local Startup Commands

Backend:

```bash
cd wcip-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/generate_local_env.py
uvicorn app.main:app --reload
```

Frontend:

```bash
cd wcip-frontend
npm install
npm run dev
```

Docker Compose:

```bash
cd wcip-backend
python scripts/generate_local_env.py
docker compose up --build
```

Production deployment:

- Generate production JWT/database/provider secrets externally.
- Add backend secrets in Render dashboard or a Render env group.
- Add frontend public configuration in Vercel dashboard.
- Never reuse local generated secrets in production.
- Never commit production `.env` files.
