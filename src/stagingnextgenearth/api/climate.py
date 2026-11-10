"""Provenance-aware climate observation submission, query, and quality review."""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    ClimateObservation,
    Membership,
    Project,
    ResearchStudy,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/climate-observations",
    tags=["climate"],
)
_WRITE_ROLES = {"admin", "researcher", "youth_volunteer"}
_REVIEW_ROLES = {"admin", "programme_manager"}


class ClimateObservationCreate(BaseModel):
    """Submit one sourced observation; submitted measurements remain unverified."""

    observed_at: datetime
    variable: str = Field(min_length=2, max_length=80)
    value: FiniteFloat
    unit: str = Field(min_length=1, max_length=32)
    latitude: FiniteFloat = Field(ge=-90, le=90)
    longitude: FiniteFloat = Field(ge=-180, le=180)
    source: str = Field(min_length=2, max_length=160)
    project_id: str | None = None
    study_id: str | None = None
    metadata_json: dict[str, object] | None = None

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class ClimateObservationReview(BaseModel):
    """Independent quality decision for a pending observation."""

    decision: Literal["verified", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class ClimateObservationRead(BaseModel):
    """Climate measurement including provenance and quality-review audit fields."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    study_id: str | None
    project_id: str | None
    observed_at: datetime
    variable: str
    value: float
    unit: str
    latitude: float
    longitude: float
    source: str
    quality_status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    metadata_json: dict[str, object] | None


@router.post("", response_model=ClimateObservationRead, status_code=status.HTTP_201_CREATED)
async def create_climate_observation(
    organization_id: str,
    body: ClimateObservationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateObservationRead:
    """Persist a measurement as pending; verification is a separate workflow."""
    if membership.role not in _WRITE_ROLES:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Climate observation submission is not permitted"
        )
    if body.project_id is not None:
        project = await session.scalar(
            select(Project.id).where(
                Project.id == body.project_id,
                Project.organization_id == organization_id,
            )
        )
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    if body.study_id is not None:
        study = await session.scalar(
            select(ResearchStudy).where(
                ResearchStudy.id == body.study_id,
                ResearchStudy.organization_id == organization_id,
            )
        )
        if study is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
        if body.project_id is not None and study.project_id not in {None, body.project_id}:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "Study and project do not match"
            )
    observation = ClimateObservation(
        organization_id=organization_id,
        study_id=body.study_id,
        project_id=body.project_id,
        observed_at=body.observed_at,
        variable=body.variable.strip(),
        value=body.value,
        unit=body.unit.strip(),
        latitude=body.latitude,
        longitude=body.longitude,
        source=body.source.strip(),
        quality_status="pending",
        metadata_json=body.metadata_json,
        created_by=principal.user_id,
    )
    session.add(observation)
    await session.commit()
    await session.refresh(observation)
    return ClimateObservationRead.model_validate(observation)


@router.get("", response_model=list[ClimateObservationRead])
async def list_climate_observations(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    variable: str | None = Query(default=None, min_length=2, max_length=80),
    quality_status: Literal["pending", "verified", "rejected"] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ClimateObservationRead]:
    """Query observations within the caller's organisation and optional filters."""
    if start and end and end < start:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "end must not precede start")
    statement = select(ClimateObservation).where(
        ClimateObservation.organization_id == organization_id
    )
    if variable is not None:
        statement = statement.where(ClimateObservation.variable == variable)
    if quality_status is not None:
        statement = statement.where(ClimateObservation.quality_status == quality_status)
    if start is not None:
        statement = statement.where(ClimateObservation.observed_at >= start)
    if end is not None:
        statement = statement.where(ClimateObservation.observed_at <= end)
    result = await session.scalars(
        statement.order_by(ClimateObservation.observed_at.desc()).limit(limit)
    )
    return [ClimateObservationRead.model_validate(item) for item in result.all()]


@router.post("/{observation_id}/review", response_model=ClimateObservationRead)
async def review_climate_observation(
    organization_id: str,
    observation_id: str,
    body: ClimateObservationReview,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ClimateObservationRead:
    """Record one independent review decision; decisions are immutable."""
    if membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Climate quality reviewer role required")
    observation = await session.scalar(
        select(ClimateObservation).where(
            ClimateObservation.id == observation_id,
            ClimateObservation.organization_id == organization_id,
        )
    )
    if observation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Climate observation not found")
    if observation.created_by == principal.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Submitters cannot review their own observations"
        )
    if observation.quality_status != "pending":
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Only pending observations can be reviewed"
        )
    observation.quality_status = body.decision
    observation.reviewed_by = principal.user_id
    observation.reviewed_at = datetime.now(UTC)
    observation.review_note = body.note.strip() if body.note else None
    await session.commit()
    await session.refresh(observation)
    return ClimateObservationRead.model_validate(observation)
