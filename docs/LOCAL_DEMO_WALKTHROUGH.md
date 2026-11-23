# Local founder demonstration and hands-on test

This is the canonical local walkthrough for the Next Gen For Earth application. Use one checkout for the API, web application, migrations, bootstrap and demo data. Do not run the same service from multiple checkouts.

## 1. Which codebase is the real one?

All three directories below are separate Git clones of `https://github.com/safuh/Stagingnextgenearth.git`. They are not automatically synchronised with one another; edits, local databases, `.env` files, Python environments and running servers are independent.

| Directory | Snapshot | Guidance |
|---|---|---|
| `Stagingnextgenearth` | Older `feat/single-tenant-bootstrap-ops` checkout; 132 commits behind its remote at the time this guide was written, with untracked local files | Preserve it for now; do not run, reset or pull it as the demo source |
| `odk-m97` | Earlier M105 checkpoint | Historical comparison only |
| `odk-m106` | Current M114 development branch, `feat/membership-invitation-audit-m114` | **Use this checkout for all local testing and the founder presentation** |

The folders share a GitHub remote, not a live working tree or a shared database. Changes become available in another clone only after an explicit fetch/pull or checkout. Do not copy `.venv`, `node_modules`, `.env`, or database files between them.

## 2. Services and addresses

| Service | Local address | Purpose |
|---|---|---|
| Public website and portal | http://localhost:3000 | Browser interface |
| FastAPI | http://127.0.0.1:8000 | Application API |
| API documentation | http://127.0.0.1:8000/docs | Interactive API reference |
| API readiness | http://127.0.0.1:8000/api/health/ready | Database-backed readiness check |
| ODK simulator | http://127.0.0.1:8765/health | Synthetic ODK Central protocol endpoint |
| Demo PostgreSQL/PostGIS | `127.0.0.1:55432`, database `backbone` | Local demo data only |

Use `http://localhost:3000` consistently for the browser. Do not alternate between `localhost` and `127.0.0.1` for the web origin; the session BFF enforces same-origin requests. The API's server-side URL remains `http://127.0.0.1:8000/api`.

At the time this guide was prepared, the API and web app were responding and the demo database was at Alembic revision `0064_membership_invite_audit`. The database had zero users, organisations, memberships, programmes and CMS entries. **That is why a login attempt could not succeed: no account had been created yet. There is no built-in founder username or default password.**

## 3. Start or verify the local services

Open three terminal tabs. In each, use the canonical checkout:

```bash
cd /home/harry/AceCode/FastApiBackbone-CLI/odk-m106
source .venv/bin/activate
```

First check whether services are already running:

```bash
ss -ltnp | grep -E ':(3000|8000|8765|55432)\\b'
curl -fsS http://127.0.0.1:8000/api/health/ready
curl -fsS http://127.0.0.1:8765/health
```

If the database is stopped, start the existing local demo database container; do not create a second database with a different name:

```bash
podman start nextgen-founder-demo-db-1
# Docker users can use: docker start nextgen-founder-demo-db-1
```

Terminal 1 — API (only if port 8000 is not already listening):

```bash
cd /home/harry/AceCode/FastApiBackbone-CLI/odk-m106
source .venv/bin/activate
make run
```

Terminal 2 — web app (only if port 3000 is not already listening):

```bash
cd /home/harry/AceCode/FastApiBackbone-CLI/odk-m106/web
npm run dev
```

Run `npm ci` only if `web/node_modules` is absent or dependencies need reinstalling. Do not start a second server on an occupied port. If a port is occupied, identify the process with `ss -ltnp 'sport = :PORT'` before deciding whether to stop it.

Terminal 3 is for bootstrap, seeding and checks. Confirm the API readiness endpoint returns `status: ready` before continuing. If it does not, inspect the API terminal; do not try to log in against a web server whose API is unavailable.

## 4. Create the first local owner account

This is a one-time step for the empty demo database. Use an email address you control for the demonstration and a unique throwaway password of at least 12 characters. Enter the password at the hidden prompt; do not paste it into chat, a command, a manifest or Git.

```bash
cd /home/harry/AceCode/FastApiBackbone-CLI/odk-m106
source .venv/bin/activate

read -rp 'Demo owner email: ' BOOTSTRAP_ADMIN_IDENTIFIER
read -rsp 'Demo owner password: ' BOOTSTRAP_ADMIN_PASSWORD
printf '\\n'
export BOOTSTRAP_ADMIN_IDENTIFIER BOOTSTRAP_ADMIN_PASSWORD
export BOOTSTRAP_API_URL=http://127.0.0.1:8000/api
export BOOTSTRAP_ORGANIZATION_NAME='Next Gen For Earth — Founder Demo'
export BOOTSTRAP_ORGANIZATION_SLUG=next-gen-for-earth-demo
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE=KE

uv run python scripts/bootstrap_nextgen.py
```

Expected result includes `Canonical organisation ready` and `Bootstrap complete`. The bootstrap uses the public API, registers or reuses the owner identity, creates the organisation and confirms the owner's active administrator membership. It loads source-attributed candidate people, partners, programmes, research records and CMS content. It does not create staff accounts from the public directory, publish content, verify partner claims or approve research ethics.

If the command reports that the email is already registered, it attempts to authenticate with the password entered. Use the existing password for that account; bootstrap will not reset it. If the organisation slug already belongs to another owner, it refuses to take ownership automatically. Do not work around that protection by editing database ownership rows.

Optional additional idempotent demo catalogue seed:

```bash
uv run python scripts/seed_nextgen_demo.py --organization-slug next-gen-for-earth-demo
```

This enriches the demo catalogue. It is intended only for this dedicated local demo database.

## 5. Sign in and prove the account works

Open **http://localhost:3000/staff/login**.

- Email: the exact `BOOTSTRAP_ADMIN_IDENTIFIER` entered above.
- Password: the exact password entered above.
- Expected result: successful sign-in and redirect to `/workspace` because the owner has an active administrator membership.

The following URLs should load after sign-in:

- `/workspace` — organisation workspace overview
- `/workspace/administration` — administration area
- `/workspace/administration/people` — people directory
- `/workspace/administration/partners` — institutional partners
- `/workspace/administration/content` — CMS authoring/review
- `/workspace/programmes` — programme catalogue and operations
- `/workspace/learning-admin` — course administration
- `/workspace/research` — research workspace
- `/workspace/research/odk` — ODK Central configuration and sync history

If sign-in fails, check in this order:

1. `curl -fsS http://127.0.0.1:8000/api/health/ready` must succeed.
2. Confirm the API terminal has no database or JWT configuration errors.
3. Confirm you are using `http://localhost:3000` consistently, not switching hostnames mid-session.
4. Confirm the email and password are the same values used during bootstrap.
5. If bootstrap succeeded but login returns `401`, do not create a second account with a different spelling; inspect the API response and bootstrap output first.
6. If the account authenticates but reports no organisation membership, confirm the bootstrap command completed against the same database used by the API. The staff login page correctly refuses to grant workspace access to an identity without an invitation or active membership.

A public registration is not an owner bootstrap. Registering at `/staff/register` creates an identity only; it does not make that account a founder, administrator, employee or partner. Learners use `/learners` and receive no staff permissions through registration.

## 6. Hands-on acceptance walkthrough

Use this order for a repeatable 15–20 minute founder demonstration. Keep all demonstration records clearly labelled as test/demo data.

1. **Public website (2 min):** show the landing page, programme/research sections, staff sign-in and separate learner entry. Explain that only approved/published CMS content is intended for public display.
2. **Owner and administration (2 min):** sign in as the bootstrapped owner; show the workspace, people directory and organisation membership administration. Explain the distinction between a public profile and a login account.
3. **People and partners (2 min):** inspect imported source-attributed people and partner candidates. Demonstrate that candidates are not automatically verified or publicly published.
4. **Programmes and activities (3 min):** inspect the programme catalogue; create or update a clearly labelled demo programme and its operational records. Verify the change in the workspace.
5. **CMS workflow (2 min):** create a draft, submit it for review and demonstrate that publication is a separate reviewer action. Use a second authorised account for independent approval; an author must not approve their own item.
6. **Staff invitation (2 min):** invite a second test email with a least-privilege role. Register that exact email as an identity in a separate browser profile, then sign in and accept its invitation. Confirm its role-aware destination. Do not use the owner's credentials for this test.
7. **Learning (3 min):** create a demo course, modules and lessons; publish the course through the intended lifecycle. In a separate browser profile, register a learner at `/learners`, apply/enrol, then return as administrator to review and approve. Continue with lesson progress, assessment, attendance and certificate workflows where configured.
8. **Research and ODK (3 min):** show research records and climate intelligence. Configure the local ODK simulator at `http://127.0.0.1:8765`, project `22`, using the simulator-only credentials `odk-demo@example.test` / `local-demo-only`. Use this form mapping:

   ```json
   {
     "nextgen_climate_observation": {
       "observed_at": "observed_at",
       "variable": "measurement",
       "value": "value",
       "unit": "unit",
       "latitude": "latitude",
       "longitude": "longitude"
     }
   }
   ```

   Demonstrate form discovery, a test connection, polling and sync history. Label this as a synthetic protocol demonstration, not a live ODK Central acceptance test.
9. **Close (1 min):** show the audit trail and explain which records are drafts, pending approval, verified or published. Do not present seeded candidates or synthetic observations as completed organisational impact.

## 7. Pre-presentation checks

After bootstrap and seeding, run the read-only founder acceptance preflight:

```bash
export API_BASE_URL=http://127.0.0.1:8000/api
export WEB_BASE_URL=http://localhost:3000
export ORGANIZATION_SLUG=next-gen-for-earth-demo
read -rp 'Founder email: ' FOUNDER_IDENTIFIER
read -rsp 'Founder password: ' FOUNDER_PASSWORD
printf '\\n'
export FOUNDER_IDENTIFIER FOUNDER_PASSWORD
uv run python scripts/verify_founder_demo.py
```

The preflight must confirm API/database readiness, owner authentication, actual organisation ownership, active admin membership, organisation administration access and safe public CMS/programme response fields. It is read-only and never prints credentials or tokens.

Run backend checks before recording the presentation:

```bash
make lint
make typecheck
TMPDIR=/var/tmp uv run pytest -q --basetemp=/var/tmp/nextgen-demo-pytest
```

Frontend checks, when memory allows:

```bash
cd web
npm run lint
npm run typecheck
npm test
```

## 8. What this local demo does not prove

- The ODK simulator is not a real Central server or a live Central account acceptance test.
- Localhost is not staging or production. HTTPS, DNS, production secrets, backups, monitoring and deployment validation remain separate release work.
- Seeded website-derived entries are candidate records for review, not verified staff, signed partners, approved studies or proven impact.
- A successful owner login proves local identity and access; it does not by itself prove every module's full acceptance criteria.
