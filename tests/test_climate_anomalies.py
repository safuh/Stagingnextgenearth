"""Tests for transparent standardized precipitation anomaly calculations."""

import math

import pytest

from stagingnextgenearth.climate_anomalies import standardized_anomaly


def test_standardized_anomaly_reports_reproducible_baseline_statistics() -> None:
    result = standardized_anomaly(15, [6, 8, 10, 12, 14, 16, 18, 20, 22, 24])
    assert result.method == "sample_standardized_anomaly_z_score"
    assert result.baseline_count == 10
    assert result.baseline_mean == 15
    assert result.baseline_sample_standard_deviation == pytest.approx(
        math.sqrt(36.6666666667)
    )
    assert result.value == pytest.approx(0)


def test_anomaly_is_not_given_a_drought_classification() -> None:
    result = standardized_anomaly(0, [10, 12, 14, 16, 18, 20, 22, 24, 26, 28])
    assert result.value < 0
    assert result.classification == "unclassified"


def test_insufficient_baseline_is_rejected() -> None:
    with pytest.raises(ValueError, match="complete baseline"):
        standardized_anomaly(12, [1, 2, 3, 4, 5, 6, 7, 8, 9])


def test_zero_variance_baseline_is_rejected() -> None:
    with pytest.raises(ValueError, match="variability is zero"):
        standardized_anomaly(12, [4] * 10)


@pytest.mark.parametrize("value", [-1, float("nan"), float("inf")])
def test_invalid_precipitation_totals_are_rejected(value: float) -> None:
    with pytest.raises(ValueError):
        standardized_anomaly(value, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])


@pytest.mark.parametrize("value", [True, "2.0"])
def test_non_numeric_totals_are_rejected(value: object) -> None:
    with pytest.raises(TypeError, match="numeric"):
        standardized_anomaly(value, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10])  # type: ignore[arg-type]


def test_custom_minimum_baseline_count_is_honoured() -> None:
    result = standardized_anomaly(10, [1, 2, 3, 4], minimum_baseline_count=4)
    assert result.baseline_count == 4
