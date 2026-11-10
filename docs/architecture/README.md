# Architecture

NextGen for Earth is a research-first organisational platform implemented as a
modular monolith. The initial runtime retains the FastAPI foundation and adds
product-specific domain modules.

## Runtime dependency flow

~~~text
Public website and authenticated portals (Next.js)
                 |
                 v
          FastAPI transport
          |-- Pydantic contracts
          |-- authentication and RBAC
          |-- organisation-scoped API policies
                 |
                 v
          Application services
          |-- programme/project workflows
          |-- research workflows
          |-- climate data workflows
          |-- community and partner workflows
                 |
                 v
          Repositories / Unit of Work
                 |
                 v
          SQLAlchemy async session
                 |
                 v
          PostgreSQL (+ PostGIS for spatial workloads)

External climate, research, field-data and payment providers connect through
adapters. Background workers own scheduled ingestion and long-running analysis.
Alembic owns schema evolution and runs as an explicit release operation.
~~~

## Product modules

- **Identity and organisations:** users, memberships, portal roles and tenant policy.
- **Programmes and projects:** programme lifecycle, projects, milestones, activities,
  assignments and evidence.
- **Research:** studies, protocols, ethics metadata, datasets and publications.
- **Climate intelligence:** sourced observations, climate ingestion, quality control,
  geospatial analysis and research dashboards.
- **Community:** youth, volunteers, ambassadors, schools and training.
- **Partnerships:** institutional collaboration, grants, reporting and controlled access.
- **Impact:** indicators, verified outputs/outcomes and reporting.

## Architectural rules

1. HTTP routers handle transport concerns and delegate use cases.
2. Pydantic models validate external request/response data and typed configuration.
3. Application services must not depend on FastAPI request objects.
4. Every tenant-owned record is authorised through an active organisation membership.
5. Repositories use the session/transaction supplied by the application boundary.
6. SQLAlchemy models and Alembic migrations own persistence schema.
7. Database migrations never run automatically in each API worker.
8. External integrations are adapters; provider-specific logic does not leak into domain services.
9. Climate observations retain source, units, timestamps, coordinates and quality state.
10. Public outputs must not expose restricted research, health or child-related data.
11. Keep the initial deployment a modular monolith; extract services only for a demonstrated
    scaling, reliability or ownership need.

## Current implementation boundary

The backend foundation is in place. The first product migration establishes organisations,
memberships, programmes, projects, research studies and climate observations. The API
workflows, access policies, analytics pipelines, integrations and Next.js portals are
separate milestones and must not be represented as complete until tested.

## Decision records

See the ADRs in this directory for dependency direction, security, persistence and product
architecture decisions.
