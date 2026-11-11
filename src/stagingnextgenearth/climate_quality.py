"""Conservative climate unit normalisation and screening.

Screening flags identify values that need review; they never verify a
measurement or alter the original provider payload.
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NormalizedClimateValue:
    """Canonical value plus transparent conversion and screening metadata."""

    variable: str
    value: float
    unit: str
    source_value: float
    source_unit: str
    conversion: str
    flags: tuple[str, ...]

    @property
    def requires_review(self) -> bool:
        return bool(self.flags)


_RULES: dict[str, tuple[str, float, float]] = {
    "precipitation": ("mm/day", 0.0, 2000.0),
    "air_temperature_2m": ("degC", -100.0, 65.0),
    "relative_humidity": ("%", 0.0, 100.0),
    "wind_speed_10m": ("m/s", 0.0, 150.0),
    "surface_pressure": ("hPa", 0.0, 1200.0),
}

_CONVERSIONS: dict[tuple[str, str], tuple[str, float, float, str]] = {
    ("precipitation", "mm"): ("mm/day", 1.0, 0.0, "mm to mm/day daily accumulation"),
    ("precipitation", "mm/day"): ("mm/day", 1.0, 0.0, "identity"),
    ("precipitation", "cm"): ("mm/day", 10.0, 0.0, "cm to mm/day daily accumulation"),
    ("precipitation", "in"): ("mm/day", 25.4, 0.0, "inches to mm/day daily accumulation"),
    ("air_temperature_2m", "degc"): ("degC", 1.0, 0.0, "identity"),
    ("air_temperature_2m", "c"): ("degC", 1.0, 0.0, "identity"),
    ("air_temperature_2m", "k"): ("degC", 1.0, -273.15, "kelvin to Celsius"),
    ("air_temperature_2m", "degf"): ("degC", 5.0 / 9.0, -32.0 * 5.0 / 9.0, "Fahrenheit to Celsius"),
    ("relative_humidity", "%"): ("%", 1.0, 0.0, "identity"),
    ("relative_humidity", "percent"): ("%", 1.0, 0.0, "identity"),
    ("wind_speed_10m", "m/s"): ("m/s", 1.0, 0.0, "identity"),
    ("wind_speed_10m", "km/h"): ("m/s", 1.0 / 3.6, 0.0, "km/h to m/s"),
    ("surface_pressure", "hpa"): ("hPa", 1.0, 0.0, "identity"),
    ("surface_pressure", "pa"): ("hPa", 0.01, 0.0, "Pa to hPa"),
    ("surface_pressure", "kpa"): ("hPa", 10.0, 0.0, "kPa to hPa"),
}


def normalize_climate_value(
    *, variable: str, value: float, unit: str
) -> NormalizedClimateValue:
    """Convert supported units and flag values outside broad physical ranges.

    Unknown variable/unit combinations remain unchanged and are flagged,
    preventing silent relabelling. Screening is not scientific validation.
    """
    if not unit.strip():
        raise ValueError("unit must not be blank")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError("value must be numeric")
    if not math.isfinite(value):
        raise ValueError("value must be finite")

    normalized_variable = variable.strip().lower()
    normalized_unit = unit.strip().lower()
    conversion = _CONVERSIONS.get((normalized_variable, normalized_unit))
    if conversion is None:
        return NormalizedClimateValue(
            variable=variable,
            value=float(value),
            unit=unit,
            source_value=float(value),
            source_unit=unit,
            conversion="not converted",
            flags=("unsupported_unit",),
        )

    canonical_unit, multiplier, offset, description = conversion
    normalized = float(value) * multiplier + offset
    rule = _RULES.get(normalized_variable)
    flags: list[str] = []
    if rule is None:
        flags.append("unsupported_variable")
    else:
        expected_unit, lower, upper = rule
        if canonical_unit != expected_unit:
            flags.append("canonical_unit_mismatch")
        elif normalized < lower or normalized > upper:
            flags.append("outside_broad_physical_range")

    return NormalizedClimateValue(
        variable=normalized_variable,
        value=normalized,
        unit=canonical_unit,
        source_value=float(value),
        source_unit=unit,
        conversion=description,
        flags=tuple(flags),
    )
