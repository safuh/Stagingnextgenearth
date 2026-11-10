"""Provider-neutral contracts for climate data ingestion.

Provider adapters translate source-specific payloads into these validated
measurement and request types before persistence. Fetching a measurement does
not imply that it has passed platform quality review.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator, model_validator


class ClimatePoint(BaseModel):
    """WGS84 point location expressed as latitude and longitude."""

    model_config = ConfigDict(frozen=True)

    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)


class ClimateBoundingBox(BaseModel):
    """WGS84 bounding box expressed as west, south, east, north."""

    model_config = ConfigDict(frozen=True)

    west: FiniteFloat = Field(ge=-180, le=180)
    south: FiniteFloat = Field(ge=-90, le=90)
    east: FiniteFloat = Field(ge=-180, le=180)
    north: FiniteFloat = Field(ge=-90, le=90)

    @model_validator(mode="after")
    def validate_bounds(self) -> "ClimateBoundingBox":
        if self.west >= self.east:
            raise ValueError("west must be less than east; antimeridian boxes are not supported")
        if self.south >= self.north:
            raise ValueError("south must be less than north")
        return self


class ClimateProviderRequest(BaseModel):
    """A bounded, timezone-aware request for a provider's observations."""

    model_config = ConfigDict(frozen=True)

    start: datetime
    end: datetime
    point: ClimatePoint | None = None
    area: ClimateBoundingBox | None = None

    @field_validator("start", "end")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("provider request timestamps must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_period(self) -> "ClimateProviderRequest":
        if self.end <= self.start:
            raise ValueError("end must be later than start")
        if self.point is not None and self.area is not None:
            raise ValueError("request cannot specify both a point and a bounding box")
        return self


class ClimateMeasurement(BaseModel):
    """Canonical provider measurement with source-level identity and provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider_record_id: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    variable: str = Field(min_length=2, max_length=80)
    value: FiniteFloat
    unit: str = Field(min_length=1, max_length=32)
    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("provider_record_id", "variable", "unit")
    @classmethod
    def require_non_whitespace(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be blank")
        return cleaned

    @field_validator("observed_at")
    @classmethod
    def require_observation_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ClimateProvider(Protocol):
    """Interface implemented by climate data provider adapters."""

    provider_id: str
    source_name: str
    licence: str | None

    def fetch(
        self, request: ClimateProviderRequest
    ) -> AsyncIterator[ClimateMeasurement]:
        """Yield normalized measurements for the requested period and area."""
        ...
