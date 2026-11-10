#!/usr/bin/env bash
set -euo pipefail

COMPOSE=(docker compose -f docker/compose.yml)
cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans
}
trap cleanup EXIT

"${COMPOSE[@]}" up --build -d
echo "Waiting for API..."
for _ in {1..30}; do
  if curl --fail --silent http://127.0.0.1:8000/api/health/live >/dev/null; then
    break
  fi
  sleep 2
done

curl --fail --silent http://127.0.0.1:8000/api/health/live
curl --fail --silent http://127.0.0.1:8000/api/health/ready
"${COMPOSE[@]}" exec -T api alembic upgrade head
"${COMPOSE[@]}" ps
