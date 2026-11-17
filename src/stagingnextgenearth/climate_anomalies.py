"""Transparent standardized anomalies for comparable monthly climate totals.

This module intentionally does not implement SPI. A standardized anomaly is
only a descriptive z-score against an explicitly supplied baseline sample.
"""

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import fmean


@dataclass(frozen=True, slots=True)
class StandardizedAnomaly:
    """A z-score and the baseline statistics required to interpret it."""

    value: float
    baseline_mean: float
    baseline_sample_standard_deviation: float
    baseline_count: int
    method: str = "sample_standardized_anomaly_z_score"
    classification: str = "unclassified"


def standardized_anomaly(
    observed_total: float,
    baseline_totals: list[float],
    *,
    minimum_baseline_count: int = 10,
) -> StandardizedAnomaly:
    """Calculate a descriptive z-score from homogeneous monthly totals.

    The caller must ensure the target and baseline represent the same
    variable, unit, calendar month, spatial support and accumulation period.
    Missing/incomplete months must be omitted before calling this function.
    """
    if isinstance(observed_total, bool) or not isinstance(observed_total, (int, float)):
        raise TypeError("observed_total must be numeric")
    observed = float(observed_total)
    if not isfinite(observed):
        raise ValueError("observed_total must be finite")
    if minimum_baseline_count < 2:
        raise ValueError("minimum_baseline_count must be at least 2")
    if len(baseline_totals) < minimum_baseline_count:
        raise ValueError(
            f"at least {minimum_baseline_count} complete baseline values are required"
        )

    values: list[float] = []
    for item in baseline_totals:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError("baseline totals must be numeric")
        numeric = float(item)
        if not isfinite(numeric):
            raise ValueError("baseline totals must be finite")
        if numeric < 0:
            raise ValueError("precipitation totals cannot be negative")
        values.append(numeric)
    if observed < 0:
        raise ValueError("precipitation total cannot be negative")

    mean = fmean(values)
    variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
    deviation = sqrt(variance)
    if deviation == 0:
        raise ValueError("baseline variability is zero; standardized anomaly undefined")

    return StandardizedAnomaly(
        value=(observed - mean) / deviation,
        baseline_mean=mean,
        baseline_sample_standard_deviation=deviation,
        baseline_count=len(values),
    )
