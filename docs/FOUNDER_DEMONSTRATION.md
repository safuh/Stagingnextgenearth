# Founder demonstration and handover

## Demonstration objective

Demonstrate one coherent organisational platform: a public website backed by governed portal records, distinct access journeys for learners and organisation members, and an executive view that separates operational records from verified public claims.

## Suggested 20-minute run of show

1. **Public organisation website (3 min)**
   - Show published programmes, courses, approved people and partner records.
   - Open a programme detail page and show projects, learning opportunities and reported indicators.
   - Explain that public sections are projections of approved portal records; review drafts and unverified partner candidates remain private.

2. **Learner journey (4 min)**
   - Open `/learners`.
   - Optionally pre-create learner demo identities from the bootstrap manifest using a dedicated password environment variable per account.
   - The bootstrap submits applications to published courses but deliberately does not approve them or grant learner memberships.
   - Register a new learner account with a unique test email.
   - Apply to a published course.
   - Show the learner's own application status.
   - In the course administration workspace, approve the application and demonstrate that an active learner membership is created.
   - Sign in as the learner and show the protected curriculum, lessons, assessments, progress and certificate verification when configured.

3. **Staff and partner onboarding (4 min)**
   - Register an identity at `/staff/register`.
   - As an organisation administrator, invite the exact registered email and assign the approved role.
   - Share the generated invitation URL privately.
   - Sign in as the invited account and accept the invitation.
   - Show that role assignment happens only through an authorised membership operation, not through the public registration form.

4. **Programme and people operations (3 min)**
   - Show programme catalogue, delivery activities, volunteer allocations and attendance.
   - Distinguish public people-directory profiles from authenticated membership accounts.
   - Explain the volunteer safeguarding gate and approval process.

5. **Research, climate intelligence and ODK (4 min)**
   - Show research studies, proposal/protocol governance, dataset review and provenance.
   - Open Research → Configure ODK Central; show the encrypted connection summary, project form catalogue, explicit form mappings and recent sync history.
   - If no Central test project/account is available, demonstrate the loopback synthetic protocol simulator (`uv run python scripts/run_odk_mock_central.py --host 127.0.0.1 --port 8765 --page-size 1`) and explicitly label its two records as synthetic.
   - Demonstrate a real ODK Central connection and worker sync only when a non-production Central project and dedicated read-only account are configured; the simulator is not evidence of live Central acceptance.
   - Demonstrate NASA POWER, OpenAlex and climate ingestion only when the providers are configured and live data is available.
   - Distinguish imported observations from independently reviewed, safeguarded research evidence.

6. **Founder / executive overview and CMS (3 min)**
   - Open Administration → Executive overview.
   - Review membership, programme, study, course, partner and CMS pipeline counts.
   - Explain that these are portal record counts, not independently verified impact.
   - Show source URLs, editorial review, independent approval and publication controls.
   - Use **Print / save founder briefing** to create a meeting handout or PDF from the live snapshot.

## Evidence and presentation rules

- Use a dedicated demo organisation or test accounts; do not use real employee credentials or disclose private invitation URLs in a presentation.
- Never present seed data as independently verified implementation, active staff, signed partnerships, completed events or measured impact.
- Partner candidates remain unverified until the organisation records evidence and changes their verification state.
- CMS entries remain unpublished until an authorised reviewer verifies the source and approves publication. Authors cannot approve their own submissions.
- Research concepts remain concepts until protocol, ethics/safeguarding, investigators, timeline and approvals are established.
- If a provider integration is unavailable, state that it is configured but not currently returning live data; do not fabricate a result.
- Do not use production learner records for a demonstration.

## Go-live acceptance checklist

- [ ] Latest branch pulled and all database migrations applied without deleting database volumes.
- [ ] Backend test suite, Ruff, frontend lint and production build pass on the deployment target.
- [ ] PostGIS migration and spatial smoke tests pass against the deployment database.
- [ ] Owner account, MFA/credential policy, secrets and backups are configured for production.
- [ ] A real employee account has registered, been invited and accepted the invitation.
- [ ] A second authorised reviewer has independently reviewed and published a source-verified CMS entry.
- [ ] A learner has registered, applied to a published course, been approved and accessed protected learning content.
- [ ] Volunteer safeguarding and any required parent/guardian consent have been verified before approval.
- [ ] Partner records have been verified before public display.
- [ ] NASA POWER, OpenAlex and climate-provider credentials, quotas, provenance and failure handling are checked in the target environment.
- [ ] Local demo: simulator connection test succeeds, two synthetic fixture records sync across OData pages, duplicate handling is confirmed, and imported observations remain pending review.
- [ ] Production go-live: a separate real ODK Central connection test succeeds, mappings are verified against a non-production Central form, scheduled worker is running, pagination and duplicate handling are confirmed, and imported observations remain pending review.
- [ ] Public website, accessibility, mobile layout, privacy notices, security headers, logging and recovery procedures are reviewed.

The print action creates a snapshot of the current executive overview. It does not certify the underlying data or replace independent programme, finance, research, safeguarding or partner verification.

## Reproducible demo environment (operator runbook)

Use one dedicated local database or the dedicated staging database. Never seed
production. The canonical API bootstrap is idempotent and creates the owner,
organisation, source-attributed people/partners/programmes/content and any
manifest-declared demo users. It deliberately keeps people private, partners
unverified, CMS records in draft/review, and learner applications unapproved.

### Local Docker-backed API

```bash
# From the repository root; start only the local Postgres/PostGIS service.
docker compose -f docker/compose.yml up -d db
uv sync --locked --extra dev
# Match the local Compose database credentials; port is bound to loopback only.
export DATABASE_URL=postgresql+asyncpg://backbone:backbone@127.0.0.1:5432/backbone
uv run alembic upgrade head
make run
```

In another terminal, start the web app:

```bash
cd web
npm ci --no-audit --no-fund
npm run dev
```

Open `http://localhost:3000`. The web BFF uses its local development fallback
to reach `http://127.0.0.1:8000/api`.

After bootstrapping and seeding, run the read-only acceptance preflight. It checks API/database readiness, the founder's active administrator membership and actual ownership, organisation administration access, and the public CMS/programme response schemas. It does not change records.

```bash
export API_BASE_URL=http://127.0.0.1:8000/api
export WEB_BASE_URL=http://127.0.0.1:3000
export ORGANIZATION_SLUG=next-gen-for-earth-demo
read -rp "Founder email: " FOUNDER_IDENTIFIER
read -rsp "Founder password: " FOUNDER_PASSWORD
printf '\n'
export FOUNDER_IDENTIFIER FOUNDER_PASSWORD
uv run python scripts/verify_founder_demo.py
```

The preflight intentionally requires the authenticated account to be the
recorded organisation owner, not merely an administrator. Keep credentials in
environment variables and never paste them into tickets or logs.

### Create a dedicated demo owner and seed the catalogue

Use a unique test mailbox controlled by the demo operator and a strong,
throwaway password. Do not use a real employee password:

```bash
read -rp "Demo owner email: " BOOTSTRAP_ADMIN_IDENTIFIER
read -rsp "Demo owner password: " BOOTSTRAP_ADMIN_PASSWORD
printf '\n'
export BOOTSTRAP_ADMIN_IDENTIFIER BOOTSTRAP_ADMIN_PASSWORD
export BOOTSTRAP_API_URL=http://127.0.0.1:8000/api
export BOOTSTRAP_ORGANIZATION_NAME="Next Gen For Earth — Founder Demo"
export BOOTSTRAP_ORGANIZATION_SLUG=next-gen-for-earth-demo
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE=KE
uv run python scripts/bootstrap_nextgen.py
```

Run the richer idempotent catalogue seed against the same demo database after
the organisation exists:

```bash
uv run python scripts/seed_nextgen_demo.py \
  --organization-slug next-gen-for-earth-demo
```

The second command inserts website-sourced people, partner prospects, CMS
records and draft programmes directly into the selected organisation. It uses
the owner as the audit actor and must only be run against the dedicated demo
DB. It does not create user accounts, verify partners, approve content or
publish impact claims. Re-running it does not duplicate matching records.

To add demo employees, volunteers or learners, use a private copy of the
manifest and the `staff` / `learners` arrays documented in
[`STAFF_BOOTSTRAP.md`](../STAFF_BOOTSTRAP.md). Passwords belong in environment
variables named by each manifest entry, never in JSON or Git. Learner bootstrap
submits applications only; staff approval is a separate demonstration step.

### ODK synthetic protocol demonstration

In another terminal, start the loopback-only mock Central:

```bash
uv run python scripts/run_odk_mock_central.py \
  --host 127.0.0.1 --port 8765 --page-size 1
```

Configure the ODK integration in the portal using the local simulator details
in [`odk-central-integration.md`](operations/odk-central-integration.md).
The two fixture submissions are synthetic. Show the sync and duplicate
suppression, then show that observations remain pending independent review.
Do not describe this as live ODK Central acceptance.

### Reset policy

For repeatable demonstrations, prefer a fresh named demo database and rerun
migrations/bootstrap rather than deleting a developer's shared Docker volume.
Never run `docker compose down -v` on a database that contains work you need.
Keep a short record of the demo organisation slug, commit SHA, seed timestamp,
synthetic account aliases and acceptance results. Delete demo data only through
an explicit, reviewed database lifecycle procedure.

For the separate staging deployment procedure, use
[`staging-deployment.md`](operations/staging-deployment.md).
