"""Copernicus Climate Data Store ERA5 single-levels adapter.

This adapter uses the official CDS API client and normalizes NetCDF output into
provider-neutral measurements. It deliberately bounds retrieval windows and
spatial output; it does not bypass dataset licence acceptance or CDS account
requirements.
"""

import asyncio
import calendar
import tempfile
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from stagingnextgenearth.climate_ingestion import (
    ClimateMeasurement,
    ClimatePoint,
    ClimateProviderRequest,
)

ERA5_SINGLE_LEVELS_DATASET = "reanalysis-era5-single-levels"
COPERNICUS_CITATION = (
    "Copernicus Climate Change Service (C3S), ERA5 hourly data on single levels, "
    "https://doi.org/10.24381/cds.adbb2d47"
)

_DEFAULT_VARIABLES = {
    "2m_temperature": "air_temperature_2m",
    "total_precipitation": "precipitation",
}


class CopernicusERA5Provider:
    """Retrieve ERA5 hourly single-level fields for a point or small area.

    The official `cdsapi` client reads credentials from the standard CDS API
    configuration. Install the `climate-copernicus` extra and configure the
    token outside application source control. Dataset terms must be accepted
    in the CDS web interface before retrieval.
    """

    provider_id = "copernicus-era5"
    source_name = "Copernicus C3S ERA5"
    licence = "Copernicus licence; see the dataset terms of use"

    def __init__(
        self,
        *,
        variables: Mapping[str, str] | None = None,
        max_days: int = 7,
        max_grid_cells: int = 2500,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        selected = dict(variables or _DEFAULT_VARIABLES)
        if not selected or len(selected) > 10:
            raise ValueError("ERA5 requires between 1 and 10 variables")
        if any(not key.strip() or not value.strip() for key, value in selected.items()):
            raise ValueError("ERA5 variable identifiers and names must not be blank")
        if not 1 <= max_days <= 31 or max_grid_cells < 1:
            raise ValueError("ERA5 request limits are invalid")
        self.variables = selected
        self.max_days = max_days
        self.max_grid_cells = max_grid_cells
        self._client_factory = client_factory

    async def fetch(self, request: ClimateProviderRequest):
        """Yield ERA5 hourly measurements from a bounded CDS retrieval."""
        if (request.point is None) == (request.area is None):
            raise ValueError("ERA5 requests require exactly one point or bounding box")
        start = request.start.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
        end = request.end.astimezone(UTC)
        last_instant = end - timedelta(microseconds=1)
        if last_instant < start:
            raise ValueError("request must cover at least one hourly interval")
        first_day = start.date()
        last_day = last_instant.date()
        day_count = (last_day - first_day).days + 1
        if day_count > self.max_days:
            raise ValueError(f"ERA5 request exceeds the {self.max_days}-day limit")

        cds_request = self._build_request(request, start, last_instant)
        content = await asyncio.to_thread(self._retrieve, cds_request)
        for item in self._decode(content, request, start, end):
            yield item

    def _build_request(
        self, request: ClimateProviderRequest, start: datetime, last: datetime
    ) -> dict[str, object]:
        days = [start.date() + timedelta(days=i) for i in range((last.date() - start.date()).days + 1)]
        result: dict[str, object] = {
            "product_type": ["reanalysis"],
            "variable": list(self.variables),
            "year": sorted({f"{day.year:04d}" for day in days}),
            "month": sorted({f"{day.month:02d}" for day in days}),
            "day": sorted({f"{day.day:02d}" for day in days}),
            "time": [f"{hour:02d}:00" for hour in range(24)],
            "data_format": "netcdf",
            "download_format": "unarchived",
        }
        if request.point is not None:
            point = request.point
            # A small envelope is used because ERA5 is a grid product.
            result["area"] = [
                min(90.0, point.latitude + 0.1),
                max(-180.0, point.longitude - 0.1),
                max(-90.0, point.latitude - 0.1),
                min(180.0, point.longitude + 0.1),
            ]
        else:
            assert request.area is not None
            result["area"] = [
                request.area.north,
                request.area.west,
                request.area.south,
                request.area.east,
            ]
        return result

    def _retrieve(self, request: dict[str, object]) -> bytes:
        factory = self._client_factory
        if factory is None:
            try:
                import cdsapi
            except ImportError as exc:
                raise RuntimeError(
                    "Copernicus ERA5 retrieval requires the climate-copernicus extra"
                ) from exc
            factory = cdsapi.Client
        with tempfile.TemporaryDirectory(prefix="nextgen-era5-") as directory:
            target = Path(directory) / "era5.nc"
            factory().retrieve(ERA5_SINGLE_LEVELS_DATASET, request, str(target))
            if not target.is_file() or target.stat().st_size == 0:
                raise ValueError("Copernicus CDS completed without a NetCDF result")
            return target.read_bytes()

    def _decode(
        self,
        content: bytes,
        request: ClimateProviderRequest,
        start: datetime,
        end: datetime,
    ) -> list[ClimateMeasurement]:
        try:
            import xarray as xr
        except ImportError as exc:
            raise RuntimeError(
                "ERA5 NetCDF decoding requires xarray; install climate-copernicus"
            ) from exc
        import io

        measurements: list[ClimateMeasurement] = []
        with xr.open_dataset(io.BytesIO(content)) as dataset:
            latitude_name = "latitude" if "latitude" in dataset.coords else "lat"
            longitude_name = "longitude" if "longitude" in dataset.coords else "lon"
            time_name = "valid_time" if "valid_time" in dataset.coords else "time"
            for source_variable, canonical_variable in self.variables.items():
                if source_variable not in dataset.data_vars:
                    raise ValueError(
                        f"Copernicus NetCDF is missing variable {source_variable!r}"
                    )
                field = dataset[source_variable]
                unit = str(field.attrs.get("units", "")).strip()
                if not unit:
                    raise ValueError(
                        f"Copernicus NetCDF is missing units for {source_variable!r}"
                    )
                for timestamp in dataset[time_name].values:
                    observed_at = datetime.fromtimestamp(
                        timestamp.astype("datetime64[s]").astype(int), UTC
                    )
                    if observed_at < start or observed_at >= end:
                        continue
                    slice_ = field.sel({time_name: timestamp})
                    latitudes = slice_[latitude_name].values
                    longitudes = slice_[longitude_name].values
                    if request.point is not None:
                        slice_ = slice_.sel(
                            {
                                latitude_name: request.point.latitude,
                                longitude_name: request.point.longitude,
                            },
                            method="nearest",
                        )
                        latitudes = [float(slice_[latitude_name].values)]
                        longitudes = [float(slice_[longitude_name].values)]
                    cells = slice_.size
                    if cells > self.max_grid_cells:
                        raise ValueError(
                            f"ERA5 area exceeds the {self.max_grid_cells}-cell limit"
                        )
                    values = slice_.values
                    if getattr(values, "ndim", 0) == 0:
                        values = [[values.item()]]
                        latitudes = [float(latitudes)]
                        longitudes = [float(longitudes)]
                    elif values.ndim == 1:
                        values = values.reshape(1, -1)
                        latitudes = [float(latitudes[0])]
                    for row, latitude in enumerate(latitudes):
                        for column, longitude in enumerate(longitudes):
                            value = float(values[row][column])
                            if not (-float("inf") < value < float("inf")):
                                continue
                            record_id = (
                                f"{source_variable}:{observed_at.isoformat()}:"
                                f"{float(latitude):.5f}:{float(longitude):.5f}"
                            )
                            measurements.append(
                                ClimateMeasurement(
                                    provider_record_id=record_id,
                                    observed_at=observed_at,
                                    variable=canonical_variable,
                                    value=value,
                                    unit=unit,
                                    latitude=float(latitude),
                                    longitude=float(longitude),
                                    metadata={
                                        "provider_dataset": ERA5_SINGLE_LEVELS_DATASET,
                                        "provider_variable": source_variable,
                                        "citation": COPERNICUS_CITATION,
                                        "licence": self.licence,
                                        "temporal_resolution": "hourly",
                                        "spatial_resolution": "ERA5 native grid",
                                    },
                                )
                            )
        return measurements
