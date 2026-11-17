"""ERA5-specific climate unit semantics tests."""

import pytest

from stagingnextgenearth.climate_quality import normalize_climate_value


def test_era5_hourly_precipitation_converts_metres_to_mm_not_mm_per_day() -> None:
    result = normalize_climate_value(
        variable="precipitation_hourly", value=0.0012, unit="m"
    )
    assert result.value == pytest.approx(1.2)
    assert result.unit == "mm"
    assert result.conversion == "metres to millimetres hourly accumulation"
    assert result.flags == ()
