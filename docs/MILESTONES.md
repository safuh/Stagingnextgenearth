# NextGen for Earth Platform — Delivery Milestones

A checkbox means the acceptance criterion has been implemented and verified.
Do not mark work complete solely because code has been written.

## Product scope

Build a complete organisational digital platform with four dedicated portal
experiences:

1. researchers;
2. youth and volunteers;
3. administrators; and
4. institutional partners.

Research and climate intelligence are the leading product priority, supported by
programme/project management, learning and mentorship, community operations,
environmental monitoring, and institutional reporting.

The platform is a modular monolith initially. FastAPI owns the application API,
PostgreSQL/PostGIS owns transactional and geospatial persistence, and Next.js
provides the public website and authenticated portal experiences.

## Foundation — inherited and retained

**Status: inherited from the backend foundation; previously verified.**

- [x] FastAPI application factory and Pydantic Settings.
- [x] Async SQLAlchemy 2.x persistence and Alembic.
- [x] PostgreSQL and SQLite development support.
- [x] Optional password/JWT authentication primitives and refresh-token rotation.
- [x] Docker and explicit migration deployment contract.
- [x] Existing lint, type-check and test workflows.

These foundation checks must continue passing as product code is added.

## M1 — Product data foundation

**Status: implemented on feature branch; CI verification passed on Python 3.11, 3.12 and 3.13.**

- [x] Organisation and tenant ownership model.
- [x] Organisation-scoped memberships and initial portal role vocabulary.
- [x] Programme lifecycle model.
- [x] Project model with programme linkage and geography.
- [x] Research study model with lead researcher and ethics reference.
- [x] Climate observation model with source, unit, timestamp, coordinates and quality status.
- [x] Alembic migration for the initial product domain.
- [x] Model persistence test.
- [x] Run lint, type checks and full tests across Python 3.11, 3.12 and 3.13.
- [x] Review tenant-boundary and role-policy design before exposing endpoints.
- [x] Verify migration upgrade/downgrade against PostgreSQL (CI integration test runs upgrade, schema assertions, downgrade to base and re-upgrade against PostgreSQL 17).

## M2 — Identity, access control and organisation workflows

- [x] Connect login/registration composition to explicit runtime JWT settings.
- [x] Access-token authentication dependency with persisted-account validation.
- [x] Organisation-scoped membership checks and initial programme role enforcement.
- [x] Organisation creation with atomic creator-to-admin membership.
- [x] Membership-scoped organisation, programme and project discovery.
- [x] Existing-account membership invitation and invitee-only acceptance.
- [x] Cross-organisation access denial and initial role-escalation tests.
- [x] Administrator-controlled membership role changes and suspension, with owner and last-admin safeguards.
- [x] Organisation ownership transfer with atomic owner/admin hand-off and former-owner access retention.
- [x] Append-only organisation audit events for membership role/status changes and ownership transfers.
- [ ] Account lifecycle controls, broader security audit coverage and rate limiting/abuse protection.
- [ ] Rate limiting and abuse protection at the application or edge.
- [x] Initial security tests for cross-organisation access and role escalation.

## M3 — Programme and project operations

- [x] Programme and project APIs with explicit tenant-scoped persistence, role checks and validated parent relationships; service/repository extraction remains a refactoring opportunity.
- [x] Activities, deliverables, volunteer allocations and activity lifecycle transitions.
- [x] Programme goals, milestone checkpoints and general assignments with tenant-scoped visibility, active-member assignment, and guarded lifecycle transitions.
- [x] Volunteer and ambassador applications, approval and activity allocation.
- [x] Aggregate school, community, youth-group and institutional participation records (no child-level PII).
- [x] HTTPS evidence-reference submission and manager approval/revision workflow for programme deliverables; private file upload attachments remain a follow-on.
- [x] Programme indicator definitions, append-only period measurements and latest-value progress reporting.

## M4 — Research workspace

- [x] Initial tenant-scoped study creation and discovery endpoints.
- [x] Initial tenant-scoped research dataset registry with metadata and data dictionaries.
- [x] Dataset access classifications and owner/admin visibility for restricted metadata.
- [x] Dataset submission and independent approval/rejection workflow with audit fields.
- [x] Owner correction and resubmission workflow for rejected datasets.
- [x] Append-only dataset review history retained across resubmissions.
- [x] Researcher profiles with private-by-default visibility and organisation-scoped sharing.
- [x] Study collaborator invitations, acceptance, revocation and role-scoped dataset access.
- [x] Study proposal submission, independent review decisions and append-only review history.
- [x] Proposal revision lineage with immutable prior versions and independent review of resubmissions.
- [x] Study milestones with active-member assignments, due dates, lifecycle states and progress tracking.
- [x] Append-only milestone change history recording actors, changed fields and before/after values.
- [x] Versioned research protocols and independent protocol review.
- [x] Append-only ethics committee decisions linked to approved protocol versions.
- [x] Dataset registry, metadata, data dictionaries and access classifications.
- [x] Study publication registry with validated DOI, ORCID and OpenAlex identifiers.
- [x] OpenAlex metadata lookup preview with bounded HTTP requests and identifier validation.
- [x] Explicit OpenAlex import with append-only provider provenance and metadata snapshot hash.
- [x] Controlled publication metadata refresh with field-level preview, explicit selection and protection for researcher-edited values.
- [x] Private object-storage adapter, constrained upload intents and authorised download grants.
- [x] Dataset file-version metadata schema with storage-key uniqueness, size constraints and scan/status state.
- [x] Optional ClamAV INSTREAM scanning; files remain quarantined unless a clean verdict is returned.
- [x] Trusted SHA-256 calculation from stored object bytes and clean/rejected state transition.
- [x] Bounded database-polled scanner worker with row locking, per-file commits and retry-safe quarantine on infrastructure failures.
- [x] Streaming object-storage reads and chunked ClamAV INSTREAM scanning with incremental SHA-256.
- [x] Executable scanner worker process with configurable polling and batch size.
- [x] Dedicated worker container/deployment manifest and production operational runbook (production Compose profiles validated in CI; operational runbook added).
- [x] Dataset file download access audit events.
- [x] Research exports and reproducible analysis hand-off.

## M5 — Climate and geospatial intelligence

- [x] PostGIS deployment and spatial migrations (PostgreSQL 17/PostGIS 3.5, geometry backfill, coordinate-sync trigger and GiST index; migration integration tests pass).
- [x] Provider-neutral climate ingestion contract, point/area request validation and provenance tracking.
- [x] NASA POWER daily point adapter for precipitation and 2 m air temperature, with UTC normalization and missing-value filtering.
- [x] CHIRPS v3 daily GeoTIFF adapter for point and bounding-box cell extraction, with variant, date-label, licence and raster provenance.
- [ ] Copernicus climate-data adapters.
- [ ] Administrative boundaries and geocoding strategy.
- [x] Spatial and temporal query APIs (tenant-scoped WGS84 bounding-box and time filters with bounded pagination).
- [x] Initial independent review workflow for field-observation quality status.
- [ ] Quality assurance, missing-data handling and unit normalisation (conservative conversions and broad-range screening are integrated into provider persistence with original-value provenance; tenant-scoped status/variable summaries, bounded flagged-observation reports and daily station coverage reports are implemented; coverage uses an explicit report-only/no-imputation policy; descriptive statistics preserve missingness; dashboard presentation and configurable domain-specific thresholds remain).
- [ ] Research-grade statistical and geospatial analysis pipelines (tested descriptive statistics primitive, tenant-scoped bounded unit-grouped analysis API, spatial bounding-box query, screening-flag report and station coverage report with interactive workspace panels implemented; inferential methods, spatial interpolation and spatial/temporal dependence methods remain).
- [x] Interactive tenant-scoped climate workspace for descriptive verified/pending analysis, WGS84 bounding-box observation queries, bounded screening-flag review and station daily-coverage reports, with unit-separated statistics and explicit scan-limit/no-imputation/provisional-data messaging.
- [ ] Uncertainty, model limitations and data lineage shown in outputs.

## M6 — Public website and four portals

- [x] Responsive Next.js public landing page, four portal entry points, API-backed sign-in and authenticated organisation workspace with server-filtered membership discovery, programme listing and published-course listing.
- [x] Learner course detail, ordered module/lesson curriculum, course application, lesson completion and progress tracking.
- [x] Learner assessment instructions and submission workflow, gated by approved enrolment.
- [x] Staff learning operations workspace for course/module/lesson authoring, publishing, application decisions, assessment creation/evaluation, mentorship assignment and attendance recording/reporting.
- [x] Researcher portal foundations (organisation-scoped study and dataset registry, metadata correction, independent review, file-version upload/scanning, and interactive descriptive, spatial-query, screening and station-coverage climate workflows; basemap visualisation and inferential workflows remain).
- [x] Youth and volunteer portal foundations: personal dashboard, caller-scoped application/allocation history, and volunteer/ambassador programme applications for active youth-volunteer members (manager approval remains tenant- and role-scoped).
- [x] Administrator portal foundations: tenant-scoped membership directory, role/status controls, invitation creation, ownership transfer and governance audit history. Production BFF session handling and broader organisation settings remain.
- [x] Institutional partner portal foundation: read-only programme indicator and privacy-filtered aggregate participation reporting; donor document exchange, grant/budget workflows and report exports remain.
- [x] Shared design system, responsive layouts and accessible navigation.
- [x] Caller-scoped membership-role endpoint and role-aware workspace navigation (server API remains the authorization boundary).
- [x] Core researcher, youth/volunteer, administrator and institutional-partner dashboards with role-aware navigation and their primary MVP workflows; advanced organisation settings, donor/grant operations and deeper researcher analysis remain.
- [x] Typed API client, authenticated requests, same-origin BFF with HttpOnly access/refresh cookies, refresh rotation, session restoration and sign-out, plus user-visible loading/error states.
- [x] Separate learner self-registration and staff/partner identity registration journeys on the shared authentication service; public registration never grants organisation roles.
- [x] Public learner course applications without pre-existing membership, with approval-created learner membership and caller-scoped application status.
- [x] Public organisation identity endpoint so learner application history loads even when no course is currently published.
- [x] Staff and partner invitation acceptance bound to the invited account; staff membership alone does not grant access to learner curriculum without an approved enrollment.
- [x] Authenticated self-service password change with current-password verification, Argon2 rehashing, and revocation of all outstanding refresh sessions; immediate access-JWT revocation via a persisted password-change timestamp and high-resolution issuance claim; verified email recovery remains an explicit launch follow-up.

## M7 — Organisation directory, integrations and organisational intelligence

**Implemented on the feature branch; full CI and local PostgreSQL verification remain pending.**

- [x] Independent organisation-person profiles, separate from portal login accounts.
- [x] Multiple concurrent positions and person classifications, including founder.
- [x] Tenant-scoped directory create/list/update and audit-history APIs.
- [x] Pending/private defaults, explicit verification and publication controls.
- [x] Public people feed restricted to active, verified, explicitly public profiles.
- [x] Directory administration UI for creating, editing, reviewing, publishing and archiving profiles.
- [x] Regression tests for moderation, non-admin denial, tenant isolation and audit events.
- [x] Idempotent website seed loader for people, partners, four programme records, four programme areas, three training tracks, fundraising initiatives, research areas, impact claims and all 12 currently listed publications.
- [x] Founder and executive organisation roles with administration access; only the organisation owner can grant elevated roles.
- [x] Existing-account employee and volunteer membership invitation with acceptance before activation.
- [x] Institutional partner registry, verification, visibility controls and programme relationships.
- [x] Public CMS with draft, review, approved, published and archived transitions plus approval provenance.
- [x] Public partner and CMS feeds use reduced schemas that omit moderation and internal source metadata.
- [x] Public volunteer/ambassador expression-of-interest flow and administration review queue.
- [x] Volunteer approval requires a recorded safeguarding and any required guardian-consent confirmation.
- [x] New-candidate employee application workflow, including candidate status history,
      withdrawal and secure employee onboarding after independent approval.
- [ ] Automated invitation notifications.
- [x] Append-only partner/CMS audit-event history with tenant-scoped admin read endpoints; partner-contact consent workflows remain.
- [ ] KoboToolbox/ODK field data integration.
- [ ] Email and calendar notifications.
- [ ] Zoom/meeting integration where required.
- [ ] M-Pesa and approved international donation providers.
- [ ] Grant, budget and donor reporting.
- [ ] Impact verification and indicator dashboards.
- [ ] CSV/XLSX/PDF exports with access controls.

## M8 — Production readiness

- [x] PostgreSQL/PostGIS integration and migration CI (PostgreSQL 17/PostGIS 3.5 service; migration upgrade, schema assertions, downgrade and re-upgrade are exercised).
- [ ] API integration suite and frontend BFF policy unit tests run in CI; browser end-to-end coverage and broader interaction tests remain.
- [ ] Security review, privacy impact assessment and safeguarding review.
- [x] Documented PostgreSQL logical backup procedure, archive validation, checksum and isolated restore-drill procedure; scheduled/off-site execution, object-storage recovery, retention approval and a successful production-like restore drill remain pending.
- [ ] Observability, alerting and operational runbooks.
- [ ] Deployment environments, secrets management and disaster recovery.
- [ ] Stakeholder acceptance testing with representative portal users.

## Architectural constraints

- Keep a modular monolith until independently scaling or deploying a module is justified.
- Every tenant-owned record must be authorised by organisation membership in the backend.
- Frontend visibility is not an access-control boundary.
- Do not store participant-level health or child data in public datasets.
- Treat climate observations as provenance-bearing measurements; ingestion does not imply verification.
- Do not claim environmental outcomes from activity counts alone.
- Run migrations as explicit release operations, never in every API worker.

### Dataset file storage increment

- [x] S3-compatible private storage adapter with constrained, expiring upload forms.
- [x] Tenant- and owner-scoped upload-intent and completion endpoints.
- [x] Verify uploaded object size and media type against the upload intent.
- [x] Quarantine accepted uploads; file metadata endpoints do not disclose object keys.
- [x] Optional ClamAV scanner integration with fail-closed quarantine on scanner errors.
- [x] Trusted SHA-256 calculation from stored bytes and clean/rejected state transition.
- [x] Database-polled asynchronous scanning worker for quarantined file versions.
- [x] Streaming worker transport and incremental file hashing.
- [x] Standalone scanner process entry point.
- [x] Dedicated worker deployment manifest and production operational runbook (production Compose profiles validated in CI; operational runbook added).
- [x] Five-minute authorised download URLs restricted to clean files and permitted organisation members.
- [x] Append-only audit event for each download URL issuance.

### M4 reproducible analysis hand-off

- [x] Approved-dataset export manifests with stable SHA-256 fingerprints.
- [x] Immutable analysis-run provenance for exact clean input versions, software,
      configuration, parameters, random seed and output checksum metadata.
- [x] Regression tests for export manifests and analysis-run lineage.

### Learning management MVP

- [x] Tenant-scoped courses, modules, lessons and publish lifecycle.
- [x] Learner applications, approval and registration.
- [x] Public learner account registration, published-course application, approval-created membership, and approved-enrollment gates on curriculum, assessments, resources and progress.
- [x] Assessment definitions, submissions and staff evaluation.
- [x] Mentor assignments, workshop attendance and learning resource metadata.
- [x] Lesson completion, assessment-derived progress and verifiable certificates.
- [x] Staff-only, tenant-scoped enrollment queue, assessment catalogue/submission review, mentorship and attendance reporting APIs; assessment configuration remains withheld from learner responses.
- [x] Staff learning operations UI for course authoring, enrollment decisions, assessment evaluation, mentorship assignment and attendance recording, using an authorised minimal member directory rather than free-form identity entry.
- [x] Institutional-partner portal backed by a dedicated role-enforced reporting API, tenant-scoped indicator summaries and minimum-cohort suppression.
- [ ] Automated quiz execution, learner notifications, certificate PDF rendering,
      safeguarding/guardian consent and dedicated role-specific portal dashboards.
- [x] Learner-owned mentorship and attendance history endpoints and workspace panels (identity is derived from the authenticated principal and records are tenant-scoped).


### M72 — Regression coverage for all adverse ethics outcomes

- [x] Exercise both `revisions_required` and `rejected` committee decisions against an active study.
- [x] Verify each adverse outcome pauses the study and records the matching decision in the governance audit trail.
- [x] Keep the same lifecycle setup and assertions parameterised to prevent decision-path drift.


### M73 — Auditable ethics clearance for study activation

- [x] Record the exact approved protocol version used to authorise study activation or resumption.
- [x] Include the ethics review event, independent reviewer, decision and committee reference in the lifecycle audit event.
- [x] Verify that adverse ethics decisions require a subsequent affirmative committee decision before a paused study can resume.


### M74 — Reject new ethics decisions for superseded protocols

- [x] Require committee decisions to reference the study's latest protocol version.
- [x] Reject stale-version ethics submissions with HTTP 409 while retaining historical decisions for audit.
- [x] Add lifecycle regression coverage proving an earlier approved version cannot receive a new decision after amendment.


### M75 — Research ethics and protocol oversight snapshot

- [x] Add a leadership-only, tenant-scoped research governance overview endpoint.
- [x] Summarise the latest protocol version, independent protocol decision, current-version ethics decision, reviewer and committee reference without exposing review notes.
- [x] Distinguish pending protocol review, required ethics clearance, adverse ethics outcomes and studies paused pending committee clearance.
- [x] Integrate governance indicators and per-study status into the founder/executive overview.
- [x] Keep superseded ethics decisions historical; they never count as current clearance.


### M76 — Exportable research governance oversight

- [x] Add a leadership-only CSV export of the latest protocol and ethics clearance snapshot.
- [x] Include study status, attention state, protocol review, ethics decision, reviewer and committee reference.
- [x] Apply spreadsheet formula-injection protection, UTF-8 BOM, bounded output, no-store caching and truncation metadata.
- [x] Add an export action to the founder/executive overview.
- [x] Verify role restrictions and export response metadata in integration tests.


## M77 — Enforce study-level evidence ledger access

- Require an effective study role before returning the study evidence ledger or its CSV export; organisation membership alone is insufficient.
- Keep restricted dataset metadata behind the same effective study-membership boundary used by the dataset registry.
- Keep analysis provenance linked only to datasets visible in the caller's evidence inventory.
- Add regression coverage for denied study access on both JSON and CSV routes.


## M78 — Research evidence workspace request isolation

- Guard evidence-ledger loads and CSV downloads against stale responses after organisation or study selection changes.
- Prevent older concurrent requests from overwriting a newer ledger or triggering a download for a previously selected study.
- Reset in-flight evidence workspace state when the organisation context changes.


## M79 — Candidate employment application self-service

- [x] Let authenticated candidates view their own application history without exposing applicant identifiers.
- [x] Allow candidates to withdraw only their own pending application; preserve the review record.
- [x] Permit a fresh application after withdrawal or rejection while enforcing one pending application per candidate and organisation.
- [x] Add a public careers-page flow for sign-in, application status, withdrawal and history.
- [x] Cover tenant ownership, duplicate submissions, withdrawal and resubmission in API tests.


## M80 — Automated learning quiz execution

- [x] Validate bounded multiple-choice quiz configuration, unique question/option identifiers and answer-key integrity.
- [x] Expose learner-safe quiz prompts and options without returning correct answers.
- [x] Enforce approved enrolment, published-course access, exact answer coverage and assessment deadlines.
- [x] Score weighted responses server-side and persist the immutable learner attempt result.
- [x] Prevent generic submission and manual staff re-scoring from bypassing automated quiz rules.
- [x] Cover answer-key secrecy, malformed answers, weighted scoring, pass thresholds and re-scoring denial.

## M81 — Authentication abuse controls

- [x] Add configurable fixed-window limits for login, registration, refresh and logout.
- [x] Return generic 429 responses with retry guidance and rate-limit headers.
- [x] Bound in-process client tracking and avoid trusting spoofable forwarding headers.
- [x] Add regression coverage for threshold enforcement and authentication no-cache headers.
- [x] Document the single-process limitation and mandatory shared ingress controls for production replicas.


## M82 — Downloadable verifiable learning certificates

- [x] Generate landscape A4 PDF certificates with course, organisation, issue date and credential number.
- [x] Include a QR code and public verification URL, configurable through `PUBLIC_BASE_URL`.
- [x] Restrict downloads to the learner who earned the credential or authorised learning managers.
- [x] Deny downloads for revoked certificates and return private no-store PDF responses.
- [x] Surface certificate download links in the learner classroom and support QR deep-link verification.
- [x] Cover PDF generation, ownership, manager access, revoked credentials and progress metadata.


## M83 — ODK Central field-data ingestion bridge

- Added a tenant-authorised ODK Central JSON import endpoint with explicit field mapping and a 100-submission batch bound.
- Added idempotency on organisation + form + ODK instance ID, with duplicate counts.
- Validates timezone-aware timestamps, finite measurements, coordinate ranges, and optional same-tenant project/study links.
- Imported records enter the climate evidence ledger as pending; independent review remains mandatory.
- Raw survey payloads are not retained; only mapped scientific fields and source identifiers are stored.
- Added a tenant-scoped ODK integration status endpoint and operational mapping documentation.
- This is the ingestion bridge, not yet a background ODK Central poller/webhook subscription; credentials and pagination belong in a trusted worker.

## M84 — Secure ODK Central connections and automated synchronisation

- Added an organisation-scoped Central connection record with encrypted-at-rest credentials, project ID, enablement and per-form mappings.
- Added admin/founder/executive connection configuration, metadata-only retrieval, connection testing, form discovery and revocation endpoints.
- Added a dedicated Fernet encryption key setting; credentials are never returned to clients.
- Added the scheduled ODK Central worker using Central session authentication and OData submission feeds.
- Added same-origin pagination validation, bounded page size and per-form polling limits.
- Added durable sync-run history, last-run status, persisted per-form continuation cursors and duplicate-safe climate-evidence imports.
- Added local and production Compose worker profiles and operating instructions. Imported records remain pending independent climate review.
- Operate one worker replica until distributed scheduling and operational alerting are established.

## M85 — ODK field-operations acceptance and reliability (in progress)

- Validate against a dedicated ODK Central test project with representative forms, submissions, pagination and credential rotation.
- [x] Add operational alerts for repeated sync failures, stale cursors and disabled/expired Central accounts.
- [x] Add a transactional key-rotation procedure that preserves/re-encrypts existing connection credentials.
- Keep imported observations pending until the independent climate-review workflow approves them.

## M86 — Staging and release readiness hardening (in progress)

- Added a non-destructive Docker smoke test using an isolated Compose project, PostgreSQL 17/PostGIS, and a configurable host port; it never removes database volumes.
- Added production environment validation for HTTPS, PostgreSQL, non-placeholder JWT/database secrets, and valid ODK Fernet keys when the ODK profile is enabled.
- Added regression tests for valid and invalid production environment configurations.
- Updated the production deployment script to validate the exact environment file, check Compose interpolation, apply migrations once and report service logs on failed readiness.
- Added founder demo and staging acceptance guidance covering governance, learning, ODK, climate, CMS, funding and security.
- Verified locally: backend suite 246 passed / 4 skipped; ODK and production-environment regression set 9 passed; Ruff and Mypy passed.
- Verified locally: frontend typecheck, ESLint and 5 unit tests passed; Next.js production build generated all 25 static pages and completed standalone tracing.
- Verified local, production, ODK and scanning Compose configurations; the ODK profile activates `odk-sync`.
- Verified the Docker smoke against PostgreSQL 17/PostGIS: API and database containers started, migrations `0001` through `0060` applied, and liveness/readiness both returned HTTP 200. Containers/network were removed; the named smoke database volume was retained.
- Remaining production acceptance: a real ODK Central test-project sync and credential/key-rotation rehearsal, verified backup/restore, production monitoring/alerting, HTTPS/CORS review and data-protection/operational sign-off.
- Do not declare production launch-ready until the remaining operational prerequisites are evidenced.


## M87 — Funding and grant management (implemented; local verification passed)

- [x] Add tenant-scoped funding opportunities and grant/award records with donor/funder details.
- [x] Track budget lines, pledges, commitments, expenditure, restrictions and reporting deadlines.
- [x] Enforce award/budget ceilings, tenant-safe references, administrator-only access and append-only audit events.
- [x] Provide per-award funding summaries and formula-safe private CSV export without cross-currency aggregation.
- [x] Add an administrator funding workspace for opportunity/award creation, budget allocation and ledger entry.
- [x] Explicitly exclude payment processing, checkout, card capture, bank integrations, transfers and payment-provider APIs.
- [x] Backend suite: 247 passed, 4 skipped; funding-specific regression rerun after audit-action correction.
- [x] Ruff and Mypy passed (87 source files); `git diff --check` passed.
- [x] Frontend typecheck, ESLint and 5 unit tests passed; Next.js production build generated all 26 routes/pages.
- [x] PostgreSQL 17/PostGIS Docker smoke passed: API liveness/readiness returned HTTP 200 and migration head reached `0061_funding_register`.
- [x] Migration rollback from `0061_funding_register` to `0060_odk_form_cursors` and re-upgrade to `0061_funding_register` both succeeded.
- Remaining external acceptance: validate funding workflows with the founder/finance owner, real ODK Central test-project sync, production backup/restore, monitoring/alerting, HTTPS/CORS review and data-protection sign-off.


## M88 — ODK operational reliability and credential rotation (implemented; external acceptance pending)

- [x] Add a manager-only ODK operations endpoint for stale workers/cursors, repeated failures, disabled connections and Central 401/403 access failures.
- [x] Classify Central HTTP failures without persisting response bodies, credentials, request URLs or submission contents.
- [x] Surface actionable operational alerts in the ODK research workspace.
- [x] Add transactional Fernet key rotation with dry-run verification and all-or-nothing rollback on undecryptable credentials.
- [x] Document local and production key-rotation sequencing, worker shutdown, backup and post-rotation verification.
- [x] ODK regression set: 12 passed; the strengthened all-or-nothing key-rotation tests re-ran separately (3 passed).
- [x] Ruff and Mypy passed (88 source files); `git diff --check` passed.
- [x] Frontend typecheck, ESLint and 5 unit tests passed; Next.js production build generated all 26 routes/pages.
- [ ] Validate form discovery, a real submission sync, pagination recovery, duplicate handling and credential rotation against the organisation's dedicated ODK Central test project.
- [ ] Confirm staging alert visibility and agree an external notification/incident owner.


## M93 — Local ODK Central without a work mailbox (implemented; live execution pending)

- [x] Add a reproducible helper to clone and configure the official ODK Central stable stack locally with self-signed TLS and non-conflicting host ports.
- [x] Add CLI-based local administrator bootstrap using the reserved `@example.test` login; the documented Central CLI flow sets the password directly and does not require an invitation or password-reset mailbox.
- [x] Add an explicit local-only TLS verification override for self-signed Central; reject insecure TLS configuration in production and reject the override for non-local Central hostnames.
- [x] Add CI shell syntax checks and regression tests for local-only TLS policy.
- [ ] Run the Central stack on the development workstation, create the local project and synthetic form, and validate login, project discovery, OData pagination and one full NextGen sync.
- [ ] Keep hosted/staging Central acceptance separate; it still requires a real domain, trusted TLS and a real operational mailbox for account verification and recovery.

## M94 — Reproducible ODK climate-observation demo (assets implemented; live Central acceptance pending)

- [x] Add a Central-uploadable XLSForm with climate variable, numeric value/unit, timestamp, decimal WGS84 coordinates and non-personal site code.
- [x] Add synthetic OData submission fixtures aligned to the worker field contract and ODK __id identifier.
- [x] Document local project creation, draft preview/publication, least-privilege integration identity, field mapping, sync, duplicate suppression, pending review and credential revocation.
- [x] Add an asset validator and execute it in the operations-scripts CI job.
- [ ] Run local Central, upload and publish the form, submit synthetic records, and verify full NextGen sync and second-run idempotency.
- [ ] Keep hosted/staging acceptance separate until trusted TLS, operational email and a dedicated non-production Central project are available.


## M95 — ODK row-level validation and durable import diagnostics

- [x] Validate each ODK submission in an isolated database savepoint so malformed rows do not roll back valid neighbours.
- [x] Validate timezone-aware ISO timestamps, finite numeric readings, WGS84 coordinate bounds, and organisation-scoped project/study mappings.
- [x] Keep raw submission content and credential material out of diagnostic summaries.
- [x] Persist rejected-row counts in ODK sync history and expose them in the research ODK workspace.
- [x] Test mixed valid/invalid pages, cursor continuation, and replay deduplication.
- [ ] Complete the full ODK integration regression suite and GitHub CI matrix.
- [ ] Verify the same behaviour against a running local ODK Central project; Docker image availability and live Central acceptance remain external prerequisites.

## M96 — ODK source revision and deletion provenance

- [x] Capture ODK Central `__system.updatedAt`, `reviewState` and `deletedAt` metadata on imported climate observations without storing raw submission payloads.
- [x] Detect changed source revisions on replay and flag them for reviewer reconciliation instead of overwriting scientific measurements or existing human verification decisions.
- [x] Preserve source-deletion evidence and mark it as requiring reviewer reconciliation; never silently delete the NextGen observation.
- [x] Add regression coverage for revised source records, verified-record preservation and deletion metadata extraction.
- [ ] Complete full CI and validate lifecycle metadata against the locally running ODK Central stack; Central version and actual form behaviour remain external acceptance checks.


## M121 — Substantive four-track learning curriculum pilot (implemented and deployed; organisational review pending)

- [x] Add four pilot tracks: research methods, climate and health, youth climate stewardship, and Indigenous/community knowledge governance.
- [x] Add eight modules and 26 substantive lessons, including one additional applied lesson in each of the research and healthcare tracks.
- [x] Include learning outcomes, core concepts, applied practice, self-checks and official further-reading links.
- [x] Add four formative quizzes with four questions each and a 70% pass mark.
- [x] Update the idempotent demo seed to refresh managed course, module, lesson, source-link and quiz content.
- [x] Improve the learner classroom with course overview, lesson counts, guided minutes, module completion and responsive lesson cards.
- [x] Add seed idempotency/content assertions and learner curriculum API coverage.
- [x] Update the founder presentation, short pitch, seven-minute demo runbook, curriculum blueprint, product status and agent guidance.
- [x] Python 3.11/3.12/3.13 quality, web, geospatial and operations/container CI passed on PR #119.
- [x] Merge PR #119; Render web and API deployments both report `live` at merge commit `f0b31989365fb5859fabfc28a1b10b3c95b5f517`.
- [x] Render API startup log confirms the four-course curriculum seed completed; API health checks return HTTP 200.
- [ ] Complete subject-matter, clinical, research, safeguarding, accessibility and community-lead review before live cohort delivery.
- [ ] Run an authenticated browser acceptance pass for enrolment, classroom content, quiz submission, progress and certificate wording.

The pilot is not an accredited qualification, clinical protocol, ethics approval or substitute for local safeguarding procedures. The original M121 seed refreshed managed demo lesson and quiz content. M168 replaces that behaviour with a non-destructive bootstrap: create missing published courses and private authoring drafts only, preserving existing staff-authored course, module, lesson and assessment content on reruns. M168 remains pending merge and deployment until its CI and staging acceptance gates are complete.


## M140 — Institutional-partner reporting resilience (implementation in review)

- [x] Isolate per-programme reporting failures so one unavailable report does not hide successful programme reports.
- [x] Distinguish report loading, unavailable and empty states in the partner workspace.
- [x] Describe the cross-period aggregate as a sum of reported cohort counts, not unique participants.
- [x] Preserve server-side institutional-partner authorization and the minimum cohort disclosure threshold.
- [ ] Frontend typecheck, lint, unit/build checks and CI pass.
- [ ] Deploy the merged commit to Render staging.
- [ ] Complete authenticated partner browser acceptance with both successful and unavailable programme reports.


## M143 — Learner roster, cohort assignment and batch review (merged; staging deployed)

- [x] Add bounded, tenant-scoped bulk application decisions with per-learner results.
- [x] Add a searchable course roster and lifecycle-status filters to the staff workspace.
- [x] Add explicit confirmation before batch decisions and display partial failures.
- [x] Batch large rosters into requests of at most 100 learners.
- [x] Add cohort/intake data model, assignment and transfers.
- [x] Add learner detail/history and privacy-safe roster references.
- [x] Add regression tests for partial success, duplicate IDs and role boundaries.
- [x] Full CI, merge and staging deployment.
- [ ] Authenticated browser acceptance and safeguarding/consent readiness.


## M145 — Deduplicated learning progress and outcomes (merged; staging deployed)

- [x] Distinguish unique learners from course-enrolment counts in programme and organisation outcomes.
- [x] Calculate average progress with one equal-weight contribution per learner across the reporting scope.
- [x] Label programme dashboards with separate unique learner and enrolment metrics.
- [x] Include both denominators in programme and portfolio CSV exports.
- [x] Document metric definitions and add API/export regression assertions.
- [x] Full CI passes and merge.
- [x] Deploy to staging.
- [ ] Authenticated dashboard and export acceptance.
- [ ] Add cohort-aware timelines, transparent at-risk rules and facilitator interventions (tracked in #167).


## M149 — Learner-level progress detail (merged; staging deployed)

- [x] Add tenant-scoped, course-scoped staff detail API for an individual enrolment.
- [x] Include ordered lesson completion timestamps, assessment attempts/evaluations, attendance and mentee-side mentorship records.
- [x] Enforce learning-management role and 404 isolation for missing enrolments.
- [x] Add on-demand expandable learner activity panel to the admin roster.
- [x] Add API regression coverage for activity and role boundaries.
- [x] Full CI passes, merge and deploy.
- [ ] Authenticated staging acceptance of roster search and learner detail.

## M144 — Curriculum draft authoring controls (merged; staging deployed)

- [x] Add tenant-scoped course metadata editing for draft courses.
- [x] Add module title, description and ordering edits while the parent course is draft.
- [x] Add lesson content, resource, duration and ordering edits while the parent course is draft.
- [x] Reject edits to published or archived curriculum to protect currently delivered content.
- [x] Reject empty patches, null required fields and duplicate ordering positions.
- [x] Add lifecycle regression coverage and operational documentation.
- [x] Add draft editing controls to the learning admin interface.
- [x] Full CI matrix passes, merge and deploy to Render staging.
- [ ] Complete authenticated browser acceptance.

## M160 — Tenant-scoped cohorts and intake foundation (merged; staging deployed)

- [x] Add tenant-scoped programme cohorts with unique organisation code, dates, capacity and lifecycle status.
- [x] Add nullable cohort assignment to course enrolments without changing existing enrolments.
- [x] Add create/list/update APIs with tenant and programme ownership validation.
- [x] Add course-enrolment cohort assignment and transfer/unassignment with audit events.
- [x] Count cohort capacity by distinct learner, not enrolment rows.
- [x] Expose the learner's own cohort in the personal enrolment response.
- [x] Add staff cohort creation, opening, roster assignment and cohort filtering controls.
- [x] Keep live cohort activation blocked pending safeguarding and consent readiness.
- [x] Add migration, tenant/capacity/lifecycle regression tests and operations documentation.
- [x] Full CI, merge and staging deployment.
- [ ] Authenticated staging browser acceptance with realistic synthetic cohorts.

## M168 — Non-destructive curriculum authoring drafts (local implementation; pending CI/merge/deploy)

- [x] Preserve existing published course metadata, modules, lessons, resources, ordering and assessments during demo seed reruns.
- [x] Create one private, staff-editable authoring draft for each of the four published pilot tracks when absent.
- [x] Create four draft programme intake fixtures, one per programme, with capacity/date metadata and no implied live activation.
- [x] Populate each authoring draft with the complete ordered module/lesson structure and formative quiz configuration.
- [x] Preserve staff-authored changes in both published courses and authoring drafts on subsequent seed runs.
- [x] Default the learning-admin workspace to a draft course and show published/draft pathway, intake, module and lesson counts.
- [x] Keep public curriculum discovery limited to published courses.
- [x] Update curriculum, operations, founder presentation and demo runbook documentation for 28 modules / 86 lessons and the draft/published boundary.
- [x] Add regression coverage for non-destructive seed reruns, draft cohort fixtures and production settings tests that explicitly disable local DEBUG.
- [ ] Focused backend tests, Ruff, mypy and web typecheck/lint/unit/build checks pass on the final M168 head.
- [ ] GitHub PR checks pass and the reviewed commit is merged into staging.
- [ ] Both Render services deploy the merge SHA and the startup seed creates four staff-only drafts without modifying published curriculum.
- [ ] Authenticated learning-admin browser acceptance verifies draft editing, published read-only state and public learner catalogue isolation.
