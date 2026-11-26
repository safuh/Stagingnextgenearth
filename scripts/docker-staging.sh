#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
ENV_FILE="${ENV_FILE:-.env.staging}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-nextgen-staging}"
if [[ ! -f "$ENV_FILE" ]]; then
  echo "Staging environment file not found: $ENV_FILE" >&2
  echo "Copy .env.staging.example to .env.staging, replace placeholders, and chmod 600 .env.staging." >&2
  exit 1
fi

uv run python scripts/validate-production-env.py "$ENV_FILE"
COMPOSE=(docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f docker/compose.production.yml)
"${COMPOSE[@]}" config --quiet
"${COMPOSE[@]}" build
"${COMPOSE[@]}" run --rm api alembic upgrade head
"${COMPOSE[@]}" up -d

echo "Waiting for staging API and web readiness..."
for _ in {1..45}; do
  if "${COMPOSE[@]}" exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=2)" >/dev/null 2>&1 \
    && curl --fail --silent "http://127.0.0.1:${WEB_PORT:-3000}/" >/dev/null; then
    echo "Staging API and web services are ready."
    "${COMPOSE[@]}" ps
    exit 0
  fi
  sleep 2
done

echo "Staging services did not become ready in time." >&2
"${COMPOSE[@]}" ps
"${COMPOSE[@]}" logs --tail=150 api web >&2 || true
exit 1
