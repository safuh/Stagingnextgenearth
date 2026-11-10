# NextGen for Earth Platform Domain

This module is the first product-specific layer built on the FastApiBackbone-derived
runtime. It establishes the shared data model for the organisation's portals and
research-first programme operations.

## Initial domain boundaries

- **Organisations and memberships:** tenant ownership and portal roles.
- **Programmes:** organisation-level initiatives with lifecycle dates and status.
- **Projects:** deliverable work packages belonging to an organisation and optionally
  to a programme.
- **Research studies:** studies linked to projects, with a lead researcher and an
  ethics reference.
- **Climate observations:** sourced, timestamped measurements with units, coordinates,
  provenance and a review state.

## Portal roles

The initial membership role vocabulary is:

- `admin`
- `programme_manager`
- `researcher`
- `youth_volunteer`
- `institutional_partner`

A membership is scoped to an organisation. A user can have different roles in
different organisations. Portal navigation must be derived from active memberships,
not from a user-editable profile field.

## Data integrity and privacy

Every product record is organisation-scoped. API queries must enforce the active
organisation boundary and role policy at the application-service layer; filtering
only in the frontend is not an authorization control.

Climate observations retain their source, unit, timestamp and coordinates. A
measurement is not considered verified merely because it was ingested. The
`quality_status` field distinguishes pending, verified and rejected records.

Research records may contain sensitive or ethically restricted information.
Public publication metadata must be separated from participant-level research
data. This initial schema does not store participant-level health records.

## Current implementation boundary

This increment establishes SQLAlchemy models and the Alembic persistence contract.
Authenticated API workflows, membership invitations, programme/project services,
research workflows, climate ingestion adapters, and portal UIs are subsequent
increments. Do not expose these tables through unrestricted generic CRUD endpoints.
