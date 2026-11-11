"""Read-only institutional-partner reporting with explicit role and privacy controls."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeIndicator,
    ProgrammeIndicatorMeasurement,
    ProgrammeParticipationRecord,
)

from .dependencies import get_session, require_membership

router = APIRouter(tags=["partner-reporting"])
_MINIMUM_DISCLOSURE_COUNT = 5


class PartnerIndicator(BaseModel):
    title: str
    unit: str
    direction: str
    baseline_value: float | None
    target_value: float | None
    latest_value: float | None
    period_start: date | None
    period_end: date | None
    progress_percent: float | None


class PartnerParticipation(BaseModel):
    participant_group: str
    participant_count: int
    period_start: date
    period_end: date


class PartnerProgrammeReport(BaseModel):
    programme_id: str
    programme_title: str
    programme_status: str
    indicators: list[PartnerIndicator]
    participation: list[PartnerParticipation]


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/partner-reporting",
    response_model=PartnerProgrammeReport,
)
async def get_partner_programme_report(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PartnerProgrammeReport:
    """Return a deliberately minimised report only to institutional partners."""
    if membership.role != "institutional_partner":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Institutional partner access required",
        )
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")

    indicator_rows = await session.scalars(
        select(ProgrammeIndicator)
        .where(
            ProgrammeIndicator.organization_id == organization_id,
            ProgrammeIndicator.programme_id == programme_id,
        )
        .order_by(ProgrammeIndicator.title)
        .limit(200)
    )
    latest_measurements = (
        select(
            ProgrammeIndicatorMeasurement.id.label("measurement_id"),
            func.row_number()
            .over(
                partition_by=ProgrammeIndicatorMeasurement.indicator_id,
                order_by=(
                    ProgrammeIndicatorMeasurement.period_end.desc(),
                    ProgrammeIndicatorMeasurement.created_at.desc(),
                    ProgrammeIndicatorMeasurement.id.desc(),
                ),
            )
            .label("row_number"),
        )
        .where(
            ProgrammeIndicatorMeasurement.organization_id == organization_id,
            ProgrammeIndicatorMeasurement.programme_id == programme_id,
        )
        .subquery()
    )
    latest_rows = await session.scalars(
        select(ProgrammeIndicatorMeasurement)
        .join(
            latest_measurements,
            ProgrammeIndicatorMeasurement.id == latest_measurements.c.measurement_id,
        )
        .where(latest_measurements.c.row_number == 1)
    )
    latest_by_indicator = {row.indicator_id: row for row in latest_rows.all()}

    indicators: list[PartnerIndicator] = []
    for indicator in indicator_rows.all():
        latest = latest_by_indicator.get(indicator.id)
        progress: float | None = None
        if latest is not None and indicator.target_value is not None:
            baseline = indicator.baseline_value if indicator.baseline_value is not None else 0.0
            denominator = indicator.target_value - baseline
            if denominator != 0 and indicator.direction != "monitor":
                progress = round((latest.value - baseline) / denominator * 100, 2)
        indicators.append(
            PartnerIndicator(
                title=indicator.title,
                unit=indicator.unit,
                direction=indicator.direction,
                baseline_value=indicator.baseline_value,
                target_value=indicator.target_value,
                latest_value=latest.value if latest is not None else None,
                period_start=latest.period_start if latest is not None else None,
                period_end=latest.period_end if latest is not None else None,
                progress_percent=progress,
            )
        )

    participation_rows = await session.scalars(
        select(ProgrammeParticipationRecord)
        .where(
            ProgrammeParticipationRecord.organization_id == organization_id,
            ProgrammeParticipationRecord.programme_id == programme_id,
            ProgrammeParticipationRecord.participant_count >= _MINIMUM_DISCLOSURE_COUNT,
        )
        .order_by(ProgrammeParticipationRecord.period_end.desc())
        .limit(500)
    )
    participation = [
        PartnerParticipation(
            participant_group=row.participant_group,
            participant_count=row.participant_count,
            period_start=row.period_start,
            period_end=row.period_end,
        )
        for row in participation_rows.all()
    ]
    return PartnerProgrammeReport(
        programme_id=programme.id,
        programme_title=programme.title,
        programme_status=programme.status,
        indicators=indicators,
        participation=participation,
    )
