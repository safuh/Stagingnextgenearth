"""Secure ODK Central connection configuration and form discovery."""

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import quote, urlsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.core.odk_tls import odk_tls_verify
from stagingnextgenearth.platform.models import Membership, ODKConnection, ODKSyncRun

from .dependencies import (
    Principal,
    get_current_principal,
    get_session,
    membership_has_any_role,
    require_membership,
)
from .odk import ODKFieldMapping

router = APIRouter(prefix="/organizations/{organization_id}/odk", tags=["odk-integration"])
_MANAGER_ROLES = {"admin", "founder", "executive"}


class ODKConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_url: HttpUrl
    project_id: int = Field(gt=0)
    account_email: str = Field(min_length=5, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: SecretStr = Field(min_length=1, max_length=1024)
    form_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("form_mappings")
    @classmethod
    def validate_form_mappings(cls, value: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
        if len(value) > 50:
            raise ValueError("At most 50 ODK forms can be mapped per project")
        for form_id, mapping in value.items():
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,160}", form_id):
                raise ValueError(
                    "ODK XML form IDs may contain letters, numbers, dots, underscores, and hyphens"
                )
            ODKFieldMapping.model_validate(mapping)
        return value

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: HttpUrl) -> HttpUrl:
        parsed = urlsplit(str(value))
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("ODK Central URL must not contain credentials, query, or fragment")
        if parsed.path not in {"", "/"}:
            raise ValueError("ODK Central URL must be the server origin, without a path")
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("ODK Central must use HTTPS except for localhost development")
        return value


class ODKConnectionSummary(BaseModel):
    configured: bool
    base_url: str | None = None
    project_id: int | None = None
    account_email: str | None = None
    enabled: bool = False
    mapped_forms: list[str] = Field(default_factory=list)
    form_mappings: dict[str, dict[str, str]] = Field(default_factory=dict)
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    last_sync_message: str | None = None


class ODKConnectionTestResult(BaseModel):
    connected: bool
    project_id: int
    forms_available: int
    message: str


class ODKOperationsAlert(BaseModel):
    code: str
    severity: Literal["info", "warning", "critical"]
    message: str


class ODKOperationsSummary(BaseModel):
    configured: bool
    enabled: bool = False
    last_sync_at: str | None = None
    last_sync_status: str | None = None
    mapped_forms: int = 0
    forms_with_cursors: int = 0
    consecutive_error_runs: int = 0
    alerts: list[ODKOperationsAlert] = Field(default_factory=list)


def _fernet(request: Request) -> Fernet:
    key = request.app.state.settings.odk_encryption_key
    if key is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "ODK credential encryption is not configured"
        )
    try:
        return Fernet(key.get_secret_value().encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "ODK encryption key is invalid"
        ) from exc


def _summary(connection: ODKConnection | None) -> ODKConnectionSummary:
    if connection is None:
        return ODKConnectionSummary(configured=False)
    return ODKConnectionSummary(
        configured=True,
        base_url=connection.base_url,
        project_id=connection.project_id,
        account_email=connection.account_email,
        enabled=connection.enabled,
        mapped_forms=sorted(connection.form_mappings),
        form_mappings=connection.form_mappings,
        last_sync_at=connection.last_sync_at.isoformat() if connection.last_sync_at else None,
        last_sync_status=connection.last_sync_status,
        last_sync_message=connection.last_sync_message,
    )


async def _authenticate_and_list_forms(
    *, base_url: str, project_id: int, email: str, password: str
) -> list[dict[str, object]]:
    timeout = httpx.Timeout(15.0, connect=5.0)
    try:
        verify_tls = odk_tls_verify(base_url, get_settings())
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Disabling ODK TLS verification is allowed only for local Central hosts",
        ) from exc
    async with httpx.AsyncClient(
        timeout=timeout, follow_redirects=False, verify=verify_tls
    ) as client:
        token: str | None = None
        try:
            login = await client.post(
                f"{base_url}/v1/sessions",
                json={"email": email, "password": password},
            )
            if login.status_code != 200:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "ODK Central authentication failed"
                )
            token_value = login.json().get("token")
            if not isinstance(token_value, str) or not token_value:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "ODK Central returned an invalid session"
                )
            token = token_value
            response = await client.get(
                f"{base_url}/v1/projects/{project_id}/forms",
                headers={"Authorization": f"Bearer {token}"},
            )
            if response.status_code != 200:
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "ODK Central project access failed"
                )
            payload = response.json()
            if not isinstance(payload, list):
                raise HTTPException(
                    status.HTTP_502_BAD_GATEWAY, "ODK Central returned an invalid forms list"
                )
            return [item for item in payload if isinstance(item, dict)]
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status.HTTP_504_GATEWAY_TIMEOUT, "ODK Central request timed out"
            ) from exc
        except httpx.RequestError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, "ODK Central could not be reached"
            ) from exc
        finally:
            if token is not None:
                try:
                    await client.delete(f"{base_url}/v1/sessions/{quote(token, safe='')}")
                except httpx.HTTPError:
                    pass


@router.put("/connection", response_model=ODKConnectionSummary)
async def save_odk_connection(
    organization_id: str,
    body: ODKConnectionRequest,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_principal)],
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ODKConnectionSummary:
    """Create or replace a tenant's ODK Central connection; never return secrets."""
    if not await membership_has_any_role(session, membership, _MANAGER_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Organisation administrator permission required"
        )
    cipher = _fernet(request)
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == organization_id)
    )
    encrypted = cipher.encrypt(body.password.get_secret_value().encode()).decode()
    if connection is None:
        connection = ODKConnection(
            organization_id=organization_id,
            base_url=str(body.base_url).rstrip("/"),
            project_id=body.project_id,
            account_email=str(body.account_email),
            encrypted_password=encrypted,
            form_mappings=body.form_mappings,
            enabled=body.enabled,
            created_by=principal.user_id,
        )
        session.add(connection)
    else:
        connection.base_url = str(body.base_url).rstrip("/")
        connection.project_id = body.project_id
        connection.account_email = str(body.account_email)
        connection.encrypted_password = encrypted
        connection.form_mappings = body.form_mappings
        connection.enabled = body.enabled
        connection.last_sync_status = "configuration_changed"
        connection.last_sync_message = None
    await session.commit()
    await session.refresh(connection)
    return _summary(connection)


@router.get("/connection", response_model=ODKConnectionSummary)
async def get_odk_connection(
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ODKConnectionSummary:
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == membership.organization_id)
    )
    return _summary(connection)


@router.post("/connection/test", response_model=ODKConnectionTestResult)
async def test_odk_connection(
    request: Request,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ODKConnectionTestResult:
    """Verify saved credentials and confirm the configured Central project is accessible."""
    if not await membership_has_any_role(session, membership, _MANAGER_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Organisation administrator permission required"
        )
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == membership.organization_id)
    )
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ODK Central connection is not configured")
    try:
        password = _fernet(request).decrypt(connection.encrypted_password.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "ODK credentials cannot be decrypted"
        ) from exc
    forms = await _authenticate_and_list_forms(
        base_url=connection.base_url,
        project_id=connection.project_id,
        email=connection.account_email,
        password=password,
    )
    return ODKConnectionTestResult(
        connected=True,
        project_id=connection.project_id,
        forms_available=len(forms),
        message="ODK Central authentication and project access succeeded",
    )


@router.get("/forms")
async def discover_odk_forms(
    request: Request,
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, str | int | None]]:
    """Discover forms available to the configured ODK Central account."""
    if not await membership_has_any_role(session, membership, _MANAGER_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Organisation administrator permission required"
        )
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == membership.organization_id)
    )
    if connection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ODK Central connection is not configured")
    try:
        password = _fernet(request).decrypt(connection.encrypted_password.encode()).decode()
    except InvalidToken as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "ODK credentials cannot be decrypted"
        ) from exc
    forms = await _authenticate_and_list_forms(
        base_url=connection.base_url,
        project_id=connection.project_id,
        email=connection.account_email,
        password=password,
    )
    result: list[dict[str, str | int | None]] = []
    for form in forms:
        xml_form_id = form.get("xmlFormId")
        if isinstance(xml_form_id, str) and xml_form_id:
            result.append(
                {
                    "xml_form_id": xml_form_id,
                    "name": str(form.get("name") or xml_form_id),
                    "version": str(form.get("version"))
                    if form.get("version") is not None
                    else None,
                    "state": str(form.get("state")) if form.get("state") is not None else None,
                }
            )
    return result


@router.delete("/connection", status_code=status.HTTP_204_NO_CONTENT)
async def delete_odk_connection(
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    if not await membership_has_any_role(session, membership, _MANAGER_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Organisation administrator permission required"
        )
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == membership.organization_id)
    )
    if connection is not None:
        await session.delete(connection)
        await session.commit()


@router.get("/operations", response_model=ODKOperationsSummary)
async def get_odk_operations_status(
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ODKOperationsSummary:
    """Summarise actionable Central sync failures and worker/cursor freshness."""
    if not await membership_has_any_role(session, membership, _MANAGER_ROLES):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Organisation administrator permission required"
        )
    connection = await session.scalar(
        select(ODKConnection).where(ODKConnection.organization_id == membership.organization_id)
    )
    if connection is None:
        return ODKOperationsSummary(configured=False)

    alerts: list[ODKOperationsAlert] = []
    runs = list(
        (
            await session.scalars(
                select(ODKSyncRun)
                .where(ODKSyncRun.connection_id == connection.id)
                .order_by(ODKSyncRun.started_at.desc())
                .limit(3)
            )
        ).all()
    )
    consecutive_errors = 0
    for run in runs:
        if run.error_count > 0 or run.status in {"failed", "partial"}:
            consecutive_errors += 1
        else:
            break

    last_sync_at = connection.last_sync_at
    if last_sync_at is not None and last_sync_at.tzinfo is None:
        last_sync_at = last_sync_at.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if not connection.enabled:
        alerts.append(
            ODKOperationsAlert(
                code="connection_disabled",
                severity="info",
                message="ODK Central synchronisation is disabled for this organisation.",
            )
        )
    elif last_sync_at is None:
        alerts.append(
            ODKOperationsAlert(
                code="sync_not_started",
                severity="warning",
                message="No ODK Central synchronisation has completed yet.",
            )
        )
    elif now - last_sync_at > timedelta(minutes=5):
        alerts.append(
            ODKOperationsAlert(
                code="worker_stale",
                severity="warning",
                message=(
                    "No ODK Central sync has completed in the last five minutes; check the worker."
                ),
            )
        )

    if connection.enabled and connection.form_cursors:
        if last_sync_at is None or now - last_sync_at > timedelta(minutes=15):
            alerts.append(
                ODKOperationsAlert(
                    code="stale_pagination_cursor",
                    severity="warning",
                    message=(
                        "A saved ODK pagination cursor has not progressed recently; "
                        "inspect the latest sync errors."
                    ),
                )
            )

    if consecutive_errors >= 3:
        alerts.append(
            ODKOperationsAlert(
                code="repeated_sync_failures",
                severity="critical",
                message=(
                    "The last three ODK sync runs reported errors; "
                    "investigate Central access and form mappings."
                ),
            )
        )

    latest_error = runs[0].error_summary or "" if runs else ""
    if "HTTP 401" in latest_error:
        alerts.append(
            ODKOperationsAlert(
                code="central_credentials_rejected",
                severity="critical",
                message=(
                    "ODK Central rejected the saved credentials. Verify the service account "
                    "password and rotate it if required."
                ),
            )
        )
    elif "HTTP 403" in latest_error:
        alerts.append(
            ODKOperationsAlert(
                code="central_project_access_denied",
                severity="critical",
                message=(
                    "The ODK Central account lacks permission for the configured project or form."
                ),
            )
        )

    return ODKOperationsSummary(
        configured=True,
        enabled=connection.enabled,
        last_sync_at=last_sync_at.isoformat() if last_sync_at else None,
        last_sync_status=connection.last_sync_status,
        mapped_forms=len(connection.form_mappings),
        forms_with_cursors=len(connection.form_cursors),
        consecutive_error_runs=consecutive_errors,
        alerts=alerts,
    )


@router.get("/sync-runs")
async def list_odk_sync_runs(
    membership: Annotated[Membership, Depends(require_membership)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[dict[str, object]]:
    """Return recent tenant-scoped ODK sync history without exposing survey data."""
    connection = await session.scalar(
        select(ODKConnection.id).where(ODKConnection.organization_id == membership.organization_id)
    )
    if connection is None:
        return []
    runs = await session.scalars(
        select(ODKSyncRun)
        .where(ODKSyncRun.connection_id == connection)
        .order_by(ODKSyncRun.started_at.desc())
        .limit(50)
    )
    return [
        {
            "id": run.id,
            "status": run.status,
            "forms_checked": run.forms_checked,
            "submissions_received": run.submissions_received,
            "observations_imported": run.observations_imported,
            "duplicates_skipped": run.duplicates_skipped,
            "rejected_count": run.rejected_count,
            "error_count": run.error_count,
            "error_summary": run.error_summary,
            "started_at": run.started_at.isoformat(),
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }
        for run in runs
    ]
