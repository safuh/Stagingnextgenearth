"""Tenant-scoped ODK Central submission import into the climate evidence ledger."""

from datetime import UTC, datetime
from math import isfinite
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.platform.models import (
    ClimateObservation,
    Membership,
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
