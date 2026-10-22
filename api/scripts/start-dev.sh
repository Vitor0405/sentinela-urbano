#!/bin/sh
# Development entrypoint: migrate, seed (idempotent) and run with auto-reload.
set -e

alembic upgrade head

if [ "${SEED_ON_START:-dev}" = "dev" ]; then
  python -m app.cli seed --dev --fake "${SEED_FAKE_COUNT:-60}"
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --proxy-headers
