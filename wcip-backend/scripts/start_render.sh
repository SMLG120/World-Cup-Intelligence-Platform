#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

if [ "${BOOTSTRAP_DATA_ON_START:-true}" = "true" ]; then
  echo "Bootstrapping production data..."
  python -m scripts.bootstrap_data
else
  echo "Skipping production data bootstrap because BOOTSTRAP_DATA_ON_START is not true."
fi

echo "Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port $PORT
