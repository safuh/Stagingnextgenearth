"""Authentication and tenant-authorization dependencies for API routes."""

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.auth import TokenError, TokenService
from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import Membership, MembershipRole

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
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    secret = request.app.state.settings.jwt_secret_key
    if secret is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Authentication is not configured")
    try:
        claims = TokenService(secret.get_secret_value()).decode(
            credentials.credentials, expected_type="access"
        )
        subject = claims["sub"]
    except (TokenError, KeyError, TypeError) as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid access token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    user = await session.scalar(select(User).where(User.id == subject))
    if user is None:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Account is unavailable",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.password_changed_at is not None:
        changed_at = user.password_changed_at
        if changed_at.tzinfo is None:
            changed_at = changed_at.replace(tzinfo=UTC)
        elapsed = changed_at.astimezone(UTC) - datetime(1970, 1, 1, tzinfo=UTC)
        changed_at_us = (elapsed.days * 86_400 + elapsed.seconds) * 1_000_000 + elapsed.microseconds
        issued_at_us = claims.get("iat_us")
        if (
            isinstance(issued_at_us, bool)
            or not isinstance(issued_at_us, int)
            or issued_at_us < changed_at_us
        ):
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Session expired after an account security change",
                headers={"WWW-Authenticate": "Bearer"},
            )
    return Principal(user_id=user.id)


async def get_membership_roles(
    session: AsyncSession,
    membership: Membership,
) -> frozenset[str]:
    """Resolve all assigned roles, retaining the legacy primary role as fallback.

    The primary role is always included so older rows and staged deployments
    remain authorization-compatible while role assignments are migrated.
    """
    assigned = await session.scalars(
        select(MembershipRole.role).where(MembershipRole.membership_id == membership.id)
    )
    return frozenset({membership.role, *assigned.all()})


async def membership_has_any_role(
    session: AsyncSession,
    membership: Membership,
    allowed_roles: set[str] | frozenset[str],
) -> bool:
    """Return whether an active membership holds any requested role."""
    if membership.status != "active":
        return False
    return bool(await get_membership_roles(session, membership) & allowed_roles)


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
