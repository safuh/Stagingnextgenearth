# Climate statistical summaries

The climate_statistics module provides deterministic descriptive summaries
for a single homogeneous series. It reports sample count, missing count, mean,
median, sample standard deviation, standard error, minimum/maximum, linearly
interpolated 5th/25th/75th/95th percentiles, and median absolute deviation.

## Interpretation and safeguards

- Group observations by the same variable and canonical unit before calling
  the function. Never pool unlike units or variables.
- None is counted as missing; it is never replaced with zero, interpolated,
  carried forward, or otherwise imputed.
- Non-finite and non-numeric values are rejected.
- Sample standard deviation and standard error are undefined for a single
  observation and are returned as null.
- Percentiles use linear interpolation (Hyndman-Fan type 7).
- These are descriptive statistics, not a trend test, confidence interval,
  attribution analysis, bias correction, or substitute for spatial/temporal
  dependence modelling.
- Standard error assumes independent observations for its conventional
  interpretation. Climate time series are often autocorrelated; do not use
  this value as an inferential uncertainty estimate without a dependence model.
- Retain source, time window, spatial extraction, quality status, units, and
  missingness alongside published results.

This is a calculation primitive only. It does not yet expose a research-analysis
API or claim a complete research-grade analysis pipeline.
