# Stagingnextgenearth

A backend service generated from [FastApiBackbone](https://github.com/safuh/FastApiBackbone).

**Stack:** FastAPI · Pydantic · SQLAlchemy 2.x · Alembic · PostgreSQL

## Quick start

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/), and Docker if you use
the container workflow.

```bash
uv sync --extra dev
cp .env.example .env
make check
make run
```

The API documentation is available at http://127.0.0.1:8000/docs.

## Database

SQLite is configured for local development. Configure `DATABASE_URL` in `.env`
for PostgreSQL, then run:

```bash
make migrate-up
```

## Deployment

Docker assets are included.
Kubernetes/Kustomize manifests are not included.

## Architecture

The project includes a FastAPI application factory, Pydantic Settings, async SQLAlchemy persistence,
Alembic migrations, health/readiness endpoints, structured logging, authentication primitives,
and tests. Review the security documentation before enabling authentication in production.

This project is an independent copy. It does not retain the source repository's Git history.
