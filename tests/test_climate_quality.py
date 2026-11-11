"""Tests for climate unit normalisation and conservative screening."""

import pytest

from stagingnextgenearth.climate_quality import normalize_climate_value


@pytest.mark.parametrize(
    ("variable", "value", "unit", "expected", "canonical"),
    [
        ("precipitation", 2.5, "cm", 25.0, "mm/day"),
        ("precipitation", 1.0, "in", 25.4, "mm/day"),
        ("air_temperature_2m", 300.0, "K", 26.85, "degC"),
        ("air_temperature_2m", 68.0, "degF", 20.0, "degC"),
        ("wind_speed_10m", 36.0, "km/h", 10.0, "m/s"),
        ("surface_pressure", 101325.0, "Pa", 1013.25, "hPa"),
    ],
)
def test_supported_units_normalize_to_canonical_units(
    variable: str, value: float, unit: str, expected: float, canonical: str
) -> None:
    result = normalize_climate_value(variable=variable, value=value, unit=unit)

    assert result.value == pytest.approx(expected)
    assert result.unit == canonical
    assert result.source_value == value
    assert result.source_unit == unit
    assert result.flags == ()
    assert not result.requires_review


def test_screening_flags_out_of_range_value_without_clamping() -> None:
    result = normalize_climate_value(
        variable="relative_humidity", value=125.0, unit="%"
    )

    assert result.value == 125.0
    assert result.flags == ("outside_broad_physical_range",)
    assert result.requires_review


def test_unknown_units_are_preserved_and_flagged() -> None:
    result = normalize_climate_value(
        variable="precipitation", value=4.0, unit="furlongs"
    )

    assert result.value == 4.0
    assert result.unit == "furlongs"
    assert result.flags == ("unsupported_unit",)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_values_are_rejected(value: float) -> None:
    with pytest.raises(ValueError, match="finite"):
        normalize_climate_value(
            variable="precipitation", value=value, unit="mm"
        )


def test_blank_unit_and_boolean_values_are_rejected() -> None:
    with pytest.raises(ValueError, match="blank"):
        normalize_climate_value(variable="precipitation", value=1.0, unit=" ")
    with pytest.raises(TypeError, match="numeric"):
        normalize_climate_value(variable="precipitation", value=True, unit="mm")  # type: ignore[arg-type]
