#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CENTRAL_DIR="${ODK_CENTRAL_DIR:-${ROOT}/.local/odk-central}"
EMAIL="${ODK_CENTRAL_ADMIN_EMAIL:-odk-admin@example.test}"

if [[ ! -f "${CENTRAL_DIR}/docker-compose.yml" ]]; then
  echo "ODK Central checkout not found at ${CENTRAL_DIR}; run setup_odk_central_local.sh first" >&2
  exit 2
fi
if [[ "${EMAIL}" != *@example.test ]]; then
  echo "For this local-only bootstrap, use a reserved @example.test address" >&2
  exit 2
fi

cd "${CENTRAL_DIR}"
echo "Creating local ODK Central account ${EMAIL}. The CLI prompts for a password."
docker compose exec service odk-cmd --email "${EMAIL}" user-create
docker compose exec service odk-cmd --email "${EMAIL}" user-promote

echo "Local ODK Central administrator created. No mailbox or email delivery was used."
