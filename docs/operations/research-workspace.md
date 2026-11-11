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


## Research authoring

The dashboard now includes two API-backed forms for users with an eligible research role:

- Study registration creates a tenant-scoped study in `concept` status and assigns the caller as lead researcher. Optional abstract, study type and ethics reference are captured as metadata.
- Dataset registration creates a metadata-only draft with optional study link, description, version, format, source, licence and access classification.

Dataset registration does not upload bytes or make a dataset approved. Drafts must follow the existing submission and independent review workflow. File upload intents, malware scanning, download grants and object-storage access remain separate, authorised operations. The UI refreshes its local registry after successful creation and reports API validation/permission errors without bypassing server checks.


## Dataset submission and review workspace

The researcher registry exposes a submit action for draft dataset metadata. Submission
uses the tenant-scoped `POST /organizations/{organization_id}/research-datasets/{dataset_id}/submit`
endpoint; ownership and study-editor permissions are enforced by the API.

Administrator and programme-manager members see review controls for submitted datasets.
Approval and rejection are recorded through the independent review endpoint, with a
review note required in the UI when requesting corrections. Review history is loaded
from the append-only dataset review endpoint and displayed per dataset. Restricted
datasets remain subject to the stricter administrator-only review policy, and owners
cannot review their own submissions.

The browser does not treat client-side role checks as authorization. Every mutation
and history request is re-authorised by the API. Owner correction/resubmission and
file upload/scanning remain separate workflows; no storage keys or download URLs are
exposed in the registry.
