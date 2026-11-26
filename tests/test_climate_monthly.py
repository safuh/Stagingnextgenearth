"""Tests for completeness-aware monthly precipitation aggregation."""

from datetime import date

import pytest

from stagingnextgenearth.climate_monthly import complete_monthly_total


def test_monthly_total_averages_duplicate_daily_records_without_double_counting() -> None:
    daily = {
        date(2024, 1, 1): [2.0, 4.0],
        date(2024, 1, 2): [6.0],
    }
    result = complete_monthly_total(
        daily, 2024, 1, minimum_completeness=2 / 31
    )
    assert result is not None
    total, observed_days, expected_days, completeness = result
    assert total == 9
    assert observed_days == 2
    assert expected_days == 31
    assert completeness == pytest.approx(2 / 31)


def test_incomplete_month_is_excluded_without_imputation() -> None:
    daily = {date(2023, 2, day): [1.0] for day in range(1, 26)}
    assert complete_monthly_total(daily, 2023, 2, minimum_completeness=0.9) is None


def test_leap_year_month_uses_29_expected_days() -> None:
    daily = {date(2024, 2, day): [1.0] for day in range(1, 28)}
    result = complete_monthly_total(daily, 2024, 2, minimum_completeness=0.9)
    assert result is not None
    assert result[1:3] == (27, 29)


@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf")])
def test_invalid_daily_precipitation_is_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite and non-negative"):
        complete_monthly_total(
            {date(2024, 1, 1): [value]}, 2024, 1, minimum_completeness=0.01
        )
