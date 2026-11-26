#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$0")/.."
if [[ -z "${BOOTSTRAP_ADMIN_IDENTIFIER:-}" ]]; then
  printf 'Founder/admin email: '
  read -r BOOTSTRAP_ADMIN_IDENTIFIER
fi
if [[ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]]; then
  printf 'Founder/admin password: '
  read -rs BOOTSTRAP_ADMIN_PASSWORD
  printf '\n'
fi
export BOOTSTRAP_ADMIN_IDENTIFIER BOOTSTRAP_ADMIN_PASSWORD
export BOOTSTRAP_ORGANIZATION_NAME="${BOOTSTRAP_ORGANIZATION_NAME:-Next Gen For Earth — Founder Demo}"
export BOOTSTRAP_ORGANIZATION_SLUG="${BOOTSTRAP_ORGANIZATION_SLUG:-next-gen-for-earth-demo}"
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE="${BOOTSTRAP_ORGANIZATION_COUNTRY_CODE:-KE}"
export BOOTSTRAP_API_URL="${BOOTSTRAP_API_URL:-http://127.0.0.1:8000/api}"
echo "[1/3] Provisioning owner account, organisation, people, partners and programmes"
uv run python scripts/bootstrap_nextgen.py
echo "[2/3] Reconciling demo catalogue"
uv run python -m scripts.seed_nextgen_demo --organization-slug "$BOOTSTRAP_ORGANIZATION_SLUG"
echo "[3/3] Importing source website pages and media"
uv run python -m scripts.import_nextgen_website --organization-slug "$BOOTSTRAP_ORGANIZATION_SLUG" --publish-website-content
echo "Provisioning completed for $BOOTSTRAP_ORGANIZATION_SLUG"
