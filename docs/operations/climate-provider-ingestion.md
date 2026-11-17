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

The current route is a bounded synchronous MVP, not a durable background-job
queue. Do not use it for large-area or long-period batch backfills. Production
deployment should put a durable queue and worker behind the same provider and
persistence contracts, with per-tenant concurrency quotas, retry policy,
cancellation and operational alerting. Edge-level rate limiting remains
required.
