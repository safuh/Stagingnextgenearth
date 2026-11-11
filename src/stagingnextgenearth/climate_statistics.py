"""Deterministic descriptive statistics for climate observation series.

These summaries are descriptive only. They do not infer causality, fill gaps,
correct bias, or quantify model/measurement uncertainty.
"""
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import fmean, median


@dataclass(frozen=True, slots=True)
class ClimateSeriesStatistics:
    """Descriptive statistics for one homogeneous variable/unit series."""
    count: int
    missing_count: int
    mean: float | None
    median: float | None
    sample_standard_deviation: float | None
    standard_error: float | None
    minimum: float | None
    maximum: float | None
    percentile_05: float | None
    percentile_25: float | None
    percentile_75: float | None
    percentile_95: float | None
    median_absolute_deviation: float | None


def _quantile(sorted_values: list[float], probability: float) -> float:
    """Return a linearly interpolated sample quantile (Hyndman-Fan type 7)."""
    position = (len(sorted_values) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = position - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def summarize_climate_series(values: Iterable[float | None]) -> ClimateSeriesStatistics:
    """Summarize finite observations without imputing missing values."""
    observed: list[float] = []
    missing_count = 0
    for value in values:
        if value is None:
            missing_count += 1
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError("climate observations must be numeric or None")
        numeric = float(value)
        if not isfinite(numeric):
            raise ValueError("climate observations must be finite")
        observed.append(numeric)

    if not observed:
        return ClimateSeriesStatistics(
            count=0, missing_count=missing_count, mean=None, median=None,
            sample_standard_deviation=None, standard_error=None, minimum=None,
            maximum=None, percentile_05=None, percentile_25=None,
            percentile_75=None, percentile_95=None,
            median_absolute_deviation=None,
        )

    ordered = sorted(observed)
    average = fmean(ordered)
    centre = median(ordered)
    deviations = sorted(abs(value - centre) for value in ordered)
    sample_stddev = (
        sqrt(sum((value - average) ** 2 for value in ordered) / (len(ordered) - 1))
        if len(ordered) > 1 else None
    )
    return ClimateSeriesStatistics(
        count=len(ordered), missing_count=missing_count, mean=average, median=centre,
        sample_standard_deviation=sample_stddev,
        standard_error=sample_stddev / sqrt(len(ordered)) if sample_stddev is not None else None,
        minimum=ordered[0], maximum=ordered[-1],
        percentile_05=_quantile(ordered, 0.05), percentile_25=_quantile(ordered, 0.25),
        percentile_75=_quantile(ordered, 0.75), percentile_95=_quantile(ordered, 0.95),
        median_absolute_deviation=median(deviations),
    )
