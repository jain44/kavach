#!/bin/sh
# Kavach Backend Entrypoint
# Runs Alembic migrations then seeds DB before starting the API server

set -e

echo "=== Kavach Backend Starting ==="
echo "Database: $DATABASE_URL"

# Run Alembic migrations
echo "[1/3] Running database migrations..."
alembic upgrade head

# Seed the database (idempotent — safe to run every time)
echo "[2/3] Seeding database..."
python -m db.seed

# Start FastAPI server
echo "[3/3] Starting Uvicorn server..."
exec uvicorn api.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info
