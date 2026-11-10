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
- dataset access classifications, submission workflow and independent approval/rejection audit;
- Alembic migrations `0004_platform_domain` through `0006_research_dataset_registry`.

Climate observations enter the system as pending and cannot be verified by their
submitter. Only organisation administrators and programme managers can review
observations, and a review decision cannot be overwritten through the API. Dataset
registration currently stores metadata only: it does not store files or issue download
URLs. Restricted dataset metadata is visible only to its owner and organisation
administrators. A public classification does not publish data to the internet.
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
