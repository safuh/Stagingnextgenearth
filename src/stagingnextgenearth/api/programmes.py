"""Organisation-scoped programme read and create endpoints."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    Organization,
    Programme,
    ProgrammeDeliverable,
    ProgrammeGoal,
    ProgrammeIndicator,
    ProgrammeIndicatorMeasurement,
    ProgrammeMilestone,
    Project,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(prefix="/organizations/{organization_id}/programmes", tags=["programmes"])
public_router = APIRouter(tags=["public-programmes"])


class ProgrammeCreate(BaseModel):
    """Programme creation contract."""

    title: str = Field(min_length=2, max_length=240)
    slug: str = Field(min_length=2, max_length=140, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    summary: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ProgrammeCreate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class ProgrammeRead(BaseModel):
    """Programme response model."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    title: str
    slug: str
    summary: str | None
    status: str
    start_date: date | None
    end_date: date | None


@router.post("", response_model=ProgrammeRead, status_code=status.HTTP_201_CREATED)
async def create_programme(
    organization_id: str,
    body: ProgrammeCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProgrammeRead:
    """Create a draft programme; only administrators and programme managers may write."""
    if membership.role not in {"admin", "founder", "executive", "programme_manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient organisation permissions")
    programme = Programme(
        organization_id=organization_id,
        title=body.title.strip(),
        slug=body.slug,
        summary=body.summary,
        status="draft",
        start_date=body.start_date,
        end_date=body.end_date,
        created_by=principal.user_id,
    )
    session.add(programme)
    try:
        await session.commit()
        await session.refresh(programme)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Programme slug already exists") from exc
    return ProgrammeRead.model_validate(programme)


@router.get("", response_model=list[ProgrammeRead])
async def list_programmes(
    organization_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProgrammeRead]:
    """List programmes only inside an organisation the caller actively belongs to."""
    result = await session.scalars(
        select(Programme)
        .where(Programme.organization_id == organization_id)
        .order_by(Programme.created_at.desc())
    )
    return [ProgrammeRead.model_validate(item) for item in result.all()]



class ProgrammeUpdate(BaseModel):
    """Partial programme metadata update; omitted fields remain unchanged."""

    title: str | None = Field(default=None, min_length=2, max_length=240)
    slug: str | None = Field(
        default=None,
        min_length=2,
        max_length=140,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    summary: str | None = Field(default=None, max_length=10000)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def validate_dates(self) -> "ProgrammeUpdate":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must not precede start_date")
        return self


class ProgrammeProjectRead(BaseModel):
    """Project metadata associated with a programme."""

    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    summary: str | None
    status: str
    country_code: str
    county: str | None


@router.patch("/{programme_id}", response_model=ProgrammeRead)
async def update_programme(
    organization_id: str,
    programme_id: str,
    body: ProgrammeUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProgrammeRead:
    """Update programme metadata without changing its lifecycle state."""
    if membership.role not in {"admin", "founder", "executive", "programme_manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    changes = body.model_dump(exclude_unset=True)
    if "title" in changes and changes["title"] is not None:
        changes["title"] = changes["title"].strip()
    if "slug" in changes and changes["slug"] is not None:
        changes["slug"] = changes["slug"].strip()
    if "summary" in changes and changes["summary"] is not None:
        changes["summary"] = changes["summary"].strip() or None
    for field, value in changes.items():
        setattr(programme, field, value)
    if (
        programme.start_date
        and programme.end_date
        and programme.end_date < programme.start_date
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "end_date must not precede start_date",
        )
    try:
        await session.commit()
        await session.refresh(programme)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Programme slug already exists") from exc
    return ProgrammeRead.model_validate(programme)


@router.get("/{programme_id}/projects", response_model=list[ProgrammeProjectRead])
async def list_programme_projects(
    organization_id: str,
    programme_id: str,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ProgrammeProjectRead]:
    """List projects linked to a programme within the same tenant."""
    programme = await session.scalar(
        select(Programme.id).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    rows = await session.scalars(
        select(Project)
        .where(Project.organization_id == organization_id, Project.programme_id == programme_id)
        .order_by(Project.title)
        .limit(500)
    )
    return [ProgrammeProjectRead.model_validate(item) for item in rows.all()]


class ProgrammeStatusUpdate(BaseModel):
    """Explicit programme lifecycle transition."""

    status: str = Field(pattern=r"^(planned|active|completed|archived)$")


@router.post("/{programme_id}/status", response_model=ProgrammeRead)
async def update_programme_status(
    organization_id: str,
    programme_id: str,
    body: ProgrammeStatusUpdate,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ProgrammeRead:
    """Apply a guarded lifecycle transition to an organisation's programme."""
    if membership.role not in {"admin", "founder", "executive", "programme_manager"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Programme management permission required")
    programme = await session.scalar(
        select(Programme).where(
            Programme.id == programme_id,
            Programme.organization_id == organization_id,
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    allowed = {
        "draft": {"planned", "archived"},
        "planned": {"active", "archived"},
        "active": {"completed", "archived"},
        "completed": {"archived"},
        "archived": set(),
    }
    if body.status not in allowed.get(programme.status, set()):
        raise HTTPException(status.HTTP_409_CONFLICT, "Invalid programme status transition")
    programme.status = body.status
    await session.commit()
    await session.refresh(programme)
    return ProgrammeRead.model_validate(programme)


class PublicProgrammeRead(BaseModel):
    """Public programme catalogue fields."""
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    title: str
    slug: str
    summary: str | None
    status: str
    start_date: date | None
    end_date: date | None


@public_router.get(
    "/public/organizations/{organization_slug}/programmes",
    response_model=list[PublicProgrammeRead],
)
async def list_public_programmes(
    organization_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicProgrammeRead]:
    """Expose planned and active programmes without requiring membership."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    rows = await session.scalars(
        select(Programme)
        .where(
            Programme.organization_id == organization.id,
            Programme.status.in_({"planned", "active"}),
        )
        .order_by(Programme.title)
        .limit(250)
    )
    return [PublicProgrammeRead.model_validate(item) for item in rows.all()]


class PublicProgrammeProjectRead(BaseModel):
    """Non-sensitive project summary for a published programme page."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: str | None
    status: str
    country_code: str
    county: str | None


@public_router.get(
    "/public/organizations/{organization_slug}/programmes/{programme_slug}/projects",
    response_model=list[PublicProgrammeProjectRead],
)
async def list_public_programme_projects(
    organization_slug: str,
    programme_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[PublicProgrammeProjectRead]:
    """Expose public-safe project summaries only for published programmes."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    programme = await session.scalar(
        select(Programme.id).where(
            Programme.organization_id == organization.id,
            Programme.slug == programme_slug,
            Programme.status.in_({"planned", "active"}),
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")
    rows = await session.scalars(
        select(Project)
        .where(
            Project.organization_id == organization.id,
            Project.programme_id == programme,
            Project.status.in_({"planned", "in_progress", "completed"}),
        )
        .order_by(Project.title)
        .limit(500)
    )
    return [PublicProgrammeProjectRead.model_validate(item) for item in rows.all()]

class PublicProgrammeMilestoneRead(BaseModel):
    """Completed public milestone without internal ownership metadata."""

    title: str
    description: str | None
    due_date: date | None
    goal_title: str


class PublicProgrammeDeliverableRead(BaseModel):
    """Accepted deliverable summary; evidence and reviewer data stay private."""

    title: str
    description: str | None
    due_date: date | None


class PublicProgrammeIndicatorRead(BaseModel):
    """Public indicator definition and latest approved reporting value."""

    key: str
    title: str
    description: str | None
    unit: str
    direction: str
    baseline_value: float | None
    target_value: float | None
    latest_value: float | None
    latest_period_start: date | None
    latest_period_end: date | None
    progress_percent: float | None


class PublicProgrammeReportRead(BaseModel):
    """Public-safe implementation and impact report for one programme."""

    milestones: list[PublicProgrammeMilestoneRead]
    deliverables: list[PublicProgrammeDeliverableRead]
    indicators: list[PublicProgrammeIndicatorRead]


@public_router.get(
    "/public/organizations/{organization_slug}/programmes/{programme_slug}/report",
    response_model=PublicProgrammeReportRead,
)
async def get_public_programme_report(
    organization_slug: str,
    programme_slug: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PublicProgrammeReportRead:
    """Publish completed milestones, accepted outputs and measured indicators only."""
    organization = await session.scalar(
        select(Organization).where(Organization.slug == organization_slug)
    )
    if organization is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    programme = await session.scalar(
        select(Programme).where(
            Programme.organization_id == organization.id,
            Programme.slug == programme_slug,
            Programme.status.in_({"planned", "active"}),
        )
    )
    if programme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Programme not found")

    milestone_rows = await session.execute(
        select(ProgrammeMilestone, ProgrammeGoal.title)
        .join(ProgrammeGoal, ProgrammeGoal.id == ProgrammeMilestone.goal_id)
        .where(
            ProgrammeMilestone.organization_id == organization.id,
            ProgrammeMilestone.programme_id == programme.id,
            ProgrammeMilestone.status == "completed",
            ProgrammeGoal.status.in_({"active", "achieved"}),
        )
        .order_by(ProgrammeMilestone.due_date, ProgrammeMilestone.title)
        .limit(500)
    )
    milestones = [
        PublicProgrammeMilestoneRead(
            title=item.title,
            description=item.description,
            due_date=item.due_date,
            goal_title=goal_title,
        )
        for item, goal_title in milestone_rows.all()
    ]

    deliverable_rows = await session.scalars(
        select(ProgrammeDeliverable)
        .where(
            ProgrammeDeliverable.organization_id == organization.id,
            ProgrammeDeliverable.programme_id == programme.id,
            ProgrammeDeliverable.status == "accepted",
        )
        .order_by(ProgrammeDeliverable.due_date, ProgrammeDeliverable.title)
        .limit(500)
    )
    deliverables = [
        PublicProgrammeDeliverableRead(
            title=item.title,
            description=item.description,
            due_date=item.due_date,
        )
        for item in deliverable_rows.all()
    ]

    indicator_rows = await session.scalars(
        select(ProgrammeIndicator)
        .where(
            ProgrammeIndicator.organization_id == organization.id,
            ProgrammeIndicator.programme_id == programme.id,
        )
        .order_by(ProgrammeIndicator.title)
        .limit(200)
    )
    indicators: list[PublicProgrammeIndicatorRead] = []
    for indicator in indicator_rows.all():
        latest = await session.scalar(
            select(ProgrammeIndicatorMeasurement)
            .where(
                ProgrammeIndicatorMeasurement.organization_id == organization.id,
                ProgrammeIndicatorMeasurement.programme_id == programme.id,
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
                progress = round(((latest.value - baseline) / denominator) * 100, 2)
        indicators.append(
            PublicProgrammeIndicatorRead(
                key=indicator.key,
                title=indicator.title,
                description=indicator.description,
                unit=indicator.unit,
                direction=indicator.direction,
                baseline_value=indicator.baseline_value,
                target_value=indicator.target_value,
                latest_value=latest.value if latest is not None else None,
                latest_period_start=latest.period_start if latest is not None else None,
                latest_period_end=latest.period_end if latest is not None else None,
                progress_percent=progress,
            )
        )
    return PublicProgrammeReportRead(
        milestones=milestones,
        deliverables=deliverables,
        indicators=indicators,
    )

