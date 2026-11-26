# Daily climate research series

The tenant-scoped endpoint `GET /api/organizations/{organization_id}/climate-observations/daily-series`
provides bounded descriptive time-series aggregation for one canonical variable.

## Query parameters

- `start` and `end`: required timezone-aware timestamps; the interval is start-inclusive and end-exclusive.
- `variable`: required canonical variable identifier.
- `quality_status`: `verified` by default; `pending` is available only when explicitly requested. Rejected observations are never included.

## Interpretation

Observations are grouped by UTC calendar day and unit. Each returned point contains count, arithmetic mean, minimum and maximum. Units are never pooled, so callers must not compare or combine different unit groups without an explicit scientific conversion.

The endpoint returns observed days only. It does not create zero-rainfall days, interpolate missing values, or impute any other missing data. It is descriptive aggregation, not a climate trend, drought classification, forecast, or causal attribution.

The query is capped at 10,000 observations. Narrow the requested time interval when the cap is exceeded. Access is restricted to an authenticated member of the requested organisation; organisation scoping is applied in the database query.
