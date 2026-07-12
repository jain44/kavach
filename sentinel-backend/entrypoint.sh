#!/bin/sh
# Kavach Backend Entrypoint
# Runs Alembic migrations, then starts the API server.

set -e

echo "=== Kavach Backend Starting ==="
echo "Database: $DATABASE_URL"

# Run Alembic migrations
echo "[1/3] Running database migrations..."
alembic upgrade head

if [ "${RUN_SEED_ON_STARTUP:-0}" = "1" ]; then
    echo "[2/3] Running database seed/backfill..."
    python -m db.seed
else
    echo "[2/3] Skipping seed/backfill on startup (set RUN_SEED_ON_STARTUP=1 to enable)"
fi

# Start FastAPI server
echo "[3/3] Starting Uvicorn server..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --log-level info
