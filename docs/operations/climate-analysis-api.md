# Climate analysis summary API

`GET /api/organizations/{organization_id}/climate-observations/analysis-summary`

Required query parameters:

- `variable`: one observation variable.
- `start`, `end`: timezone-aware ISO-8601 timestamps; the interval is
  inclusive at start and exclusive at end.

Optional `quality_status` is either `verified` (default) or `pending`.
Rejected observations are never analysed. Pending measurements must be
requested explicitly and should not be presented as independently verified.

The endpoint groups measurements by their stored unit and never pools unlike
units. It reports count, mean, median, sample standard deviation, standard
error, extrema, interpolated percentiles and median absolute deviation.
Percentiles use Hyndman-Fan type 7. Missingness is not imputed; the API
currently summarizes recorded values and does not infer unrecorded dates.

The query is capped at 10,000 rows. Requests exceeding the cap receive HTTP
422 and must be narrowed; partial summaries are never returned as complete.
Results are tenant-scoped and require active organisation membership.

These are descriptive statistics only. Standard error has its conventional
interpretation only under assumptions such as independent observations;
climate series commonly exhibit temporal and spatial dependence. This endpoint
does not provide trend significance, confidence intervals, attribution,
bias correction, spatial interpolation or uncertainty quantification.


## Observation submission and quality review

- `POST /api/organizations/{organization_id}/climate-observations` accepts a
  timezone-aware timestamp, finite measurement value, unit, WGS84 coordinates,
  source reference, and optional project/study association. New records are
  always persisted with `quality_status=pending`.
- `GET /api/organizations/{organization_id}/climate-observations?quality_status=pending&limit=200`
  provides the bounded pending-review queue for active organisation members.
- `POST /api/organizations/{organization_id}/climate-observations/{observation_id}/review`
  accepts `verified` or `rejected` and an optional review note. Only
  administrators and programme managers may review; submitters cannot review
  their own observations, and only pending records can be decided. Decisions
  are immutable through this endpoint.
- The researcher workspace exposes submission and a role-gated review queue.
  Backend role, tenant and independent-review checks remain authoritative.
- The review queue is capped at 200 records per request. Use the API's supported
  filters and pagination strategy before treating it as a complete backlog.
