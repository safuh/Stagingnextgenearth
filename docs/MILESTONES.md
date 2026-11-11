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

- [ ] Programme and project APIs with explicit service/repository boundaries.
- [x] Activities, deliverables, volunteer allocations and activity lifecycle transitions.
- [x] Programme goals, milestone checkpoints and general assignments with tenant-scoped visibility, active-member assignment, and guarded lifecycle transitions.
- [x] Volunteer and ambassador applications, approval and activity allocation.
- [x] Aggregate school, community, youth-group and institutional participation records (no child-level PII).
- [ ] Evidence uploads and approval workflow.
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
- [ ] Research-grade statistical and geospatial analysis pipelines (tested descriptive statistics primitive and tenant-scoped, bounded, unit-grouped verified-data analysis summary API implemented; inferential and spatial/temporal dependence methods remain) (deterministic descriptive statistics are implemented as a tested calculation primitive; inferential methods, spatial/temporal dependence handling and API integration remain).
- [ ] Interactive map and climate research dashboards.
- [ ] Uncertainty, model limitations and data lineage shown in outputs.

## M6 — Public website and four portals

- [x] Responsive Next.js public landing page, four portal entry points, API-backed sign-in and authenticated organisation workspace with server-filtered membership discovery, programme listing and published-course listing.
- [x] Learner course detail, ordered module/lesson curriculum, course application, lesson completion and progress tracking.
- [x] Learner assessment instructions and submission workflow, gated by approved enrolment.
- [x] Staff learning operations workspace for course/module/lesson authoring, publishing, application decisions, assessment creation/evaluation, mentorship assignment and attendance recording/reporting.
- [ ] Researcher portal (initial organisation-scoped study and dataset registry dashboard is implemented; study/dataset authoring, review queues, file workflows and interactive climate analysis remain).
- [ ] Youth and volunteer portal (initial personal dashboard and caller-scoped application/allocation history APIs are implemented; learner interactions and application actions remain).
- [ ] Administrator portal.
- [ ] Institutional partner portal.
- [x] Shared design system, responsive layouts and accessible navigation.
- [x] Caller-scoped membership-role endpoint and role-aware workspace navigation (server API remains the authorization boundary).
- [ ] Dedicated researcher, youth/volunteer, administrator and institutional-partner dashboards with their complete workflows (initial researcher registry and youth/volunteer personal dashboards implemented; remaining role workflows are outstanding).
- [x] Typed API client, authenticated requests, explicit in-memory session lifecycle and user-visible loading/error states (production BFF/HttpOnly-cookie session remains a hardening item).

## M7 — Integrations and organisational intelligence

- [ ] KoboToolbox/ODK field data integration.
- [ ] Email and calendar notifications.
- [ ] Zoom/meeting integration where required.
- [ ] M-Pesa and approved international donation providers.
- [ ] Grant, budget and donor reporting.
- [ ] Impact verification and indicator dashboards.
- [ ] CSV/XLSX/PDF exports with access controls.

## M8 — Production readiness

- [ ] PostgreSQL/PostGIS integration and migration CI.
- [ ] Automated API and frontend test suites.
- [ ] Security review, privacy impact assessment and safeguarding review.
- [ ] Backups, restore drills, retention and deletion policies.
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
- [x] Assessment definitions, submissions and staff evaluation.
- [x] Mentor assignments, workshop attendance and learning resource metadata.
- [x] Lesson completion, assessment-derived progress and verifiable certificates.
- [x] Staff-only, tenant-scoped enrollment queue, assessment catalogue/submission review, mentorship and attendance reporting APIs; assessment configuration remains withheld from learner responses.
- [x] Staff learning operations UI for course authoring, enrollment decisions, assessment evaluation, mentorship assignment and attendance recording, using an authorised minimal member directory rather than free-form identity entry.
- [ ] Automated quiz execution, learner notifications, certificate PDF rendering,
      safeguarding/guardian consent and dedicated role-specific portal dashboards.
- [x] Learner-owned mentorship and attendance history endpoints and workspace panels (identity is derived from the authenticated principal and records are tenant-scoped).
