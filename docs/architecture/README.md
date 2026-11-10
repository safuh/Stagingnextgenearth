# Architecture

Stagingnextgenearth is a backend-only foundation. The supported runtime architecture is FastAPI + Pydantic + SQLAlchemy + Alembic + PostgreSQL, with Docker and Kubernetes as deployment options.

## Runtime dependency flow

~~~text
HTTP clients
    |
    v
FastAPI transport
    |-- Pydantic request/response validation
    |-- middleware and exception mapping
    |-- health/readiness
    |
    v
Application services
    |-- authentication use cases (optional)
    |-- transaction boundaries
    |
    v
Repository interfaces / adapters
    |
    v
SQLAlchemy async session
    |
    v
PostgreSQL

Alembic owns schema evolution and runs as a release operation.

Docker packages the application.
Docker Compose supports local development.
Kubernetes/Kustomize provides an optional cluster deployment.
~~~

## Architectural rules

1. HTTP routers handle transport concerns and delegate use cases.
2. Pydantic models validate external request/response data and typed configuration.
3. Application services must not depend on FastAPI request objects.
4. Repositories use the session/transaction supplied by the application boundary.
5. SQLAlchemy models and Alembic migrations own persistence schema.
6. Database migrations never run automatically in each API worker.
7. Runtime configuration and secrets are injected by the environment.
8. Docker and Kubernetes are deployment concerns; the Python package remains runnable without either.
9. Authentication is opt-in at the composition root and requires explicit secret/lifetime configuration.

## Explicit non-goals

PydanticAI, agent orchestration, AI provider integrations, Flutter/mobile clients, frontend code, and project generation are not part of this architecture or MVP.

## Decision records

See the ADRs in this directory for durable decisions about dependency direction, security, and deployment.
