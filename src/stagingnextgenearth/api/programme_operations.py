"""Programme activity scheduling and volunteer application/allocation workflows."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeActivity,
    ProgrammeVolunteerAllocation,
    ProgrammeVolunteerApplication,
    Project,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(tags=["programme-operations"])
_MANAGERS = {"admin", "programme_manager"}


async def _programme(
    session: AsyncSession, organization_id: str, programme_id: str
) -> Programme:
    item = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    return item


class ActivityCreate(BaseModel):
    """Scheduled activity payload."""

    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    location: str | None = Field(default=None, max_length=300)
    project_id: str | None = None
    start_at: datetime
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_time_order(self) -> "ActivityCreate":
        if self.end_at is not None and self.end_at < self.start_at:
            raise ValueError("end_at must not precede start_at")
        if self.start_at.tzinfo is None or (
            self.end_at is not None and self.end_at.tzinfo is None
        ):
            raise ValueError("Activity timestamps must include a timezone")
        return self


class ActivityRead(BaseModel):
    """Activity response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    project_id: str | None
    title: str
    description: str | None
    location: str | None
    start_at: datetime
    end_at: datetime | None
    status: str


class VolunteerApplicationCreate(BaseModel):
    """Volunteer or ambassador application."""

    participation_type: str = Field(pattern=r"^(volunteer|ambassador)$")
    interest: str = Field(min_length=20, max_length=5000)
    availability: str | None = Field(default=None, max_length=500)


class VolunteerApplicationRead(BaseModel):
    """Application response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    user_id: str
    participation_type: str
    interest: str
    availability: str | None
    status: str
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class ApplicationDecision(BaseModel):
    """Manager decision on a volunteer application."""

    decision: str = Field(pattern=r"^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=4000)


class VolunteerAllocationCreate(BaseModel):
    """Volunteer assignment to a scheduled activity."""

    user_id: str


class VolunteerAllocationRead(BaseModel):
    """Allocation response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    activity_id: str
    user_id: str
    status: str
    assigned_by: str


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/activities",
    response_model=ActivityRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_activity(
    organization_id: str,
    programme_id: str,
    body: ActivityCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActivityRead:
    """Create a programme activity; project links must remain in the same programme."""
    if membership.role not in _MANAGERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    if body.project_id is not None:
        project_id = await session.scalar(
            select(Project.id).where(
                Project.id == body.project_id,
                Project.organization_id == organization_id,
                Project.programme_id == programme_id,
            )
        )
        if project_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found in this programme")
    item = ProgrammeActivity(
        organization_id=organization_id,
        programme_id=programme_id,
        project_id=body.project_id,
        title=body.title.strip(),
        description=body.description,
        location=body.location,
        start_at=body.start_at,
        end_at=body.end_at,
        status="planned",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return ActivityRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/activities",
    response_model=list[ActivityRead],
)
async def list_activities(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ActivityRead]:
    """List activities visible to active organisation members."""
    await _programme(session, organization_id, programme_id)
    rows = await session.scalars(
        select(ProgrammeActivity)
        .where(
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
        .order_by(ProgrammeActivity.start_at)
        .limit(500)
    )
    return [ActivityRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications",
    response_model=VolunteerApplicationRead,
    status_code=status.HTTP_201_CREATED,
)
async def apply_to_volunteer(
    organization_id: str,
    programme_id: str,
    body: VolunteerApplicationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerApplicationRead:
    """Allow an authenticated non-member to apply to a programme."""
    await _programme(session, organization_id, programme_id)
    existing_membership = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
    )
    if existing_membership is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Existing members cannot apply as new volunteers",
        )
    item = ProgrammeVolunteerApplication(
        organization_id=organization_id,
        programme_id=programme_id,
        user_id=principal.user_id,
        participation_type=body.participation_type,
        interest=body.interest.strip(),
        availability=body.availability,
        status="pending",
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "An application already exists") from exc
    return VolunteerApplicationRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications",
    response_model=list[VolunteerApplicationRead],
)
async def list_volunteer_applications(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolunteerApplicationRead]:
    """List applications for programme managers only."""
    if membership.role not in _MANAGERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    rows = await session.scalars(
        select(ProgrammeVolunteerApplication)
        .where(
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.programme_id == programme_id,
        )
        .order_by(ProgrammeVolunteerApplication.created_at.desc())
        .limit(500)
    )
    return [VolunteerApplicationRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/volunteer-applications/{application_id}/decision",
    response_model=VolunteerApplicationRead,
)
async def decide_volunteer_application(
    organization_id: str,
    programme_id: str,
    application_id: str,
    body: ApplicationDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerApplicationRead:
    """Approve an applicant into the youth-volunteer role or reject the application."""
    if membership.role not in _MANAGERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    item = await session.scalar(
        select(ProgrammeVolunteerApplication).where(
            ProgrammeVolunteerApplication.id == application_id,
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    if item.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, "Application has already been decided")
    if body.decision == "approved":
        existing = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == item.user_id,
            )
        )
        if existing is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Applicant already has an organisation membership",
            )
        session.add(
            Membership(
                organization_id=organization_id,
                user_id=item.user_id,
                role="youth_volunteer",
                status="active",
            )
        )
    item.status = body.decision
    item.reviewed_by = principal.user_id
    item.reviewed_at = datetime.now(UTC)
    item.review_note = body.note
    await session.commit()
    await session.refresh(item)
    return VolunteerApplicationRead.model_validate(item)


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/activities/{activity_id}/volunteers",
    response_model=VolunteerAllocationRead,
    status_code=status.HTTP_201_CREATED,
)
async def allocate_volunteer(
    organization_id: str,
    programme_id: str,
    activity_id: str,
    body: VolunteerAllocationCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerAllocationRead:
    """Allocate an active youth-volunteer member to a programme activity."""
    if membership.role not in _MANAGERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    activity = await session.scalar(
        select(ProgrammeActivity).where(
            ProgrammeActivity.id == activity_id,
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
    )
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    volunteer = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.user_id,
            Membership.role == "youth_volunteer",
            Membership.status == "active",
        )
    )
    if volunteer is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "User is not an active volunteer")
    item = ProgrammeVolunteerAllocation(
        organization_id=organization_id,
        programme_id=programme_id,
        activity_id=activity_id,
        user_id=body.user_id,
        status="assigned",
        assigned_by=principal.user_id,
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Volunteer is already allocated to this activity",
        ) from exc
    return VolunteerAllocationRead.model_validate(item)


class ActivityStatusUpdate(BaseModel):
    """Requested activity lifecycle state."""

    status: str = Field(pattern=r"^(in_progress|completed|cancelled)$")


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/activities/{activity_id}/status",
    response_model=ActivityRead,
)
async def update_activity_status(
    organization_id: str,
    programme_id: str,
    activity_id: str,
    body: ActivityStatusUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActivityRead:
    """Apply a guarded activity lifecycle transition."""
    if membership.role not in _MANAGERS:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    item = await session.scalar(
        select(ProgrammeActivity).where(
            ProgrammeActivity.id == activity_id,
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    allowed = {
        "planned": {"in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": set(),
        "cancelled": set(),
    }
    if body.status not in allowed.get(item.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid activity status transition")
    item.status = body.status
    await session.commit()
    await session.refresh(item)
    return ActivityRead.model_validate(item)
