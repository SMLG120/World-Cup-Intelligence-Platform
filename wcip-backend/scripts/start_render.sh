#!/usr/bin/env bash
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Bootstrapping production data..."
python -m scripts.bootstrap_data

echo "Starting FastAPI server..."
uvicorn app.main:app --host 0.0.0.0 --port $PORT
