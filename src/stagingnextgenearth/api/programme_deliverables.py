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
    Project,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/programmes/{programme_id}/deliverables",
    tags=["programme-deliverables"],
)
_MANAGERS = {"admin", "programme_manager"}


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
    if membership.role not in _MANAGERS:
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
    rows = await session.scalars(
        select(ProgrammeDeliverable)
        .where(
            ProgrammeDeliverable.organization_id == organization_id,
            ProgrammeDeliverable.programme_id == programme_id,
        )
        .order_by(ProgrammeDeliverable.due_date, ProgrammeDeliverable.created_at)
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
    if membership.role not in _MANAGERS and item.assigned_to != principal.user_id:
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
    if membership.role not in _MANAGERS:
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
    await session.commit()
    await session.refresh(item)
    return DeliverableRead.model_validate(item)
