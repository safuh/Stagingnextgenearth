#!/usr/bin/env bash
set -euo pipefail

COMPOSE=(docker compose -f docker/compose.production.yml)

: "${DATABASE_URL:?DATABASE_URL must be set}"

"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm api alembic upgrade head
"${COMPOSE[@]}" up -d

echo "Waiting for API readiness..."
for _ in {1..30}; do
  if curl --fail --silent http://127.0.0.1:"${APP_PORT:-8000}"/api/health/ready >/dev/null; then
    echo "Production deployment is ready."
    exit 0
  fi
  sleep 2
done

echo "Production API did not become ready in time." >&2
"${COMPOSE[@]}" ps
exit 1
