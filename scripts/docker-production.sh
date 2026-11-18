#!/usr/bin/env bash
set -euo pipefail

COMPOSE=(docker compose -f docker/compose.production.yml)

: "${DATABASE_URL:?DATABASE_URL must be set}"

"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm api alembic upgrade head
"${COMPOSE[@]}" up -d

echo "Waiting for API and web readiness..."
for _ in {1..30}; do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2)" >/dev/null 2>&1 \
    && curl --fail --silent "http://127.0.0.1:${WEB_PORT:-3000}/" >/dev/null; then
    echo "API and web services are ready."
    exit 0
  fi
  sleep 2
done

echo "Production services did not become ready in time." >&2
"${COMPOSE[@]}" ps
exit 1
