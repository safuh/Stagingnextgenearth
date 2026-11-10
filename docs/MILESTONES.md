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
- [ ] Membership role changes, suspension and ownership transfer.
- [ ] Account lifecycle, audit events and privileged-action logging.
- [ ] Rate limiting and abuse protection at the application or edge.
- [x] Initial security tests for cross-organisation access and role escalation.

## M3 — Programme and project operations

- [ ] Programme and project APIs with explicit service/repository boundaries.
- [ ] Goals, milestones, activities, deliverables and assignments.
- [ ] Volunteer and ambassador registration and allocation.
- [ ] School and community participation records.
- [ ] Evidence uploads and approval workflow.
- [ ] Programme indicators and progress reporting.

## M4 — Research workspace

- [x] Initial tenant-scoped study creation and discovery endpoints.
- [x] Initial tenant-scoped research dataset registry with metadata and data dictionaries.
- [x] Dataset access classifications and owner/admin visibility for restricted metadata.
- [x] Dataset submission and independent approval/rejection workflow with audit fields.
- [x] Owner correction and resubmission workflow for rejected datasets.
- [x] Append-only dataset review history retained across resubmissions.
- [ ] Researcher profiles and collaborator access.
- [ ] Study proposals, protocols, ethics approvals and milestones.
- [x] Dataset registry, metadata, data dictionaries and access classifications.
- [ ] Publication records and DOI/ORCID/OpenAlex integrations.
- [x] Private object-storage adapter, constrained upload intents and authorised download grants.
- [x] Dataset file-version metadata schema with storage-key uniqueness, size constraints and scan/status state.
- [x] Optional ClamAV INSTREAM scanning; files remain quarantined unless a clean verdict is returned.
- [x] Trusted SHA-256 calculation from stored object bytes and clean/rejected state transition.
- [x] Bounded database-polled scanner worker with row locking, per-file commits and retry-safe quarantine on infrastructure failures.
- [x] Streaming object-storage reads and chunked ClamAV INSTREAM scanning with incremental SHA-256.
- [x] Executable scanner worker process with configurable polling and batch size.
- [x] Dedicated worker container/deployment manifest and production operational runbook (production Compose profiles validated in CI; operational runbook added).
- [x] Dataset file download access audit events.
- [ ] Research exports and reproducible analysis hand-off.

## M5 — Climate and geospatial intelligence

- [ ] PostGIS deployment and spatial migrations.
- [x] Provider-neutral climate ingestion contract, point/area request validation and provenance tracking.
- [x] NASA POWER daily point adapter for precipitation and 2 m air temperature, with UTC normalization and missing-value filtering.
- [x] CHIRPS v3 daily GeoTIFF adapter for point and bounding-box cell extraction, with variant, date-label, licence and raster provenance.
- [ ] Copernicus climate-data adapters.
- [ ] Administrative boundaries and geocoding strategy.
- [ ] Spatial and temporal query APIs.
- [x] Initial independent review workflow for field-observation quality status.
- [ ] Quality assurance, missing-data handling and unit normalisation.
- [ ] Research-grade statistical and geospatial analysis pipelines.
- [ ] Interactive map and climate research dashboards.
- [ ] Uncertainty, model limitations and data lineage shown in outputs.

## M6 — Public website and four portals

- [ ] Next.js public website and content management workflow.
- [ ] Researcher portal.
- [ ] Youth and volunteer portal.
- [ ] Administrator portal.
- [ ] Institutional partner portal.
- [ ] Shared design system, responsive layouts and accessible navigation.
- [ ] Role-aware navigation driven by server-authorised memberships.
- [ ] API client, typed contracts, error states and session handling.

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
