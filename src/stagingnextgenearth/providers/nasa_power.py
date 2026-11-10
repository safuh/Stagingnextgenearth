"""NASA POWER daily point-data adapter.

The adapter requests UTC daily data and normalizes POWER parameter series into
the platform's provider-neutral climate measurement contract.
"""

import asyncio
from collections.abc import AsyncIterator, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from stagingnextgenearth.climate_ingestion import (
    ClimateMeasurement,
    ClimatePoint,
    ClimateProviderRequest,
)

NASA_POWER_DAILY_POINT_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)
NASA_POWER_CITATION = (
    "NASA POWER Project, Prediction Of Worldwide Energy Resources "
    "(https://power.larc.nasa.gov/)"
)
_MISSING_VALUE = -999.0
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class NASAPowerProvider:
    """Fetch daily NASA POWER meteorological observations for one WGS84 point.

    parameter_variables maps NASA parameter identifiers to canonical platform
    variable names. Values are retained in the units returned by POWER; the
    response unit is stored with every measurement.
    """

    provider_id = "nasa-power"
    source_name = "NASA POWER"
    licence = None

    def __init__(
        self,
        *,
        parameter_variables: Mapping[str, str] | None = None,
        community: str = "AG",
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.parameter_variables = dict(
            parameter_variables
            or {
                "PRECTOTCORR": "precipitation",
                "T2M": "air_temperature_2m",
            }
        )
        if not self.parameter_variables:
            raise ValueError("at least one NASA POWER parameter is required")
        if len(self.parameter_variables) > 20:
            raise ValueError("NASA POWER point requests support at most 20 parameters")
        if any(not key.strip() or not value.strip() for key, value in self.parameter_variables.items()):
            raise ValueError("parameter identifiers and variable names must not be blank")
        if not community.strip():
            raise ValueError("NASA POWER community must not be blank")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if max_retries < 0 or max_retries > 5:
            raise ValueError("max_retries must be between 0 and 5")
        self.community = community.upper()
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self._client = client

    async def fetch(
        self, request: ClimateProviderRequest
    ) -> AsyncIterator[ClimateMeasurement]:
        """Yield UTC daily measurements for a point request."""
        point = self._require_point(request)
        start_utc = request.start.astimezone(UTC)
        end_utc = request.end.astimezone(UTC)
        start_date = start_utc.date()
        # The provider contract uses an exclusive end; POWER's API end date is inclusive.
        end_date = (end_utc - timedelta(microseconds=1)).date()
        if end_date < start_date:
            raise ValueError("request must cover at least one calendar day")

        params = {
            "parameters": ",".join(self.parameter_variables),
            "community": self.community,
            "longitude": str(point.longitude),
            "latitude": str(point.latitude),
            "start": start_date.strftime("%Y%m%d"),
            "end": end_date.strftime("%Y%m%d"),
            "time-standard": "UTC",
            "format": "JSON",
        }

        if self._client is not None:
            payload = await self._request_payload(self._client, params)
        else:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout_seconds, connect=5.0)
            ) as client:
                payload = await self._request_payload(client, params)

        parameter_values = self._extract_parameter_values(payload)
        parameter_metadata = payload.get("parameters", {})
        geometry = payload.get("geometry", {})
        coordinates = geometry.get("coordinates", [])
        latitude = float(coordinates[1]) if len(coordinates) >= 2 else point.latitude
        longitude = float(coordinates[0]) if len(coordinates) >= 2 else point.longitude

        for parameter, variable in self.parameter_variables.items():
            values = parameter_values.get(parameter)
            if not isinstance(values, dict):
                raise ValueError(f"NASA POWER response is missing parameter {parameter!r}")
            details = parameter_metadata.get(parameter, {})
            unit = details.get("units") if isinstance(details, dict) else None
            if not isinstance(unit, str) or not unit.strip():
                raise ValueError(f"NASA POWER response is missing units for {parameter!r}")
            long_name = details.get("longname") if isinstance(details, dict) else None

            for date_key, raw_value in sorted(values.items()):
                try:
                    observed_date = datetime.strptime(date_key, "%Y%m%d").date()
                    numeric_value = float(raw_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"NASA POWER returned an invalid {parameter} daily value"
                    ) from exc
                if observed_date < start_date or observed_date > end_date:
                    continue
                if numeric_value == _MISSING_VALUE:
                    continue

                record_id = (
                    f"{parameter}:{observed_date.isoformat()}:"
                    f"{latitude:.5f}:{longitude:.5f}"
                )
                yield ClimateMeasurement(
                    provider_record_id=record_id,
                    observed_at=datetime.combine(observed_date, datetime.min.time(), UTC),
                    variable=variable,
                    value=numeric_value,
                    unit=unit,
                    latitude=latitude,
                    longitude=longitude,
                    metadata={
                        "provider_parameter": parameter,
                        "provider_parameter_name": long_name,
                        "time_standard": "UTC",
                        "citation": NASA_POWER_CITATION,
                    },
                )

    @staticmethod
    def _require_point(request: ClimateProviderRequest) -> ClimatePoint:
        if request.point is None:
            raise ValueError("NASA POWER daily point requests require request.point")
        if request.area is not None:
            raise ValueError("NASA POWER point adapter does not accept bounding-box requests")
        return request.point

    async def _request_payload(
        self, client: httpx.AsyncClient, params: dict[str, str]
    ) -> dict[str, Any]:
        for attempt in range(self.max_retries + 1):
            response = await client.get(NASA_POWER_DAILY_POINT_URL, params=params)
            if response.status_code in _RETRYABLE_STATUS_CODES and attempt < self.max_retries:
                retry_after = response.headers.get("Retry-After")
                try:
                    delay = (
                        min(max(float(retry_after), 0.0), 5.0)
                        if retry_after
                        else 0.5 * (2**attempt)
                    )
                except ValueError:
                    delay = 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue
            response.raise_for_status()
            try:
                payload = response.json()
            except ValueError as exc:
                raise ValueError("NASA POWER returned invalid JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("NASA POWER returned an unexpected response document")
            messages = payload.get("messages", [])
            if messages:
                raise ValueError(f"NASA POWER reported a provider error: {messages!r}"[:500])
            return payload
        raise RuntimeError("NASA POWER request exhausted its retry budget")

    @staticmethod
    def _extract_parameter_values(payload: dict[str, Any]) -> dict[str, Any]:
        properties = payload.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("NASA POWER response is missing properties")
        parameters = properties.get("parameter")
        if not isinstance(parameters, dict):
            raise ValueError("NASA POWER response is missing daily parameter values")
        return parameters
