"""Controlled upload-intent and quarantine workflow for dataset file versions."""

import asyncio
import hashlib
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    Membership,
    ResearchDataset,
    ResearchDatasetFile,
    ResearchDatasetFileAccessEvent,
)
from stagingnextgenearth.storage import ObjectStorage

from .dependencies import Principal, get_current_principal, get_session, require_membership

router = APIRouter(
    prefix="/organizations/{organization_id}/research-datasets",
    tags=["research-dataset-files"],
)
_WRITE_ROLES = {"admin", "programme_manager", "researcher"}
_ALLOWED_TYPES = {
    "text/csv": ".csv",
    "application/json": ".json",
    "application/pdf": ".pdf",
    "application/zip": ".zip",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
}
_MAX_FILE_BYTES = 100 * 1024 * 1024
_UPLOAD_EXPIRY_SECONDS = 600
_DOWNLOAD_EXPIRY_SECONDS = 300
_READ_ROLES = _WRITE_ROLES | {"institutional_partner"}


class DatasetFileUploadIntent(BaseModel):
    """Client metadata used to request a constrained upload form."""

    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(gt=0, le=_MAX_FILE_BYTES)


class DatasetFileUploadIntentRead(BaseModel):
    """Upload form and server-owned file-version identity."""

    file_id: str
    version: int
    status: str
    upload_method: str
    upload_url: str
    upload_fields: dict[str, str]
    expires_in_seconds: int




class DatasetFileDownloadRead(BaseModel):
    """Short-lived download location and its durable audit reference."""

    download_url: str
    expires_in_seconds: int
    access_event_id: str


class DatasetFileRead(BaseModel):
    """Safe file metadata; storage keys and provider details are never exposed."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    version: int
    original_filename: str
    media_type: str
    size_bytes: int
    sha256_hex: str | None
    status: str
    scan_status: str
    uploaded_at: datetime | None


def _storage(request: Request) -> ObjectStorage:
    """Resolve configured storage without leaking provider configuration."""
    adapter = request.app.state.object_storage
    if adapter is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Private object storage is not configured",
        )
    return adapter


@router.post(
    "/{dataset_id}/files/upload-intents",
    response_model=DatasetFileUploadIntentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_dataset_file_upload_intent(
    organization_id: str,
    dataset_id: str,
    body: DatasetFileUploadIntent,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetFileUploadIntentRead:
    """Reserve a file version and issue a short-lived constrained upload form."""
    if membership.role not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset upload is not permitted")
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
    if dataset.owner_user_id != principal.user_id and membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the dataset owner can upload files")
    if dataset.status not in {"draft", "rejected"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Files can only be added to draft or rejected datasets",
        )
    if body.media_type not in _ALLOWED_TYPES:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "File type is not allowed")
    filename = PurePath(body.filename).name.strip()
    if (
        not filename
        or filename != body.filename
        or filename in {".", ".."}
        or "\\" in filename
        or any(ord(character) < 32 for character in filename)
        or not filename.lower().endswith(_ALLOWED_TYPES[body.media_type])
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid filename or extension")

    storage = _storage(request)
    latest_version = await session.scalar(
        select(func.max(ResearchDatasetFile.version)).where(
            ResearchDatasetFile.dataset_id == dataset_id
        )
    )
    version = int(latest_version or 0) + 1
    file_id = str(uuid4())
    storage_key = f"dataset-files/{organization_id}/{dataset_id}/{file_id}"
    try:
        form = storage.create_upload_form(
            key=storage_key,
            content_type=body.media_type,
            max_bytes=body.size_bytes,
            expires_seconds=_UPLOAD_EXPIRY_SECONDS,
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Unable to initialise private upload",
        ) from exc

    record = ResearchDatasetFile(
        id=file_id,
        dataset_id=dataset_id,
        version=version,
        original_filename=filename,
        media_type=body.media_type,
        size_bytes=body.size_bytes,
        storage_key=storage_key,
        status="upload_pending",
        scan_status="pending",
        created_by=principal.user_id,
    )
    session.add(record)
    await session.commit()
    return DatasetFileUploadIntentRead(
        file_id=file_id,
        version=version,
        status=record.status,
        upload_method="POST",
        upload_url=form.url,
        upload_fields=form.fields,
        expires_in_seconds=_UPLOAD_EXPIRY_SECONDS,
    )


@router.post(
    "/{dataset_id}/files/{file_id}/complete",
    response_model=DatasetFileRead,
)
async def complete_dataset_file_upload(
    organization_id: str,
    dataset_id: str,
    file_id: str,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetFileRead:
    """Verify, quarantine, and scan a completed upload when a scanner is configured."""
    if membership.role not in _WRITE_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset upload is not permitted")
    record = await session.scalar(
        select(ResearchDatasetFile)
        .join(ResearchDataset, ResearchDataset.id == ResearchDatasetFile.dataset_id)
        .where(
            ResearchDatasetFile.id == file_id,
            ResearchDatasetFile.dataset_id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
        .with_for_update()
    )
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset file not found")
    if record.created_by != principal.user_id and membership.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the uploader can complete this upload")
    if record.status not in {"upload_pending", "quarantined"}:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Upload is not awaiting verification or scanning",
        )

    storage = _storage(request)
    if record.status == "upload_pending":
        try:
            stored = await asyncio.to_thread(storage.inspect, key=record.storage_key)
        except Exception as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Unable to verify uploaded object",
            ) from exc
        if stored is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Uploaded object was not found")
        if stored.size_bytes != record.size_bytes or stored.content_type != record.media_type:
            record.status = "rejected"
            # Metadata validation is not a malware scan; keep scan state pending.
            record.scan_status = "pending"
            record.scanned_at = None
            await session.commit()
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Uploaded object metadata does not match the upload intent",
            )
        record.uploaded_at = datetime.now(UTC)
        record.status = "quarantined"
        await session.commit()
        await session.refresh(record)

    scanner = request.app.state.dataset_file_scanner
    if scanner is None:
        return DatasetFileRead.model_validate(record)

    try:
        content = await asyncio.to_thread(
            storage.get_object,
            key=record.storage_key,
            max_bytes=_MAX_FILE_BYTES,
        )
        if len(content) != record.size_bytes:
            record.status = "rejected"
            record.scan_status = "pending"
            record.scanned_at = None
            await session.commit()
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "Stored object size changed after upload verification",
            )
        is_clean = await asyncio.to_thread(scanner.scan, content)
    except HTTPException:
        raise
    except Exception as exc:
        # Keep the object quarantined; transient scanner/storage failures are retryable.
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "File remains quarantined because scanning could not be completed",
        ) from exc

    record.sha256_hex = hashlib.sha256(content).hexdigest()
    record.scanned_at = datetime.now(UTC)
    record.scan_status = "clean" if is_clean else "rejected"
    record.status = "available" if is_clean else "rejected"
    await session.commit()
    await session.refresh(record)
    return DatasetFileRead.model_validate(record)




@router.post(
    "/{dataset_id}/files/{file_id}/download",
    response_model=DatasetFileDownloadRead,
)
async def create_dataset_file_download(
    organization_id: str,
    dataset_id: str,
    file_id: str,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DatasetFileDownloadRead:
    """Issue a short-lived URL only for clean files and record the access grant."""
    if membership.role not in _READ_ROLES:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset file access is not permitted")
    result = await session.execute(
        select(ResearchDatasetFile, ResearchDataset)
        .join(ResearchDataset, ResearchDataset.id == ResearchDatasetFile.dataset_id)
        .where(
            ResearchDatasetFile.id == file_id,
            ResearchDatasetFile.dataset_id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    record, dataset = result.one_or_none() or (None, None)
    if record is None or dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset file not found")
    if (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset file not found")
    if record.status != "available" or record.scan_status != "clean" or not record.sha256_hex:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Dataset file is not available for download",
        )
    try:
        download_url = _storage(request).create_download_url(
            key=record.storage_key,
            expires_seconds=_DOWNLOAD_EXPIRY_SECONDS,
        )
    except Exception as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Unable to create authorised download",
        ) from exc

    event = ResearchDatasetFileAccessEvent(
        dataset_file_id=record.id,
        user_id=principal.user_id,
        action="download_url_issued",
    )
    session.add(event)
    await session.commit()
    return DatasetFileDownloadRead(
        download_url=download_url,
        expires_in_seconds=_DOWNLOAD_EXPIRY_SECONDS,
        access_event_id=event.id,
    )


@router.get("/{dataset_id}/files", response_model=list[DatasetFileRead])
async def list_dataset_files(
    organization_id: str,
    dataset_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DatasetFileRead]:
    """List file metadata without disclosing storage keys or download locations."""
    if membership.role not in _WRITE_ROLES | {"institutional_partner"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Dataset registry access required")
    dataset = await session.scalar(
        select(ResearchDataset).where(
            ResearchDataset.id == dataset_id,
            ResearchDataset.organization_id == organization_id,
        )
    )
    if dataset is None or (
        dataset.access_classification == "restricted"
        and dataset.owner_user_id != principal.user_id
        and membership.role != "admin"
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    result = await session.scalars(
        select(ResearchDatasetFile)
        .where(ResearchDatasetFile.dataset_id == dataset_id)
        .order_by(ResearchDatasetFile.version.desc())
    )
    return [DatasetFileRead.model_validate(item) for item in result.all()]
