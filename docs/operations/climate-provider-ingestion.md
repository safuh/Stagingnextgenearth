# Climate provider ingestion operations

## Trusted API workflow

Organisation administrators and researchers can start a provider ingestion run:

```http
POST /api/organizations/{organization_id}/climate-ingestion
Authorization: Bearer <access-token>
Content-Type: application/json
```

Example point request:

```json
{
  "provider": "nasa-power",
  "start": "2026-01-01T00:00:00Z",
  "end": "2026-01-08T00:00:00Z",
  "point": {"latitude": -1.286, "longitude": 36.817}
}
```

Example CHIRPS area request:

```json
{
  "provider": "chirps-v3",
  "chirps_variant": "rnl",
  "start": "2026-01-01T00:00:00Z",
  "end": "2026-01-04T00:00:00Z",
  "area": {"west": 36.7, "south": -1.3, "east": 36.8, "north": -1.2}
}
```

Allowed provider identifiers are `nasa-power`, `chirps-v3`, and
`copernicus-era5`. The API does not accept caller-supplied URLs, provider
credentials, arbitrary provider names, or arbitrary query parameters. Exactly
one WGS84 point or bounding box is required. NASA POWER accepts point requests;
CHIRPS and ERA5 accept points or bounded areas. CHIRPS selects `rnl` or
`sat`. ERA5 additionally requires its optional runtime libraries and
operator-configured CDS credentials and dataset acceptance.

## CHIRPS request-rate and failure handling

The Climate Hazards Center data service recommends keeping total traffic at
about one request per second or less per public IP. The API therefore spaces
daily raster requests by at least 1.1 seconds, serializes CHIRPS ingestion
across API instances with a PostgreSQL advisory lock, and enforces a persisted
cooldown from the latest CHIRPS run completion time. A new one-day ingestion
cannot bypass the interval by creating a fresh provider instance. After a
provider timeout or 403/429 rate-limit response, the persisted failed-run
record enforces a three-hour minimum cooldown and returns HTTP 503 with a
Retry-After header. Do not start overlapping or repeated provider runs.

HTTP 403/429 responses and request timeouts are treated as provider
unavailability, not transient errors to hammer with retries. The workspace
returns HTTP 503 with an actionable message and a numeric `Retry-After`
header, and records a failed ingestion run without persisting partial
observations. The same header is forwarded through the web BFF; the Climate
Studio displays a countdown and disables further ingestion while the server
cooldown is active. If this occurs, stop retrying and wait several hours before
another attempt; the provider documents that automated blocks can also appear
as repeated timeouts. See the CHC
[downloading guidance](https://github.com/chc-ucsb/chc-data-download#downloading-politely).

Only active organisation memberships holding `admin` or `researcher` can
start ingestion. Learners, volunteers and ordinary members cannot trigger
upstream retrieval. The route uses the existing tenant-scoped membership
dependency; it cannot ingest into another organisation.

## Run and review semantics

The request executes synchronously and returns the persisted ingestion-run
summary. A run records provider, source, licence, requested time and area,
initiating user, record counts, status and timestamps. Replaying a provider
record is idempotent within the organisation. A provider failure rolls back
partial observations and leaves a failed run audit record; the API response
does not expose upstream exception details or secrets.

Every newly imported observation is stored with `quality_status=pending`.
Normalization metadata retains source value/unit, canonical value/unit,
conversion and screening flags. Import is not verification: a different
authorised reviewer must make the separate quality decision. Reviewers cannot
verify their own submissions.

## Licence review and publication separation

A release cannot be approved until a separate licence reviewer records four
explicit checks: the licence permits the intended public use, provider terms
and dataset conditions have been checked, attribution is correct, and the
source citation identifies the intended product/version. The reviewer must
not be the release author, ingestion operator or observation quality reviewer.
The checklist, exact licence metadata, reviewer identity and substantive note
are retained in the append-only release event ledger.

The release approver must be different from the author, ingestion operator,
quality reviewer and licence reviewer. Publication is a further decision: the
publisher must be different from all those actors and must record a substantive
publication note. The API enforces these separations; hiding buttons in the
workspace is not an authorization boundary. If the organisation cannot staff
the independent roles, the release remains in review rather than weakening
the control.

The current route is a bounded synchronous MVP, not a durable background-job
queue. Do not use it for large-area or long-period batch backfills. Production
deployment should put a durable queue and worker behind the same provider and
persistence contracts, with per-tenant concurrency quotas, retry policy,
cancellation and operational alerting. Edge-level rate limiting remains
required.
