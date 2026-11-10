# Core Module

The core module owns cross-cutting infrastructure and the FastAPI application lifecycle.

## Responsibilities

- Typed environment configuration with Pydantic Settings.
- Async SQLAlchemy engine/session construction.
- FastAPI application lifespan and deterministic resource cleanup.
- Structured logging and request correlation context.
- Stable exception mapping and error responses.
- Health and readiness behavior.

## Boundaries

Core remains domain-neutral. It must not contain product-specific user, billing, order, or other business entities.

Application code may consume core abstractions. Core should not import consuming application modules. Authentication and identity are separate optional modules.

## Runtime contract

- Development and tests may use SQLite.
- Production requires PostgreSQL with asyncpg.
- Production debug mode is rejected.
- CORS origins must be explicitly configured.
- Database connections are checked during startup.
- Engine resources are disposed during shutdown.

See MVP acceptance tracker (../../MILESTONES.md) for the verified project scope.
