"""Tenant-scoped climate screening reports and explicit missing-data coverage."""

from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import ClimateObservation, Membership

from .dependencies import get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-observations",
    tags=["climate"],
)


class FlaggedObservation(BaseModel):
    """A bounded screening-report row without exposing arbitrary provider metadata."""

    id: str
    observed_at: datetime
    variable: str
    value: float
    unit: str
    latitude: float
    longitude: float
    source: str
    quality_status: str
    flags: list[str]


class FlaggedObservationReport(BaseModel):
    """Screening flags found in a bounded, tenant-scoped scan."""

    items: list[FlaggedObservation]
    scanned_count: int
    matched_count: int
    offset: int
    limit: int
    scan_truncated: bool


@router.get("/flagged", response_model=FlaggedObservationReport)
async def list_flagged_climate_observations(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    flag: str | None = Query(default=None, min_length=2, max_length=80),
    quality_status: Literal["pending", "verified", "rejected"] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    offset: int = Query(default=0, ge=0, le=10_000),
    limit: int = Query(default=100, ge=1, le=200),
) -> FlaggedObservationReport:
    """Report provider screening flags; flags are not scientific validation."""
    if start is not None and (start.tzinfo is None or start.utcoffset() is None):
        from fastapi import HTTPException, status

        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "start must include a timezone"
        )
    if end is not None and (end.tzinfo is None or end.utcoffset() is None):
        from fastapi import HTTPException, status

        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end must include a timezone"
        )
    if start is not None and end is not None and end < start:
        from fastapi import HTTPException, status

        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end must not precede start"
        )

    statement = select(ClimateObservation).where(
        ClimateObservation.organization_id == organization_id,
        ClimateObservation.metadata_json.is_not(None),
    )
    if quality_status is not None:
        statement = statement.where(ClimateObservation.quality_status == quality_status)
    if start is not None:
        statement = statement.where(ClimateObservation.observed_at >= start)
    if end is not None:
        statement = statement.where(ClimateObservation.observed_at < end)

    # Bound JSON screening evaluation in application code for consistent
    # PostgreSQL/SQLite behaviour. The response discloses when the scan cap
    # was reached rather than presenting a partial result as exhaustive.
    rows = list(
        (
            await session.scalars(
                statement.order_by(ClimateObservation.observed_at.desc())
                .limit(5001)
            )
        ).all()
    )
    scan_truncated = len(rows) > 5000
    rows = rows[:5000]
    matches: list[FlaggedObservation] = []
    for observation in rows:
        metadata = observation.metadata_json or {}
        raw_flags = metadata.get("quality_screening_flags", [])
        if not isinstance(raw_flags, list):
            continue
        flags = sorted(
            {
                item.strip()
                for item in raw_flags
                if isinstance(item, str) and item.strip()
            }
        )
        if not flags or (flag is not None and flag not in flags):
            continue
        matches.append(
            FlaggedObservation(
                id=observation.id,
                observed_at=observation.observed_at,
                variable=observation.variable,
                value=observation.value,
                unit=observation.unit,
                latitude=observation.latitude,
                longitude=observation.longitude,
                source=observation.source,
                quality_status=observation.quality_status,
                flags=flags,
            )
        )

    return FlaggedObservationReport(
        items=matches[offset : offset + limit],
        scanned_count=len(rows),
        matched_count=len(matches),
        offset=offset,
        limit=limit,
        scan_truncated=scan_truncated,
    )


class DailyCoverageReport(BaseModel):
    """Daily completeness report; missing dates are never imputed."""

    variable: str
    latitude: float
    longitude: float
    start_date: date
    end_date: date
    expected_days: int
    observed_days: int
    missing_days: list[date]
    coverage_ratio: float
    missing_data_policy: Literal["report_only_no_imputation"] = (
        "report_only_no_imputation"
    )


@router.get("/coverage", response_model=DailyCoverageReport)
async def climate_daily_coverage(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    variable: str = Query(min_length=2, max_length=80),
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    start_date: date = Query(),
    end_date: date = Query(),
) -> DailyCoverageReport:
    """Report daily gaps for one station; no synthetic observations are created."""
    from fastapi import HTTPException, status

    if end_date < start_date:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "end_date must be on or after start_date",
        )
    expected_days = (end_date - start_date).days + 1
    if expected_days > 366:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "coverage windows are limited to 366 calendar days",
        )

    start_at = datetime.combine(start_date, time.min, tzinfo=UTC)
    end_at = datetime.combine(end_date + timedelta(days=1), time.min, tzinfo=UTC)
    timestamps = (
        await session.scalars(
            select(ClimateObservation.observed_at).where(
                ClimateObservation.organization_id == organization_id,
                ClimateObservation.variable == variable,
                ClimateObservation.latitude.between(latitude - 0.0001, latitude + 0.0001),
                ClimateObservation.longitude.between(
                    longitude - 0.0001, longitude + 0.0001
                ),
                ClimateObservation.observed_at >= start_at,
                ClimateObservation.observed_at < end_at,
                ClimateObservation.quality_status != "rejected",
            )
        )
    ).all()
    observed_dates = {
        timestamp.astimezone(UTC).date()
        if timestamp.tzinfo is not None
        else timestamp.date()
        for timestamp in timestamps
    }
    expected_dates = {
        start_date + timedelta(days=day)
        for day in range(expected_days)
    }
    missing_dates = sorted(expected_dates - observed_dates)
    observed_count = expected_days - len(missing_dates)
    return DailyCoverageReport(
        variable=variable,
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        expected_days=expected_days,
        observed_days=observed_count,
        missing_days=missing_dates,
        coverage_ratio=round(observed_count / expected_days, 6),
    )
