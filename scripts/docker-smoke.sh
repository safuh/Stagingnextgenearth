#!/usr/bin/env bash
set -euo pipefail

# Isolate this smoke stack from the developer's normal Compose project.
# Never remove volumes: the smoke database may contain useful diagnostics.
if [[ -z "${COMPOSE_PROJECT_NAME:-}" ]]; then
  SAFE_USER="$(printf '%s' "${USER:-local}" | tr '[:upper:]' '[:lower:]' | tr -cs 'a-z0-9-' '-')"
  export COMPOSE_PROJECT_NAME="nextgen-smoke-${SAFE_USER}"
fi
export API_PORT="${API_PORT:-18000}"
COMPOSE=(docker compose -p "$COMPOSE_PROJECT_NAME" -f docker/compose.yml)
cleanup() {
  "${COMPOSE[@]}" down --remove-orphans
}
trap cleanup EXIT

wait_for() {
  local url="$1"
  local description="$2"
  echo "Waiting for ${description}..."
  for _ in {1..45}; do
    if curl --fail --silent "$url" >/dev/null; then
      return 0
    fi
    sleep 2
  done
  echo "${description} did not become ready." >&2
  "${COMPOSE[@]}" ps >&2
  "${COMPOSE[@]}" logs --tail=120 api db >&2 || true
  return 1
}

"${COMPOSE[@]}" up --build -d
wait_for "http://127.0.0.1:${API_PORT}/api/health/live" "API liveness"
"${COMPOSE[@]}" exec -T api alembic upgrade head
wait_for "http://127.0.0.1:${API_PORT}/api/health/ready" "API readiness after migrations"
"${COMPOSE[@]}" ps
