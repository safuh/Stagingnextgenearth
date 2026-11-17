"""Bounded daily climate time-series aggregation for research workflows."""

from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import ClimateObservation, Membership

from .dependencies import get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-observations",
    tags=["climate"],
)
_MAX_SERIES_OBSERVATIONS = 10_000


class DailyClimatePoint(BaseModel):
    """Daily descriptive values for one variable and canonical unit."""

    day: date
    unit: str
    count: int
    mean: float
    minimum: float
    maximum: float


class DailyClimateSeries(BaseModel):
    """Daily UTC series with explicit review and missing-data semantics."""

    variable: str
    quality_status: Literal["verified", "pending"]
    start: datetime
    end: datetime
    observation_count: int
    points: list[DailyClimatePoint]
    aggregation: Literal["utc_day_mean_min_max"] = "utc_day_mean_min_max"
    missing_data_policy: Literal["observed_days_only_no_imputation"] = (
        "observed_days_only_no_imputation"
    )


@router.get("/daily-series", response_model=DailyClimateSeries)
async def daily_climate_series(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    start: datetime,
    end: datetime,
    variable: str = Query(min_length=2, max_length=80),
    quality_status: Literal["verified", "pending"] = "verified",
) -> DailyClimateSeries:
    """Aggregate one tenant's observations by UTC day without imputing gaps.

    Values are grouped by unit before aggregation. Rejected observations are
    excluded by construction; pending records require an explicit opt-in.
    The observation cap prevents an unbounded in-process research query.
    """
    if start.tzinfo is None or start.utcoffset() is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "start must include a timezone"
        )
    if end.tzinfo is None or end.utcoffset() is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end must include a timezone"
        )
    if end <= start:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, "end must be later than start"
        )

    rows = (
        await session.execute(
            select(
                ClimateObservation.observed_at,
                ClimateObservation.value,
                ClimateObservation.unit,
            )
            .where(
                ClimateObservation.organization_id == organization_id,
                ClimateObservation.variable == variable,
                ClimateObservation.quality_status == quality_status,
                ClimateObservation.observed_at >= start,
                ClimateObservation.observed_at < end,
            )
            .order_by(ClimateObservation.observed_at.asc(), ClimateObservation.id.asc())
            .limit(_MAX_SERIES_OBSERVATIONS + 1)
        )
    ).all()
    if len(rows) > _MAX_SERIES_OBSERVATIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Series exceeds 10000 observations; narrow the time range",
        )

    buckets: dict[tuple[date, str], list[float]] = defaultdict(list)
    for observed_at, value, unit in rows:
        timestamp = (
            observed_at.replace(tzinfo=UTC)
            if observed_at.tzinfo is None
            else observed_at.astimezone(UTC)
        )
        buckets[(timestamp.date(), str(unit))].append(float(value))

    points = []
    for (day, unit), values in sorted(buckets.items()):
        points.append(
            DailyClimatePoint(
                day=day,
                unit=unit,
                count=len(values),
                mean=sum(values) / len(values),
                minimum=min(values),
                maximum=max(values),
            )
        )

    return DailyClimateSeries(
        variable=variable,
        quality_status=quality_status,
        start=start,
        end=end,
        observation_count=len(rows),
        points=points,
    )
