# Founder demo and staging acceptance

Use a dedicated staging environment with synthetic learner/staff accounts and
verified organisation content. Do not use production passwords, personal records,
safeguarding documents, or unreviewed impact claims in a pitch environment.

## 1. Release preflight

- [ ] Deploy an immutable reviewed commit; record the commit SHA and deployment time.
- [ ] Confirm a dedicated PostgreSQL 17/PostGIS database and separate staging secrets.
- [ ] Apply migrations explicitly and confirm `alembic current` reports the expected head.
- [ ] Verify API liveness/readiness and the public web homepage.
- [ ] Confirm HTTPS, CORS origins, JWT secret, object-storage settings and malware-scanning profile where enabled.
- [ ] Confirm a recent database backup and a tested restore procedure (see `docs/operations/database-backup-restore.md`).
- [ ] Enable the ODK profile only after a valid Fernet key and dedicated test Central account are configured.

## 2. Founder and organisation operations

- [ ] Sign in as the organisation owner/founder and confirm the organisation overview loads.
- [ ] Invite one executive, one administrator, one employee and one programme manager using separate accounts.
- [ ] Accept each invitation as the invited account; verify that pending invitations do not grant access.
- [ ] Confirm elevated roles are owner-controlled and that ordinary staff cannot grant themselves administrator, founder or executive access.
- [ ] Review the imported people directory. Keep unverified people private and do not equate a public profile with a portal account.
- [ ] Review institutional partners as private prospects; activate and publish only verified relationships.

## 3. Programmes, learning and youth participation

- [ ] Review the programme catalogue and create or edit a draft programme.
- [ ] Publish an approved programme and confirm its public description is reflected on the landing page.
- [ ] Create a course with modules and lessons, then publish it.
- [ ] Register a synthetic learner, submit an enrolment application and approve it as programme staff.
- [ ] Complete a lesson, submit a configured multiple-choice quiz and verify the server-calculated result.
- [ ] Submit an assignment and evaluate it as authorised staff.
- [ ] Record workshop attendance and assign a mentor using active same-organisation accounts.
- [ ] Issue a certificate, download its PDF and verify its public QR/code URL. Revoke a test certificate and confirm its download is denied.
- [ ] Submit a volunteer expression of interest and review the safeguarding/consent attestations before approval.

## 4. Research, climate intelligence and ODK

- [ ] Create a research project/study and verify protocol and ethics decisions are attributable and audited.
- [ ] Preview an OpenAlex record, explicitly select fields and import it; confirm provider provenance is retained.
- [ ] Request a bounded NASA POWER climate series and confirm the source, units and date range are visible.
- [ ] Configure a dedicated ODK Central test connection and test authentication/form discovery.
- [ ] Map only the intended climate fields; sync a small test form with known observations.
- [ ] Run the same sync again and confirm duplicates are not imported.
- [ ] Confirm ODK observations remain `pending` until the independent climate-review workflow approves them.
- [ ] Confirm sync run history, last-run state and errors are visible to authorised research managers; confirm credentials are never returned to the browser.

## 5. Funding management

- [ ] Register a funding opportunity with donor, deadline, expected amount, currency and stage.
- [ ] Create an award linked to the opportunity and record its restrictions, dates and reporting deadline.
- [ ] Allocate programme budget lines and confirm total allocations cannot exceed the award.
- [ ] Record a pledge, commitment and expenditure; confirm expenditure cannot exceed the budget line or award.
- [ ] Review the funding summary and download the private CSV report.
- [ ] Confirm only administrators, founders and executives can access the funding register.
- [ ] Confirm the workflow records financial plans and actuals only and does not process payments or move money.

## 6. CMS and public site

- [ ] Create a CMS draft, submit it for review, approve it and publish it.
- [ ] Confirm only approved/published content and explicitly public people/partners appear on the public site.
- [ ] Unpublish a test content item and verify it disappears from public responses.
- [ ] Review public programme, partner, research and impact descriptions for source attribution and factual accuracy.

## 7. Security and operational acceptance

- [ ] Verify learner accounts cannot access staff dashboards or other learners' records.
- [ ] Verify employee, researcher, volunteer, partner and administrator permissions match their assigned roles.
- [ ] Verify cross-organisation identifiers are rejected or concealed by the API.
- [ ] Verify session expiry, refresh, logout and authentication rate limiting.
- [ ] Verify no API response, browser bundle or log contains passwords, ODK credentials, JWT secrets or storage credentials.
- [ ] Confirm error monitoring, log retention, backup schedule, restore owner and incident contact.
- [ ] Record unresolved defects with severity, owner and target date; do not label a critical/high security or data-integrity defect as accepted.

## 8. Go/no-go evidence pack

The founder demo is accepted when the team can provide:

1. Reviewed commit SHA and deployment record.
2. Migration head, health-check and automated test evidence.
3. Screenshots or a short recording of the founder, programme, learner, research/ODK and public CMS journeys.
4. A successful test ODK sync plus duplicate/idempotency evidence and climate-review state.
5. A funding report showing budgets and expenditure without payment processing.
6. Role-boundary checks and backup/restore evidence.
7. A defect register and named operational owners.

A successful demo is not production approval by itself. Production launch additionally
requires a real ODK Central acceptance run, verified backups/restore, production secrets,
monitoring/alerting, HTTPS and CORS review, and sign-off from the organisation's
operational and data-protection owners.

## Funding-management boundary

The funding workspace is an internal register for opportunities, awards, budgets,
pledges, commitments, expenditure and reporting. It is not an accounting system or
payment service: **no payment gateway, checkout, card capture, bank integration,
fund transfers, or payment-provider API** is included. Pledges are not evidence of
cleared funds, and manually entered expenditure must be reconciled under the
organisation's separate finance controls.
