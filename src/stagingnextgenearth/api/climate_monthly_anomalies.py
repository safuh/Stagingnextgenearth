"""Tenant-scoped monthly precipitation anomaly research endpoint."""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.climate_anomalies import standardized_anomaly
from stagingnextgenearth.climate_monthly import complete_monthly_total
from stagingnextgenearth.platform.models import ClimateObservation, Membership

from .dependencies import get_session, membership_has_any_role, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-observations",
    tags=["climate"],
)
_MAX_OBSERVATIONS = 50_000


class MonthlyPrecipitationAnomaly(BaseModel):
    year: int
    month: int
    observed_total_mm: float
    observed_days: int
    expected_days: int
    completeness: float
    baseline_mean_mm: float
    baseline_sample_standard_deviation_mm: float
    baseline_year_count: int
    standardized_anomaly: float
    method: Literal["sample_standardized_anomaly_z_score"]
    classification: Literal["unclassified"] = "unclassified"


class MonthlyAnomalySeries(BaseModel):
    variable: Literal["precipitation"] = "precipitation"
    unit: Literal["mm/day"] = "mm/day"
    quality_status: Literal["verified", "pending"]
    latitude: float
    longitude: float
    baseline_start: date
    baseline_end: date
    target_start: date
    target_end: date
    minimum_completeness: float
    minimum_baseline_years: int
    observation_count: int
    provenance_sources: list[str]
    provider_ids: list[str]
    ingestion_run_ids: list[str]
    points: list[MonthlyPrecipitationAnomaly]
    missing_data_policy: Literal["no_imputation_incomplete_months_excluded"] = (
        "no_imputation_incomplete_months_excluded"
    )


def _month_boundary(value: date, *, end: bool) -> bool:
    if not end:
        return value.day == 1
    from calendar import monthrange
    return value.day == monthrange(value.year, value.month)[1]


@router.get("/monthly-precipitation-anomalies", response_model=MonthlyAnomalySeries)
async def monthly_precipitation_anomalies(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    baseline_start: date,
    baseline_end: date,
    target_start: date,
    target_end: date,
    latitude: float = Query(ge=-90, le=90),
    longitude: float = Query(ge=-180, le=180),
    quality_status: Literal["verified", "pending"] = "verified",
    minimum_completeness: float = Query(default=0.9, gt=0, le=1),
    minimum_baseline_years: int = Query(default=10, ge=2, le=100),
) -> MonthlyAnomalySeries:
    """Compare target calendar months with same-calendar-month baseline samples.

    Dates are inclusive and must describe complete calendar-month periods.
    A single exact coordinate is required to prevent spatial pooling. Only
    daily precipitation in mm/day is accepted; rejected records are excluded.
    """
    if not await membership_has_any_role(
        session,
        membership,
        {"founder", "admin", "executive", "researcher", "programme_manager"},
    ):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A research or organisational leadership role is required",
        )
    if not all((
        _month_boundary(baseline_start, end=False),
        _month_boundary(baseline_end, end=True),
        _month_boundary(target_start, end=False),
        _month_boundary(target_end, end=True),
    )):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "All period dates must span complete calendar months")
    if baseline_end < baseline_start or target_end < target_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid date range")
    if baseline_end >= target_start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Baseline and target periods must not overlap")
    if (target_end - baseline_start).days > 36_600:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Requested analysis exceeds 100 years")

    start_at = datetime.combine(baseline_start, time.min, UTC)
    end_at = datetime.combine(target_end + timedelta(days=1), time.min, UTC)
    rows = (await session.execute(
        select(
            ClimateObservation.observed_at,
            ClimateObservation.value,
            ClimateObservation.source,
            ClimateObservation.provider_id,
            ClimateObservation.ingestion_run_id,
        ).where(
            ClimateObservation.organization_id == organization_id,
            ClimateObservation.variable == "precipitation",
            ClimateObservation.unit == "mm/day",
            ClimateObservation.quality_status == quality_status,
            ClimateObservation.latitude == latitude,
            ClimateObservation.longitude == longitude,
            ClimateObservation.observed_at >= start_at,
            ClimateObservation.observed_at < end_at,
        ).order_by(ClimateObservation.observed_at.asc(), ClimateObservation.id.asc())
        .limit(_MAX_OBSERVATIONS + 1)
    )).all()
    if len(rows) > _MAX_OBSERVATIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Analysis exceeds 50000 observations; narrow the periods")

    daily: dict[date, list[float]] = defaultdict(list)
    sources: set[str] = set()
    providers: set[str] = set()
    runs: set[str] = set()
    for observed_at, value, source, provider_id, run_id in rows:
        timestamp = (observed_at.replace(tzinfo=UTC) if observed_at.tzinfo is None
                     else observed_at.astimezone(UTC))
        daily[timestamp.date()].append(float(value))
        sources.add(str(source))
        if provider_id:
            providers.add(str(provider_id))
        if run_id:
            runs.add(str(run_id))

    monthly: dict[tuple[int, int], tuple[float, int, int, float]] = {}
    cursor = date(baseline_start.year, baseline_start.month, 1)
    while cursor <= baseline_end:
        result = complete_monthly_total(
            daily, cursor.year, cursor.month,
            minimum_completeness=minimum_completeness,
        )
        if result is not None:
            monthly[(cursor.year, cursor.month)] = result
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)

    points: list[MonthlyPrecipitationAnomaly] = []
    cursor = date(target_start.year, target_start.month, 1)
    while cursor <= target_end:
        observed = complete_monthly_total(
            daily, cursor.year, cursor.month,
            minimum_completeness=minimum_completeness,
        )
        if observed is not None:
            baseline_values = [
                value[0] for (year, month), value in monthly.items()
                if month == cursor.month
            ]
            if len(baseline_values) >= minimum_baseline_years:
                anomaly = standardized_anomaly(
                    observed[0], baseline_values,
                    minimum_baseline_count=minimum_baseline_years,
                )
                points.append(MonthlyPrecipitationAnomaly(
                    year=cursor.year, month=cursor.month,
                    observed_total_mm=observed[0], observed_days=observed[1],
                    expected_days=observed[2], completeness=observed[3],
                    baseline_mean_mm=anomaly.baseline_mean,
                    baseline_sample_standard_deviation_mm=(
                        anomaly.baseline_sample_standard_deviation
                    ),
                    baseline_year_count=anomaly.baseline_count,
                    standardized_anomaly=anomaly.value,
                    method="sample_standardized_anomaly_z_score",
                    classification="unclassified",
                ))
        cursor = date(cursor.year + (cursor.month == 12), cursor.month % 12 + 1, 1)

    if not points:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "No target months have sufficient daily completeness and baseline years",
        )
    return MonthlyAnomalySeries(
        quality_status=quality_status, latitude=latitude, longitude=longitude,
        baseline_start=baseline_start, baseline_end=baseline_end,
        target_start=target_start, target_end=target_end,
        minimum_completeness=minimum_completeness,
        minimum_baseline_years=minimum_baseline_years,
        observation_count=len(rows), provenance_sources=sorted(sources),
        provider_ids=sorted(providers), ingestion_run_ids=sorted(runs),
        points=points,
    )
