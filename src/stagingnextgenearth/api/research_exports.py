"""Reproducible research dataset hand-off manifests."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchAnalysisRun,
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


class AnalysisOutputArtifact(BaseModel):
    """Checksum-addressed output metadata; storage credentials are never accepted."""

    artifact_id: str = Field(min_length=1, max_length=120)
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(ge=0, le=10_000_000_000)
    sha256: str = Field(pattern=r"^[a-fA-F0-9]{64}$")


class ResearchAnalysisRunCreate(BaseModel):
    """Immutable execution provenance submitted after an analysis has run."""

    file_ids: list[str] = Field(min_length=1, max_length=100)
    analysis_configuration: dict[str, object] = Field(default_factory=dict)
    software_name: str = Field(min_length=1, max_length=120)
    software_version: str = Field(min_length=1, max_length=80)
    code_revision: str | None = Field(default=None, max_length=160)
    parameters: dict[str, object] = Field(default_factory=dict)
    random_seed: int | None = Field(default=None, ge=0, le=9_223_372_036_854_775_807)
    output_artifacts: list[AnalysisOutputArtifact] = Field(default_factory=list, max_length=100)

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("File identifiers cannot be blank")
        if len(set(values)) != len(values):
            raise ValueError("Input file identifiers must be unique")
        return values

    @field_validator("software_name", "software_version")
    @classmethod
    def trim_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Software name and version cannot be blank")
        return cleaned

    @field_validator("analysis_configuration", "parameters")
    @classmethod
    def limit_json_payload(cls, value: dict[str, object]) -> dict[str, object]:
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > 64_000:
            raise ValueError("Analysis metadata cannot exceed 64 KiB per field")
        return value


class ResearchAnalysisRunRead(BaseModel):
    """Persisted analysis provenance and immutable input/output references."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    dataset_id: str
    study_id: str | None
    input_manifest_sha256: str
    input_file_versions: list[dict[str, object]]
    analysis_configuration: dict[str, object]
    software_name: str
    software_version: str
    code_revision: str | None
    parameters: dict[str, object]
    random_seed: int | None
    output_artifacts: list[dict[str, object]]
    created_by: str
    created_at: datetime


async def _get_exportable_dataset(
    session: AsyncSession,
    organization_id: str,
    dataset_id: str,
    principal: Principal,
    membership: Membership,
) -> ResearchDataset:
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if dataset.status != "approved":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only approved datasets can be used")
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
    return dataset


@router.post(
    "/{dataset_id}/analysis-runs",
    response_model=ResearchAnalysisRunRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_analysis_run(
    organization_id: str,
    dataset_id: str,
    body: ResearchAnalysisRunCreate,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ResearchAnalysisRunRead:
    """Record a completed analysis against exact, clean dataset file versions."""
    dataset = await _get_exportable_dataset(
        session, organization_id, dataset_id, principal, membership
    )
    result = await session.scalars(
        select(ResearchDatasetFile).where(
            ResearchDatasetFile.dataset_id == dataset_id,
            ResearchDatasetFile.id.in_(body.file_ids),
            ResearchDatasetFile.status == "available",
            ResearchDatasetFile.scan_status == "clean",
        )
    )
    files = result.all()
    if len(files) != len(body.file_ids) or any(
        item.sha256_hex is None or item.uploaded_at is None for item in files
    ):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Every input must be an available, clean file version with a trusted checksum",
        )
    files_by_id = {item.id: item for item in files}
    ordered_files = [files_by_id[file_id] for file_id in body.file_ids]
    input_snapshot = [
        {
            "file_id": item.id,
            "version": item.version,
            "filename": item.original_filename,
            "media_type": item.media_type,
            "size_bytes": item.size_bytes,
            "sha256": item.sha256_hex,
            "uploaded_at": item.uploaded_at.isoformat(),
        }
        for item in ordered_files
    ]
    canonical = json.dumps(
        input_snapshot, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    run = ResearchAnalysisRun(
        organization_id=organization_id,
        dataset_id=dataset_id,
        study_id=dataset.study_id,
        input_manifest_sha256=hashlib.sha256(canonical).hexdigest(),
        input_file_versions=input_snapshot,
        analysis_configuration=body.analysis_configuration,
        software_name=body.software_name,
        software_version=body.software_version,
        code_revision=body.code_revision,
        parameters=body.parameters,
        random_seed=body.random_seed,
        output_artifacts=[item.model_dump() for item in body.output_artifacts],
        created_by=principal.user_id,
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    return ResearchAnalysisRunRead.model_validate(run)


@router.get(
    "/{dataset_id}/analysis-runs",
    response_model=list[ResearchAnalysisRunRead],
)
async def list_analysis_runs(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
) -> list[ResearchAnalysisRunRead]:
    """List immutable analysis provenance for an authorised approved dataset."""
    await _get_exportable_dataset(
        session, organization_id, dataset_id, principal, membership
    )
    result = await session.scalars(
        select(ResearchAnalysisRun)
        .where(
            ResearchAnalysisRun.organization_id == organization_id,
            ResearchAnalysisRun.dataset_id == dataset_id,
        )
        .order_by(ResearchAnalysisRun.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    return [ResearchAnalysisRunRead.model_validate(item) for item in result.all()]
