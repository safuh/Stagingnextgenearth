# ADR 0003: NextGen for Earth Product Architecture

- Status: Accepted
- Date: 2026-11-10

## Context

The repository began as a backend-only FastAPI foundation. The product requirement
is now a complete organisational platform with dedicated researcher, youth and
volunteer, administrator, and institutional partner experiences. Research and
climate intelligence are the leading priority, alongside programme management
and a public website.

The platform must support multiple organisations and partners without allowing
one tenant to access another tenant's operational or research records.

## Decision

1. Retain the existing FastAPI, Pydantic v2, SQLAlchemy 2.x and Alembic foundation.
2. Build a modular monolith with explicit domain boundaries rather than starting
   with independently deployed microservices.
3. Use PostgreSQL as the transactional system of record and PostGIS for spatial
   workloads.
4. Use Next.js and TypeScript for the public website and authenticated portal
   experiences.
5. Model organisation membership and role assignment as server-side, organisation-
   scoped records. Frontend route visibility is never an authorization control.
6. Prioritise programme/project workflows, research studies, climate observations,
   provenance, data quality and geospatial analysis.
7. Integrate mature field data, research metadata, climate and payment services
   through adapters rather than rebuilding those providers.
8. Keep participant-level health data and information about minors out of public
   datasets and public impact dashboards.
9. Run database migrations as explicit release operations.

## Consequences

- The initial platform schema is shared across all portal experiences.
- Users can hold different roles in different organisations.
- Product modules can evolve independently while sharing transaction and identity
  infrastructure.
- The first schema migration does not imply that API authorization or complete
  workflows are already implemented; those remain explicit milestones.
- PostGIS, Next.js, climate ingestion, and research integrations are introduced
  in later milestones with their own tests and deployment requirements.
