"""Versioned research protocol and independent ethics-review workflows."""

import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    OrganizationAuditEvent,
    ResearchEthicsReviewEvent,
    ResearchProtocolReviewEvent,
    ResearchProtocolVersion,
    ResearchStudy,
    ResearchStudyCollaborator,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(
    prefix="/organizations/{organization_id}/research-studies/{study_id}",
    tags=["research-governance"],
)
audit_router = APIRouter(
    prefix="/organizations/{organization_id}/research-governance",
    tags=["research-governance"],
)
_REVIEW_ROLES = {"admin", "founder", "executive", "programme_manager"}
_WRITE_ROLES = {"editor", "contributor"}


class ProtocolCreate(BaseModel):
    """Content for a new immutable protocol version."""

    title: str = Field(min_length=3, max_length=240)
    objectives: str = Field(min_length=20, max_length=12000)
    methodology: str = Field(min_length=30, max_length=20000)
    sampling_and_participants: str | None = Field(default=None, max_length=12000)
    data_management: str | None = Field(default=None, max_length=12000)
    risk_and_safeguarding: str | None = Field(default=None, max_length=12000)


class ProtocolRead(BaseModel):
    """Protocol version without internal account identifiers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    version_number: int
    title: str
    objectives: str
    methodology: str
    sampling_and_participants: str | None
    data_management: str | None
    risk_and_safeguarding: str | None
    status: str
    submitted_at: datetime | None
    created_at: datetime


class ProtocolComparisonFieldRead(BaseModel):
    """One protocol field compared between two immutable versions."""

    field: Literal[
        "title",
        "objectives",
        "methodology",
        "sampling_and_participants",
        "data_management",
        "risk_and_safeguarding",
    ]
    before: str | None
    after: str | None
    changed: bool


class ProtocolComparisonRead(BaseModel):
    """Field-level comparison between two versions of one study protocol."""

    study_id: str
    from_version: int
    to_version: int
    changed_field_count: int
    fields: list[ProtocolComparisonFieldRead]


class ProtocolReviewCreate(BaseModel):
    """Independent protocol review decision."""

    decision: Literal["approved", "revisions_required", "rejected"]
    note: str = Field(min_length=10, max_length=5000)


class ProtocolReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    protocol_version_id: str
    reviewer_user_id: str
    decision: str
    note: str | None
    reviewed_at: datetime


class EthicsReviewCreate(BaseModel):
    """Formal ethics committee outcome for an approved protocol version."""

    protocol_version_id: str
    decision: Literal["approved", "revisions_required", "rejected", "exempt"]
    reference: str | None = Field(default=None, max_length=160)
    note: str = Field(min_length=10, max_length=5000)


class EthicsReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    study_id: str
    protocol_version_id: str | None
    reviewer_user_id: str
    decision: str
    reference: str | None
    note: str | None
    reviewed_at: datetime


class ResearchGovernanceStudyStatusRead(BaseModel):
    """Minimal oversight status for one tenant-owned research study."""

    study_id: str
    study_title: str
    study_status: str
    protocol_version_id: str | None
    protocol_version_number: int | None
    protocol_status: str | None
    latest_protocol_decision: str | None
    latest_protocol_reviewed_at: datetime | None
    ethics_decision: str | None
    ethics_reviewer_user_id: str | None
    ethics_reference: str | None
    ethics_reviewed_at: datetime | None
    attention_state: Literal[
        "no_protocol",
        "protocol_review_pending",
        "ethics_review_required",
        "ethics_revisions_required",
        "ethics_rejected",
        "paused_pending_clearance",
        "active",
        "other",
    ]


class ResearchGovernanceOversightRead(BaseModel):
    """Leadership snapshot of research protocol and ethics clearance."""

    organization_id: str
    studies_total: int
    active_studies: int
    paused_studies: int
    protocol_reviews_pending: int
    ethics_reviews_required: int
    adverse_ethics_outcomes: int
    studies: list[ResearchGovernanceStudyStatusRead]


class ResearchGovernanceAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    actor_user_id: str
    subject_user_id: str | None
    action: str
    changes: dict[str, object]
    created_at: datetime


@audit_router.get("/oversight", response_model=ResearchGovernanceOversightRead)
async def get_research_governance_oversight(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchGovernanceOversightRead:
    """Summarise current protocol and ethics gates for organisation leadership."""
    if not await membership_has_any_role(
        session, membership, _REVIEW_ROLES - {"programme_manager"}
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation leadership role required")

    studies_result = await session.scalars(
        select(ResearchStudy)
        .where(ResearchStudy.organization_id == organization_id)
        .order_by(ResearchStudy.created_at.desc(), ResearchStudy.id.desc())
        .limit(5000)
    )
    studies = studies_result.all()
    study_ids = [study.id for study in studies]
    if not study_ids:
        return ResearchGovernanceOversightRead(
            organization_id=organization_id,
            studies_total=0,
            active_studies=0,
            paused_studies=0,
            protocol_reviews_pending=0,
            ethics_reviews_required=0,
            adverse_ethics_outcomes=0,
            studies=[],
        )

    protocol_result = await session.scalars(
        select(ResearchProtocolVersion)
        .where(ResearchProtocolVersion.study_id.in_(study_ids))
        .order_by(
            ResearchProtocolVersion.study_id,
            ResearchProtocolVersion.version_number.desc(),
            ResearchProtocolVersion.id.desc(),
        )
    )
    latest_protocols: dict[str, ResearchProtocolVersion] = {}
    for protocol in protocol_result.all():
        latest_protocols.setdefault(protocol.study_id, protocol)

    protocol_ids = [protocol.id for protocol in latest_protocols.values()]
    protocol_reviews: dict[str, ResearchProtocolReviewEvent] = {}
    if protocol_ids:
        review_result = await session.scalars(
            select(ResearchProtocolReviewEvent)
            .where(ResearchProtocolReviewEvent.protocol_version_id.in_(protocol_ids))
            .order_by(
                ResearchProtocolReviewEvent.protocol_version_id,
                ResearchProtocolReviewEvent.reviewed_at.desc(),
                ResearchProtocolReviewEvent.id.desc(),
            )
        )
        for review in review_result.all():
            protocol_reviews.setdefault(review.protocol_version_id, review)

    ethics_result = await session.scalars(
        select(ResearchEthicsReviewEvent)
        .where(ResearchEthicsReviewEvent.study_id.in_(study_ids))
        .order_by(
            ResearchEthicsReviewEvent.study_id,
            ResearchEthicsReviewEvent.reviewed_at.desc(),
            ResearchEthicsReviewEvent.id.desc(),
        )
    )
    latest_ethics: dict[str, ResearchEthicsReviewEvent] = {}
    for event in ethics_result.all():
        latest_ethics.setdefault(event.study_id, event)

    rows: list[ResearchGovernanceStudyStatusRead] = []
    for study in studies:
        current_protocol = latest_protocols.get(study.id)
        current_review = (
            protocol_reviews.get(current_protocol.id) if current_protocol is not None else None
        )
        ethics = latest_ethics.get(study.id)
        # An ethics decision for an older protocol is historical, not current clearance.
        if (
            ethics is not None
            and current_protocol is not None
            and ethics.protocol_version_id != current_protocol.id
        ):
            ethics = None
        attention: Literal[
            "no_protocol",
            "protocol_review_pending",
            "ethics_review_required",
            "ethics_revisions_required",
            "ethics_rejected",
            "paused_pending_clearance",
            "active",
            "other",
        ]
        if current_protocol is None:
            attention = "no_protocol"
        elif current_protocol.status == "submitted":
            attention = "protocol_review_pending"
        elif ethics is not None and ethics.decision == "revisions_required":
            attention = "ethics_revisions_required"
        elif ethics is not None and ethics.decision == "rejected":
            attention = "ethics_rejected"
        elif study.status == "protocol" and current_protocol.status == "approved":
            attention = "paused_pending_clearance"
        elif current_protocol.status == "approved" and (
            ethics is None or ethics.decision not in {"approved", "exempt"}
        ):
            attention = "ethics_review_required"
        elif study.status == "active":
            attention = "active"
        else:
            attention = "other"
        rows.append(
            ResearchGovernanceStudyStatusRead(
                study_id=study.id,
                study_title=study.title,
                study_status=study.status,
                protocol_version_id=current_protocol.id if current_protocol else None,
                protocol_version_number=current_protocol.version_number
                if current_protocol
                else None,
                protocol_status=current_protocol.status if current_protocol else None,
                latest_protocol_decision=current_review.decision if current_review else None,
                latest_protocol_reviewed_at=current_review.reviewed_at if current_review else None,
                ethics_decision=ethics.decision if ethics else None,
                ethics_reviewer_user_id=ethics.reviewer_user_id if ethics else None,
                ethics_reference=ethics.reference if ethics else None,
                ethics_reviewed_at=ethics.reviewed_at if ethics else None,
                attention_state=attention,
            )
        )
    return ResearchGovernanceOversightRead(
        organization_id=organization_id,
        studies_total=len(rows),
        active_studies=sum(row.study_status == "active" for row in rows),
        paused_studies=sum(row.study_status == "protocol" for row in rows),
        protocol_reviews_pending=sum(
            row.attention_state == "protocol_review_pending" for row in rows
        ),
        ethics_reviews_required=sum(
            row.attention_state == "ethics_review_required" for row in rows
        ),
        adverse_ethics_outcomes=sum(
            row.attention_state in {"ethics_revisions_required", "ethics_rejected"} for row in rows
        ),
        studies=rows,
    )


@audit_router.get("/audit-events", response_model=list[ResearchGovernanceAuditRead])
async def list_research_governance_audit_events(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0, le=100000),
) -> list[ResearchGovernanceAuditRead]:
    """List bounded research governance audit events for organisation leaders."""
    if not await membership_has_any_role(
        session, membership, _REVIEW_ROLES - {"programme_manager"}
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation leadership role required")
    actions = {
        "research.study.status_changed",
        "research.protocol.version_created",
        "research.protocol.submitted",
        "research.protocol.reviewed",
        "research.ethics.review_recorded",
    }
    events = await session.scalars(
        select(OrganizationAuditEvent)
        .where(
            OrganizationAuditEvent.organization_id == organization_id,
            OrganizationAuditEvent.action.in_(actions),
        )
        .order_by(OrganizationAuditEvent.created_at.desc(), OrganizationAuditEvent.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [ResearchGovernanceAuditRead.model_validate(event) for event in events.all()]


@audit_router.get("/audit-events/export")
async def export_research_governance_audit_events(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=5000, ge=1, le=5000),
) -> Response:
    """Export bounded research governance metadata with spreadsheet formula protection."""
    if not await membership_has_any_role(
        session, membership, _REVIEW_ROLES - {"programme_manager"}
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Organisation leadership role required")
    actions = {
        "research.study.status_changed",
        "research.protocol.version_created",
        "research.protocol.submitted",
        "research.protocol.reviewed",
        "research.ethics.review_recorded",
    }
    result = await session.scalars(
        select(OrganizationAuditEvent)
        .where(
            OrganizationAuditEvent.organization_id == organization_id,
            OrganizationAuditEvent.action.in_(actions),
        )
        .order_by(OrganizationAuditEvent.created_at.desc(), OrganizationAuditEvent.id.desc())
        .limit(limit + 1)
    )
    events = result.all()
    truncated = len(events) > limit

    def cell(value: object) -> str:
        text_value = "" if value is None else str(value)
        formula_candidate = text_value.lstrip(" \t\r\n")
        return (
            f"'{text_value}" if formula_candidate.startswith(("=", "+", "-", "@")) else text_value
        )

    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\r\n")
    writer.writerow(
        [
            "recorded_at",
            "action",
            "actor_user_id",
            "subject_user_id",
            "study_id",
            "protocol_version_id",
            "version_number",
            "decision",
            "from_status",
            "to_status",
            "reference",
        ]
    )
    for event in events[:limit]:
        changes = event.changes
        writer.writerow(
            [
                cell(event.created_at.isoformat()),
                cell(event.action),
                cell(event.actor_user_id),
                cell(event.subject_user_id),
                cell(changes.get("study_id")),
                cell(changes.get("protocol_version_id")),
                cell(changes.get("version_number")),
                cell(changes.get("decision")),
                cell(changes.get("from_status")),
                cell(changes.get("to_status")),
                cell(changes.get("reference")),
            ]
        )
    return Response(
        content=output.getvalue().encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="research-governance-audit.csv"',
            "X-Records-Truncated": "true" if truncated else "false",
            "Cache-Control": "no-store",
        },
    )


async def _study(
    session: AsyncSession,
    organization_id: str,
    study_id: str,
    *,
    lock: bool = False,
) -> ResearchStudy:
    statement = select(ResearchStudy).where(
        ResearchStudy.id == study_id,
        ResearchStudy.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    study = await session.scalar(statement)
    if study is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    return study


async def _study_role(
    session: AsyncSession,
    study: ResearchStudy,
    principal: Principal,
    membership: Membership,
) -> str | None:
    if (
        await membership_has_any_role(session, membership, {"admin", "founder", "executive"})
        or study.lead_researcher_id == principal.user_id
    ):  # noqa: E501
        return "editor"
    collaborator = await session.scalar(
        select(ResearchStudyCollaborator).where(
            ResearchStudyCollaborator.study_id == study.id,
            ResearchStudyCollaborator.organization_id == study.organization_id,
            ResearchStudyCollaborator.user_id == principal.user_id,
            ResearchStudyCollaborator.status == "active",
        )
    )
    return collaborator.role if collaborator is not None else None


async def _require_research_access(
    session: AsyncSession,
    study: ResearchStudy,
    principal: Principal,
    membership: Membership,
) -> str:
    role = await _study_role(session, study, principal, membership)
    if role is None and not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study access required")
    return role or "reviewer"


@router.post("/protocol-versions", response_model=ProtocolRead, status_code=201)
async def create_protocol_version(
    organization_id: str,
    study_id: str,
    body: ProtocolCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolRead:
    """Create a new protocol version; existing versions are never overwritten."""
    # Serialize version-number allocation per study on databases supporting row locks.
    study = await _study(session, organization_id, study_id, lock=True)
    role = await _require_research_access(session, study, principal, membership)
    if role not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Protocol authoring permission required")
    if study.status in {"completed", "published", "archived"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A finalised study cannot be amended; create a new study for further research",
        )
    latest = await session.scalar(
        select(func.max(ResearchProtocolVersion.version_number)).where(
            ResearchProtocolVersion.study_id == study_id
        )
    )
    version = ResearchProtocolVersion(
        study_id=study_id,
        version_number=(latest or 0) + 1,
        title=body.title.strip(),
        objectives=body.objectives.strip(),
        methodology=body.methodology.strip(),
        sampling_and_participants=body.sampling_and_participants,
        data_management=body.data_management,
        risk_and_safeguarding=body.risk_and_safeguarding,
        status="draft",
        created_by=principal.user_id,
    )
    session.add(version)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A protocol version was created concurrently; reload the study and retry",
        ) from exc
    if study.status == "active":
        # A material protocol amendment pauses field activity until independent
        # approval and a fresh ethics decision are recorded for this exact version.
        study.status = "protocol"
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                subject_user_id=study.lead_researcher_id,
                action="research.study.status_changed",
                changes={
                    "study_id": study_id,
                    "from_status": "active",
                    "to_status": "protocol",
                    "reason": "protocol_amendment_requires_reapproval",
                    "protocol_version_id": version.id,
                },
            )
        )
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=study.lead_researcher_id,
            action="research.protocol.version_created",
            changes={
                "study_id": study_id,
                "protocol_version_id": version.id,
                "version_number": version.version_number,
                "status": "draft",
            },
        )
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A protocol version was created concurrently; reload the study and retry",
        ) from exc
    await session.refresh(version)
    return ProtocolRead.model_validate(version)


@router.get("/protocol-versions", response_model=list[ProtocolRead])
async def list_protocol_versions(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> list[ProtocolRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    result = await session.scalars(
        select(ResearchProtocolVersion)
        .where(ResearchProtocolVersion.study_id == study_id)
        .order_by(ResearchProtocolVersion.version_number.desc(), ResearchProtocolVersion.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [ProtocolRead.model_validate(item) for item in result.all()]


@router.post("/protocol-versions/{protocol_id}/submit", response_model=ProtocolRead)
async def submit_protocol_version(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolRead:
    """Submit a draft or revision for independent review."""
    study = await _study(session, organization_id, study_id)
    role = await _require_research_access(session, study, principal, membership)
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    if role not in _WRITE_ROLES or (protocol.created_by != principal.user_id and role != "editor"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Protocol submission permission required")
    if protocol.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Protocol version cannot be submitted")
    protocol.status = "submitted"
    protocol.submitted_at = datetime.now(UTC)
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=protocol.created_by,
            action="research.protocol.submitted",
            changes={
                "study_id": study_id,
                "protocol_version_id": protocol.id,
                "version_number": protocol.version_number,
                "status": "submitted",
            },
        )
    )
    await session.commit()
    await session.refresh(protocol)
    return ProtocolRead.model_validate(protocol)


@router.get(
    "/protocol-versions/{protocol_id}/compare/{other_protocol_id}",
    response_model=ProtocolComparisonRead,
)
async def compare_protocol_versions(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    other_protocol_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolComparisonRead:
    """Compare immutable protocol content without exposing another study's records."""
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    if protocol_id == other_protocol_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Choose two different protocol versions")
    versions = await session.scalars(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.study_id == study_id,
            ResearchProtocolVersion.id.in_([protocol_id, other_protocol_id]),
        )
    )
    by_id = {version.id: version for version in versions.all()}
    before = by_id.get(protocol_id)
    after = by_id.get(other_protocol_id)
    if before is None or after is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")

    field_names: tuple[
        Literal[
            "title",
            "objectives",
            "methodology",
            "sampling_and_participants",
            "data_management",
            "risk_and_safeguarding",
        ],
        ...,
    ] = (
        "title",
        "objectives",
        "methodology",
        "sampling_and_participants",
        "data_management",
        "risk_and_safeguarding",
    )
    fields = [
        ProtocolComparisonFieldRead(
            field=field,
            before=getattr(before, field),
            after=getattr(after, field),
            changed=getattr(before, field) != getattr(after, field),
        )
        for field in field_names
    ]
    return ProtocolComparisonRead(
        study_id=study_id,
        from_version=before.version_number,
        to_version=after.version_number,
        changed_field_count=sum(item.changed for item in fields),
        fields=fields,
    )


@router.post(
    "/protocol-versions/{protocol_id}/reviews",
    response_model=ProtocolReviewRead,
    status_code=201,
)
async def review_protocol_version(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    body: ProtocolReviewCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProtocolReviewRead:
    """Record an independent review; submitters cannot review their own version."""
    study = await _study(session, organization_id, study_id)
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Independent reviewer role required")
    if protocol.created_by == principal.user_id or study.lead_researcher_id == principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Authors and study leads cannot review")
    if protocol.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted protocols can be reviewed")
    event = ResearchProtocolReviewEvent(
        protocol_version_id=protocol.id,
        reviewer_user_id=principal.user_id,
        decision=body.decision,
        note=body.note.strip(),
    )
    protocol.status = body.decision
    session.add(event)
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=protocol.created_by,
            action="research.protocol.reviewed",
            changes={
                "study_id": study_id,
                "protocol_version_id": protocol.id,
                "version_number": protocol.version_number,
                "decision": body.decision,
            },
        )
    )
    await session.commit()
    await session.refresh(event)
    return ProtocolReviewRead.model_validate(event)


@router.get(
    "/protocol-versions/{protocol_id}/reviews",
    response_model=list[ProtocolReviewRead],
)
async def list_protocol_reviews(
    organization_id: str,
    study_id: str,
    protocol_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> list[ProtocolReviewRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    protocol = await session.scalar(
        select(ResearchProtocolVersion.id).where(
            ResearchProtocolVersion.id == protocol_id,
            ResearchProtocolVersion.study_id == study_id,
        )
    )
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Protocol version not found")
    result = await session.scalars(
        select(ResearchProtocolReviewEvent)
        .where(ResearchProtocolReviewEvent.protocol_version_id == protocol_id)
        .order_by(ResearchProtocolReviewEvent.reviewed_at, ResearchProtocolReviewEvent.id)
        .offset(offset)
        .limit(limit)
    )
    return [ProtocolReviewRead.model_validate(item) for item in result.all()]


@router.post("/ethics-reviews", response_model=EthicsReviewRead, status_code=201)
async def record_ethics_review(
    organization_id: str,
    study_id: str,
    body: EthicsReviewCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EthicsReviewRead:
    """Record a formal ethics outcome, separate from protocol and dataset review."""
    # Lock the study row so an adverse committee decision cannot race with
    # a concurrent lifecycle transition that would otherwise leave fieldwork active.
    study = await _study(session, organization_id, study_id, lock=True)
    if not await membership_has_any_role(session, membership, _REVIEW_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Ethics reviewer role required")
    if study.lead_researcher_id == principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Study leads cannot review their own study")
    protocol = await session.scalar(
        select(ResearchProtocolVersion).where(
            ResearchProtocolVersion.id == body.protocol_version_id,
            ResearchProtocolVersion.study_id == study_id,
            ResearchProtocolVersion.status == "approved",
        )
    )
    if protocol is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ethics review must reference an approved protocol version for this study",
        )
    if protocol.created_by == principal.user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Protocol authors cannot review its ethics")
    latest_version_number = await session.scalar(
        select(func.max(ResearchProtocolVersion.version_number)).where(
            ResearchProtocolVersion.study_id == study_id
        )
    )
    if protocol.version_number != latest_version_number:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Ethics review must reference the latest protocol version; superseded versions "
            "cannot receive new committee decisions",
        )
    event = ResearchEthicsReviewEvent(
        study_id=study_id,
        protocol_version_id=protocol.id,
        reviewer_user_id=principal.user_id,
        decision=body.decision,
        reference=body.reference,
        note=body.note.strip(),
        # Preserve sub-second ordering so a fresh committee decision always
        # supersedes an earlier decision even on databases with second precision
        # for server-side CURRENT_TIMESTAMP defaults.
        reviewed_at=datetime.now(UTC),
    )
    session.add(event)
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=study.lead_researcher_id,
            action="research.ethics.review_recorded",
            changes={
                "study_id": study_id,
                "protocol_version_id": protocol.id,
                "decision": body.decision,
                "reference": body.reference,
            },
        )
    )
    if study.status == "active" and body.decision in {"revisions_required", "rejected"}:
        study.status = "protocol"
        session.add(
            OrganizationAuditEvent(
                organization_id=organization_id,
                actor_user_id=principal.user_id,
                subject_user_id=study.lead_researcher_id,
                action="research.study.status_changed",
                changes={
                    "study_id": study_id,
                    "from_status": "active",
                    "to_status": "protocol",
                    "reason": "adverse_ethics_decision_requires_pause",
                    "protocol_version_id": protocol.id,
                    "ethics_decision": body.decision,
                },
            )
        )
    await session.commit()
    await session.refresh(event)
    return EthicsReviewRead.model_validate(event)


@router.get("/ethics-reviews", response_model=list[EthicsReviewRead])
async def list_ethics_reviews(
    organization_id: str,
    study_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=10000),
) -> list[EthicsReviewRead]:
    study = await _study(session, organization_id, study_id)
    await _require_research_access(session, study, principal, membership)
    result = await session.scalars(
        select(ResearchEthicsReviewEvent)
        .where(ResearchEthicsReviewEvent.study_id == study_id)
        .order_by(ResearchEthicsReviewEvent.reviewed_at, ResearchEthicsReviewEvent.id)
        .offset(offset)
        .limit(limit)
    )
    return [EthicsReviewRead.model_validate(item) for item in result.all()]
