# Environment setup and first-run operations

This guide defines one repeatable workflow for local development, deployed staging,
and production. The application remains tenant-aware, but **Next Gen For Earth is the
single provisioned organisation for the current product rollout**. Staff should not
be asked to create an organisation during normal onboarding.

## Operating model

- Keep organisation IDs on every organisation-owned record and keep tenant authorization
  enabled. Do not add a global tenant bypass or remove membership checks.
- Provision the canonical organisation once with the bootstrap operator account.
- Give the bootstrap account an active `admin` membership. It is the initial owner.
- Add staff through the existing invitation and acceptance workflow. Founder and
  executive invitations are owner-controlled by the API.
- Keep public directory profiles separate from login accounts. A person listed on the
  public website does not automatically need a portal login.
- Seed only verified, approved source data. Do not invent staff, partners, programmes,
  projects, research findings, or impact metrics.
- Use separate databases, credentials, JWT secrets, and storage buckets for local,
  staging, and production. Never copy production data into local development.

## 1. Clone and update the repository

Use the active integration branch until its pull request is merged:

```bash
git clone --branch feat/single-tenant-bootstrap-ops https://github.com/safuh/Stagingnextgenearth.git
cd Stagingnextgenearth
git pull --ff-only
```

For an existing checkout:

```bash
git status --short --branch
git fetch origin
git switch feat/single-tenant-bootstrap-ops
git pull --ff-only origin feat/single-tenant-bootstrap-ops
```

Do not discard uncommitted work to update the checkout. Resolve or commit it first.

## 2. Local development (Linux/macOS)

Requirements: Python 3.11 or newer, `uv`, Node.js compatible with the
Next.js project, npm, and Docker Compose (Docker or Podman Compose).

Install dependencies and configure the backend:

```bash
uv sync --locked --extra dev
cp .env.example .env
chmod 600 .env
```

For PostgreSQL/PostGIS, configure a dedicated local database. If local PostgreSQL
already uses port 5432, map the Compose service to 5433 and make the backend URL
use the same port:

```dotenv
POSTGRES_DB=nextgen
POSTGRES_USER=nextgen
POSTGRES_PASSWORD=REPLACE_WITH_A_UNIQUE_URL_SAFE_PASSWORD
POSTGRES_PORT=5433
DATABASE_URL=postgresql+asyncpg://nextgen:REPLACE_WITH_THE_SAME_PASSWORD@127.0.0.1:5433/nextgen
ENVIRONMENT=development
DEBUG=true
JWT_SECRET_KEY=REPLACE_WITH_A_UNIQUE_RANDOM_SECRET_AT_LEAST_32_CHARACTERS
```

Use the same password in both database settings. Do not put credentials in shell
history or commit `.env`. A password containing URL-reserved characters must be
URL-encoded in `DATABASE_URL`; a generated URL-safe password avoids that issue.

Start and verify PostGIS:

```bash
docker compose --env-file .env -p nextgen-local -f docker/compose.postgis.yml up -d
docker compose --env-file .env -p nextgen-local -f docker/compose.postgis.yml ps
docker compose --env-file .env -p nextgen-local -f docker/compose.postgis.yml exec postgres pg_isready
docker compose --env-file .env -p nextgen-local -f docker/compose.postgis.yml exec postgres psql -U nextgen -d nextgen -c "SELECT PostGIS_Full_Version();"
```

The database role is the configured `POSTGRES_USER`. Do not assume a `postgres`
superuser exists when `POSTGRES_USER` was set to another name. Changing
`POSTGRES_PASSWORD` after a named volume has already been initialised does not
change the role password; update the role inside PostgreSQL instead.

Apply schema migrations as an explicit operation:

```bash
uv run alembic upgrade head
uv run alembic current
```

Install and configure the frontend:

```bash
cd web
npm ci
cp .env.example .env.local
```

Set `BACKEND_API_URL=http://127.0.0.1:8000/api` in `web/.env.local`.
Run the backend from the repository root in one terminal:

```bash
make run
```

Run the frontend from `web/` in another:

```bash
npm run dev
```

Local URLs: frontend http://localhost:3000 and API docs
http://127.0.0.1:8000/docs.

## 3. Bootstrap the canonical organisation

The bootstrap command uses the public authentication and organisation APIs; it does
not write directly to database tables or bypass tenant checks.

Set the initial operator credentials in the environment (not in a committed file):

```bash
export BOOTSTRAP_ADMIN_IDENTIFIER='portal-owner@example.org'
export BOOTSTRAP_ADMIN_PASSWORD='USE_A_UNIQUE_STRONG_PASSWORD'
export BOOTSTRAP_ORGANIZATION_NAME='Next Gen For Earth'
export BOOTSTRAP_ORGANIZATION_SLUG='next-gen-for-earth'
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE='KE'
export BOOTSTRAP_API_URL='http://127.0.0.1:8000/api'
uv run python scripts/bootstrap_nextgen.py
```

The command registers the account if it does not exist, authenticates it, creates
the canonical organisation if it does not exist, and confirms the resulting
administrator membership. It is safe to re-run: an existing account and organisation
are reused. It will not reset an existing password or silently take ownership of an
organisation owned by another account.

Keep the bootstrap account credentials in your approved secret manager. Require
the operator to change the initial password after first sign-in. Do not use the
same credentials in local, staging, and production.

## 4. Populate staff, public people, and programmes

Create a private JSON manifest from verified organisation records. The manifest
format is documented in `scripts/bootstrap-manifest.example.json`. For each staff
account, provide a `password_env` key naming an environment variable; never place
the actual password in the JSON file. Use unique temporary passwords and distribute
them through a secure onboarding channel.

Run:

```bash
chmod 600 path/to/your-bootstrap-manifest.json
uv run python scripts/bootstrap_nextgen.py --manifest path/to/your-bootstrap-manifest.json
```

Staff accounts are registered if necessary, invited into the canonical organisation,
and invited users accept their own invitations. This preserves the existing account
and membership security model. Founder and executive roles can only be provisioned
by the organisation owner.

Directory entries are public-profile records, not login accounts. Programme records
are created as drafts unless the manifest explicitly requests activation. Review
directory visibility and CMS publication state in the portal before publishing.

The bootstrap utility is intentionally conservative: it creates missing records and
does not overwrite existing biographies, roles, programme descriptions, or passwords.
Make changes to existing records through the portal's audited administration workflows.

## 5. Staging environment

Staging must use a separate PostgreSQL/PostGIS database and a separate JWT secret.
For a VM/container staging deployment:

1. Pull the exact reviewed Git commit; do not deploy an unpinned moving branch.
2. Install dependencies from `uv.lock` and build the web application from
   `web/package-lock.json`.
3. Set `ENVIRONMENT=production`, `DEBUG=false`, a PostgreSQL
   `DATABASE_URL`, a unique `JWT_SECRET_KEY`, and the server-side
   `BACKEND_API_URL`.
4. Restrict database ingress to the API and operator networks.
5. Take a database backup before migrations.
6. Run `uv run alembic upgrade head` once as a release step, not in every API worker.
7. Start API and web services; verify `/api/health/live`,
   `/api/health/ready`, login, and public website feeds.
8. Run the bootstrap command against the staging API using staging-only credentials
   and a staging manifest. Verify the organisation, owner, staff, programmes and
   public directory before inviting testers.

## 6. Production environment

Production follows the same release procedure as staging, with stricter controls:

- Use a managed PostgreSQL 17/PostGIS database with automated backups and tested restore.
- Store credentials in the hosting provider's secret/environment settings.
- Restrict database access; do not publish the database port.
- Deploy an immutable reviewed commit and run migrations once before shifting traffic.
- Bootstrap the organisation once with the designated owner account.
- Do not load demo users, fake programme activity, sample research observations, or
  fabricated impact metrics into production.
- Use real, verified people and programme information, and review public visibility
  before publishing.
- Keep a documented recovery owner and rotate initial credentials after onboarding.

## 7. Render deployment (planned, not yet configured)

Render is the intended hosting target, but this repository is not yet configured
or deployed there. Before the first Render release, define separate Render services
for the FastAPI API and Next.js web application, plus a managed PostgreSQL instance
with PostGIS support. Confirm that the selected database plan/version supports the
PostGIS extension before relying on spatial migrations.

Expected service configuration:

- API build: `uv sync --locked --no-dev`
- API start: `uv run uvicorn stagingnextgenearth.app:create_app --factory --host 0.0.0.0 --port $PORT`
- Web build: `cd web && npm ci && npm run build`
- Web start: `cd web && npm run start -- --hostname 0.0.0.0 --port $PORT`
- Web server variable: `BACKEND_API_URL` pointing to the private API URL plus `/api`.
- API variables: `ENVIRONMENT=production`, `DEBUG=false`,
  `DATABASE_URL`, `JWT_SECRET_KEY`, token lifetimes and any required storage settings.

Render-specific health checks, private networking, build caching, and database URL
format must be verified against the actual Render service configuration before release.
Do not treat the commands above as evidence that Render has already been configured.

## 8. Release and smoke-test checklist

```bash
uv run ruff check .
uv run mypy src
uv run pytest -q
(cd web && npm ci && npm run typecheck && npm run lint && npm test && npm run build)
uv run alembic current
curl --fail --silent "$BOOTSTRAP_API_URL/health/ready"
```

Also verify login, logout, organisation membership, role restrictions, programme
creation, CMS moderation, public feeds, cross-tenant access denial, and database
backup/restore. A passing health endpoint alone is not a complete release test.

## Recovery rules

- Never use `docker compose down -v` on an environment containing data.
- Never remove PostgreSQL volumes as a password troubleshooting step.
- Do not downgrade migrations as an ad-hoc production repair.
- Restore backups into an isolated database for recovery rehearsals.
- Redact credentials, tokens, personal data, and database URLs from diagnostic output.
