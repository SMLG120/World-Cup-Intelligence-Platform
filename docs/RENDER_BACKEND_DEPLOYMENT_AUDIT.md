# Render Backend Deployment Audit

Date: 2026-06-22

## Backend Structure

- Backend root directory: `wcip-backend`
- FastAPI entrypoint file: `wcip-backend/app/main.py`
- FastAPI app import path: `app.main:app`
- `app = FastAPI(...)` location: `wcip-backend/app/main.py`
- Requirements file: `wcip-backend/requirements.txt`
- Alembic config: `wcip-backend/alembic.ini`
- Alembic env: `wcip-backend/alembic/env.py`
- Database config: `wcip-backend/app/db/base.py`
- Environment loader: `wcip-backend/app/core/config.py`
- CORS config: `wcip-backend/app/core/config.py` and `wcip-backend/app/main.py`
- Auth/JWT config: `wcip-backend/app/core/config.py` and `wcip-backend/app/core/security.py`
- Health endpoints: `GET /` and `GET /health`
- Data freshness endpoint: `GET /api/v1/data/freshness`

## Render Commands

Use these Render dashboard settings for the backend web service:

```text
Service Type: Web Service
Runtime: Python
Root Directory: wcip-backend
Build Command: pip install -r requirements.txt
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Run migrations and bootstrap data separately from Render Shell before serving a
fresh production database:

```bash
alembic upgrade head
python -m scripts.bootstrap_data
```

The web start command is:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Required Render Environment Variables

```env
DATABASE_URL=Render PostgreSQL Internal Database URL
SECRET_KEY=generated secret
JWT_SECRET_KEY=generated jwt secret
JWT_REFRESH_SECRET_KEY=generated refresh jwt secret
ALLOWED_ORIGINS=https://world-cup-intelligence-platform.vercel.app,http://localhost:3000
ENVIRONMENT=production
APP_ENV=production
DEBUG=false
JWT_ALGORITHM=HS256
```

Optional but recommended when using the worker/cache:

```env
REDIS_URL=Render Redis connection string
CELERY_BROKER_URL=Render Redis connection string
CELERY_RESULT_BACKEND=Render Redis connection string
```

## Secret Generation

Generate `SECRET_KEY` locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Generate a different `JWT_SECRET_KEY` locally:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Generate a different `JWT_REFRESH_SECRET_KEY` the same way if you keep refresh
tokens on a separate signing secret. Do not commit any generated values.

## Database

`DATABASE_URL` comes from the Render PostgreSQL database:

```text
New -> PostgreSQL -> Create database -> Copy Internal Database URL
```

Use Render's internal PostgreSQL URL on the backend service only. Do not put
`DATABASE_URL`, `SECRET_KEY`, or `JWT_SECRET_KEY` in Vercel frontend variables.

The SQLAlchemy engine reads `settings.DATABASE_URL`, and Alembic injects the
same value in `alembic/env.py`.

## CORS

The backend reads `ALLOWED_ORIGINS`, `CORS_ORIGINS`, or
`BACKEND_CORS_ORIGINS`. For Render, set:

```env
ALLOWED_ORIGINS=https://world-cup-intelligence-platform.vercel.app,http://localhost:3000
```

The code also allows the exact production Vercel URL by default and supports a
constrained Vercel preview regex.

## Vercel Frontend Connection

After Render deploys the backend, set this in Vercel:

```env
NEXT_PUBLIC_API_BASE_URL=https://YOUR_RENDER_BACKEND_URL
```

This belongs in:

```text
Vercel -> Project -> Settings -> Environment Variables
```

Redeploy Vercel after changing the value.

## Deployment Verification

Backend checks:

```text
https://YOUR_RENDER_BACKEND_URL/
https://YOUR_RENDER_BACKEND_URL/health
https://YOUR_RENDER_BACKEND_URL/docs
https://YOUR_RENDER_BACKEND_URL/api/v1/data/freshness
```

Frontend check:

```text
https://world-cup-intelligence-platform.vercel.app
```

In DevTools Network, the freshness request must go to:

```text
https://YOUR_RENDER_BACKEND_URL/api/v1/data/freshness
```

It must not go to localhost, `undefined`, or the Vercel frontend origin.

## Risks

- `wcip-backend/.env` and `wcip-backend/wcip.db` exist locally; do not commit or
  deploy them as production configuration.
- The production backend needs Render PostgreSQL. SQLite is for local fallback
  only.
- The Python build installs ML packages such as XGBoost, LightGBM, CatBoost, and
  SHAP; Render build time and memory should be monitored on the selected plan.
- `SECRET_KEY` is accepted for compatibility, but JWT signing uses
  `JWT_SECRET_KEY` when it is set. Keep `JWT_SECRET_KEY` and
  `JWT_REFRESH_SECRET_KEY` strong and private.
