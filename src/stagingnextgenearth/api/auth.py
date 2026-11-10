"""HTTP transport for the password authentication lifecycle."""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..auth import (
    AuthenticationApplication,
    AuthenticationError,
    IdentifierAlreadyExistsError,
    LoginRequest,
    RegistrationError,
    RegistrationRequest,
    TokenError,
)
from ..core.errors import BackboneError

router = APIRouter(prefix="/auth", tags=["auth"])


class CredentialsRequest(BaseModel):
    """Credentials accepted by registration and login endpoints."""

    identifier: str = Field(min_length=1)
    password: str = Field(min_length=1)


class TokenRequest(BaseModel):
    """Refresh token accepted by rotation and logout endpoints."""

    refresh_token: str = Field(min_length=1)


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
