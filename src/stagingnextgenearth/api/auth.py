"""HTTP transport for the password authentication lifecycle."""

from collections.abc import Callable
from typing import Annotated, Any, cast

import structlog
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import update
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
from ..identity.models import User
from ..identity.refresh_tokens import RefreshToken
from .dependencies import Principal, get_current_principal, get_session

router = APIRouter(prefix="/auth", tags=["auth"])
_audit_logger = structlog.get_logger("stagingnextgenearth.audit")


class CredentialsRequest(BaseModel):
    """Credentials accepted by registration and login endpoints."""

    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)


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


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password(
    body: PasswordChangeRequest,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PasswordChangeResponse:
    """Change the caller's password and revoke every outstanding refresh session.

    Existing access JWTs remain valid only until their short configured expiry.
    The caller should replace its local tokens by signing in again.
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
