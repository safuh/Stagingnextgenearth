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


## Research dataset export hand-off

Approved research datasets expose a versioned metadata manifest at:

`GET /api/organizations/{organization_id}/research-datasets/{dataset_id}/export-manifest`

The manifest includes the dataset's descriptive metadata, collection period,
data dictionary, access classification, clean file-version identifiers, file
sizes, media types, upload timestamps and SHA-256 checksums. A canonical
serialization of the dataset snapshot is hashed into `manifest_sha256`, so
clients can detect metadata changes between hand-offs.

Only file versions in the `available` state with a `clean` scan verdict and
a trusted SHA-256 are referenced. Quarantined, pending, rejected, deleted or
incompletely scanned versions are counted in `excluded_file_versions` and
never included as downloadable content. Storage keys and signed object URLs
are not embedded in the manifest; clients must obtain file access through the
existing tenant-authorised download endpoint.

The export endpoint requires active organisation membership, an approved
dataset, and the applicable study/access-classification permissions. The
manifest is a reproducibility descriptor, not a substitute for the original
file bytes or for a researcher's documented analysis methods and software
environment.


## Reproducible analysis execution records

An approved dataset can record a completed analysis execution:

- `POST /api/organizations/{organization_id}/research-datasets/{dataset_id}/analysis-runs`
- `GET /api/organizations/{organization_id}/research-datasets/{dataset_id}/analysis-runs`

Each run stores the exact selected input file-version IDs, versions, trusted
checksums, sizes and upload timestamps. The ordered input snapshot is
canonically serialized and fingerprinted as `input_manifest_sha256`. Inputs
must belong to the dataset and be available, clean and checksummed at creation
time; a later upload does not rewrite the recorded lineage.

The record also captures a bounded JSON analysis configuration and parameter
set, software name/version, optional source revision and random seed, and
checksum-addressed output artifact metadata. Output records contain descriptive
artifact identifiers and checksums only; they do not accept storage keys,
signed URLs or credentials. The API records provenance for an analysis that
has already run; it does not execute notebooks or claim that output artifacts
have been independently verified.

Analysis-run records are append-only through this API. Listing is scoped to
the same approved dataset and organisation access policy as the export
manifest. The database migration is `0020_research_analysis_runs`.
