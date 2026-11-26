"""Tenant-scoped ODK Central submission import into the climate evidence ledger."""

from datetime import UTC, datetime
from math import isfinite
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    ClimateObservation,
    Membership,
    OrganizationAuditEvent,
    Project,
    ResearchStudy,
)

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)

router = APIRouter(prefix="/organizations/{organization_id}/odk", tags=["odk-integration"])
_IMPORT_ROLES = {"admin", "founder", "executive", "researcher", "programme_manager"}


class ODKFieldMapping(BaseModel):
    """Explicit mapping from ODK form field names to climate evidence fields."""

    model_config = ConfigDict(extra="forbid")

    observed_at: str = Field(min_length=1, max_length=160)
    variable: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=160)
    unit: str = Field(min_length=1, max_length=160)
    latitude: str = Field(min_length=1, max_length=160)
    longitude: str = Field(min_length=1, max_length=160)
    project_id: str | None = Field(default=None, max_length=160)
    study_id: str | None = Field(default=None, max_length=160)


class ODKImportRequest(BaseModel):
    """A bounded page of ODK Central JSON submissions and its form mapping."""

    model_config = ConfigDict(extra="forbid")

    form_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_.-]+$")
    submissions: list[dict[str, object]] = Field(min_length=1, max_length=100)
    mapping: ODKFieldMapping


class ODKReconciliationDecision(BaseModel):
    """Explicit human decision for an upstream revision or deletion notice."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["acknowledge_revision", "acknowledge_deletion", "retain_observation"]
    note: str | None = Field(default=None, max_length=2000)


class ODKImportResult(BaseModel):
    form_id: str
    received: int
    imported: int
    skipped_duplicates: int
    observation_ids: list[str]


def _field(data: dict[str, object], key: str) -> object | None:
    """Read exact ODK JSON keys, including slash-delimited metadata paths."""
    if key in data:
        return data[key]
    current: object = data
    for part in key.split("/"):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _required_text(data: dict[str, object], key: str, label: str) -> str:
    value = _field(data, key)
    if value is None or isinstance(value, (dict, list, bool)):
        raise ValueError(f"ODK field '{key}' is required for {label}")
    text = str(value).strip()
    if not text:
        raise ValueError(f"ODK field '{key}' is empty")
    return text


@router.post("/imports", response_model=ODKImportResult, status_code=status.HTTP_200_OK)
async def import_odk_submissions(
    organization_id: str,
    body: ODKImportRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ODKImportResult:
    """Import an ODK Central JSON page as pending climate observations.

    The endpoint deliberately accepts data, not an upstream URL or credentials:
    ODK Central authentication and pagination belong in the trusted sync worker.
    Raw form payloads are not retained; only mapped scientific fields and source
    identifiers enter the climate ledger.
    """
    if not await membership_has_any_role(session, membership, _IMPORT_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ODK import permission required")

    imported_ids: list[str] = []
    skipped = 0
    for index, submission in enumerate(body.submissions):
        data_value = submission.get("data", submission)
        if not isinstance(data_value, dict):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Submission {index} has no data object"
            )
        data = data_value
        instance_value = (
            submission.get("instanceId")
            or submission.get("instanceID")
            or submission.get("__id")
            or _field(data, "meta/instanceID")
            or _field(data, "instanceID")
        )
        if instance_value is None or not str(instance_value).strip():
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Submission {index} has no ODK instance ID"
            )
        record_id = f"{body.form_id}:{str(instance_value).strip()}"
        if len(record_id) > 200:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Submission {index} has an overlong instance ID",
            )
        existing = await session.scalar(
            select(ClimateObservation.id).where(
                ClimateObservation.organization_id == organization_id,
                ClimateObservation.provider_id == "odk-central",
                ClimateObservation.provider_record_id == record_id,
            )
        )
        if existing is not None:
            skipped += 1
            continue

        try:
            observed_at = datetime.fromisoformat(
                _required_text(data, body.mapping.observed_at, "observed_at")
            )
            if observed_at.tzinfo is None or observed_at.utcoffset() is None:
                raise ValueError("observed_at must include a timezone")
            variable = _required_text(data, body.mapping.variable, "variable")
            unit = _required_text(data, body.mapping.unit, "unit")
            if len(variable) > 80 or len(unit) > 32:
                raise ValueError("variable or unit exceeds the supported length")
            value = float(_required_text(data, body.mapping.value, "value"))
            latitude = float(_required_text(data, body.mapping.latitude, "latitude"))
            longitude = float(_required_text(data, body.mapping.longitude, "longitude"))
            if not all(isfinite(number) for number in (value, latitude, longitude)):
                raise ValueError("numeric fields must be finite")
            if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
                raise ValueError("coordinates are outside valid latitude/longitude bounds")
            project_id_value = (
                _field(data, body.mapping.project_id) if body.mapping.project_id else None
            )
            study_id_value = _field(data, body.mapping.study_id) if body.mapping.study_id else None
            project_id = str(project_id_value).strip() if project_id_value is not None else None
            study_id = str(study_id_value).strip() if study_id_value is not None else None
        except (ValueError, TypeError, OverflowError) as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, f"Invalid ODK submission {index}: {exc}"
            ) from exc

        if project_id is not None:
            project = await session.scalar(
                select(Project.id).where(
                    Project.id == project_id, Project.organization_id == organization_id
                )
            )
            if project is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Submission {index} references an unknown project",
                )
        if study_id is not None:
            study = await session.scalar(
                select(ResearchStudy).where(
                    ResearchStudy.id == study_id, ResearchStudy.organization_id == organization_id
                )
            )
            if study is None or (
                project_id is not None and study.project_id not in {None, project_id}
            ):
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Submission {index} references an incompatible study",
                )

        observation = ClimateObservation(
            organization_id=organization_id,
            project_id=project_id,
            study_id=study_id,
            observed_at=observed_at.astimezone(UTC),
            variable=variable,
            value=value,
            unit=unit,
            latitude=latitude,
            longitude=longitude,
            source=f"ODK Central form {body.form_id}"[:160],
            provider_id="odk-central",
            provider_record_id=record_id,
            quality_status="pending",
            metadata_json={
                "provider": "odk-central",
                "form_id": body.form_id,
                "instance_id": str(instance_value),
            },
            created_by=principal.user_id,
        )
        session.add(observation)
        await session.flush()
        imported_ids.append(observation.id)

    await session.commit()
    return ODKImportResult(
        form_id=body.form_id,
        received=len(body.submissions),
        imported=len(imported_ids),
        skipped_duplicates=skipped,
        observation_ids=imported_ids,
    )


@router.get("/reconciliation")
async def odk_source_reconciliation_queue(
    membership: Annotated[Membership, Depends(require_membership)],
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 100,
) -> dict[str, object]:
    """List changed/deleted Central records needing human reconciliation.

    The endpoint intentionally exposes identifiers and provenance only; it never
    returns raw submissions or silently replaces scientific measurements.
    """
    if not 1 <= limit <= 250:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "limit must be between 1 and 250")
    if not await membership_has_any_role(session, membership, _IMPORT_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ODK reconciliation permission required")

    from sqlalchemy import func, or_

    revision_flag = ClimateObservation.metadata_json["odk_source_revision_detected"].as_boolean()
    deletion_flag = ClimateObservation.metadata_json[
        "odk_source_deletion_review_required"
    ].as_boolean()
    scope = (
        ClimateObservation.organization_id == membership.organization_id,
        ClimateObservation.provider_id == "odk-central",
        or_(revision_flag.is_(True), deletion_flag.is_(True)),
    )
    total = await session.scalar(select(func.count(ClimateObservation.id)).where(*scope))
    records = list(
        (
            await session.scalars(
                select(ClimateObservation)
                .where(*scope)
                .order_by(ClimateObservation.created_at.desc(), ClimateObservation.id)
                .limit(limit)
            )
        ).all()
    )
    return {
        "total": int(total or 0),
        "returned": len(records),
        "items": [
            {
                "observation_id": item.id,
                "form_id": (item.metadata_json or {}).get("form_id"),
                "instance_id": (item.metadata_json or {}).get("instance_id"),
                "source_updated_at": (item.metadata_json or {}).get("odk_source_updated_at"),
                "source_deleted_at": (item.metadata_json or {}).get("odk_source_deleted_at"),
                "revision_detected": bool(
                    (item.metadata_json or {}).get("odk_source_revision_detected")
                ),
                "deletion_review_required": bool(
                    (item.metadata_json or {}).get("odk_source_deletion_review_required")
                ),
                "quality_status": item.quality_status,
                "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            }
            for item in records
        ],
    }


@router.post("/{observation_id}/reconciliation")
async def decide_odk_source_reconciliation(
    organization_id: str,
    observation_id: str,
    body: ODKReconciliationDecision,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, object]:
    """Record a human decision without deleting or rewriting scientific evidence."""
    if not await membership_has_any_role(session, membership, _IMPORT_ROLES):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ODK reconciliation permission required")
    observation = await session.scalar(
        select(ClimateObservation).where(
            ClimateObservation.id == observation_id,
            ClimateObservation.organization_id == organization_id,
            ClimateObservation.provider_id == "odk-central",
        )
    )
    if observation is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ODK observation not found")

    metadata = dict(observation.metadata_json or {})
    revision_pending = bool(metadata.get("odk_source_revision_detected"))
    deletion_pending = bool(metadata.get("odk_source_deletion_review_required"))
    if not revision_pending and not deletion_pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "No source reconciliation is pending")
    if body.decision == "acknowledge_revision" and not revision_pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "No source revision is pending")
    if body.decision == "acknowledge_deletion" and not deletion_pending:
        raise HTTPException(status.HTTP_409_CONFLICT, "No source deletion is pending")

    if body.decision in {"acknowledge_revision", "retain_observation"}:
        metadata["odk_source_revision_detected"] = False
    if body.decision in {"acknowledge_deletion", "retain_observation"}:
        metadata["odk_source_deletion_review_required"] = False
    reviewed_at = datetime.now(UTC)
    metadata["odk_reconciliation_decision"] = body.decision
    metadata["odk_reconciliation_reviewed_at"] = reviewed_at.isoformat()
    metadata["odk_reconciliation_reviewed_by"] = principal.user_id
    observation.metadata_json = metadata
    observation.reviewed_by = principal.user_id
    observation.reviewed_at = reviewed_at
    observation.review_note = body.note.strip() if body.note else None
    session.add(
        OrganizationAuditEvent(
            organization_id=organization_id,
            actor_user_id=principal.user_id,
            subject_user_id=observation.created_by,
            action="climate.observation.reviewed",
            changes={
                "workflow": "odk.source_reconciliation",
                "observation_id": observation.id,
                "decision": body.decision,
                "source_revision_detected": revision_pending,
                "source_deletion_review_required": deletion_pending,
                "note": observation.review_note,
            },
        )
    )
    await session.commit()
    return {
        "observation_id": observation.id,
        "decision": body.decision,
        "revision_pending": bool(metadata.get("odk_source_revision_detected")),
        "deletion_review_pending": bool(metadata.get("odk_source_deletion_review_required")),
        "reviewed_at": reviewed_at.isoformat(),
    }


@router.get("/status")
async def odk_integration_status(
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, int | str]:
    """Return tenant-scoped ODK import counts without exposing submission data."""
    from sqlalchemy import func

    total = await session.scalar(
        select(func.count(ClimateObservation.id)).where(
            ClimateObservation.organization_id == membership.organization_id,
            ClimateObservation.provider_id == "odk-central",
        )
    )
    pending = await session.scalar(
        select(func.count(ClimateObservation.id)).where(
            ClimateObservation.organization_id == membership.organization_id,
            ClimateObservation.provider_id == "odk-central",
            ClimateObservation.quality_status == "pending",
        )
    )
    return {
        "provider": "odk-central",
        "imported_observations": int(total or 0),
        "pending_review": int(pending or 0),
    }
