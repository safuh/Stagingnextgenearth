#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CENTRAL_DIR="${ODK_CENTRAL_DIR:-${ROOT}/.local/odk-central}"
CENTRAL_REF="${ODK_CENTRAL_REF:-master}"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 127; }
command -v docker >/dev/null 2>&1 || { echo "Docker Engine is required" >&2; exit 127; }
docker compose version >/dev/null 2>&1 || { echo "Docker Compose v2 is required" >&2; exit 127; }

if [[ -e "${CENTRAL_DIR}" ]]; then
  if [[ ! -d "${CENTRAL_DIR}/.git" ]]; then
    echo "Refusing to use existing non-Git path: ${CENTRAL_DIR}" >&2
    exit 2
  fi
  echo "Using existing ODK Central checkout: ${CENTRAL_DIR}"
else
  mkdir -p "$(dirname "${CENTRAL_DIR}")"
  git clone --depth 1 --branch "${CENTRAL_REF}" https://github.com/getodk/central.git "${CENTRAL_DIR}"
fi
git -C "${CENTRAL_DIR}" submodule update --init --recursive

if [[ ! -f "${CENTRAL_DIR}/.env" ]]; then
  cp "${CENTRAL_DIR}/.env.template" "${CENTRAL_DIR}/.env"
fi

python3 - "${CENTRAL_DIR}/.env" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
values = {
    "DOMAIN": "local",
    "SYSADMIN_EMAIL": "odk-admin@example.test",
    "SSL_TYPE": "selfsign",
    "HTTP_PORT": "127.0.0.1:8088",
    "HTTPS_PORT": "127.0.0.1:8443",
}
lines = path.read_text().splitlines()
seen: set[str] = set()
updated: list[str] = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else ""
    if key in values:
        updated.append(f"{key}={values[key]}")
        seen.add(key)
    else:
        updated.append(line)
for key, value in values.items():
    if key not in seen:
        updated.append(f"{key}={value}")
path.write_text("\n".join(updated) + "\n")
PY

mkdir -p "${CENTRAL_DIR}/files"
touch "${CENTRAL_DIR}/files/allow-postgres14-upgrade"
echo "Building ODK Central (first run may take several minutes)..."
(
  cd "${CENTRAL_DIR}"
  docker compose build
  docker compose up --detach
  docker compose ps
)

cat <<EOF

ODK Central local stack has been started.

Next steps:
  1. Add this hosts entry if 'local' does not resolve to 127.0.0.1:
       127.0.0.1 local
  2. Wait until the Central nginx container is healthy.
  3. Create the local administrator without an email inbox:
       ODK_CENTRAL_DIR='${CENTRAL_DIR}' ./scripts/bootstrap_odk_central_local_admin.sh
  4. Open https://local:8443 (accept the local self-signed certificate warning).

This stack is for local development only. Do not expose it publicly or reuse
its credentials/data in staging or production.

EOF
