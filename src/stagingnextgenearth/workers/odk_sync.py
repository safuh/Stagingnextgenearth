"""Scheduled ODK Central OData poller and climate-evidence importer."""

import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from math import isfinite
from urllib.parse import quote, urljoin, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.api.odk import ODKFieldMapping, _field, _required_text
from stagingnextgenearth.platform.models import (
    ClimateObservation,
    ODKConnection,
    ODKSyncRun,
    Project,
    ResearchStudy,
)

logger = logging.getLogger("stagingnextgenearth.odk_sync")
_PAGE_SIZE = 100
_MAX_PAGES_PER_FORM = 10


class ODKCentralClient:
    """Small Central API client using documented session auth and OData feeds."""

    def __init__(self, base_url: str, email: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self._email = email
        self._password = password
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30, connect=8), follow_redirects=False
        )
        self._token: str | None = None

    async def __aenter__(self) -> "ODKCentralClient":
        try:
            response = await self._client.post(
                f"{self.base_url}/v1/sessions",
                json={"email": self._email, "password": self._password},
            )
            response.raise_for_status()
            token = response.json().get("token")
            if not isinstance(token, str) or not token:
                raise ValueError("ODK Central did not return a session token")
            self._token = token
            return self
        except Exception:
            await self._client.aclose()
            raise

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._token:
            try:
                await self._client.delete(
                    f"{self.base_url}/v1/sessions/{quote(self._token, safe='')}"
                )
            except httpx.HTTPError:
                logger.warning("ODK Central session revocation failed")
        await self._client.aclose()

    @property
    def headers(self) -> dict[str, str]:
        if not self._token:
            raise RuntimeError("ODK Central client is not authenticated")
        return {"Authorization": f"Bearer {self._token}"}

    async def list_forms(self, project_id: int) -> list[dict[str, object]]:
        response = await self._client.get(
            f"{self.base_url}/v1/projects/{project_id}/forms", headers=self.headers
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("ODK Central returned an invalid forms document")
        return [item for item in payload if isinstance(item, dict)]

    async def submission_pages(
        self, project_id: int, form_id: str, cursor: str | None = None
    ) -> AsyncIterator[tuple[list[dict[str, object]], str | None]]:
        path = f"/v1/projects/{project_id}/forms/{quote(form_id, safe='')}.svc/Submissions"
        url = cursor or f"{self.base_url}{path}"
        params: dict[str, str] | None = {"$top": str(_PAGE_SIZE)} if cursor is None else None
        base_origin = urlsplit(self.base_url)
        for _ in range(_MAX_PAGES_PER_FORM):
            response = await self._client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("value"), list):
                raise ValueError("ODK Central returned an invalid OData submissions page")
            page = [item for item in payload["value"] if isinstance(item, dict)]
            next_link = payload.get("@odata.nextLink")
            if not isinstance(next_link, str) or not next_link:
                yield page, None
                return
            next_url = urljoin(f"{self.base_url}/", next_link)
            next_origin = urlsplit(next_url)
            if (next_origin.scheme, next_origin.netloc) != (base_origin.scheme, base_origin.netloc):
                raise ValueError(
                    "ODK Central returned a pagination link outside the configured server"
                )
            yield page, next_url
            url = next_url
            params = None
        raise ValueError("ODK Central form exceeded the per-run pagination limit")


async def _persist_page(
    session: AsyncSession,
    *,
    connection: ODKConnection,
    form_id: str,
    rows: list[dict[str, object]],
    mapping: ODKFieldMapping,
) -> tuple[int, int]:
    imported = 0
    duplicates = 0
    for index, data in enumerate(rows):
        instance_id = data.get("__id") or _field(data, "meta/instanceID") or data.get("instanceId")
        if not isinstance(instance_id, str) or not instance_id.strip():
            raise ValueError(f"Submission row {index} has no ODK instance ID")
        record_id = f"{form_id}:{instance_id.strip()}"
        if len(record_id) > 200:
            raise ValueError("ODK form and instance identifier exceed the supported length")
        existing = await session.scalar(
            select(ClimateObservation.id).where(
                ClimateObservation.organization_id == connection.organization_id,
                ClimateObservation.provider_id == "odk-central",
                ClimateObservation.provider_record_id == record_id,
            )
        )
        if existing is not None:
            duplicates += 1
            continue
        observed_at = datetime.fromisoformat(
            _required_text(data, mapping.observed_at, "observed_at")
        )
        if observed_at.tzinfo is None or observed_at.utcoffset() is None:
            raise ValueError("ODK observation timestamp must include a timezone")
        variable = _required_text(data, mapping.variable, "variable")
        unit = _required_text(data, mapping.unit, "unit")
        if len(variable) > 80 or len(unit) > 32:
            raise ValueError("ODK variable or unit exceeds the supported length")
        value = float(_required_text(data, mapping.value, "value"))
        latitude = float(_required_text(data, mapping.latitude, "latitude"))
        longitude = float(_required_text(data, mapping.longitude, "longitude"))
        if not all(isfinite(number) for number in (value, latitude, longitude)):
            raise ValueError("ODK numeric values must be finite")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("ODK coordinates are outside valid bounds")
        project_id_value = _field(data, mapping.project_id) if mapping.project_id else None
        study_id_value = _field(data, mapping.study_id) if mapping.study_id else None
        project_id = str(project_id_value).strip() if project_id_value is not None else None
        study_id = str(study_id_value).strip() if study_id_value is not None else None
        if project_id is not None:
            project = await session.scalar(
                select(Project.id).where(
                    Project.id == project_id,
                    Project.organization_id == connection.organization_id,
                )
            )
            if project is None:
                raise ValueError("ODK mapping references a project outside this organisation")
        if study_id is not None:
            study = await session.scalar(
                select(ResearchStudy).where(
                    ResearchStudy.id == study_id,
                    ResearchStudy.organization_id == connection.organization_id,
                )
            )
            if study is None or (
                project_id is not None and study.project_id not in {None, project_id}
            ):
                raise ValueError("ODK mapping references an incompatible research study")
        session.add(
            ClimateObservation(
                organization_id=connection.organization_id,
                project_id=project_id,
                study_id=study_id,
                observed_at=observed_at.astimezone(UTC),
                variable=variable,
                value=value,
                unit=unit,
                latitude=latitude,
                longitude=longitude,
                source=f"ODK Central form {form_id}"[:160],
                provider_id="odk-central",
                provider_record_id=record_id,
                quality_status="pending",
                metadata_json={
                    "provider": "odk-central",
                    "form_id": form_id,
                    "instance_id": instance_id,
                },
                created_by=connection.created_by,
            )
        )
        imported += 1
    await session.flush()
    return imported, duplicates


async def sync_odk_connection(
    session_factory: async_sessionmaker[AsyncSession],
    connection_id: str,
    *,
    encryption_key: str,
) -> dict[str, int | str]:
    """Execute one bounded sync for a connection, recording a durable run summary."""
    cipher = Fernet(encryption_key.encode())
    async with session_factory() as session:
        connection = await session.scalar(
            select(ODKConnection)
            .where(ODKConnection.id == connection_id, ODKConnection.enabled)
            .with_for_update(skip_locked=True)
        )
        if connection is None:
            return {"status": "skipped", "forms": 0, "imported": 0}
        run = ODKSyncRun(
            connection_id=connection.id,
            organization_id=connection.organization_id,
            status="running",
        )
        session.add(run)
        await session.flush()
        totals = {"forms": 0, "received": 0, "imported": 0, "duplicates": 0, "errors": 0}
        errors: list[str] = []
        try:
            password = cipher.decrypt(connection.encrypted_password.encode()).decode()
            async with ODKCentralClient(
                connection.base_url, connection.account_email, password
            ) as central:
                forms = await central.list_forms(connection.project_id)
                available = {
                    str(form.get("xmlFormId")): form
                    for form in forms
                    if isinstance(form.get("xmlFormId"), str)
                }
                for form_id, raw_mapping in connection.form_mappings.items():
                    if form_id not in available:
                        totals["errors"] += 1
                        errors.append(f"Configured form unavailable: {form_id[:80]}")
                        continue
                    try:
                        mapping = ODKFieldMapping.model_validate(raw_mapping)
                        totals["forms"] += 1
                        async for page, next_cursor in central.submission_pages(
                            connection.project_id,
                            form_id,
                            connection.form_cursors.get(form_id),
                        ):
                            totals["received"] += len(page)
                            async with session.begin_nested():
                                imported, duplicates = await _persist_page(
                                    session,
                                    connection=connection,
                                    form_id=form_id,
                                    rows=page,
                                    mapping=mapping,
                                )
                            totals["imported"] += imported
                            totals["duplicates"] += duplicates
                            updated_cursors = dict(connection.form_cursors)
                            if next_cursor is None:
                                updated_cursors.pop(form_id, None)
                            else:
                                updated_cursors[form_id] = next_cursor
                            connection.form_cursors = updated_cursors
                            await session.commit()
                    except (
                        ValueError,
                        TypeError,
                        OverflowError,
                        ValidationError,
                        httpx.HTTPError,
                    ) as exc:
                        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {
                            400,
                            404,
                            410,
                        }:
                            updated_cursors = dict(connection.form_cursors)
                            updated_cursors.pop(form_id, None)
                            connection.form_cursors = updated_cursors
                        totals["errors"] += 1
                        errors.append(f"Form {form_id[:80]} sync failed ({type(exc).__name__})")
                        logger.warning(
                            "ODK form sync failed: form=%s error_type=%s",
                            form_id,
                            type(exc).__name__,
                        )
            run.status = (
                "failed"
                if totals["errors"] and not totals["imported"]
                else "partial"
                if totals["errors"]
                else "succeeded"
            )
        except (InvalidToken, UnicodeDecodeError, httpx.HTTPError, ValueError) as exc:
            run.status = "failed"
            totals["errors"] += 1
            errors.append(f"Connection sync failed ({type(exc).__name__})")
            logger.warning(
                "ODK connection sync failed: connection=%s error_type=%s",
                connection_id,
                type(exc).__name__,
            )
        run.forms_checked = totals["forms"]
        run.submissions_received = totals["received"]
        run.observations_imported = totals["imported"]
        run.duplicates_skipped = totals["duplicates"]
        run.error_count = totals["errors"]
        run.error_summary = "; ".join(errors)[:500] if errors else None
        run.completed_at = datetime.now(UTC)
        connection.last_sync_at = run.completed_at
        connection.last_sync_status = run.status
        connection.last_sync_message = run.error_summary
        await session.commit()
        return {
            "status": run.status,
            "forms": totals["forms"],
            "received": totals["received"],
            "imported": totals["imported"],
            "duplicates": totals["duplicates"],
            "errors": totals["errors"],
        }


async def sync_enabled_connections(
    session_factory: async_sessionmaker[AsyncSession], *, encryption_key: str, batch_size: int = 10
) -> int:
    """Run a bounded batch of enabled Central connections."""
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")
    async with session_factory() as session:
        ids = list(
            (
                await session.scalars(
                    select(ODKConnection.id)
                    .where(ODKConnection.enabled)
                    .order_by(ODKConnection.updated_at, ODKConnection.id)
                    .limit(batch_size)
                )
            ).all()
        )
    completed = 0
    for connection_id in ids:
        await sync_odk_connection(session_factory, connection_id, encryption_key=encryption_key)
        completed += 1
    return completed
