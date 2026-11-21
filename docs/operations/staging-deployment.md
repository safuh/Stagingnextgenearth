# Dedicated staging deployment

This is the repeatable staging path for NextGen For Earth. It uses the same
locked API and Next.js production images as production, but a separate Compose
project, database, hostname, credentials and secret set. Staging runs with
`ENVIRONMENT=production` so production security settings are validated; it is
not a development-mode public server.

## Infrastructure prerequisites

- A dedicated PostgreSQL 17 database with PostGIS 3.5 enabled, reachable from
the deployment host. Do not point staging at production data.
- A DNS name such as `staging.nextgenforearth.org` and TLS termination at a
managed ingress or reverse proxy. Route only the browser-facing web service
through the ingress; keep API and database private.
- Docker Engine with the Compose plugin, `uv`, `curl`, and Git on the deploy
host. The repository's locked dependencies must be available to `uv`.
- A staging-only database user with schema privileges required by Alembic,
a unique JWT signing secret, and a backup/restore policy.

## Configure once

```bash
cp .env.staging.example .env.staging
chmod 600 .env.staging
```

Edit `.env.staging` and replace all placeholders. Set `DATABASE_URL` to the
staging Postgres/PostGIS database and `PUBLIC_BASE_URL` to the HTTPS staging
hostname. Generate a fresh JWT secret and a Fernet key (do not reuse either
from local development or production):

```bash
uv run python -c 'import secrets; print(secrets.token_urlsafe(48))'
uv run python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Store secrets in the host's secret manager where available. The `.env.staging`
file is a deploy-host secret and must never be committed. Keep `CORS_ORIGINS=[]`
for the same-origin Next.js BFF deployment. Do not enable the `odk` profile
until a separate non-production ODK Central project and least-privilege account
exist. The local mock server is not a substitute for staging Central acceptance.

## Deploy / update

Deploy from a reviewed immutable commit (not a developer's uncommitted tree):

```bash
git fetch origin
git checkout <reviewed-commit-or-release-tag>
uv sync --locked --extra dev
ENV_FILE=.env.staging make staging
```

Equivalent direct command:

```bash
ENV_FILE=.env.staging bash scripts/docker-staging.sh
```

The script validates settings without printing secret values, validates the
Compose model, builds both production images, runs `alembic upgrade head` as a
one-shot operation, starts the dedicated `nextgen-staging` Compose project and
waits for API readiness plus the web homepage. It is additive: it never runs
`down -v`, drops tables, resets data or removes database volumes. Keep one web
replica until the BFF refresh coordinator supports multiple replicas.

Check release state:

```bash
docker compose --project-name nextgen-staging --env-file .env.staging \
  -f docker/compose.production.yml ps

docker compose --project-name nextgen-staging --env-file .env.staging \
  -f docker/compose.production.yml exec -T api alembic current

curl --fail https://staging.nextgenforearth.org/api/health/ready
curl --fail https://staging.nextgenforearth.org/
```

The public readiness URL depends on ingress routing. If ingress exposes only
the web app, use the host-local API health check from the deploy script and
verify the browser-facing homepage through HTTPS. Do not publish the API port
or database port merely to make a health check convenient.

## Optional workers

Start dataset scanning only after private object storage and ClamAV are fully
configured and tested:

```bash
docker compose --project-name nextgen-staging --env-file .env.staging \
  -f docker/compose.production.yml --profile scanning up -d dataset-scanner
```

Start ODK sync only after a real staging Central connection is configured and
accepted:

```bash
docker compose --project-name nextgen-staging --env-file .env.staging \
  -f docker/compose.production.yml --profile odk up -d odk-sync
```

Never enable the worker against the local mock Central service from a publicly
reachable deployment.

## Rollback and recovery

1. Record the currently deployed image commit/tag and migration head before
   every release.
2. Take and verify a database backup before applying a migration.
3. If the new web/API release fails, redeploy the previous reviewed image
   commit using the same staging secret file. Do not automatically downgrade
   the database: migrations may be forward-only or may have changed data.
4. Restore a database backup only under an approved recovery decision, with
   writes stopped and the restore owner recording the recovery point.
5. Inspect `docker compose ... logs --tail=200 api web` and health state; never
   put secrets or personal learner data into issue reports.

## Staging acceptance before a founder session

- [ ] The deployment SHA/tag is recorded and matches the reviewed release.
- [ ] `alembic current` reports the expected migration head.
- [ ] API readiness and HTTPS web homepage succeed.
- [ ] Database is dedicated to staging; backup and restore have been tested.
- [ ] Owner/founder can sign in; a separate staff account can accept an invitation.
- [ ] Learner registration/application/approval is tested with synthetic accounts.
- [ ] CMS draft/review/independent approval/publication is tested; no unreviewed
      people, partner, publication or impact claims are public.
- [ ] Public pages contain only intentionally published data.
- [ ] Browser session cookies are HttpOnly/Secure and cross-origin mutations fail.
- [ ] No staging secrets, real safeguarding records or production learner data
      are present in the demo dataset.
- [ ] ODK is explicitly labelled simulator-only or separately accepted against
      a real staging Central project.
- [ ] Open defects, operational owners and rollback contact are documented.

A staging deployment is suitable for founder review only after the relevant
acceptance items are signed off. It is not production approval.
