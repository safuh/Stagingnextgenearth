"""Privacy-preserving aggregate school and community participation records."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeActivity,
    ProgrammeParticipationRecord,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(tags=["programme-participation"])
_MANAGERS = {"admin", "programme_manager"}


class ParticipationCreate(BaseModel):
    """Aggregate cohort participation, intentionally excluding participant identities."""

    participant_group: str = Field(
        pattern=r"^(school|community|youth_group|institution)$"
    )
    group_name: str = Field(min_length=2, max_length=200)
    participant_count: int = Field(gt=0, le=100000)
    period_start: date
    period_end: date
    activity_id: str | None = None
    notes: str | None = Field(default=None, max_length=5000)
    evidence_reference: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def validate_period_and_evidence(self) -> "ParticipationCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not precede period_start")
        if self.evidence_reference is not None and not self.evidence_reference.startswith(
            ("https://", "urn:")
        ):
            raise ValueError("Evidence reference must use HTTPS or a URN")
        return self


class ParticipationRead(BaseModel):
    """Aggregate participation response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    activity_id: str | None
    participant_group: str
    group_name: str
    participant_count: int
    period_start: date
    period_end: date
    notes: str | None
    evidence_reference: str | None
    recorded_by: str


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/participation",
    response_model=ParticipationRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_participation(
    organization_id: str,
    programme_id: str,
    body: ParticipationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ParticipationRead:
    """Record a school/community cohort total without collecting child-level PII."""
    if membership.role not in _MANAGERS:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    if body.activity_id is not None:
        activity = await session.scalar(
            select(ProgrammeActivity.id).where(
                ProgrammeActivity.id == body.activity_id,
                ProgrammeActivity.organization_id == organization_id,
                ProgrammeActivity.programme_id == programme_id,
            )
        )
        if activity is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    item = ProgrammeParticipationRecord(
        organization_id=organization_id,
        programme_id=programme_id,
        activity_id=body.activity_id,
        participant_group=body.participant_group,
        group_name=body.group_name.strip(),
        participant_count=body.participant_count,
        period_start=body.period_start,
        period_end=body.period_end,
        notes=body.notes,
        evidence_reference=body.evidence_reference,
        recorded_by=principal.user_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return ParticipationRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/participation",
    response_model=list[ParticipationRead],
)
async def list_participation(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ParticipationRead]:
    """List bounded aggregate participation records for organisation members."""
    programme = await session.scalar(
        select(Programme.id).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    rows = await session.scalars(
        select(ProgrammeParticipationRecord)
        .where(
            ProgrammeParticipationRecord.organization_id == organization_id,
            ProgrammeParticipationRecord.programme_id == programme_id,
        )
        .order_by(ProgrammeParticipationRecord.period_end.desc())
        .limit(500)
    )
    return [ParticipationRead.model_validate(row) for row in rows.all()]
