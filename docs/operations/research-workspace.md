# Research workspace

The Next.js route `/workspace/research` provides an organisation-scoped,
read-only registry view for active members with the roles
`admin`, `programme_manager`, `researcher`, or `institutional_partner`.

## Data displayed

- Research studies: title, abstract, type, lifecycle status, lead researcher
  identifier and ethics reference.
- Dataset registry: title, version, format, source, licence, access
  classification, governance status and collection period.
- Summary counts for studies, datasets, submitted datasets and approved datasets.

The page obtains the active organisation's membership from
`GET /organizations/{organization_id}/memberships/me`, then loads
`GET /organizations/{organization_id}/research-studies` and
`GET /organizations/{organization_id}/research-datasets`.

## Security boundaries

The role check in the page controls presentation only. The API independently
checks organisation membership, role, study collaboration and dataset
classification. Dataset metadata endpoints do not return storage keys or file
bytes. The dashboard does not issue upload forms, download grants, or expose
private object-storage URLs.

Restricted dataset metadata remains subject to the dataset API's owner/admin
and study-collaboration rules. A dashboard error is not permission to bypass
those rules or query another organisation.

## Current scope

This is the initial researcher-facing registry dashboard, not the complete
research workflow. Study creation, dataset registration/editing, submissions,
review queues, file upload/scanning, authorised downloads, analysis manifests
and analysis-run provenance remain in their dedicated API workflows. Dedicated
researcher workflow forms and interactive climate analysis/map views remain
follow-on frontend work.
