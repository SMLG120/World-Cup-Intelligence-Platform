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
# Render terminates TLS at its proxy, so without these flags every request
# appears to come from the proxy IP and all visitors share one rate-limit
# bucket (RATE_LIMIT_PER_MINUTE). Only Render's proxy can reach $PORT.
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT" \
  --proxy-headers --forwarded-allow-ips='*'
