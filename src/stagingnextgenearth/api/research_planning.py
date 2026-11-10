"""Research proposal governance and study milestone tracking."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchMilestone,
    ResearchMilestoneEvent,
    ResearchProposalReviewEvent,
    ResearchStudy,
    ResearchStudyCollaborator,
    ResearchStudyProposal,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}",
    tags=["research-planning"],
)
_REVIEW_ROLES = {"admin", "programme_manager"}
_WRITE_ROLES = {"editor", "contributor"}


class ProposalCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    rationale: str = Field(min_length=20, max_length=12000)
    objectives: str = Field(min_length=20, max_length=12000)
    proposed_methods: str = Field(min_length=30, max_length=20000)
    expected_outcomes: str | None = Field(default=None, max_length=12000)


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    supersedes_proposal_id: str | None
    title: str
    rationale: str
    objectives: str
    proposed_methods: str
    expected_outcomes: str | None
    status: str
    version_number: int
    submitted_at: datetime | None
    created_at: datetime


class ProposalReviewCreate(BaseModel):
    decision: Literal["approved", "revisions_required", "rejected"]
    note: str = Field(min_length=10, max_length=5000)


class ProposalReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    proposal_id: str
    decision: str
    note: str
    reviewed_at: datetime


class MilestoneCreate(BaseModel):
    title: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=12000)
    assigned_to: str | None = None
    due_date: date | None = None


class MilestoneUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=12000)
    assigned_to: str | None = None
    due_date: date | None = None
    status: Literal["planned", "in_progress", "blocked", "completed", "cancelled"] | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="before")
    @classmethod
    def reject_null_for_required_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("title", "status", "progress_percent"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value


class MilestoneEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    milestone_id: str
    event_type: str
    changes: dict[str, object]
    created_at: datetime


class MilestoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    study_id: str
    title: str
    description: str | None
    assigned_to: str | None
    due_date: date | None
    status: str
    progress_percent: int
    created_at: datetime
    updated_at: datetime


async def _study(
    session: AsyncSession, organization_id: str, study_id: str
) -> ResearchStudy:
    study = await session.scalar(
        select(ResearchStudy).where(
            ResearchStudy.id == study_id,
            ResearchStudy.organization_id == organization_id,
        )
    )
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    return study


async def _role(
    session: AsyncSession, study: ResearchStudy, principal: Principal, membership: Membership
) -> str | None:
    if membership.role == "admin" or study.lead_researcher_id == principal.user_id:
        return "editor"
    collaborator = await session.scalar(
        select(ResearchStudyCollaborator).where(
            ResearchStudyCollaborator.study_id == study.id,
            ResearchStudyCollaborator.organization_id == study.organization_id,
            ResearchStudyCollaborator.user_id == principal.user_id,
            ResearchStudyCollaborator.status == "active",
        )
    )
    return collaborator.role if collaborator else None


async def _access(
    session: AsyncSession, study: ResearchStudy, principal: Principal, membership: Membership
) -> str:
    role = await _role(session, study, principal, membership)
    if role is None and membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study access required")
    return role or "reviewer"


async def _validate_assignee(
    session: AsyncSession, organization_id: str, assigned_to: str | None
) -> None:
    if assigned_to is None:
        return
    active = await session.scalar(
        select(Membership.id).where(
            Membership.organization_id == organization_id,
            Membership.user_id == assigned_to,
            Membership.status == "active",
        )
    )
    if active is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Milestone assignee must be an active organisation member",
        )


@router.post("/proposals", response_model=ProposalRead, status_code=201)
async def create_proposal(
    organization_id: str,
    study_id: str,
    body: ProposalCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProposalRead:
    study = await _study(session, organization_id, study_id)
    if await _access(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Proposal authoring permission required")
    title = body.title.strip()
    rationale = body.rationale.strip()
    objectives = body.objectives.strip()
    proposed_methods = body.proposed_methods.strip()
    if min(map(len, (title, rationale, objectives, proposed_methods))) == 0:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Proposal fields cannot be blank")
    proposal = ResearchStudyProposal(
        study_id=study_id,
        title=title,
        rationale=rationale,
        objectives=objectives,
        proposed_methods=proposed_methods,
        expected_outcomes=body.expected_outcomes.strip() if body.expected_outcomes else None,
        status="draft",
        version_number=1,
        created_by=principal.user_id,
    )
    session.add(proposal)
    await session.commit()
    await session.refresh(proposal)
    return ProposalRead.model_validate(proposal)


@router.post(
    "/proposals/{proposal_id}/revisions",
    response_model=ProposalRead,
    status_code=201,
)
async def create_proposal_revision(
    organization_id: str,
    study_id: str,
    proposal_id: str,
    body: ProposalCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProposalRead:
    study = await _study(session, organization_id, study_id)
    role = await _access(session, study, principal, membership)
    if role not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Proposal authoring permission required")

    # Serialize revision allocation for databases that support row-level locks.
    await session.scalar(
        select(ResearchStudy.id)
        .where(ResearchStudy.id == study_id)
        .with_for_update()
    )
    previous = await session.scalar(
        select(ResearchStudyProposal).where(
            ResearchStudyProposal.id == proposal_id,
            ResearchStudyProposal.study_id == study_id,
        )
    )
    if previous is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if previous.created_by != principal.user_id and role != "editor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Proposal revision permission required")
    if previous.status != "revisions_required":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only proposals requiring revisions can be revised",
        )
    existing_revision = await session.scalar(
        select(ResearchStudyProposal.id).where(
            ResearchStudyProposal.supersedes_proposal_id == previous.id
        )
    )
    if existing_revision is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A revision already exists for this proposal version",
        )

    title = body.title.strip()
    rationale = body.rationale.strip()
    objectives = body.objectives.strip()
    proposed_methods = body.proposed_methods.strip()
    if min(map(len, (title, rationale, objectives, proposed_methods))) == 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Proposal fields cannot be blank",
        )
    latest_version = await session.scalar(
        select(func.max(ResearchStudyProposal.version_number)).where(
            ResearchStudyProposal.study_id == study_id
        )
    )
    revision = ResearchStudyProposal(
        study_id=study_id,
        supersedes_proposal_id=previous.id,
        title=title,
        rationale=rationale,
        objectives=objectives,
        proposed_methods=proposed_methods,
        expected_outcomes=body.expected_outcomes.strip() if body.expected_outcomes else None,
        status="draft",
        version_number=(latest_version or previous.version_number) + 1,
        created_by=principal.user_id,
    )
    session.add(revision)
    await session.commit()
    await session.refresh(revision)
    return ProposalRead.model_validate(revision)


@router.get("/proposals", response_model=list[ProposalRead])
async def list_proposals(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProposalRead]:
    study = await _study(session, organization_id, study_id)
    await _access(session, study, principal, membership)
    rows = await session.scalars(
        select(ResearchStudyProposal)
        .where(ResearchStudyProposal.study_id == study_id)
        .order_by(ResearchStudyProposal.version_number.desc())
    )
    return [ProposalRead.model_validate(item) for item in rows.all()]


@router.post("/proposals/{proposal_id}/submit", response_model=ProposalRead)
async def submit_proposal(
    organization_id: str,
    study_id: str,
    proposal_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProposalRead:
    study = await _study(session, organization_id, study_id)
    role = await _access(session, study, principal, membership)
    proposal = await session.scalar(
        select(ResearchStudyProposal).where(
            ResearchStudyProposal.id == proposal_id,
            ResearchStudyProposal.study_id == study_id,
        )
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if role not in _WRITE_ROLES or (
        proposal.created_by != principal.user_id and role != "editor"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Proposal submission permission required")
    if proposal.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only draft proposals can be submitted")
    proposal.status = "submitted"
    proposal.submitted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(proposal)
    return ProposalRead.model_validate(proposal)


@router.post("/proposals/{proposal_id}/reviews", response_model=ProposalReviewRead, status_code=201)
async def review_proposal(
    organization_id: str,
    study_id: str,
    proposal_id: str,
    body: ProposalReviewCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProposalReviewRead:
    study = await _study(session, organization_id, study_id)
    proposal = await session.scalar(
        select(ResearchStudyProposal).where(
            ResearchStudyProposal.id == proposal_id,
            ResearchStudyProposal.study_id == study_id,
        )
    )
    if proposal is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    if membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Independent reviewer role required")
    if proposal.created_by == principal.user_id or study.lead_researcher_id == principal.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Proposal authors and study leads cannot review",
        )
    if proposal.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted proposals can be reviewed")
    event = ResearchProposalReviewEvent(
        proposal_id=proposal.id,
        reviewer_user_id=principal.user_id,
        decision=body.decision,
        note=body.note.strip(),
    )
    proposal.status = body.decision
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return ProposalReviewRead.model_validate(event)


@router.get("/proposals/{proposal_id}/reviews", response_model=list[ProposalReviewRead])
async def list_proposal_reviews(
    organization_id: str,
    study_id: str,
    proposal_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProposalReviewRead]:
    study = await _study(session, organization_id, study_id)
    await _access(session, study, principal, membership)
    exists = await session.scalar(
        select(ResearchStudyProposal.id).where(
            ResearchStudyProposal.id == proposal_id,
            ResearchStudyProposal.study_id == study_id,
        )
    )
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    rows = await session.scalars(
        select(ResearchProposalReviewEvent)
        .where(ResearchProposalReviewEvent.proposal_id == proposal_id)
        .order_by(ResearchProposalReviewEvent.reviewed_at)
    )
    return [ProposalReviewRead.model_validate(item) for item in rows.all()]


@router.post("/milestones", response_model=MilestoneRead, status_code=201)
async def create_milestone(
    organization_id: str,
    study_id: str,
    body: MilestoneCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MilestoneRead:
    study = await _study(session, organization_id, study_id)
    if await _access(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Milestone management permission required")
    await _validate_assignee(session, organization_id, body.assigned_to)
    title = body.title.strip()
    if not title:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Milestone title cannot be blank")
    milestone = ResearchMilestone(
        study_id=study_id,
        title=title,
        description=body.description,
        assigned_to=body.assigned_to,
        due_date=body.due_date,
        status="planned",
        progress_percent=0,
        created_by=principal.user_id,
    )
    session.add(milestone)
    await session.flush()
    initial_values: dict[str, object] = {
        "title": title,
        "description": body.description,
        "assigned_to": body.assigned_to,
        "due_date": body.due_date.isoformat() if body.due_date else None,
        "status": "planned",
        "progress_percent": 0,
    }
    session.add(
        ResearchMilestoneEvent(
            milestone_id=milestone.id,
            actor_user_id=principal.user_id,
            event_type="created",
            changes={key: {"old": None, "new": value} for key, value in initial_values.items()},
        )
    )
    await session.commit()
    await session.refresh(milestone)
    return MilestoneRead.model_validate(milestone)


@router.get("/milestones", response_model=list[MilestoneRead])
async def list_milestones(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MilestoneRead]:
    study = await _study(session, organization_id, study_id)
    await _access(session, study, principal, membership)
    rows = await session.scalars(
        select(ResearchMilestone)
        .where(ResearchMilestone.study_id == study_id)
        .order_by(ResearchMilestone.due_date, ResearchMilestone.created_at)
    )
    return [MilestoneRead.model_validate(item) for item in rows.all()]


@router.patch("/milestones/{milestone_id}", response_model=MilestoneRead)
async def update_milestone(
    organization_id: str,
    study_id: str,
    milestone_id: str,
    body: MilestoneUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MilestoneRead:
    study = await _study(session, organization_id, study_id)
    if await _access(session, study, principal, membership) not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Milestone management permission required")
    milestone = await session.scalar(
        select(ResearchMilestone).where(
            ResearchMilestone.id == milestone_id,
            ResearchMilestone.study_id == study_id,
        )
    )
    if milestone is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    changes = body.model_dump(exclude_unset=True)
    for field in ("title", "description"):
        if field in changes and isinstance(changes[field], str):
            changes[field] = changes[field].strip()
            if field == "title" and not changes[field]:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, "Milestone title cannot be blank"
                )
    if "assigned_to" in changes:
        await _validate_assignee(session, organization_id, changes["assigned_to"])

    tracked_fields = (
        "title", "description", "assigned_to", "due_date", "status", "progress_percent"
    )
    previous_values = {field: getattr(milestone, field) for field in tracked_fields}
    for key, value in changes.items():
        setattr(milestone, key, value)
    if milestone.status == "completed":
        milestone.progress_percent = 100
    elif milestone.progress_percent == 100 and milestone.status != "completed":
        milestone.status = "completed"

    audit_changes: dict[str, object] = {}
    for field in tracked_fields:
        old_value = previous_values[field]
        new_value = getattr(milestone, field)
        if old_value != new_value:
            audit_changes[field] = {
                "old": old_value.isoformat() if isinstance(old_value, date) else old_value,
                "new": new_value.isoformat() if isinstance(new_value, date) else new_value,
            }
    if audit_changes:
        session.add(
            ResearchMilestoneEvent(
                milestone_id=milestone.id,
                actor_user_id=principal.user_id,
                event_type="updated",
                changes=audit_changes,
            )
        )
    await session.commit()
    await session.refresh(milestone)
    return MilestoneRead.model_validate(milestone)


@router.get(
    "/milestones/{milestone_id}/events",
    response_model=list[MilestoneEventRead],
)
async def list_milestone_events(
    organization_id: str,
    study_id: str,
    milestone_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MilestoneEventRead]:
    study = await _study(session, organization_id, study_id)
    await _access(session, study, principal, membership)
    exists = await session.scalar(
        select(ResearchMilestone.id).where(
            ResearchMilestone.id == milestone_id,
            ResearchMilestone.study_id == study_id,
        )
    )
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Milestone not found")
    rows = await session.scalars(
        select(ResearchMilestoneEvent)
        .where(ResearchMilestoneEvent.milestone_id == milestone_id)
        .order_by(ResearchMilestoneEvent.created_at, ResearchMilestoneEvent.id)
    )
    return [MilestoneEventRead.model_validate(item) for item in rows.all()]
