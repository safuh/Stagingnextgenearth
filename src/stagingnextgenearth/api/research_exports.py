"""Reproducible research dataset hand-off manifests."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchDataset,
    ResearchDatasetFile,
)

from .dependencies import Principal, get_current_principal, get_session, require_membership
from .research_collaborators import study_access_role

router = APIRouter(
    prefix="/organizations/{organization_id}/research-datasets",
    tags=["research-exports"],
)
_REGISTRY_READ_ROLES = {"admin", "programme_manager", "researcher", "institutional_partner"}


class ResearchExportFile(BaseModel):
    """A clean, immutable file version included in the hand-off."""

    file_id: str
    version: int
    filename: str
    media_type: str
    size_bytes: int
    sha256: str
    uploaded_at: datetime


class ResearchExportDataset(BaseModel):
    """Dataset metadata required to interpret a research hand-off."""

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
    data_dictionary: dict[str, object]
    collection_start: str | None
    collection_end: str | None
    files: list[ResearchExportFile]
    excluded_file_versions: int


class ResearchExportManifest(BaseModel):
    """Versioned manifest; file bytes remain behind normal authorised downloads."""

    schema_version: str
    generated_at: datetime
    manifest_sha256: str
    dataset: ResearchExportDataset


@router.get("/{dataset_id}/export-manifest", response_model=ResearchExportManifest)
async def create_research_export_manifest(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchExportManifest:
    """Create a reproducible metadata hand-off for an approved dataset.

    Only clean, available file versions are referenced. File bytes are not
    embedded or exposed; consumers must use the authorised download endpoint.
    """
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if dataset.status != "approved":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only approved datasets can be exported",
        )

    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    if (
        membership.role not in _REGISTRY_READ_ROLES
        and study_role is None
        and dataset.owner_user_id != principal.user_id
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research export access required")
    if (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")

    result = await session.scalars(
        select(ResearchDatasetFile)
        .where(ResearchDatasetFile.dataset_id == dataset_id)
        .order_by(ResearchDatasetFile.version.asc())
    )
    file_versions = result.all()
    included_files = [
        ResearchExportFile(
            file_id=item.id,
            version=item.version,
            filename=item.original_filename,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256_hex,
            uploaded_at=item.uploaded_at,
        )
        for item in file_versions
        if item.status == "available"
        and item.scan_status == "clean"
        and item.sha256_hex is not None
        and item.uploaded_at is not None
    ]

    dataset_manifest = ResearchExportDataset(
        id=dataset.id,
        organization_id=dataset.organization_id,
        study_id=dataset.study_id,
        title=dataset.title,
        description=dataset.description,
        version=dataset.version,
        format=dataset.format,
        source=dataset.source,
        license=dataset.license,
        access_classification=dataset.access_classification,
        data_dictionary=dataset.data_dictionary,
        collection_start=dataset.collection_start.isoformat()
        if dataset.collection_start
        else None,
        collection_end=dataset.collection_end.isoformat() if dataset.collection_end else None,
        files=included_files,
        excluded_file_versions=len(file_versions) - len(included_files),
    )
    canonical = json.dumps(
        dataset_manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return ResearchExportManifest(
        schema_version="1.0",
        generated_at=datetime.now(UTC),
        manifest_sha256=hashlib.sha256(canonical).hexdigest(),
        dataset=dataset_manifest,
    )
