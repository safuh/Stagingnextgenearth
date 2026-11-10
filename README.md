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
It requires object storage to be enabled. The API reads the stored bytes with a hard
100 MiB limit, computes SHA-256 itself, and only marks a file available after ClamAV
returns a clean verdict. Infected files are rejected. Scanner or storage errors fail
closed and leave files quarantined; the uploader or an organisation admin can retry
the completion request. Without a configured scanner, files remain quarantined.

The authorised download endpoint issues a five-minute presigned GET URL only to eligible
organisation members for clean, available files. Restricted datasets remain owner/admin
only. Each URL issuance is recorded in an append-only access event table. The application
does not proxy file bytes, and the URL can be used until it expires; configure the bucket
with public access blocked and encryption enabled.
The current scanner path buffers each file in application memory (up to 100 MiB); a
streaming worker queue is a production scaling improvement still to be implemented.
Configure ClamAV's `StreamMaxLength` and `MaxFileSize` to at least the platform's
100 MiB upload limit. Keep the ClamAV TCP service on a private, trusted network; this
adapter does not provide transport encryption or authentication.
