"""Programme goals, milestone planning and general assignment workflows."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeAssignment,
    ProgrammeDeliverable,
    ProgrammeDeliverableEvent,
    ProgrammeGoal,
    ProgrammeMilestone,
    ProgrammePlanningEvent,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(tags=["programme-planning"])
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




async def _record_planning_event(
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




class PlanningEventRead(BaseModel):
    """Manager-visible programme planning audit event."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    entity_type: str
    entity_id: str
    entity_title: str
    actor_user_id: str
    action: str
    details: dict[str, object]
    created_at: datetime




class ProgrammeTimelineEventRead(BaseModel):
    """Unified manager-facing event across programme planning and delivery."""

    id: str
    entity_type: str
    entity_id: str
    entity_title: str
    actor_user_id: str
    action: str
    details: dict[str, object]
    created_at: datetime


class GoalCreate(BaseModel):
    """Programme goal payload."""

    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    target_date: date | None = None


class GoalRead(BaseModel):
    """Programme goal response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    title: str
    description: str | None
    target_date: date | None
    status: str


class GoalStatusUpdate(BaseModel):
    """Goal lifecycle transition."""

    status: str = Field(pattern=r"^(active|achieved|cancelled)$")


class MilestoneCreate(BaseModel):
    """Milestone checkpoint payload."""

    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    due_date: date | None = None


class MilestoneRead(BaseModel):
    """Milestone response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    goal_id: str
    title: str
    description: str | None
    due_date: date | None
    status: str


class MilestoneStatusUpdate(BaseModel):
    """Milestone lifecycle transition."""

    status: str = Field(pattern=r"^(in_progress|completed|blocked|cancelled)$")


class AssignmentCreate(BaseModel):
    """General task assigned to an active organisation member."""

    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    assigned_to: str
    milestone_id: str | None = None
    due_date: date | None = None
    priority: str = Field(default="normal", pattern=r"^(low|normal|high)$")


class AssignmentRead(BaseModel):
    """General programme assignment response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    milestone_id: str | None
    title: str
    description: str | None
    assigned_to: str
    due_date: date | None
    priority: str
    status: str
    created_by: str
    completed_at: datetime | None


class AssignmentStatusUpdate(BaseModel):
    """Assignee or manager status transition."""

    status: str = Field(pattern=r"^(in_progress|completed|cancelled)$")


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/goals",
    response_model=GoalRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_goal(
    organization_id: str,
    programme_id: str,
    body: GoalCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoalRead:
    """Create a programme goal."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    item = ProgrammeGoal(
        organization_id=organization_id,
        programme_id=programme_id,
        title=body.title.strip(),
        description=body.description,
        target_date=body.target_date,
        status="planned",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.flush()
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="goal",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="created",
        details={"status": item.status},
    )
    await session.commit()
    await session.refresh(item)
    return GoalRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/goals",
    response_model=list[GoalRead],
)
async def list_goals(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[GoalRead]:
    """List programme goals for active members."""
    await _programme(session, organization_id, programme_id)
    rows = await session.scalars(
        select(ProgrammeGoal)
        .where(
            ProgrammeGoal.organization_id == organization_id,
            ProgrammeGoal.programme_id == programme_id,
        )
        .order_by(ProgrammeGoal.target_date, ProgrammeGoal.created_at)
        .limit(500)
    )
    return [GoalRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/goals/{goal_id}/status",
    response_model=GoalRead,
)
async def update_goal_status(
    organization_id: str,
    programme_id: str,
    goal_id: str,
    body: GoalStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> GoalRead:
    """Apply a valid goal lifecycle transition."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    transitions = {"planned": {"active", "cancelled"}, "active": {"achieved", "cancelled"}}
    item = await session.scalar(
        select(ProgrammeGoal).where(
            ProgrammeGoal.id == goal_id,
            ProgrammeGoal.organization_id == organization_id,
            ProgrammeGoal.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    if body.status not in transitions.get(item.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid goal status transition")
    previous_status = item.status
    item.status = body.status
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="goal",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="status_changed",
        details={"from": previous_status, "to": body.status},
    )
    await session.commit()
    await session.refresh(item)
    return GoalRead.model_validate(item)


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/goals/{goal_id}/milestones",
    response_model=MilestoneRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_milestone(
    organization_id: str,
    programme_id: str,
    goal_id: str,
    body: MilestoneCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MilestoneRead:
    """Create a checkpoint under a goal in the same programme."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    goal = await session.scalar(
        select(ProgrammeGoal.id).where(
            ProgrammeGoal.id == goal_id,
            ProgrammeGoal.organization_id == organization_id,
            ProgrammeGoal.programme_id == programme_id,
        )
    )
    if goal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Goal not found")
    item = ProgrammeMilestone(
        organization_id=organization_id,
        programme_id=programme_id,
        goal_id=goal_id,
        title=body.title.strip(),
        description=body.description,
        due_date=body.due_date,
        status="planned",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.flush()
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="milestone",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="created",
        details={"goal_id": goal_id, "status": item.status},
    )
    await session.commit()
    await session.refresh(item)
    return MilestoneRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/milestones",
    response_model=list[MilestoneRead],
)
async def list_milestones(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MilestoneRead]:
    """List programme milestones."""
    await _programme(session, organization_id, programme_id)
    rows = await session.scalars(
        select(ProgrammeMilestone)
        .where(
            ProgrammeMilestone.organization_id == organization_id,
            ProgrammeMilestone.programme_id == programme_id,
        )
        .order_by(ProgrammeMilestone.due_date, ProgrammeMilestone.created_at)
        .limit(500)
    )
    return [MilestoneRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/milestones/{milestone_id}/status",
    response_model=MilestoneRead,
)
async def update_milestone_status(
    organization_id: str,
    programme_id: str,
    milestone_id: str,
    body: MilestoneStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MilestoneRead:
    """Apply a valid milestone lifecycle transition."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    transitions = {
        "planned": {"in_progress", "cancelled"},
        "in_progress": {"completed", "blocked", "cancelled"},
        "blocked": {"in_progress", "cancelled"},
    }
    item = await session.scalar(
        select(ProgrammeMilestone).where(
            ProgrammeMilestone.id == milestone_id,
            ProgrammeMilestone.organization_id == organization_id,
            ProgrammeMilestone.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    if body.status not in transitions.get(item.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid milestone status transition")
    previous_status = item.status
    item.status = body.status
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="milestone",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="status_changed",
        details={"from": previous_status, "to": body.status},
    )
    await session.commit()
    await session.refresh(item)
    return MilestoneRead.model_validate(item)


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/assignments",
    response_model=AssignmentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_assignment(
    organization_id: str,
    programme_id: str,
    body: AssignmentCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssignmentRead:
    """Assign a programme task to an active member."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    assignee = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == body.assigned_to,
            Membership.status == "active",
        )
    )
    if assignee is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Assignee must be an active organisation member",
        )
    if body.milestone_id is not None:
        milestone = await session.scalar(
            select(ProgrammeMilestone.id).where(
                ProgrammeMilestone.id == body.milestone_id,
                ProgrammeMilestone.organization_id == organization_id,
                ProgrammeMilestone.programme_id == programme_id,
            )
        )
        if milestone is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found in this programme")
    item = ProgrammeAssignment(
        organization_id=organization_id,
        programme_id=programme_id,
        milestone_id=body.milestone_id,
        title=body.title.strip(),
        description=body.description,
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        priority=body.priority,
        status="open",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.flush()
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="assignment",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="assigned",
        details={
            "assigned_to": item.assigned_to,
            "milestone_id": item.milestone_id,
            "priority": item.priority,
            "status": item.status,
        },
    )
    await session.commit()
    await session.refresh(item)
    return AssignmentRead.model_validate(item)


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/assignments",
    response_model=list[AssignmentRead],
)
async def list_assignments(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[AssignmentRead]:
    """List assignments visible to members; members see their own tasks and managers see all."""
    await _programme(session, organization_id, programme_id)
    query = select(ProgrammeAssignment).where(
        ProgrammeAssignment.organization_id == organization_id,
        ProgrammeAssignment.programme_id == programme_id,
    )
    if not await membership_has_any_role(session, membership, _MANAGERS):
        query = query.where(ProgrammeAssignment.assigned_to == membership.user_id)
    rows = await session.scalars(
        query.order_by(ProgrammeAssignment.due_date, ProgrammeAssignment.created_at).limit(500)
    )
    return [AssignmentRead.model_validate(row) for row in rows.all()]


@router.post(
    "/organizations/{organization_id}/programmes/{programme_id}/assignments/{assignment_id}/status",
    response_model=AssignmentRead,
)
async def update_assignment_status(
    organization_id: str,
    programme_id: str,
    assignment_id: str,
    body: AssignmentStatusUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AssignmentRead:
    """Allow the assignee or a manager to update task progress."""
    item = await session.scalar(
        select(ProgrammeAssignment).where(
            ProgrammeAssignment.id == assignment_id,
            ProgrammeAssignment.organization_id == organization_id,
            ProgrammeAssignment.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Assignment not found")
    if not await membership_has_any_role(session, membership, _MANAGERS) and item.assigned_to != principal.user_id:  # noqa: E501
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the assignee or a manager may update this task",
        )
    transitions = {"open": {"in_progress", "cancelled"}, "in_progress": {"completed", "cancelled"}}
    if body.status not in transitions.get(item.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid assignment status transition")
    previous_status = item.status
    item.status = body.status
    item.completed_at = datetime.now(UTC) if body.status == "completed" else None
    await _record_planning_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        entity_type="assignment",
        entity_id=item.id,
        entity_title=item.title,
        actor_user_id=principal.user_id,
        action="status_changed",
        details={"from": previous_status, "to": body.status},
    )
    await session.commit()
    await session.refresh(item)
    return AssignmentRead.model_validate(item)



@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/planning-activity",
    response_model=list[PlanningEventRead],
)
async def list_planning_activity(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PlanningEventRead]:
    """Return bounded goal, milestone and indicator history to programme managers."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    await _programme(session, organization_id, programme_id)
    rows = await session.scalars(
        select(ProgrammePlanningEvent)
        .where(
            ProgrammePlanningEvent.organization_id == organization_id,
            ProgrammePlanningEvent.programme_id == programme_id,
        )
        .order_by(
            ProgrammePlanningEvent.created_at.desc(),
            ProgrammePlanningEvent.id.desc(),
        )
        .limit(100)
    )
    return [PlanningEventRead.model_validate(row) for row in rows.all()]


@router.get(
    "/organizations/{organization_id}/programmes/{programme_id}/activity-timeline",
    response_model=list[ProgrammeTimelineEventRead],
)
async def list_programme_activity_timeline(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProgrammeTimelineEventRead]:
    """Combine planning, assignment, activity and deliverable events for managers."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    await _programme(session, organization_id, programme_id)

    planning_rows = await session.scalars(
        select(ProgrammePlanningEvent)
        .where(
            ProgrammePlanningEvent.organization_id == organization_id,
            ProgrammePlanningEvent.programme_id == programme_id,
        )
        .order_by(
            ProgrammePlanningEvent.created_at.desc(),
            ProgrammePlanningEvent.id.desc(),
        )
        .limit(100)
    )
    deliverable_rows = await session.execute(
        select(ProgrammeDeliverableEvent, ProgrammeDeliverable.title)
        .join(
            ProgrammeDeliverable,
            ProgrammeDeliverable.id == ProgrammeDeliverableEvent.deliverable_id,
        )
        .where(
            ProgrammeDeliverableEvent.organization_id == organization_id,
            ProgrammeDeliverableEvent.programme_id == programme_id,
        )
        .order_by(
            ProgrammeDeliverableEvent.created_at.desc(),
            ProgrammeDeliverableEvent.id.desc(),
        )
        .limit(100)
    )

    events = [
        ProgrammeTimelineEventRead(
            id=event.id,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            entity_title=event.entity_title,
            actor_user_id=event.actor_user_id,
            action=event.action,
            details=event.details,
            created_at=event.created_at,
        )
        for event in planning_rows.all()
    ]
    events.extend(
        ProgrammeTimelineEventRead(
            id=event.id,
            entity_type="deliverable",
            entity_id=event.deliverable_id,
            entity_title=title,
            actor_user_id=event.actor_user_id,
            action=event.action,
            details=event.details,
            created_at=event.created_at,
        )
        for event, title in deliverable_rows.all()
    )
    events.sort(key=lambda event: (event.created_at, event.id), reverse=True)
    return events[:100]
