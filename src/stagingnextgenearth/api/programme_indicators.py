"""Programme indicator definitions and append-only progress measurements."""

import math
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeIndicator,
    ProgrammeIndicatorMeasurement,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(tags=["programme-indicators"])
_MANAGERS = {"admin", "programme_manager"}


async def _get_programme(
    session: AsyncSession,
    organization_id: str,
    programme_id: str,
) -> Programme:
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    return programme


class IndicatorCreate(BaseModel):
    """Definition of a measurable programme indicator."""

    key: str = Field(pattern=r"^[a-z][a-z0-9_]{1,79}$")
    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=5000)
    unit: str = Field(min_length=1, max_length=40)
    direction: str = Field(default="increase", pattern=r"^(increase|decrease|monitor)$")
    baseline_value: float | None = None
    target_value: float | None = None

    @model_validator(mode="after")
    def validate_values(self) -> "IndicatorCreate":
        for value in (self.baseline_value, self.target_value):
            if value is not None and not math.isfinite(value):
                raise ValueError("Indicator values must be finite numbers")
        return self


class IndicatorRead(BaseModel):
    """Indicator definition response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    key: str
    title: str
    description: str | None
    unit: str
    direction: str
    baseline_value: float | None
    target_value: float | None


class MeasurementCreate(BaseModel):
    """One immutable reporting-period measurement."""

    period_start: date
    period_end: date
    value: float
    notes: str | None = Field(default=None, max_length=5000)
    evidence_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_period_and_value(self) -> "MeasurementCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if not math.isfinite(self.value):
            raise ValueError("Measurement value must be finite")
        if self.evidence_reference is not None and not self.evidence_reference.startswith(
            ("https://", "urn:")
        ):
            raise ValueError("Evidence reference must use HTTPS or a URN")
        return self


class MeasurementRead(BaseModel):
    """Immutable measurement response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    indicator_id: str
    period_start: date
    period_end: date
    value: float
    notes: str | None
    evidence_reference: str | None
    reported_by: str


class IndicatorProgress(BaseModel):
    """Indicator with its latest measurement and transparent target progress."""

    indicator: IndicatorRead
    latest_measurement: MeasurementRead | None
    progress_percent: float | None


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/indicators",
    response_model=IndicatorRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_indicator(
    organization_id: str,
    programme_id: str,
    body: IndicatorCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IndicatorRead:
    """Create an indicator definition."""
    if membership.role not in _MANAGERS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    await _get_programme(session, organization_id, programme_id)
    item = ProgrammeIndicator(
        organization_id=organization_id,
        programme_id=programme_id,
        key=body.key,
        title=body.title.strip(),
        description=body.description,
        unit=body.unit.strip(),
        direction=body.direction,
        baseline_value=body.baseline_value,
        target_value=body.target_value,
        created_by=principal.user_id,
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "An indicator with this key already exists in the programme",
        ) from exc
    return IndicatorRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/indicators",
    response_model=list[IndicatorProgress],
)
async def list_indicators(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[IndicatorProgress]:
    """List indicator definitions with the latest recorded value."""
    await _get_programme(session, organization_id, programme_id)
    indicators = await session.scalars(
        select(ProgrammeIndicator)
        .where(
            ProgrammeIndicator.organization_id == organization_id,
            ProgrammeIndicator.programme_id == programme_id,
        )
        .order_by(ProgrammeIndicator.title)
        .limit(200)
    )
    result: list[IndicatorProgress] = []
    for indicator in indicators.all():
        latest = await session.scalar(
            select(ProgrammeIndicatorMeasurement)
            .where(
                ProgrammeIndicatorMeasurement.organization_id == organization_id,
                ProgrammeIndicatorMeasurement.indicator_id == indicator.id,
            )
            .order_by(
                ProgrammeIndicatorMeasurement.period_end.desc(),
                ProgrammeIndicatorMeasurement.created_at.desc(),
            )
            .limit(1)
        )
        progress: float | None = None
        if latest is not None and indicator.target_value is not None:
            baseline = indicator.baseline_value or 0.0
            denominator = indicator.target_value - baseline
            if denominator != 0 and indicator.direction != "monitor":
                progress = round(
                    ((latest.value - baseline) / denominator) * 100,
                    2,
                )
        result.append(
            IndicatorProgress(
                indicator=IndicatorRead.model_validate(indicator),
                latest_measurement=(
                    MeasurementRead.model_validate(latest) if latest is not None else None
                ),
                progress_percent=progress,
            )
        )
    return result


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/indicators/{indicator_id}/measurements",
    response_model=MeasurementRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_measurement(
    organization_id: str,
    programme_id: str,
    indicator_id: str,
    body: MeasurementCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MeasurementRead:
    """Append a measurement; corrections are new records, never overwrites."""
    if membership.role not in _MANAGERS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    await _get_programme(session, organization_id, programme_id)
    indicator = await session.scalar(
        select(ProgrammeIndicator).where(
            ProgrammeIndicator.id == indicator_id,
            ProgrammeIndicator.organization_id == organization_id,
            ProgrammeIndicator.programme_id == programme_id,
        )
    )
    if indicator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicator not found")
    item = ProgrammeIndicatorMeasurement(
        organization_id=organization_id,
        programme_id=programme_id,
        indicator_id=indicator_id,
        period_start=body.period_start,
        period_end=body.period_end,
        value=body.value,
        notes=body.notes,
        evidence_reference=body.evidence_reference,
        reported_by=principal.user_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return MeasurementRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/indicators/{indicator_id}/measurements",
    response_model=list[MeasurementRead],
)
async def list_measurements(
    organization_id: str,
    programme_id: str,
    indicator_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MeasurementRead]:
    """Return bounded, tenant-scoped measurement history."""
    await _get_programme(session, organization_id, programme_id)
    indicator_exists = await session.scalar(
        select(ProgrammeIndicator.id).where(
            ProgrammeIndicator.id == indicator_id,
            ProgrammeIndicator.organization_id == organization_id,
            ProgrammeIndicator.programme_id == programme_id,
        )
    )
    if indicator_exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Indicator not found")
    rows = await session.scalars(
        select(ProgrammeIndicatorMeasurement)
        .where(
            ProgrammeIndicatorMeasurement.organization_id == organization_id,
            ProgrammeIndicatorMeasurement.programme_id == programme_id,
            ProgrammeIndicatorMeasurement.indicator_id == indicator_id,
        )
        .order_by(
            ProgrammeIndicatorMeasurement.period_end.desc(),
            ProgrammeIndicatorMeasurement.created_at.desc(),
        )
        .limit(500)
    )
    return [MeasurementRead.model_validate(row) for row in rows.all()]
