# Monthly precipitation anomaly research API

The tenant-scoped endpoint
`GET /api/organizations/{organization_id}/climate-observations/monthly-precipitation-anomalies`
computes monthly precipitation totals and descriptive standardized anomalies.

Required query parameters: `baseline_start`, `baseline_end`, `target_start`,
`target_end` (inclusive ISO dates), `latitude`, and `longitude`.
All date bounds must cover complete calendar months. Baseline and target periods
must be disjoint. Defaults are verified observations, 90% daily completeness,
and ten baseline years; callers may explicitly request pending observations.

Only `precipitation` in `mm/day` at the exact requested coordinate is included.
Same-day duplicate records are averaged before monthly summation. A month below
the completeness threshold is excluded; no values are imputed. Target months are
compared only with baseline months having the same calendar month. The response
includes baseline statistics, completeness, source/provider/run provenance, and
the method identifier.

The score is a sample-standardized z-score. It is **not SPI**, a WMO climate
normal, or a drought classification. Ten years is a computational minimum,
not a recommendation that ten years is a climatological normal. Interpret
results with the data provider's spatial/temporal conventions and quality review.
