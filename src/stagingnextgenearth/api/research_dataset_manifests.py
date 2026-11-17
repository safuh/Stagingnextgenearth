"""Deterministic, access-controlled manifests for approved research datasets."""

from hashlib import sha256
import json
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

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)
from .research_collaborators import study_access_role

router = APIRouter(
    prefix="/organizations/{organization_id}/research-datasets",
    tags=["research-datasets"],
)
_MANIFEST_ROLES = {
    "admin", "founder", "executive", "programme_manager",
    "researcher", "institutional_partner",
}
_PRIVILEGED_ROLES = {"admin", "founder", "executive"}


class DatasetManifestFile(BaseModel):
    """Public-safe identity and integrity fields for one available file version."""

    file_id: str
    version: int
    filename: str
    media_type: str
    size_bytes: int
    sha256: str


class ResearchDatasetManifestRead(BaseModel):
    """Deterministic manifest; storage keys and file contents are never exposed."""

    dataset_id: str
    dataset_version: str
    manifest_sha256: str
    file_count: int
    files: list[DatasetManifestFile]


@router.get("/{dataset_id}/manifest", response_model=ResearchDatasetManifestRead)
async def get_research_dataset_manifest(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchDatasetManifestRead:
    """Return a stable digest over clean, available file versions in an approved dataset."""
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None or dataset.status != "approved":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approved research dataset not found")

    study_role = await study_access_role(
        session, organization_id, dataset.study_id, principal, membership
    )
    has_role = await membership_has_any_role(session, membership, _MANIFEST_ROLES)
    if not has_role and study_role is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Research manifest access required")

    privileged = await membership_has_any_role(
        session, membership, _PRIVILEGED_ROLES
    )
    if (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and not privileged
        and study_role is None
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Approved research dataset not found")

    result = await session.scalars(
        select(ResearchDatasetFile)
        .where(
            ResearchDatasetFile.dataset_id == dataset_id,
            ResearchDatasetFile.status == "available",
            ResearchDatasetFile.scan_status == "clean",
            ResearchDatasetFile.sha256_hex.is_not(None),
        )
        .order_by(ResearchDatasetFile.version.asc(), ResearchDatasetFile.id.asc())
    )
    files = [
        DatasetManifestFile(
            file_id=item.id,
            version=item.version,
            filename=item.original_filename,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256_hex,
        )
        for item in result.all()
    ]
    manifest_data = {
        "dataset_id": dataset.id,
        "dataset_version": dataset.version,
        "files": [item.model_dump() for item in files],
    }
    digest = sha256(
        json.dumps(
            manifest_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
    ).hexdigest()
    return ResearchDatasetManifestRead(
        dataset_id=dataset.id,
        dataset_version=dataset.version,
        manifest_sha256=digest,
        file_count=len(files),
        files=files,
    )
