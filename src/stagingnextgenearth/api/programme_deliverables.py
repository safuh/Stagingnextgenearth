"""Programme deliverable assignment, evidence submission, and review workflows."""

from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Programme,
    ProgrammeDeliverable,
    ProgrammeDeliverableEvent,
    Project,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/programmes/{programme_id}/deliverables",
    tags=["programme-deliverables"],
)
_MANAGERS = {"admin", "founder", "executive", "programme_manager"}


class DeliverableCreate(BaseModel):
    """Validated deliverable creation payload."""

    title: str = Field(min_length=2, max_length=240)
    description: str | None = Field(default=None, max_length=10000)
    due_date: date | None = None
    project_id: str | None = None
    assigned_to: str | None = None


class EvidenceSubmission(BaseModel):
    """Evidence reference submitted for review."""

    evidence_url: str = Field(min_length=8, max_length=1000)
    note: str | None = Field(default=None, max_length=4000)


class DeliverableDecision(BaseModel):
    """Manager decision on submitted evidence."""

    decision: str = Field(pattern=r"^(accepted|revisions_required)$")
    note: str | None = Field(default=None, max_length=4000)


class DeliverableRead(BaseModel):
    """Deliverable API representation."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    programme_id: str
    project_id: str | None
    title: str
    description: str | None
    due_date: date | None
    assigned_to: str | None
    status: str
    evidence_url: str | None
    submitted_at: datetime | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None


class DeliverableEventRead(BaseModel):
    """Auditable lifecycle event for a programme deliverable."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str
    action: str
    details: dict[str, object]
    created_at: datetime

class ProgrammeActivityRead(DeliverableEventRead):
    """Programme-wide deliverable activity item."""

    deliverable_id: str
    deliverable_title: str


async def _record_event(
    session: AsyncSession,
    *,
    organization_id: str,
    programme_id: str,
    deliverable_id: str,
    actor_user_id: str,
    action: str,
    details: dict[str, object],
) -> None:
    session.add(
        ProgrammeDeliverableEvent(
            organization_id=organization_id,
            programme_id=programme_id,
            deliverable_id=deliverable_id,
            actor_user_id=actor_user_id,
            action=action,
            details=details,
            created_at=datetime.now(UTC),
        )
    )


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


@router.post("", response_model=DeliverableRead, status_code=status.HTTP_201_CREATED)
async def create_deliverable(
    organization_id: str,
    programme_id: str,
    body: DeliverableCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeliverableRead:
    """Create a programme output and optionally assign it to an active member."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    await _programme(session, organization_id, programme_id)
    if body.project_id is not None:
        project = await session.scalar(
            select(Project.id).where(
                Project.id == body.project_id,
                Project.organization_id == organization_id,
                Project.programme_id == programme_id,
            )
        )
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found in this programme")
    if body.assigned_to is not None:
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
    item = ProgrammeDeliverable(
        organization_id=organization_id,
        programme_id=programme_id,
        project_id=body.project_id,
        title=body.title.strip(),
        description=body.description,
        due_date=body.due_date,
        assigned_to=body.assigned_to,
        status="planned",
        created_by=principal.user_id,
    )
    session.add(item)
    await session.flush()
    await _record_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        deliverable_id=item.id,
        actor_user_id=principal.user_id,
        action="created",
        details={"title": item.title, "assigned_to": item.assigned_to},
    )
    if item.assigned_to is not None:
        await _record_event(
            session,
            organization_id=organization_id,
            programme_id=programme_id,
            deliverable_id=item.id,
            actor_user_id=principal.user_id,
            action="assigned",
            details={"assigned_to": item.assigned_to},
        )
    await session.commit()
    await session.refresh(item)
    return DeliverableRead.model_validate(item)


@router.get("", response_model=list[DeliverableRead])
async def list_deliverables(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DeliverableRead]:
    """List programme deliverables within the caller's active tenant."""
    await _programme(session, organization_id, programme_id)
    statement = select(ProgrammeDeliverable).where(
        ProgrammeDeliverable.organization_id == organization_id,
        ProgrammeDeliverable.programme_id == programme_id,
    )
    # Contributors see only work assigned to their own account. In particular,
    # evidence references and reviewer notes for other members stay private.
    if not await membership_has_any_role(session, membership, _MANAGERS):
        statement = statement.where(
            ProgrammeDeliverable.assigned_to == membership.user_id
        )
    rows = await session.scalars(
        statement.order_by(ProgrammeDeliverable.due_date, ProgrammeDeliverable.created_at)
        .limit(500)
    )
    return [DeliverableRead.model_validate(row) for row in rows.all()]


@router.post("/{deliverable_id}/submit", response_model=DeliverableRead)
async def submit_deliverable_evidence(
    organization_id: str,
    programme_id: str,
    deliverable_id: str,
    body: EvidenceSubmission,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeliverableRead:
    """Allow the assignee or a manager to submit an HTTPS evidence reference."""
    item = await session.scalar(
        select(ProgrammeDeliverable).where(
            ProgrammeDeliverable.id == deliverable_id,
            ProgrammeDeliverable.organization_id == organization_id,
            ProgrammeDeliverable.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deliverable not found")
    if not await membership_has_any_role(session, membership, _MANAGERS) and item.assigned_to != principal.user_id:  # noqa: E501
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Only the assignee or a manager may submit evidence",
        )
    if item.status not in {"planned", "in_progress", "revisions_required"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Deliverable cannot be submitted in its current state",
        )
    if not body.evidence_url.startswith("https://"):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Evidence URL must use HTTPS")
    item.evidence_url = body.evidence_url
    item.status = "submitted"
    item.submitted_at = datetime.now(UTC)
    item.review_note = body.note
    await _record_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        deliverable_id=item.id,
        actor_user_id=principal.user_id,
        action="evidence_submitted",
        details={"evidence_url": body.evidence_url, "note": body.note},
    )
    await session.commit()
    await session.refresh(item)
    return DeliverableRead.model_validate(item)


@router.post("/{deliverable_id}/decision", response_model=DeliverableRead)
async def review_deliverable_evidence(
    organization_id: str,
    programme_id: str,
    deliverable_id: str,
    body: DeliverableDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DeliverableRead:
    """Accept evidence or request revisions; only programme managers may decide."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    item = await session.scalar(
        select(ProgrammeDeliverable).where(
            ProgrammeDeliverable.id == deliverable_id,
            ProgrammeDeliverable.organization_id == organization_id,
            ProgrammeDeliverable.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deliverable not found")
    if item.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted evidence can be reviewed")
    item.status = body.decision
    item.reviewed_by = principal.user_id
    item.reviewed_at = datetime.now(UTC)
    item.review_note = body.note
    await _record_event(
        session,
        organization_id=organization_id,
        programme_id=programme_id,
        deliverable_id=item.id,
        actor_user_id=principal.user_id,
        action=body.decision,
        details={"note": body.note},
    )
    await session.commit()
    await session.refresh(item)
    return DeliverableRead.model_validate(item)



@router.get("/activity", response_model=list[ProgrammeActivityRead])
async def list_programme_deliverable_activity(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProgrammeActivityRead]:
    """Return the latest programme deliverable events to programme managers."""
    if not await membership_has_any_role(session, membership, _MANAGERS):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Programme management permission required",
        )
    await _programme(session, organization_id, programme_id)
    rows = await session.execute(
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
    return [
        ProgrammeActivityRead(
            id=event.id,
            actor_user_id=event.actor_user_id,
            action=event.action,
            details=event.details,
            created_at=event.created_at,
            deliverable_id=event.deliverable_id,
            deliverable_title=title,
        )
        for event, title in rows.all()
    ]

@router.get("/{deliverable_id}/events", response_model=list[DeliverableEventRead])
async def list_deliverable_events(
    organization_id: str,
    programme_id: str,
    deliverable_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DeliverableEventRead]:
    """Return lifecycle history to managers and the deliverable's assignee only."""
    item = await session.scalar(
        select(ProgrammeDeliverable).where(
            ProgrammeDeliverable.id == deliverable_id,
            ProgrammeDeliverable.organization_id == organization_id,
            ProgrammeDeliverable.programme_id == programme_id,
        )
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Deliverable not found")
    if not await membership_has_any_role(session, membership, _MANAGERS) and item.assigned_to != principal.user_id:  # noqa: E501
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Deliverable history access denied")
    events = await session.scalars(
        select(ProgrammeDeliverableEvent)
        .where(
            ProgrammeDeliverableEvent.organization_id == organization_id,
            ProgrammeDeliverableEvent.programme_id == programme_id,
            ProgrammeDeliverableEvent.deliverable_id == deliverable_id,
        )
        .order_by(ProgrammeDeliverableEvent.created_at, ProgrammeDeliverableEvent.id)
        .limit(200)
    )
    return [DeliverableEventRead.model_validate(event) for event in events.all()]
