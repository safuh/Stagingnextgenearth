# NextGen for Earth Platform

A full organisational digital platform for NextGen for Earth, built on the
FastAPI foundation generated from [FastApiBackbone](https://github.com/safuh/FastApiBackbone).

The product direction is a research-first programme and impact platform with
dedicated experiences for researchers, youth and volunteers, administrators,
and institutional partners.

**Backend:** FastAPI · Pydantic v2 · SQLAlchemy 2.x · Alembic · PostgreSQL  
**Geospatial and analytics:** PostGIS · Pandas · NumPy · Xarray · GeoPandas  
**Web application:** Next.js · TypeScript · responsive portal experiences

## Current implementation

The repository currently contains the reusable backend foundation and the first
authenticated product workflows:

- JWT-authenticated organisation creation and tenant-scoped discovery;
- organisation membership invitations and invitee-only acceptance;
- programme and project creation with tenant-safe parent validation;
- research study creation and discovery;
- provenance-bearing climate observation submission and filtering;
- independent climate-observation review with immutable verified/rejected decisions;
- a tenant-scoped research dataset registry with data dictionaries and collection metadata;
- dataset access classifications, submission workflow, correction/resubmission and append-only review history;
- Alembic migrations `0004_platform_domain` through `0009_dataset_file_access_audit`.

Climate observations enter the system as pending and cannot be verified by their
submitter. Only organisation administrators and programme managers can review
observations, and a review decision cannot be overwritten through the API. Dataset
registration stores governed metadata and supports private file upload intents when
S3-compatible object storage is configured. Completed files remain quarantined unless optional ClamAV scanning returns a clean verdict. Authorised download grants are issued as short-lived signed URLs and recorded in an access audit table. Restricted
dataset metadata is visible only to its owner and organisation administrators. A public
classification does not publish data to the internet.
Do not expose domain tables through unrestricted generic CRUD endpoints.

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and Docker for the
PostgreSQL workflow.

~~~bash
uv sync --extra dev
cp .env.example .env
make check
make run
~~~

The API documentation is available at http://127.0.0.1:8000/docs.

Set `JWT_SECRET_KEY` to a unique secret of at least 32 characters before enabling
password authentication. Access tokens default to 15 minutes and refresh tokens
to 14 days; configure `ACCESS_TOKEN_MINUTES` and `REFRESH_TOKEN_DAYS` as needed.
Do not commit production secrets.

## Database

SQLite is available for lightweight local development. PostgreSQL is the target
for shared development and production. Apply migrations explicitly:

~~~bash
make migrate-up
~~~

Do not run migrations automatically in API workers.

## Project documentation

- [Architecture](docs/architecture/README.md)
- [Platform domain](docs/modules/platform/README.md)
- [Milestones](docs/MILESTONES.md)
- [Security](docs/SECURITY.md)

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
requests to 366 days and bounding-box extraction to 10,000 cells per day;
larger jobs should be partitioned into smaller requests. Each requested day
is downloaded separately, so missing or not-yet-published source rasters
fail explicitly rather than being silently skipped.

CHIRPS is a gridded rainfall estimate, not a direct gauge observation or a
sub-daily rainfall intensity product. The adapter does not aggregate an area
to a single mean or total: it emits one observation per selected raster cell.
Copernicus adapters, unit harmonisation, quality assessment and
spatial/temporal query APIs remain planned work.
