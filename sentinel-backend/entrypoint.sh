#!/bin/sh
# Kavach Backend Entrypoint
# Runs Alembic migrations then seeds DB before starting the API server

set -e

echo "=== Kavach Backend Starting ==="
echo "Database: $DATABASE_URL"

# Run Alembic migrations
echo "[1/3] Running database migrations..."
alembic upgrade head

# Seed/backfill the database in the background so Render sees an open port quickly.
# The seed script is idempotent and only fills missing/incomplete tables.
echo "[2/3] Starting database seed/backfill in background..."
python -m db.seed &

# Start FastAPI server
echo "[3/3] Starting Uvicorn server..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-1}" \
    --log-level info
