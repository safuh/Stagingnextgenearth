"""Monthly precipitation totals and comparable standardized anomalies.

Only complete-enough daily accumulations at one exact grid/station coordinate
are compared. This is a descriptive z-score, not SPI or a drought category.
"""

from calendar import monthrange
from datetime import date
from math import isfinite

from stagingnextgenearth.climate_anomalies import StandardizedAnomaly, standardized_anomaly


def month_days(year: int, month: int) -> int:
    return monthrange(year, month)[1]


def complete_monthly_total(
    daily_values: dict[date, list[float]],
    year: int,
    month: int,
    *,
    minimum_completeness: float = 0.9,
) -> tuple[float, int, int, float] | None:
    """Return total/count/expected/completeness, or None for incomplete month.

    Multiple same-day records are averaged before summing to avoid double
    counting overlapping provider or station submissions.
    """
    if not 0 < minimum_completeness <= 1:
        raise ValueError("minimum_completeness must be in (0, 1]")
    expected = month_days(year, month)
    daily_means: list[float] = []
    for day in range(1, expected + 1):
        values = daily_values.get(date(year, month, day), [])
        if not values:
            continue
        if any(not isfinite(value) or value < 0 for value in values):
            raise ValueError("daily precipitation values must be finite and non-negative")
        daily_means.append(sum(values) / len(values))
    count = len(daily_means)
    completeness = count / expected
    if completeness < minimum_completeness:
        return None
    return sum(daily_means), count, expected, completeness


def monthly_anomaly(
    observed_total: float,
    baseline_totals: list[float],
    *,
    minimum_baseline_count: int = 10,
) -> StandardizedAnomaly:
    """Expose the shared anomaly method with an explicit monthly contract."""
    return standardized_anomaly(
        observed_total, baseline_totals, minimum_baseline_count=minimum_baseline_count
    )
