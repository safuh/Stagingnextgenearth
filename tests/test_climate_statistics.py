"""Tests for descriptive climate-series statistics."""

import math

import pytest

from stagingnextgenearth.climate_statistics import summarize_climate_series


def test_statistics_are_deterministic_and_include_robust_summaries() -> None:
    result = summarize_climate_series([1, 2, 3, 4, 5, None])
    assert result.count == 5
    assert result.missing_count == 1
    assert result.mean == 3
    assert result.median == 3
    assert result.minimum == 1
    assert result.maximum == 5
    assert result.percentile_05 == pytest.approx(1.2)
    assert result.percentile_25 == 2
    assert result.percentile_75 == 4
    assert result.percentile_95 == pytest.approx(4.8)
    assert result.median_absolute_deviation == 1
    assert result.sample_standard_deviation == pytest.approx(math.sqrt(2.5))
    assert result.standard_error == pytest.approx(math.sqrt(0.5))


def test_empty_series_preserves_missing_count_without_inventing_values() -> None:
    result = summarize_climate_series([None, None])
    assert result.count == 0
    assert result.missing_count == 2
    assert result.mean is None
    assert result.percentile_95 is None
    assert result.sample_standard_deviation is None


def test_single_value_has_no_sample_variance_or_standard_error() -> None:
    result = summarize_climate_series([12.5])
    assert result.mean == 12.5
    assert result.sample_standard_deviation is None
    assert result.standard_error is None
    assert result.median_absolute_deviation == 0


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_observations_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        summarize_climate_series([1.0, value])


@pytest.mark.parametrize("value", [True, False, "2.5"])
def test_non_numeric_observations_are_rejected(value: object) -> None:
    with pytest.raises(TypeError, match="numeric"):
        summarize_climate_series([value])  # type: ignore[list-item]


def test_input_order_does_not_change_statistics() -> None:
    ascending = summarize_climate_series([1, 2, 3, 4, 5])
    descending = summarize_climate_series([5, 4, 3, 2, 1])
    assert ascending == descending
