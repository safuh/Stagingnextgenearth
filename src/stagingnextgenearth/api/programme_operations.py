"""Programme activity scheduling and volunteer application/allocation workflows."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeActivity,
    ProgrammeActivityAttendance,
    ProgrammePlanningEvent,
    ProgrammeVolunteerAllocation,
    ProgrammeVolunteerApplication,
    Project,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["programme-operations"])
_MANAGERS = {"admin", "founder", "executive", "programme_manager"}


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


async def _record_activity_event(
    session: AsyncSession,
    *,
    organization_id: str,
    programme_id: str,
    entity_type: str,
    entity_id: str,
    entity_title: str,
    actor_user_id: str,
    action: str,
    details: dict[str, object],
) -> None:
    session.add(
        ProgrammePlanningEvent(
            organization_id=organization_id,
            programme_id=programme_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_title=entity_title,
            actor_user_id=actor_user_id,
            action=action,
            details=details,
            created_at=datetime.now(UTC),
        )
    )


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
    safeguarding_confirmed: bool = False
    applicant_identifier: str | None = None


class ApplicationDecision(BaseModel):
    """Manager decision on a volunteer application."""

    decision: str = Field(pattern=r"^(approved|rejected)$")
    note: str | None = Field(default=None, max_length=4000)
    safeguarding_confirmed: bool = False


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
    if not await membership_has_any_role(session, membership, _MANAGERS):
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
    await session.flush()
    await _record_activity_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="activity",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="created",
        details={"location": item.location, "start_at": item.start_at.isoformat()},
    )
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


@router.get(
    "/organizations/{organization_id}/my-volunteer-applications",
    response_model=list[VolunteerApplicationRead],
)
async def list_my_volunteer_applications(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[VolunteerApplicationRead]:
    """Return only the authenticated caller's volunteer applications in this tenant."""
    rows = await session.scalars(
        select(ProgrammeVolunteerApplication)
        .where(
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.user_id == principal.user_id,
        )
        .order_by(ProgrammeVolunteerApplication.created_at.desc())
        .limit(100)
    )
    return [VolunteerApplicationRead.model_validate(row) for row in rows.all()]


@router.get("/organizations/{organization_id}/my-volunteer-allocations")
async def list_my_volunteer_allocations(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return activity assignments belonging only to the authenticated caller."""
    rows = await session.execute(
        select(ProgrammeVolunteerAllocation, ProgrammeActivity, Programme)
        .join(ProgrammeActivity, ProgrammeActivity.id == ProgrammeVolunteerAllocation.activity_id)
        .join(Programme, Programme.id == ProgrammeVolunteerAllocation.programme_id)
        .where(
            ProgrammeVolunteerAllocation.organization_id == organization_id,
            ProgrammeVolunteerAllocation.user_id == principal.user_id,
            ProgrammeActivity.organization_id == organization_id,
            Programme.organization_id == organization_id,
        )
        .order_by(ProgrammeActivity.start_at)
        .limit(200)
    )
    return [
        {
            "id": allocation.id,
            "programme_id": allocation.programme_id,
            "programme_title": programme.title,
            "activity_id": activity.id,
            "activity_title": activity.title,
            "activity_description": activity.description,
            "location": activity.location,
            "start_at": activity.start_at,
            "end_at": activity.end_at,
            "activity_status": activity.status,
            "allocation_status": allocation.status,
        }
        for allocation, activity, programme in rows.all()
    ]


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
    """Allow a new applicant or active youth volunteer to apply to a programme."""
    await _programme(session, organization_id, programme_id)
    existing_membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
        )
    )
    if existing_membership is not None and (
        existing_membership.status != "active"
        or not await membership_has_any_role(
            session, existing_membership, {"youth_volunteer"}
        )
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only active youth volunteers can apply as existing organisation members",
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
    await session.flush()
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
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    rows = await session.execute(
        select(ProgrammeVolunteerApplication, User.identifier)
        .join(User, User.id == ProgrammeVolunteerApplication.user_id)
        .where(
            ProgrammeVolunteerApplication.organization_id == organization_id,
            ProgrammeVolunteerApplication.programme_id == programme_id,
        )
        .order_by(ProgrammeVolunteerApplication.created_at.desc())
        .limit(500)
    )
    return [
        VolunteerApplicationRead.model_validate(application).model_copy(
            update={"applicant_identifier": identifier}
        )
        for application, identifier in rows.all()
    ]


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
    if not await membership_has_any_role(session, membership, _MANAGERS):
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
        if not body.safeguarding_confirmed:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Confirm safeguarding and any required guardian consent before approval",
            )
        existing = await session.scalar(
            select(Membership).where(
                Membership.organization_id == organization_id,
                Membership.user_id == item.user_id,
            )
        )
        if existing is not None and (
            existing.status != "active"
            or not await membership_has_any_role(
                session, existing, {"youth_volunteer"}
            )
        ):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Applicant already has a non-volunteer or inactive organisation membership",
            )
        if existing is None:
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
    item.safeguarding_confirmed = body.safeguarding_confirmed
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
    if not await membership_has_any_role(session, membership, _MANAGERS):
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
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.user_id,
            Membership.status == "active",
        )
    )
    if volunteer is None or not await membership_has_any_role(
        session, volunteer, {"youth_volunteer"}
    ):
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
        await session.flush()
        await _record_activity_event(
            session,
            organization_id=organization_id,
            programme_id=programme_id,
            entity_type="volunteer_allocation",
            entity_id=item.id,
            entity_title=activity.title,
            actor_user_id=principal.user_id,
            action="assigned",
            details={"user_id": item.user_id, "activity_id": activity.id},
        )
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Volunteer is already allocated to this activity",
        ) from exc
    return VolunteerAllocationRead.model_validate(item)


class VolunteerAllocationStatusUpdate(BaseModel):
    """Terminal state requested for an existing volunteer allocation."""

    status: str = Field(pattern=r"^(completed|withdrawn)$")


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/activities/{activity_id}/volunteers/{allocation_id}/status",
    response_model=VolunteerAllocationRead,
)
async def update_volunteer_allocation_status(
    organization_id: str,
    programme_id: str,
    activity_id: str,
    allocation_id: str,
    body: VolunteerAllocationStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VolunteerAllocationRead:
    """Close an allocation as completed or withdrawn; retain its unique assignment record."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    allocation = await session.scalar(
        select(ProgrammeVolunteerAllocation).where(
            ProgrammeVolunteerAllocation.id == allocation_id,
            ProgrammeVolunteerAllocation.organization_id == organization_id,
            ProgrammeVolunteerAllocation.programme_id == programme_id,
            ProgrammeVolunteerAllocation.activity_id == activity_id,
        )
    )
    if allocation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Volunteer allocation not found")
    if allocation.status != "assigned":
        raise HTTPException(status.HTTP_409_CONFLICT, "Volunteer allocation is already closed")
    activity = await session.scalar(
        select(ProgrammeActivity).where(
            ProgrammeActivity.id == activity_id,
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
    )
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    allocation.status = body.status
    await _record_activity_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="volunteer_allocation",
        entity_id=allocation.id,
        entity_title=activity.title,
        actor_user_id=principal.user_id,
        action="status_changed",
        details={
            "user_id": allocation.user_id,
            "activity_id": activity.id,
            "from": "assigned",
            "to": body.status,
        },
    )
    await session.commit()
    await session.refresh(allocation)
    return VolunteerAllocationRead.model_validate(allocation)


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
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActivityRead:
    """Apply a guarded activity lifecycle transition."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
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
    previous_status = item.status
    item.status = body.status
    await _record_activity_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="activity",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="status_changed",
        details={"from": previous_status, "to": body.status},
    )
    await session.commit()
    await session.refresh(item)
    return ActivityRead.model_validate(item)


class ActivityAttendanceCreate(BaseModel):
    """Attendance result for a volunteer allocated to this activity."""

    user_id: str
    attendance_status: str = Field(pattern=r"^(present|late|absent|excused)$")
    note: str | None = Field(default=None, max_length=1000)


class ActivityAttendanceRead(BaseModel):
    """Attendance record response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    activity_id: str
    user_id: str
    attendance_status: str
    note: str | None
    recorded_by: str
    recorded_at: datetime


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/activities/{activity_id}/attendance",
    response_model=ActivityAttendanceRead,
    status_code=status.HTTP_201_CREATED,
)
async def record_activity_attendance(
    organization_id: str,
    programme_id: str,
    activity_id: str,
    body: ActivityAttendanceCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ActivityAttendanceRead:
    """Record attendance for an allocated volunteer; managers only."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    activity = await session.scalar(
        select(ProgrammeActivity).where(
            ProgrammeActivity.id == activity_id,
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
    )
    if activity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    allocation = await session.scalar(
        select(ProgrammeVolunteerAllocation.id).where(
            ProgrammeVolunteerAllocation.organization_id == organization_id,
            ProgrammeVolunteerAllocation.programme_id == programme_id,
            ProgrammeVolunteerAllocation.activity_id == activity_id,
            ProgrammeVolunteerAllocation.user_id == body.user_id,
            ProgrammeVolunteerAllocation.status != "withdrawn",
        )
    )
    if allocation is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Attendance can only be recorded for an allocated volunteer",
        )
    item = ProgrammeActivityAttendance(
        organization_id=organization_id,
        programme_id=programme_id,
        activity_id=activity_id,
        user_id=body.user_id,
        attendance_status=body.attendance_status,
        note=body.note.strip() if body.note else None,
        recorded_by=principal.user_id,
    )
    session.add(item)
    try:
        await session.commit()
        await session.refresh(item)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Attendance has already been recorded for this volunteer",
        ) from exc
    return ActivityAttendanceRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/activities/{activity_id}/attendance",
    response_model=list[ActivityAttendanceRead],
)
async def list_activity_attendance(
    organization_id: str,
    programme_id: str,
    activity_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ActivityAttendanceRead]:
    """Return the attendance register to programme managers only."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    activity_id_found = await session.scalar(
        select(ProgrammeActivity.id).where(
            ProgrammeActivity.id == activity_id,
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
    )
    if activity_id_found is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Activity not found")
    rows = await session.scalars(
        select(ProgrammeActivityAttendance)
        .where(
            ProgrammeActivityAttendance.organization_id == organization_id,
            ProgrammeActivityAttendance.programme_id == programme_id,
            ProgrammeActivityAttendance.activity_id == activity_id,
        )
        .order_by(ProgrammeActivityAttendance.recorded_at, ProgrammeActivityAttendance.user_id)
        .limit(1000)
    )
    return [ActivityAttendanceRead.model_validate(row) for row in rows.all()]


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/delivery-summary",
)
async def programme_delivery_summary(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int | str]:
    """Aggregate operational delivery counts without exposing participant details."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    activity_rows = await session.execute(
        select(ProgrammeActivity.status, func.count(ProgrammeActivity.id))
        .where(
            ProgrammeActivity.organization_id == organization_id,
            ProgrammeActivity.programme_id == programme_id,
        )
        .group_by(ProgrammeActivity.status)
    )
    allocation_rows = await session.execute(
        select(ProgrammeVolunteerAllocation.status, func.count(ProgrammeVolunteerAllocation.id))
        .where(
            ProgrammeVolunteerAllocation.organization_id == organization_id,
            ProgrammeVolunteerAllocation.programme_id == programme_id,
        )
        .group_by(ProgrammeVolunteerAllocation.status)
    )
    attendance_rows = await session.execute(
        select(
            ProgrammeActivityAttendance.attendance_status,
            func.count(ProgrammeActivityAttendance.id),
        )
        .where(
            ProgrammeActivityAttendance.organization_id == organization_id,
            ProgrammeActivityAttendance.programme_id == programme_id,
        )
        .group_by(ProgrammeActivityAttendance.attendance_status)
    )
    activities = {str(key): int(value) for key, value in activity_rows.all()}
    allocations = {str(key): int(value) for key, value in allocation_rows.all()}
    attendance = {str(key): int(value) for key, value in attendance_rows.all()}
    return {
        "programme_id": programme_id,
        "activities_total": sum(activities.values()),
        "activities_planned": activities.get("planned", 0),
        "activities_in_progress": activities.get("in_progress", 0),
        "activities_completed": activities.get("completed", 0),
        "activities_cancelled": activities.get("cancelled", 0),
        "volunteers_assigned": allocations.get("assigned", 0),
        "volunteers_completed": allocations.get("completed", 0),
        "volunteers_withdrawn": allocations.get("withdrawn", 0),
        "attendance_total": sum(attendance.values()),
        "attendance_present": attendance.get("present", 0),
        "attendance_late": attendance.get("late", 0),
        "attendance_absent": attendance.get("absent", 0),
        "attendance_excused": attendance.get("excused", 0),
    }


@router.get("/organizations/{organization_id}/delivery-overview")
async def organization_delivery_overview(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Return tenant-scoped portfolio delivery totals and per-programme breakdowns."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")

    programmes_result = await session.scalars(
        select(Programme)
        .where(Programme.organization_id == organization_id)
        .order_by(Programme.title, Programme.id)
        .limit(200)
    )
    programmes = list(programmes_result.all())
    programme_ids = [item.id for item in programmes]
    activity_counts: dict[str, dict[str, int]] = {}
    allocation_counts: dict[str, dict[str, int]] = {}
    attendance_counts: dict[str, dict[str, int]] = {}

    if programme_ids:
        activity_rows = await session.execute(
            select(
                ProgrammeActivity.programme_id,
                ProgrammeActivity.status,
                func.count(ProgrammeActivity.id),
            )
            .where(
                ProgrammeActivity.organization_id == organization_id,
                ProgrammeActivity.programme_id.in_(programme_ids),
            )
            .group_by(ProgrammeActivity.programme_id, ProgrammeActivity.status)
        )
        allocation_rows = await session.execute(
            select(
                ProgrammeVolunteerAllocation.programme_id,
                ProgrammeVolunteerAllocation.status,
                func.count(ProgrammeVolunteerAllocation.id),
            )
            .where(
                ProgrammeVolunteerAllocation.organization_id == organization_id,
                ProgrammeVolunteerAllocation.programme_id.in_(programme_ids),
            )
            .group_by(
                ProgrammeVolunteerAllocation.programme_id,
                ProgrammeVolunteerAllocation.status,
            )
        )
        attendance_rows = await session.execute(
            select(
                ProgrammeActivityAttendance.programme_id,
                ProgrammeActivityAttendance.attendance_status,
                func.count(ProgrammeActivityAttendance.id),
            )
            .where(
                ProgrammeActivityAttendance.organization_id == organization_id,
                ProgrammeActivityAttendance.programme_id.in_(programme_ids),
            )
            .group_by(
                ProgrammeActivityAttendance.programme_id,
                ProgrammeActivityAttendance.attendance_status,
            )
        )
        for programme_id, state, total in activity_rows.all():
            activity_counts.setdefault(programme_id, {})[state] = int(total)
        for programme_id, state, total in allocation_rows.all():
            allocation_counts.setdefault(programme_id, {})[state] = int(total)
        for programme_id, state, total in attendance_rows.all():
            attendance_counts.setdefault(programme_id, {})[state] = int(total)

    rows: list[dict[str, int | str]] = []
    for programme in programmes:
        activities = activity_counts.get(programme.id, {})
        allocations = allocation_counts.get(programme.id, {})
        attendance = attendance_counts.get(programme.id, {})
        rows.append(
            {
                "programme_id": programme.id,
                "programme_title": programme.title,
                "programme_status": programme.status,
                "activities_total": sum(activities.values()),
                "activities_planned": activities.get("planned", 0),
                "activities_in_progress": activities.get("in_progress", 0),
                "activities_completed": activities.get("completed", 0),
                "activities_cancelled": activities.get("cancelled", 0),
                "volunteers_assigned": allocations.get("assigned", 0),
                "volunteers_completed": allocations.get("completed", 0),
                "volunteers_withdrawn": allocations.get("withdrawn", 0),
                "attendance_total": sum(attendance.values()),
                "attendance_present": attendance.get("present", 0),
                "attendance_late": attendance.get("late", 0),
                "attendance_absent": attendance.get("absent", 0),
                "attendance_excused": attendance.get("excused", 0),
            }
        )

    total_keys = (
        "activities_total",
        "activities_planned",
        "activities_in_progress",
        "activities_completed",
        "activities_cancelled",
        "volunteers_assigned",
        "volunteers_completed",
        "volunteers_withdrawn",
        "attendance_total",
        "attendance_present",
        "attendance_late",
        "attendance_absent",
        "attendance_excused",
    )
    totals: dict[str, int] = {
        key: sum(int(row[key]) for row in rows) for key in total_keys
    }
    return {
        "organization_id": organization_id,
        "programmes_total": len(programmes),
        "programmes_active": sum(item.status == "active" for item in programmes),
        **totals,
        "programmes": rows,
    }
