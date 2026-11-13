"""Authentication and tenant-authorization dependencies for API routes."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.auth import TokenError, TokenService
from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import Membership

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Authenticated user identity; organisation roles are resolved separately."""

    user_id: str


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped database session."""
    factory: async_sessionmaker[AsyncSession] = request.app.state.db_session_factory
    async with factory() as session:
        yield session


async def get_current_principal(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Principal:
    """Validate an access JWT and ensure its subject is still an active user."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    secret = request.app.state.settings.jwt_secret_key
    if secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured")
    try:
        claims = TokenService(secret.get_secret_value()).decode(
            credentials.credentials, expected_type="access"
        )
        subject = claims["sub"]
    except (TokenError, KeyError, TypeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token",
                            headers={"WWW-Authenticate": "Bearer"}) from exc
    user = await session.scalar(select(User.id).where(User.id == subject))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account is unavailable",
                            headers={"WWW-Authenticate": "Bearer"})
    return Principal(user_id=user)


async def require_membership(
    organization_id: str,
    principal: Annotated[Principal, Depends(get_current_principal)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Membership:
    """Resolve an active membership in the requested tenant or deny access."""
    membership = await session.scalar(
        select(Membership).where(
            Membership.organization_id == organization_id,
            Membership.user_id == principal.user_id,
            Membership.status == "active",
        )
    )
    if membership is None:
        # Avoid disclosing whether an inaccessible tenant exists.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Organisation not found")
    return membership

