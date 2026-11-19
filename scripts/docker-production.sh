#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Production environment file not found: $ENV_FILE" >&2
  echo "Copy .env.production.example to .env, replace every placeholder, and chmod 600 .env." >&2
  exit 1
fi

# Validate the exact file Compose will use. The validator never prints secrets.
uv run python scripts/validate-production-env.py "$ENV_FILE"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f docker/compose.production.yml)
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm api alembic upgrade head
"${COMPOSE[@]}" up -d

echo "Waiting for API and web readiness..."
for _ in {1..45}; do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2)" >/dev/null 2>&1 \
    && curl --fail --silent "http://127.0.0.1:${WEB_PORT:-3000}/" >/dev/null; then
    echo "API and web services are ready."
    exit 0
  fi
  sleep 2
done

echo "Production services did not become ready in time." >&2
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" logs --tail=150 api web >&2 || true
exit 1
