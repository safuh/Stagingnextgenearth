# Standardized precipitation anomaly foundation

The climate anomaly calculation in `stagingnextgenearth.climate_anomalies` returns a descriptive z-score:

`(observed monthly total - baseline mean) / baseline sample standard deviation`

It is deliberately named a **standardized anomaly**, not the Standardized Precipitation Index (SPI). SPI requires a probability-distribution fitting and transformation procedure, appropriate accumulation windows, and additional methodological validation. This implementation does not perform those steps.

## Required comparability

Before calling the function, the data pipeline must establish that the observed total and every baseline value have the same:

- precipitation variable and physical unit;
- calendar month and accumulation period;
- spatial support (same station/grid cell or a documented spatial aggregation);
- completeness rule.

Incomplete months must be excluded, not silently treated as zero. The caller must preserve the baseline period and source lineage with the result. The function requires at least ten supplied baseline values by default and rejects a zero-variance baseline. Ten values are a computational minimum, not a WMO climate normal or a claim of climatological adequacy.

## Interpretation limits

The function returns no drought category. A negative anomaly means the observed total is below the supplied baseline mean; it is not, by itself, a drought declaration. It does not impute missing data, correct systematic bias, quantify observational uncertainty, or establish impacts. Operational drought monitoring requires validated thresholds, longer and representative baselines, quality-controlled data, spatial context and domain review.
