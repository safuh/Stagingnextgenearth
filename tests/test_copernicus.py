"""Tests for the Copernicus ERA5 request planner and adapter boundaries."""

from datetime import UTC, datetime

import pytest

from stagingnextgenearth.climate_ingestion import (
    ClimateBoundingBox,
    ClimatePoint,
    ClimateProviderRequest,
)
from stagingnextgenearth.providers.copernicus import (
    CopernicusERA5Provider,
)


def _request(**kwargs):
    return ClimateProviderRequest(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 2, tzinfo=UTC),
        **kwargs,
    )


def test_era5_builds_bounded_point_request() -> None:
    provider = CopernicusERA5Provider()
    request = _request(point=ClimatePoint(latitude=-1.28, longitude=36.82))
    payload = provider._build_request(request, request.start, request.end)

    assert payload["product_type"] == ["reanalysis"]
    assert payload["variable"] == ["2m_temperature", "total_precipitation"]
    assert payload["year"] == ["2026"]
    assert payload["month"] == ["01"]
    assert payload["day"] == ["01"]
    assert len(payload["time"]) == 24
    assert payload["area"] == pytest.approx([-1.18, 36.72, -1.38, 36.92])
    assert payload["data_format"] == "netcdf"


def test_era5_builds_area_in_cds_north_west_south_east_order() -> None:
    provider = CopernicusERA5Provider()
    request = _request(
        area=ClimateBoundingBox(west=34, south=-5, east=42, north=5)
    )
    payload = provider._build_request(request, request.start, request.end)
    assert payload["area"] == [5, 34, -5, 42]


def test_era5_rejects_unbounded_or_ambiguous_spatial_requests() -> None:
    provider = CopernicusERA5Provider()
    request = _request()
    with pytest.raises(ValueError, match="exactly one"):
        provider._build_request(request, request.start, request.end)


def test_era5_enforces_small_retrieval_window() -> None:
    provider = CopernicusERA5Provider(max_days=2)
    request = ClimateProviderRequest(
        start=datetime(2026, 1, 1, tzinfo=UTC),
        end=datetime(2026, 1, 4, tzinfo=UTC),
        point=ClimatePoint(latitude=-1.28, longitude=36.82),
    )
    with pytest.raises(ValueError, match="2-day limit"):
        provider._validate_area_size(request)
        # The time-window guard runs before any CDS client is constructed.
        provider._validate_window(request)
