# ADR 0001: Backend Foundation Architecture

- Status: Accepted
- Date: 2026-08-28

## Context

FastAPI applications repeatedly rebuild configuration, persistence, migration, authentication, testing, and deployment infrastructure. Stagingnextgenearth should provide these capabilities without coupling consumers to a business domain or frontend.

## Decision

Stagingnextgenearth uses a src-layout Python package with the following architecture:

1. FastAPI is the HTTP boundary and OpenAPI contract.
2. Pydantic v2 validates request/response data; Pydantic Settings provides typed environment configuration.
3. SQLAlchemy 2.x async APIs provide persistence and transaction boundaries.
4. Alembic owns schema history and runs as an explicit deployment operation.
5. PostgreSQL is the production database; SQLite is available for lightweight local development and tests.
6. Optional password/JWT authentication is composed explicitly by the consuming application.
7. Docker packages a reproducible, non-root runtime image.
8. Docker Compose provides the local API/PostgreSQL workflow.
9. Kubernetes/Kustomize provides an optional production deployment path.

The project is backend-only and remains domain-neutral.

## Consequences

- Consumers can use the backend foundation without a frontend or mobile client.
- Pydantic remains a first-class part of validation and configuration.
- Application processes do not independently run migrations.
- Production secrets are supplied at runtime and are not committed.
- Docker and Kubernetes remain optional deployment targets.
- The architecture does not require PydanticAI, AI providers, Flutter, or a project generator.
