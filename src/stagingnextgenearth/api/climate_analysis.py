"""Tenant-scoped descriptive climate summaries over bounded verified data."""

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_statistics import summarize_climate_series
from stagingnextgenearth.platform.models import ClimateObservation, Membership

from .dependencies import get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-observations",
    tags=["climate"],
)
_MAX_ANALYSIS_OBSERVATIONS = 10_000


class ClimateUnitSummary(BaseModel):
    """Descriptive statistics for one canonical unit."""

    unit: str
    count: int
    missing_count: int
    mean: float | None
    median: float | None
    sample_standard_deviation: float | None
    standard_error: float | None
    minimum: float | None
    maximum: float | None
    percentile_05: float | None
    percentile_25: float | None
    percentile_75: float | None
    percentile_95: float | None
    median_absolute_deviation: float | None


class ClimateAnalysisSummary(BaseModel):
    """Reproducible summary metadata and per-unit descriptive statistics."""

    variable: str
    quality_status: Literal["verified", "pending"]
    start: datetime
    end: datetime
    observation_count: int
    groups: list[ClimateUnitSummary]
    method: Literal["descriptive_hyndman_fan_type_7"] = (
        "descriptive_hyndman_fan_type_7"
    )
    missing_data_policy: Literal["no_imputation"] = "no_imputation"


@router.get("/analysis-summary", response_model=ClimateAnalysisSummary)
async def climate_analysis_summary(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    variable: str = Query(min_length=2, max_length=80),
    start: datetime,
    end: datetime,
    quality_status: Literal["verified", "pending"] = "verified",
) -> ClimateAnalysisSummary:
    """Summarise one variable over an explicit bounded time window.

    Rejected observations are never included. Verified observations are the
    default; pending observations require an explicit query parameter.
    Results are grouped by unit so unlike measurements are never pooled.
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

    statement = (
        select(ClimateObservation.value, ClimateObservation.unit)
        .where(
            ClimateObservation.organization_id == organization_id,
            ClimateObservation.variable == variable,
            ClimateObservation.quality_status == quality_status,
            ClimateObservation.observed_at >= start,
            ClimateObservation.observed_at < end,
        )
        .order_by(ClimateObservation.observed_at.asc(), ClimateObservation.id.asc())
        .limit(_MAX_ANALYSIS_OBSERVATIONS + 1)
    )
    rows = (await session.execute(statement)).all()
    if len(rows) > _MAX_ANALYSIS_OBSERVATIONS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Analysis window exceeds 10000 observations; narrow the time range",
        )

    grouped: dict[str, list[float]] = defaultdict(list)
    for value, unit in rows:
        grouped[str(unit)].append(float(value))

    summaries = []
    for unit, values in sorted(grouped.items()):
        stats = summarize_climate_series(values)
        summaries.append(ClimateUnitSummary(unit=unit, **asdict(stats)))

    return ClimateAnalysisSummary(
        variable=variable,
        quality_status=quality_status,
        start=start,
        end=end,
        observation_count=len(rows),
        groups=summaries,
    )
