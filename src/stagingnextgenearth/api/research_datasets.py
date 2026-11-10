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

from stagingnextgenearth.platform.models import Membership, ResearchDataset, ResearchStudy

from .dependencies import Principal, get_current_principal, get_session, require_membership

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
        if (
            self.collection_start is not None
            and self.collection_end is not None
            and self.collection_end < self.collection_start
        ):
            raise ValueError("collection_end must not precede collection_start")
        if len(self.data_dictionary) > 200:
            raise ValueError("data_dictionary cannot contain more than 200 fields")
        return self


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
    if membership.role not in _CREATE_ROLES:
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
    if membership.role not in _REGISTRY_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research registry access required")
    statement = select(ResearchDataset).where(
        ResearchDataset.organization_id == organization_id
    )
    if membership.role != "admin":
        statement = statement.where(
            (ResearchDataset.access_classification != "restricted")
            | (ResearchDataset.owner_user_id == principal.user_id)
        )
    if dataset_status is not None:
        statement = statement.where(ResearchDataset.status == dataset_status)
    result = await session.scalars(
        statement.order_by(ResearchDataset.created_at.desc()).limit(limit)
    )
    return [ResearchDatasetRead.model_validate(item) for item in result.all()]


@router.post("/{dataset_id}/submit", response_model=ResearchDatasetRead)
async def submit_research_dataset(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetRead:
    """Submit an owned draft for independent governance review."""
    if membership.role not in _CREATE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset submission is not permitted")
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if dataset.owner_user_id != principal.user_id and membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the dataset owner can submit it")
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
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
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
    dataset.status = body.decision
    dataset.reviewed_by = principal.user_id
    dataset.reviewed_at = datetime.now(UTC)
    dataset.review_note = body.note.strip() if body.note else None
    await session.commit()
    await session.refresh(dataset)
    return ResearchDatasetRead.model_validate(dataset)
