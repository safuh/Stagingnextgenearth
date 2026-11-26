"""Optional integration tests against synthetic GeoTIFF rasters."""

import pytest

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
)
from stagingnextgenearth.providers.chirps import _decode_geotiff

np = pytest.importorskip("numpy")
rasterio = pytest.importorskip("rasterio")
MemoryFile = rasterio.io.MemoryFile
from_origin = rasterio.transform.from_origin


@pytest.fixture
def synthetic_chirps_geotiff() -> bytes:
    values = np.array(
        [[1.0, 2.0], [3.0, -9999.0]],
        dtype="float32",
    )
    with MemoryFile() as memory_file:
        with memory_file.open(
            driver="GTiff",
            height=2,
            width=2,
            count=1,
            dtype="float32",
            crs="EPSG:4326",
            transform=from_origin(36.7, -1.2, 0.05, 0.05),
            nodata=-9999.0,
        ) as dataset:
            dataset.write(values, 1)
        return memory_file.read()


def test_geotiff_point_extraction_returns_containing_cell(
    synthetic_chirps_geotiff: bytes,
) -> None:
    cells = _decode_geotiff(
        synthetic_chirps_geotiff,
        ClimatePoint(latitude=-1.225, longitude=36.725),
        None,
        10,
    )

    assert cells == [(-1.225, 36.725, 1.0)]


def test_geotiff_area_extraction_returns_cell_centres_and_skips_nodata(
    synthetic_chirps_geotiff: bytes,
) -> None:
    cells = _decode_geotiff(
        synthetic_chirps_geotiff,
        None,
        ClimateBoundingBox(
            west=36.7,
            south=-1.3,
            east=36.8,
            north=-1.2,
        ),
        10,
    )

    assert cells == [
        (-1.225, 36.725, 1.0),
        (-1.225, 36.775, 2.0),
        (-1.275, 36.725, 3.0),
    ]


def test_geotiff_area_extraction_enforces_cell_limit(
    synthetic_chirps_geotiff: bytes,
) -> None:
    with pytest.raises(ValueError, match="exceeds the 1-cell"):
        _decode_geotiff(
            synthetic_chirps_geotiff,
            None,
            ClimateBoundingBox(
                west=36.7,
                south=-1.3,
                east=36.8,
                north=-1.2,
            ),
            1,
        )


def test_geotiff_point_outside_raster_is_rejected(
    synthetic_chirps_geotiff: bytes,
) -> None:
    with pytest.raises(ValueError, match="outside the CHIRPS raster"):
        _decode_geotiff(
            synthetic_chirps_geotiff,
            ClimatePoint(latitude=0.0, longitude=0.0),
            None,
            10,
        )
