"""CHIRPS v3 daily precipitation raster adapter.

The adapter reads the Climate Hazards Center's daily GeoTIFF archive. It
extracts the containing pixel for point requests and cell centres inside a
bounding box for area requests. The default decoder requires rasterio.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import TypeAlias

import httpx

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimateMeasurement,
    ClimatePoint,
    ClimateProviderRequest,
)

CHIRPS_V3_DAILY_BASE_URL = (
    "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final"
)
CHIRPS_V3_CITATION = (
    "Climate Hazards Center Infrared Precipitation with Stations version 3 "
    "(CHIRPS3), https://doi.org/10.15780/G2JQ0P"
)
CHIRPS_V3_LICENSE = "CC-BY-4.0"
CHIRPS_V3_RESOLUTION_DEGREES = 0.05
_VARIANT_START_DATES = {"rnl": date(1981, 1, 1), "sat": date(1998, 1, 1)}
_MISSING_VALUES = {-9999.0, -999.0}
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

RasterCell: TypeAlias = tuple[float, float, float]


class CHIRPSProvider:
    """Fetch CHIRPS v3 daily rainfall for a point or bounding box.

    variant selects rnl (ERA5-disaggregated reanalysis) or sat
    (IMERG-disaggregated satellite) daily estimates. Values are daily
    precipitation accumulations in millimetres. The date is a product date
    label, not a guaranteed common gauge-observation window.
    """

    provider_id = "chirps-v3"
    source_name = "CHIRPS v3"
    licence = CHIRPS_V3_LICENSE

    def __init__(
        self,
        *,
        variant: str = "rnl",
        timeout_seconds: float = 60.0,
        max_retries: int = 2,
        max_days: int = 366,
        max_area_cells: int = 10_000,
        max_raster_bytes: int = 256 * 1024 * 1024,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if variant not in {"rnl", "sat"}:
            raise ValueError("CHIRPS v3 variant must be 'rnl' or 'sat'")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not 0 <= max_retries <= 5:
            raise ValueError("max_retries must be between 0 and 5")
        if max_days < 1 or max_area_cells < 1 or max_raster_bytes < 1:
            raise ValueError("request limits must be positive")
        self.variant = variant
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.max_days = max_days
        self.max_area_cells = max_area_cells
        self.max_raster_bytes = max_raster_bytes
        self._client = client

    async def fetch(
        self, request: ClimateProviderRequest
    ) -> AsyncIterator[ClimateMeasurement]:
        """Yield daily rainfall measurements extracted from CHIRPS rasters."""
        if (request.point is None) == (request.area is None):
            raise ValueError("CHIRPS requests require exactly one point or bounding box")

        start_utc = request.start.astimezone(UTC)
        end_utc = request.end.astimezone(UTC)
        first_date = start_utc.date()
        last_date = (end_utc - timedelta(microseconds=1)).date()
        day_count = (last_date - first_date).days + 1
        if day_count < 1:
            raise ValueError("request must cover at least one calendar day")
        if day_count > self.max_days:
            raise ValueError(f"CHIRPS request exceeds the {self.max_days}-day limit")
        earliest_date = _VARIANT_START_DATES[self.variant]
        if first_date < earliest_date:
            raise ValueError(
                f"CHIRPS v3 {self.variant} data starts on {earliest_date.isoformat()}"
            )

        if self._client is not None:
            for day_offset in range(day_count):
                observed_date = first_date + timedelta(days=day_offset)
                content = await self._download_day(self._client, observed_date)
                cells = await asyncio.to_thread(
                    _decode_geotiff, content, request.point, request.area,
                    self.max_area_cells
                )
                for measurement in _measurements_for_day(
                    cells, observed_date, self.variant, request.point is not None
                ):
                    yield measurement
            return

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds, connect=10.0),
            headers={"User-Agent": "NextGenForEarth/0.1 climate-ingestion"},
        ) as client:
            for day_offset in range(day_count):
                observed_date = first_date + timedelta(days=day_offset)
                content = await self._download_day(client, observed_date)
                cells = await asyncio.to_thread(
                    _decode_geotiff, content, request.point, request.area,
                    self.max_area_cells
                )
                for measurement in _measurements_for_day(
                    cells, observed_date, self.variant, request.point is not None
                ):
                    yield measurement

    async def _download_day(self, client: httpx.AsyncClient, observed_date: date) -> bytes:
        date_text = observed_date.strftime("%Y.%m.%d")
        url = (
            f"{CHIRPS_V3_DAILY_BASE_URL}/{self.variant}/{observed_date.year}/"
            f"chirps-v3.0.{self.variant}.{date_text}.tif"
        )
        for attempt in range(self.max_retries + 1):
            retry_delay: float | None = None
            try:
                async with client.stream("GET", url) as response:
                    if response.status_code in _RETRYABLE_STATUS_CODES:
                        if attempt >= self.max_retries:
                            response.raise_for_status()
                        retry_after = response.headers.get("Retry-After")
                        try:
                            retry_delay = (
                                min(max(float(retry_after), 0.0), 5.0)
                                if retry_after
                                else 0.5 * (2**attempt)
                            )
                        except ValueError:
                            retry_delay = 0.5 * (2**attempt)
                    elif response.status_code == 404:
                        raise ValueError(
                            f"CHIRPS v3 {self.variant} raster is unavailable for {observed_date}"
                        )
                    else:
                        response.raise_for_status()
                        content = bytearray()
                        async for chunk in response.aiter_bytes():
                            if len(content) + len(chunk) > self.max_raster_bytes:
                                raise ValueError(
                                    "CHIRPS raster exceeds the configured download-size "
                                    f"limit ({self.max_raster_bytes} bytes)"
                                )
                            content.extend(chunk)
                        if not content:
                            raise ValueError(
                                f"CHIRPS returned an empty raster for {observed_date}"
                            )
                        return bytes(content)
            except httpx.TransportError:
                if attempt >= self.max_retries:
                    raise
                await asyncio.sleep(0.5 * (2**attempt))
                continue
            if retry_delay is not None:
                await asyncio.sleep(retry_delay)
                continue
        raise RuntimeError("CHIRPS download exhausted its retry budget")

def _measurements_for_day(
    cells: list[RasterCell],
    observed_date: date,
    variant: str,
    is_point: bool,
) -> list[ClimateMeasurement]:
    measurements: list[ClimateMeasurement] = []
    for latitude, longitude, value in cells:
        if value in _MISSING_VALUES:
            continue
        measurements.append(
            ClimateMeasurement(
                provider_record_id=(
                    f"{variant}:{observed_date.isoformat()}:"
                    f"{latitude:.5f}:{longitude:.5f}"
                ),
                observed_at=datetime.combine(observed_date, datetime.min.time(), UTC),
                variable="precipitation",
                value=value,
                unit="mm/day",
                latitude=latitude,
                longitude=longitude,
                metadata={
                    "provider_product": "CHIRPS v3 daily",
                    "provider_variant": variant,
                    "grid_resolution_degrees": CHIRPS_V3_RESOLUTION_DEGREES,
                    "spatial_extraction": (
                        "containing_pixel" if is_point else "cell_centres_in_bbox"
                    ),
                    "time_label_convention": (
                        "CHIRPS daily product date; not a uniform gauge observation window"
                    ),
                    "citation": CHIRPS_V3_CITATION,
                    "licence": CHIRPS_V3_LICENSE,
                },
            )
        )
    return measurements


def _decode_geotiff(
    content: bytes,
    point: ClimatePoint | None,
    area: ClimateBoundingBox | None,
    max_area_cells: int,
) -> list[RasterCell]:
    """Decode a GeoTIFF with rasterio and return selected cell-centre values."""
    try:
        import numpy as np
        import rasterio
        from rasterio.io import MemoryFile
        from rasterio.windows import Window, from_bounds
    except ImportError as exc:
        raise RuntimeError(
            "CHIRPS GeoTIFF decoding requires rasterio and numpy; install "
            "them in the climate-ingestion environment"
        ) from exc

    with MemoryFile(content) as memory_file:
        with memory_file.open() as dataset:
            if dataset.crs is None or dataset.crs.to_epsg() != 4326:
                raise ValueError("CHIRPS raster must use the WGS84 coordinate reference system")

            if point is not None:
                row, column = dataset.index(point.longitude, point.latitude)
                if row < 0 or column < 0 or row >= dataset.height or column >= dataset.width:
                    raise ValueError("requested point is outside the CHIRPS raster coverage")
                values = dataset.read(
                    1, window=((row, row + 1), (column, column + 1)), masked=True
                )
                if values.size == 0 or np.ma.is_masked(values[0, 0]):
                    return []
                longitude, latitude = dataset.xy(row, column)
                return [
                    (
                        round(float(latitude), 5),
                        round(float(longitude), 5),
                        float(values[0, 0]),
                    )
                ]

            if area is None:
                raise ValueError("a point or bounding box is required for raster extraction")
            window = from_bounds(
                area.west, area.south, area.east, area.north, dataset.transform
            )
            window = window.round_offsets().round_lengths()
            try:
                window = window.intersection(Window(0, 0, dataset.width, dataset.height))
            except rasterio.errors.WindowError as exc:
                raise ValueError(
                    "requested bounding box does not intersect CHIRPS coverage"
                ) from exc
            if window.width <= 0 or window.height <= 0:
                raise ValueError("requested bounding box does not intersect CHIRPS coverage")
            if window.width * window.height > max_area_cells:
                raise ValueError(
                    f"CHIRPS area request exceeds the {max_area_cells}-cell extraction limit"
                )

            values = dataset.read(1, window=window, masked=True)
            row_offset = int(window.row_off)
            column_offset = int(window.col_off)
            cells: list[RasterCell] = []
            for local_row in range(values.shape[0]):
                for local_column in range(values.shape[1]):
                    raw_value = values[local_row, local_column]
                    if np.ma.is_masked(raw_value):
                        continue
                    row = row_offset + local_row
                    column = column_offset + local_column
                    longitude, latitude = dataset.xy(row, column)
                    if not (
                        area.south <= latitude <= area.north
                        and area.west <= longitude <= area.east
                    ):
                        continue
                    cells.append(
                        (
                            round(float(latitude), 5),
                            round(float(longitude), 5),
                            float(raw_value),
                        )
                    )
            return cells
