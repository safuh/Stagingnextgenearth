#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${NGINX_VALIDATION_IMAGE:-docker.io/library/nginx:1.27-alpine}"

command -v docker >/dev/null 2>&1 || {
  echo "docker is required to validate the Nginx edge configuration" >&2
  exit 127
}

docker run --rm \
  --mount "type=bind,src=${ROOT}/docker/nginx/nginx.conf,dst=/etc/nginx/nginx.conf,readonly" \
  "${IMAGE}" nginx -t
