"""Tenant-scoped research dataset registry and governance workflow.

This module manages metadata only. It deliberately does not accept file uploads,
issue download URLs, or expose dataset contents.
"""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchDataset,
    ResearchDatasetReviewEvent,
    ResearchStudy,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership
from .research_collaborators import study_access_role

router = APIRouter(
    prefix="/organizations/{organization_id}/research-datasets",
    tags=["research-datasets"],
)
_REGISTRY_ROLES = {"admin", "programme_manager", "researcher", "institutional_partner"}
_CREATE_ROLES = {"admin", "programme_manager", "researcher"}
_REVIEW_ROLES = {"admin", "programme_manager"}


class ResearchDatasetCreate(BaseModel):
    """Metadata supplied when registering a dataset."""

    title: str = Field(min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    version: str = Field(default="1.0", min_length=1, max_length=40)
    format: str = Field(min_length=2, max_length=40)
    source: str = Field(min_length=2, max_length=200)
    license: str | None = Field(default=None, max_length=120)
    access_classification: Literal["public", "organization", "restricted"] = "organization"
    study_id: str | None = None
    data_dictionary: dict[str, object] = Field(default_factory=dict)
    collection_start: date | None = None
    collection_end: date | None = None

    @model_validator(mode="after")
    def validate_collection_dates(self) -> "ResearchDatasetCreate":
        if not self.title.strip() or not self.version.strip():
            raise ValueError("title and version cannot be blank")
        if not self.format.strip() or not self.source.strip():
            raise ValueError("format and source cannot be blank")
        if (
            self.collection_start is not None
            and self.collection_end is not None
            and self.collection_end < self.collection_start
        ):
            raise ValueError("collection_end must not precede collection_start")
        if len(self.data_dictionary) > 200:
            raise ValueError("data_dictionary cannot contain more than 200 fields")
        return self



class ResearchDatasetUpdate(BaseModel):
    """Owner-supplied metadata corrections for drafts and rejected submissions."""

    title: str | None = Field(default=None, min_length=3, max_length=240)
    description: str | None = Field(default=None, max_length=20000)
    version: str | None = Field(default=None, min_length=1, max_length=40)
    format: str | None = Field(default=None, min_length=2, max_length=40)
    source: str | None = Field(default=None, min_length=2, max_length=200)
    license: str | None = Field(default=None, max_length=120)
    access_classification: Literal["public", "organization", "restricted"] | None = None
    study_id: str | None = None
    data_dictionary: dict[str, object] | None = None
    collection_start: date | None = None
    collection_end: date | None = None

    @model_validator(mode="after")
    def validate_dictionary_size(self) -> "ResearchDatasetUpdate":
        if self.data_dictionary is not None and len(self.data_dictionary) > 200:
            raise ValueError("data_dictionary cannot contain more than 200 fields")
        return self


class ResearchDatasetReviewEventRead(BaseModel):
    """A historical review decision."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_id: str
    reviewer_user_id: str | None
    decision: str
    note: str | None
    reviewed_at: datetime


class ResearchDatasetReview(BaseModel):
    """Independent approval or rejection decision."""

    decision: Literal["approved", "rejected"]
    note: str | None = Field(default=None, max_length=2000)


class ResearchDatasetRead(BaseModel):
    """Dataset registry metadata and governance audit state; no file contents."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    study_id: str | None
    title: str
    description: str | None
    version: str
    format: str
    source: str
    license: str | None
    access_classification: str
    status: str
    data_dictionary: dict[str, object]
    collection_start: date | None
    collection_end: date | None
    owner_user_id: str
    submitted_at: datetime | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime
    updated_at: datetime


@router.post("", response_model=ResearchDatasetRead, status_code=status.HTTP_201_CREATED)
async def create_research_dataset(
    organization_id: str,
    body: ResearchDatasetCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetRead:
    """Register metadata; new datasets remain drafts until submitted for review."""
    study_role = await study_access_role(
        session, organization_id, body.study_id, principal, membership
    )
    if membership.role not in _CREATE_ROLES and study_role not in {"editor", "contributor"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset registration is not permitted")
    if body.study_id is not None:
        study = await session.scalar(
            select(ResearchStudy.id).where(
                ResearchStudy.id == body.study_id,
                ResearchStudy.organization_id == organization_id,
            )
        )
        if study is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")
    dataset = ResearchDataset(
        organization_id=organization_id,
        study_id=body.study_id,
        title=body.title.strip(),
        description=body.description,
        version=body.version.strip(),
        format=body.format.strip().lower(),
        source=body.source.strip(),
        license=body.license,
        access_classification=body.access_classification,
        status="draft",
        data_dictionary=body.data_dictionary,
        collection_start=body.collection_start,
        collection_end=body.collection_end,
        owner_user_id=principal.user_id,
    )
    session.add(dataset)
    await session.commit()
    await session.refresh(dataset)
    return ResearchDatasetRead.model_validate(dataset)


@router.get("", response_model=list[ResearchDatasetRead])
async def list_research_datasets(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    dataset_status: Literal[
        "draft", "submitted", "approved", "rejected", "archived"
    ] | None = Query(default=None, alias="status"),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[ResearchDatasetRead]:
    """List registry metadata; restricted entries are visible only to owner/admin."""
    has_registry_access = membership.role in _REGISTRY_ROLES
    result = await session.scalars(
        select(ResearchDataset)
        .where(ResearchDataset.organization_id == organization_id)
        .where(
            ResearchDataset.status == dataset_status
            if dataset_status is not None
            else True
        )
        .order_by(ResearchDataset.created_at.desc())
        .limit(500)
    )
    visible: list[ResearchDatasetRead] = []
    for item in result.all():
        study_role = await study_access_role(
            session, organization_id, item.study_id, principal, membership
        )
        if not has_registry_access and study_role is None:
            continue
        if (
            item.access_classification == "restricted"
            and item.owner_user_id != principal.user_id
            and membership.role != "admin"
            and study_role is None
        ):
            continue
        visible.append(ResearchDatasetRead.model_validate(item))
    if not has_registry_access and not visible:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research registry access required")
    return visible[:limit]


@router.patch("/{dataset_id}", response_model=ResearchDatasetRead)
async def update_research_dataset(
    organization_id: str,
    dataset_id: str,
    body: ResearchDatasetUpdate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetRead:
    """Correct an owned draft or rejected submission before resubmitting it."""
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    if membership.role not in _CREATE_ROLES and study_role not in {"editor", "contributor"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset editing is not permitted")
    if (
        dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
        and study_role not in {"editor", "contributor"}
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset owner or study editor required")
    if dataset.status not in {"draft", "rejected"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only draft or rejected datasets can be edited",
        )

    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "No dataset changes supplied")
    required_fields = {
        "title",
        "version",
        "format",
        "source",
        "access_classification",
        "data_dictionary",
    }
    if any(field in changes and changes[field] is None for field in required_fields):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Required dataset metadata fields cannot be null",
        )
    if "study_id" in changes and changes["study_id"] is not None:
        target_role = await study_access_role(
            session, organization_id, changes["study_id"], principal, membership
        )
        if membership.role not in _CREATE_ROLES and target_role not in {"editor", "contributor"}:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Target study access required")
        study = await session.scalar(
            select(ResearchStudy.id).where(
                ResearchStudy.id == changes["study_id"],
                ResearchStudy.organization_id == organization_id,
            )
        )
        if study is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Research study not found")

    for field, value in changes.items():
        if isinstance(value, str) and field in {"title", "version", "format", "source"}:
            value = value.strip()
            if not value:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"{field} cannot be blank",
                )
        if field == "format" and value is not None:
            value = value.lower()
        setattr(dataset, field, value)

    if (
        dataset.collection_start is not None
        and dataset.collection_end is not None
        and dataset.collection_end < dataset.collection_start
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "collection_end must not precede collection_start",
        )
    if dataset.status == "rejected":
        dataset.status = "draft"
        dataset.submitted_at = None
        dataset.reviewed_by = None
        dataset.reviewed_at = None
        dataset.review_note = None

    await session.commit()
    await session.refresh(dataset)
    return ResearchDatasetRead.model_validate(dataset)


@router.get("/{dataset_id}/reviews", response_model=list[ResearchDatasetReviewEventRead])
async def list_research_dataset_reviews(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ResearchDatasetReviewEventRead]:
    """Read immutable review history subject to the dataset's metadata visibility."""
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    if membership.role not in _REGISTRY_ROLES and study_role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research registry access required")
    if (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
        and study_role is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    result = await session.scalars(
        select(ResearchDatasetReviewEvent)
        .where(ResearchDatasetReviewEvent.dataset_id == dataset_id)
        .order_by(ResearchDatasetReviewEvent.reviewed_at.asc())
    )
    return [ResearchDatasetReviewEventRead.model_validate(item) for item in result.all()]


@router.post("/{dataset_id}/submit", response_model=ResearchDatasetRead)
async def submit_research_dataset(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetRead:
    """Submit an owned draft for independent governance review."""
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    if membership.role not in _CREATE_ROLES and study_role != "editor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset submission is not permitted")
    if (
        dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
        and study_role != "editor"
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset owner or study editor required")
    if dataset.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only draft datasets can be submitted")
    dataset.status = "submitted"
    dataset.submitted_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(dataset)
    return ResearchDatasetRead.model_validate(dataset)


@router.post("/{dataset_id}/review", response_model=ResearchDatasetRead)
async def review_research_dataset(
    organization_id: str,
    dataset_id: str,
    body: ResearchDatasetReview,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetRead:
    """Record an independent, one-time approval or rejection decision."""
    if membership.role not in _REVIEW_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset reviewer role required")
    dataset = await session.scalar(
        select(ResearchDataset)
        .where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
        .with_for_update()
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if dataset.access_classification == "restricted" and membership.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Restricted datasets require an administrator reviewer",
        )
    if dataset.owner_user_id == principal.user_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Dataset owners cannot review their own data",
        )
    if dataset.status != "submitted":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only submitted datasets can be reviewed")
    reviewed_at = datetime.now(UTC)
    review_note = body.note.strip() if body.note else None
    dataset.status = body.decision
    dataset.reviewed_by = principal.user_id
    dataset.reviewed_at = reviewed_at
    dataset.review_note = review_note
    session.add(
        ResearchDatasetReviewEvent(
            dataset_id=dataset.id,
            reviewer_user_id=principal.user_id,
            decision=body.decision,
            note=review_note,
            reviewed_at=reviewed_at,
        )
    )
    await session.commit()
    await session.refresh(dataset)
    return ResearchDatasetRead.model_validate(dataset)
