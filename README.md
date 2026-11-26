# NextGen for Earth Platform

A full organisational digital platform for NextGen for Earth, built on the
FastAPI foundation generated from [FastApiBackbone](https://github.com/safuh/FastApiBackbone).

The product direction is a research-first programme and impact platform with
dedicated experiences for researchers, youth and volunteers, administrators,
and institutional partners.

**Backend:** FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic · PostgreSQL  
**Geospatial and analytics:** PostGIS · Pandas · NumPy · Xarray · GeoPandas  
**Web application:** Next.js · TypeScript · responsive portal experiences

## Current platform capabilities

The platform now includes the following integrated product areas:

- **Identity and organisation administration:** account registration/sign-in, HttpOnly-cookie web sessions, tenant-scoped memberships, invitations and acceptance, multiple assigned roles, owner/founder/executive controls, audit history and people directory.
- **Programmes and delivery:** programme/project catalogue, activities, assignments, deliverables, goals, milestones, indicators, participation, volunteer applications/allocations and attendance.
- **Learning management:** courses, modules, lessons, learner applications/enrolments, approval, assessments/quizzes, progress, attendance, mentorship and downloadable QR-verifiable certificates.
- **Institutional partnerships:** partner records, verification workflow and partner reporting.
- **Research governance:** study lifecycle, proposals, protocol versioning/review, ethics decisions, collaborators, publications, dataset registry, file access governance, evidence manifests and reproducibility records.
- **Climate intelligence:** NASA POWER and CHIRPS ingestion, climate observations, independent quality review, spatial/time-series analysis, monthly anomalies, coverage and reporting. A dedicated public climate intelligence hub and governed public-release API are specified in [the public climate blueprint](docs/PUBLIC_CLIMATE_INTELLIGENCE.md); the public release workflow is not yet implemented. OpenAlex publication metadata workflows are also available.
- **ODK Central:** encrypted organisation-level Central connection settings, credential test, form discovery, explicit per-form mappings, scheduled OData polling, persistent pagination cursors, idempotent ingestion and durable sync history. Imported field observations remain pending independent review.
- **Public website/CMS:** public programme and content projections from approved portal records, with editorial review and publication controls.
- **Web portals:** separate learner, staff, researcher, youth/volunteer, partner and administration experiences, using a same-origin Next.js BFF and HttpOnly session cookies.

The ODK Central connection and sync worker are described in [the ODK operations guide](docs/operations/odk-central-integration.md). The worker is a separate process and must be enabled explicitly. It is designed for one replica until distributed leasing is added.

Funding management is intentionally non-payment-based. Its scope is grant/opportunity records, budgets, pledges, commitments, allocations and expenditure reporting; no payment gateway, checkout, wallet or payment processor is part of this platform.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), Node.js/npm and Docker Compose (Docker or Podman Compose).

~~~bash
uv sync --locked --extra dev
cp .env.example .env
chmod 600 .env
# Review .env and replace the local database password and JWT secret.
docker compose --env-file .env -p nextgen-local -f docker/compose.postgis.yml up -d postgres
uv run alembic upgrade head
~~~

Start the API from the repository root:

~~~bash
make run
~~~

In another terminal, install and start the web application:

~~~bash
cd web
npm ci
cp .env.example .env.local
npm run dev
~~~

Local URLs: frontend http://localhost:3000, API health http://127.0.0.1:8000/api/health/ready, and API documentation http://127.0.0.1:8000/docs.

The local `.env.example` uses PostgreSQL/PostGIS because the production schema relies on spatial capabilities. SQLite remains useful for isolated unit tests, but the supported local integration workflow uses PostGIS. Apply migrations explicitly; do not run migrations automatically in API or worker startup.

## First organisation bootstrap

The idempotent API-based bootstrap utility creates/reuses the initial owner account and canonical organisation, then loads curated public people, staff memberships, partners, programmes, research studies and CMS records from the seed manifest. It does not write directly to database tables, reset existing passwords, or publish content automatically.

Follow [the environment setup and operations guide](docs/operations/environment-setup.md) for secure bootstrap prompts, local/staging/production separation and demo data rules. A typical owner bootstrap is:

~~~bash
export BOOTSTRAP_ADMIN_IDENTIFIER='owner@example.org'
read -r -s -p 'Initial owner password: ' BOOTSTRAP_ADMIN_PASSWORD; export BOOTSTRAP_ADMIN_PASSWORD; printf '\n'
export BOOTSTRAP_ORGANIZATION_NAME='Next Gen For Earth'
export BOOTSTRAP_ORGANIZATION_SLUG='next-gen-for-earth'
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE='KE'
export BOOTSTRAP_API_URL='http://127.0.0.1:8000/api'
uv run python scripts/bootstrap_nextgen.py
~~~

Never place passwords in manifests or commit real organisation data. Review imported people, partners, programmes, research and CMS records before making any of them public. Seed records are source-attributed candidates, not proof of staff employment, signed partnerships, completed activity or verified impact.

## Project documentation

- [Architecture](docs/architecture/README.md)
- [Platform domain](docs/modules/platform/README.md)
- [Milestones](docs/MILESTONES.md)
- [Security](docs/SECURITY.md)
- [PostgreSQL/PostGIS deployment](docs/operations/postgis.md)
- [Web BFF/session deployment](docs/operations/web-deployment.md)
- [Founder demo and staging acceptance](docs/operations/founder-demo-acceptance.md)
- [ODK Central integration](docs/operations/odk-central-integration.md)
- [Public climate intelligence product and API specification](docs/PUBLIC_CLIMATE_INTELLIGENCE.md)

## Development checks

~~~bash
make lint
make typecheck
make test
make check
~~~

The project is an independent application repository and does not retain the
source FastApiBackbone Git history.


### Research dataset file uploads

Private file upload intents are available when S3-compatible object storage is configured.
Set `OBJECT_STORAGE_ENABLED=true`, `OBJECT_STORAGE_BUCKET`, and optionally
`OBJECT_STORAGE_REGION`, `OBJECT_STORAGE_ENDPOINT_URL`, `OBJECT_STORAGE_ACCESS_KEY_ID`,
and `OBJECT_STORAGE_SECRET_ACCESS_KEY`. Provide an access key and secret through the deployment secret manager; this adapter currently
uses explicit static credentials and does not yet support workload/IAM role credential discovery.

The API issues a short-lived presigned POST (10 minutes), restricts accepted media types
and upload size (100 MiB maximum), verifies the stored object's size and media type at
completion, and moves accepted uploads into quarantine. File listings never expose
storage keys.

Optional ClamAV scanning can be enabled with `MALWARE_SCANNING_ENABLED=true`,
`CLAMAV_HOST`, and the optional `CLAMAV_PORT`/`CLAMAV_TIMEOUT_SECONDS` settings.
It requires object storage to be enabled. The synchronous API completion path reads stored bytes with a hard 100 MiB limit. For larger-scale processing, the database-polled worker streams bounded object-storage chunks directly into ClamAV INSTREAM while computing SHA-256 incrementally, avoiding whole-file buffering. Both paths only mark a file available after ClamAV returns a clean verdict. Infected files are rejected. Scanner or storage errors fail
closed and leave files quarantined; the uploader or an organisation admin can retry
the completion request. Without a configured scanner, files remain quarantined.

The authorised download endpoint issues a five-minute presigned GET URL only to eligible
organisation members for clean, available files. Restricted datasets remain owner/admin
only. Each URL issuance is recorded in an append-only access event table. The application
does not proxy file bytes, and the URL can be used until it expires; configure the bucket
with public access blocked and encryption enabled.
A separately managed worker process is included and can be started with `uv run python -m stagingnextgenearth.workers.run_dataset_scanner`. It claims quarantined rows with database row locks, streams bounded object-storage chunks into ClamAV, computes SHA-256 incrementally, commits each verdict independently, and leaves files quarantined when storage or scanning fails. Configure the same database, object-storage and ClamAV environment variables used by the API. Tune polling with `--batch-size` (1–100) and `--poll-interval-seconds` (default 5). Run API and scanner as separate processes; do not start the scanner inside each API worker.
Configure ClamAV's `StreamMaxLength` and `MaxFileSize` to at least the platform's
100 MiB upload limit. Keep the ClamAV TCP service on a private, trusted network; this
adapter does not provide transport encryption or authentication.

### Climate data ingestion

The climate ingestion contract separates provider requests from normalized
measurements and records the source, provider identifier, licence metadata when
verified, requested time window and requested point/area in each ingestion run.
Ingestion is idempotent for provider record identifiers within an organisation;
new observations enter review as pending and ingestion does not imply scientific
validation.

A tenant-scoped spatial query is available at
`GET /api/organizations/{organization_id}/climate-observations/spatial`.
Supply `west`, `south`, `east`, and `north` as WGS84 longitude/latitude
bounds; optional `variable`, `quality_status`, `start`, `end`, `limit`,
and `offset` filters constrain the result. The API uses the PostGIS geometry
and GiST index on PostgreSQL, with coordinate predicates as a SQLite
development fallback. Bounding boxes crossing the antimeridian are not yet
supported. Results are organisation-scoped and capped at 500 per page.

The first adapter, `NASAPowerProvider`, requests daily point data from the NASA
POWER API. It currently maps `PRECTOTCORR` to precipitation and `T2M` to
2-metre air temperature by default. Requests explicitly use UTC; the platform's
exclusive end-time contract is translated to POWER's inclusive end date.
POWER's `-999` missing-data sentinel is omitted rather than stored as a
measurement. The adapter supports point requests only; bounding-box requests
are rejected rather than silently treated as point data. Parameter units are
preserved from the provider response, and the adapter does not assert a licence
where the applicable terms have not yet been verified.

The second adapter, `CHIRPSProvider`, reads CHIRPS v3 daily GeoTIFF
rasters from the Climate Hazards Center archive. It supports both point
extraction (the containing raster cell) and bounding-box extraction (each
selected cell centre), emits precipitation in `mm/day`, and records the
CHIRPS variant, grid resolution, extraction method, citation and licence.
The default `rnl` variant partitions pentad totals into daily amounts using
ERA5; `sat` uses IMERG Late V07 and is available from 1998, while `rnl`
extends back to 1981. Both variants begin with the same pentad total but can
allocate it differently among days. The daily label follows the UTC calendar
day used for disaggregation (approximately 00:00 UTC to 00:00 UTC the next
day); it is not a uniform observation window for the station data blended
into the pentad total. Daily values are derived from pentad totals, not
independent daily station blends. Prefer pentad or monthly values when daily
timing is not essential. CHIRPS v3 is a 0.05-degree gridded product covering
60°S–60°N and is licensed CC BY 4.0 with attribution to the Climate Hazards
Center.

CHIRPS raster decoding uses the optional `rasterio` package (which installs
NumPy). Install it in deployments that enable this adapter with
`uv pip install rasterio`. The core application and CI test suite do not
install the geospatial binary dependency by default. Optional synthetic
GeoTIFF decoder tests in `tests/test_chirps_raster.py` run when rasterio is
installed; they are skipped otherwise. The normal CI suite also tests the
provider stream through climate persistence using a mocked raster decoder. The adapter limits
requests to 366 days, bounding-box extraction to 10,000 cells per day, and each
GeoTIFF download to 256 MiB by default (`max_raster_bytes` is configurable);
larger jobs should be partitioned into smaller requests. Each requested day
is downloaded separately, so missing or not-yet-published source rasters
fail explicitly rather than being silently skipped.

CHIRPS is a gridded rainfall estimate, not a direct gauge observation or a
sub-daily rainfall intensity product. The adapter does not aggregate an area
to a single mean or total: it emits one observation per selected raster cell.
Copernicus adapters, unit harmonisation, quality assessment and
spatial/temporal query APIs remain planned work.


## Climate intelligence

The public evidence hub is available at `/climate-intelligence`. The authenticated researcher-facing Climate Studio is available at `/workspace/research/climate` and connects bounded CHIRPS v3 ingestion, provider-run inspection, independent batch quality review and versioned public release governance. The public hub displays published releases only; it remains empty until real provider data have passed review and explicit publication.

## Web application

The Next.js application lives in `web/` and includes the public landing page and role-oriented workspaces. Browser code calls the same-origin BFF at `/api/backend/*`; the BFF keeps access and rotating refresh tokens in HttpOnly cookies and forwards authorised requests to FastAPI. Browser JavaScript does not receive bearer tokens.

Configure `BACKEND_API_URL=http://127.0.0.1:8000/api` in `web/.env.local` for local development. Do not use a `NEXT_PUBLIC_*` variable for backend credentials or private service URLs. See [web deployment and session security](docs/operations/web-deployment.md).

## Verification

~~~bash
uv run ruff check .
uv run mypy src
uv run pytest
cd web && npm run typecheck && npm run lint && npm test && npm run build
~~~

For the founder demonstration, use [the run of show and acceptance checklist](docs/FOUNDER_DEMONSTRATION.md). A successful local build is not a production deployment: production still requires verified organisation content, configured secrets/storage, database backups and restore rehearsal, TLS/ingress, monitoring, security review and stakeholder acceptance.
