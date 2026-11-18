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

if [ "${SYNC_DATA_ON_START:-false}" = "true" ]; then
  # Background + non-fatal: a slow or failing provider must not block the
  # port bind or crash the API. sync_data holds an advisory lock, so
  # overlapping starts are safe.
  echo "Starting background data sync..."
  (python -m scripts.sync_data || echo "Background data sync failed (exit $?); serving previously stored data.") &
fi

echo "Starting FastAPI server..."
# Render terminates TLS at its proxy, so without these flags every request
# appears to come from the proxy IP and all visitors share one rate-limit
# bucket (RATE_LIMIT_PER_MINUTE). Only Render's proxy can reach $PORT.
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
  --proxy-headers --forwarded-allow-ips='*'
