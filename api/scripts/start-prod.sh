#!/bin/sh
# Production/demo entrypoint: migrate, reference data, single process behind Caddy.
set -e

alembic upgrade head
# Types, weights and coefficients (only inserts what is missing; never overwrites).
python -m app.cli seed

# demo stack only: test users and fictitious data, clearly labelled in the screens.
if [ "${SEED_DEMO:-false}" = "true" ] && [ "${APP_ENV}" != "production" ]; then
  python -m app.cli seed --dev --fake "${SEED_FAKE_COUNT:-60}"
fi

# One process: the in-memory rate limiter needs a single worker (see app/ratelimit.py).
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 \
  --proxy-headers --forwarded-allow-ips='*' --workers 1 --no-server-header
