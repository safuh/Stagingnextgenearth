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


## Dataset corrections and file versions

Rejected dataset owners can edit the supported metadata fields. Saving corrections returns
the record to draft state and clears the previous decision fields; the owner must submit
the revised metadata again for independent review. The API rejects edits to submitted
or approved datasets.

The workspace can request a short-lived upload intent for CSV, JSON, PDF, ZIP and XLSX
files up to 100 MiB, post the file to the private storage form, and call the completion
endpoint. The completion endpoint verifies stored size and media type, quarantines the
object, and invokes the configured scanner. A missing scanner leaves the file quarantined;
a scanner/storage error does not make it downloadable. The workspace exposes a retry action
for quarantined versions so transient scanner/storage failures can be retried without
creating another file version. Only clean, available files can
receive an audited, short-lived download grant through the separate download endpoint.

The browser displays safe file-version metadata and scan state only. It does not persist
upload credentials, expose storage keys, or request download URLs in the registry.


## Interactive climate analysis

The research workspace now provides a bounded descriptive-analysis form backed by
`GET /organizations/{organization_id}/climate-observations/analysis-summary`.
Researchers select one variable, a local start/end time, and either verified
(default) or pending observations. The browser converts the entered local
timestamps to timezone-aware ISO-8601 values before requesting the API.

The results show the observation count and per-unit descriptive statistics:
mean, median, sample standard deviation, standard error, minimum, maximum,
type-7 percentiles and median absolute deviation. Distinct measurement units
remain separate. Pending results are explicitly labelled provisional; rejected
observations are excluded by the API. Empty result sets and bounded-query errors
are presented without fabricating partial summaries.

This is a descriptive workspace, not an inferential climate model. The API
limits requests to 10,000 observations, performs no missing-value imputation,
and does not establish temporal independence, trend significance, attribution,
or uncertainty bounds. The selected end timestamp is exclusive.


## Spatial climate observation workspace

The research workspace exposes a bounded WGS84 bounding-box query backed by
`GET /api/organizations/{organization_id}/climate-observations/spatial`.
The default extent is Kenya (west 33.9, south -4.7, east 41.9, north 5.2);
researchers can narrow or replace it. Optional filters include variable,
quality status, and timezone-aware start/end timestamps. Each request returns
at most 500 tenant-scoped observations and starts at offset zero.

The interface presents returned point coordinates and measurement provenance
in a table. It does not render a basemap, interpolate a continuous surface, or
infer values between stations. Bounding boxes crossing the antimeridian are
not supported by this API. Use the separate daily coverage report for
station-level missing-day summaries; no missing observations are imputed.


## Climate quality and station coverage reports

The workspace includes two additional bounded reports:

- **Flagged observations** calls `GET /organizations/{organization_id}/climate-observations/flagged`
  with an optional exact screening flag and quality-status filter. The response
  shows scan count, matched count, returned rows and whether the 5,000-row
  screening scan was truncated. A truncated scan is explicitly non-exhaustive.
  The UI pages through matches in batches of 200 using the endpoint's offset
  parameter, with previous/next controls and a displayed range. Optional
  timezone-aware start/end filters bound the scan window (end-exclusive), which
  helps inspect a narrower period when the 5,000-row cap is reached. Changing
  filters starts a new scan at offset zero. Screening flags are triage metadata,
  not scientific validation or an automatic quality decision.
- **Daily station coverage** calls
  `GET /organizations/{organization_id}/climate-observations/coverage`
  for one variable, WGS84 station coordinate and inclusive date range. The
  report displays expected, observed and missing calendar days and the
  coverage ratio. The API caps the range at 366 days and matches coordinates
  within 0.0001 degrees. Any non-rejected observation, including pending
  observations, counts as a day with data; rejected records do not.

Coverage is a completeness indicator, not a claim that each day's measurement
is valid or representative. Missing dates are listed explicitly and are never
filled, interpolated or converted to zero.
