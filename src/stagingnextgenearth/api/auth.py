"""HTTP transport for the password authentication lifecycle."""

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..auth import (
    AuthenticationApplication,
    AuthenticationError,
    IdentifierAlreadyExistsError,
    LoginRequest,
    PasswordHasher,
    RegistrationError,
    RegistrationRequest,
    TokenError,
)
from ..core.errors import BackboneError
from ..identity.models import ExternalIdentity, User
from ..identity.refresh_tokens import RefreshToken
from ..platform.models import Membership, Organization
from .dependencies import (
    Principal,
    get_current_principal,
    get_membership_roles,
    get_session,
)

router = APIRouter(prefix="/auth", tags=["auth"])
_audit_logger = structlog.get_logger("stagingnextgenearth.audit")


class CredentialsRequest(BaseModel):
    """Credentials accepted by registration and login endpoints."""

    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)


class PortalMembershipContext(BaseModel):
    """One organisation context used to route an authenticated user safely."""

    membership_id: str
    organization_id: str
    organization_name: str
    organization_slug: str
    role: str
    roles: list[str]
    status: str


class AuthenticationContextResponse(BaseModel):
    """Minimal identity and tenant memberships for post-login portal routing."""

    user_id: str
    identifier: str
    email_verified: bool
    memberships: list[PortalMembershipContext]


class TokenRequest(BaseModel):
    """Refresh token accepted by rotation and logout endpoints."""

    refresh_token: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    """Current and replacement password for an authenticated account."""

    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class PasswordChangeResponse(BaseModel):
    """Non-sensitive confirmation returned after a password change."""

    message: str
    revoked_refresh_sessions: int


class RegistrationResponseModel(BaseModel):
    """Public registration response."""

    subject: str


class TokenResponseModel(BaseModel):
    """Public access/refresh token response."""

    subject: str
    access_token: str
    refresh_token: str


async def _session(request: Request) -> AsyncSession:
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    return session_factory()


def _application(request: Request, session: AsyncSession) -> AuthenticationApplication:
    factory: Callable[[AsyncSession], AuthenticationApplication] | None = getattr(
        request.app.state, "auth_application_factory", None
    )
    if factory is None:
        raise BackboneError(
            "auth_not_configured",
            "Authentication is not configured",
            status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return factory(session)


@router.post("/register", response_model=RegistrationResponseModel, status_code=201)
async def register(
    request: Request,
    body: CredentialsRequest,
    session: Annotated[AsyncSession, Depends(_session)],
) -> RegistrationResponseModel:
    if not request.app.state.settings.public_registration_allowed:
        await session.close()
        raise BackboneError(
            "registration_invitation_required",
            "Account creation is invitation-only. Use an authorised onboarding link.",
            status.HTTP_403_FORBIDDEN,
        )
    try:
        result = await _application(request, session).register(
            RegistrationRequest(identifier=body.identifier, password=body.password)
        )
        await session.commit()
    except IdentifierAlreadyExistsError as exc:
        await session.rollback()
        raise BackboneError("identifier_exists", "Identifier is already registered", 409) from exc
    except RegistrationError as exc:
        await session.rollback()
        raise BackboneError("registration_error", str(exc)) from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
    return RegistrationResponseModel(subject=result.subject)


@router.post("/login", response_model=TokenResponseModel)
async def login(
    request: Request,
    body: CredentialsRequest,
    session: Annotated[AsyncSession, Depends(_session)],
) -> TokenResponseModel:
    try:
        result = await _application(request, session).login(
            LoginRequest(identifier=body.identifier, password=body.password)
        )
        await session.commit()
    except AuthenticationError as exc:
        await session.rollback()
        raise BackboneError(
            "invalid_credentials", "Invalid credentials", status.HTTP_401_UNAUTHORIZED
        ) from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
    return TokenResponseModel(
        subject=result.subject,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


@router.get("/context", response_model=AuthenticationContextResponse)
async def get_authentication_context(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AuthenticationContextResponse:
    """Return only the caller's memberships for deterministic portal routing.

    Active and invited memberships are included so the client can distinguish
    staff workspaces, learner access, and invitations awaiting acceptance.
    Public registration never assigns an organisation role; an empty list is
    therefore a valid state for a newly registered applicant.
    """
    user = await session.get(User, principal.user_id)
    if user is None:
        raise BackboneError("account_unavailable", "Account is unavailable", 401)
    rows = await session.execute(
        select(Membership, Organization.name, Organization.slug)
        .join(Organization, Organization.id == Membership.organization_id)
        .where(
            Membership.user_id == principal.user_id,
            Membership.status.in_({"active", "invited"}),
        )
        .order_by(Organization.name, Membership.created_at)
    )
    memberships: list[PortalMembershipContext] = []
    for membership, organization_name, organization_slug in rows.all():
        memberships.append(
            PortalMembershipContext(
                membership_id=membership.id,
                organization_id=membership.organization_id,
                organization_name=organization_name,
                organization_slug=organization_slug,
                role=membership.role,
                roles=sorted(await get_membership_roles(session, membership)),
                status=membership.status,
            )
        )
    return AuthenticationContextResponse(
        user_id=user.id,
        identifier=user.identifier,
        email_verified=user.email_verified_at is not None,
        memberships=memberships,
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password(
    body: PasswordChangeRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PasswordChangeResponse:
    """Change the password and invalidate every older access/refresh session.

    Access JWTs issued before the change timestamp are rejected immediately.
    """
    user = await session.get(User, principal.user_id, with_for_update=True)
    if user is None:
        raise BackboneError("account_unavailable", "Account is unavailable", 401)
    hasher = PasswordHasher()
    if not hasher.verify(body.current_password, user.password_hash):
        _audit_logger.info(
            "identity_audit",
            audit_action="password_change",
            audit_outcome="failure",
            subject=principal.user_id,
        )
        raise BackboneError("invalid_current_password", "Current password is incorrect", 400)
    if body.current_password == body.new_password:
        raise BackboneError("password_unchanged", "Choose a different password", 422)

    user.password_hash = hasher.hash(body.new_password)
    user.password_changed_at = datetime.now(UTC)
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.subject == principal.user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        ),
    )
    await session.commit()
    _audit_logger.info(
        "identity_audit",
        audit_action="password_change",
        audit_outcome="success",
        subject=principal.user_id,
    )
    return PasswordChangeResponse(
        message="Password changed. Sign in again on your devices.",
        revoked_refresh_sessions=max(int(result.rowcount or 0), 0),
    )


@router.post("/refresh", response_model=TokenResponseModel)
async def refresh(
    request: Request,
    body: TokenRequest,
    session: Annotated[AsyncSession, Depends(_session)],
) -> TokenResponseModel:
    try:
        result = await _application(request, session).refresh(body.refresh_token)
        await session.commit()
    except TokenError as exc:
        await session.rollback()
        raise BackboneError("invalid_refresh_token", "Invalid refresh token", 401) from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
    return TokenResponseModel(
        subject=result.subject,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
    )


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    body: TokenRequest,
    session: Annotated[AsyncSession, Depends(_session)],
) -> Response:
    try:
        await _application(request, session).logout(body.refresh_token)
        await session.commit()
    except TokenError as exc:
        await session.rollback()
        raise BackboneError("invalid_refresh_token", "Invalid refresh token", 401) from exc
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
    return Response(status_code=204)


class IdentityConnectionsResponse(BaseModel):
    """External identity providers linked to the current account."""

    providers: list[str]


@router.get("/connections", response_model=IdentityConnectionsResponse)
async def identity_connections(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> IdentityConnectionsResponse:
    providers = await session.scalars(
        select(ExternalIdentity.provider)
        .where(ExternalIdentity.user_id == principal.user_id)
        .order_by(ExternalIdentity.provider)
    )
    return IdentityConnectionsResponse(providers=list(providers.all()))


@router.post("/sessions/revoke-all", response_model=PasswordChangeResponse)
async def revoke_all_sessions(
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PasswordChangeResponse:
    """Invalidate refresh tokens and all previously issued access tokens."""
    user = await session.get(User, principal.user_id, with_for_update=True)
    if user is None:
        raise BackboneError("account_unavailable", "Account is unavailable", 401)
    user.password_changed_at = datetime.now(UTC)
    result = cast(
        CursorResult[Any],
        await session.execute(
            update(RefreshToken)
            .where(
                RefreshToken.subject == principal.user_id,
                RefreshToken.revoked.is_(False),
            )
            .values(revoked=True)
        ),
    )
    await session.commit()
    _audit_logger.info(
        "identity_audit",
        audit_action="session_revoke_all",
        audit_outcome="success",
        subject=principal.user_id,
    )
    return PasswordChangeResponse(
        message="All sessions have been revoked. Sign in again.",
        revoked_refresh_sessions=max(int(result.rowcount or 0), 0),
    )
