"""Application-level refresh-token rotation and revocation contract."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol
from uuid import UUID, uuid4

from .tokens import TokenError, TokenService


@dataclass(frozen=True, slots=True)
class RefreshTokenRecord:
    """Persisted refresh-token family state required for rotation."""

    token_id: UUID
    subject: str
    expires_in: timedelta
    revoked: bool = False


class RefreshTokenStore(Protocol):
    """Persistence boundary for refresh-token family state."""

    async def create(self, record: RefreshTokenRecord) -> None:
        """Persist a newly issued refresh-token record."""

    async def consume(self, token_id: UUID, subject: str) -> RefreshTokenRecord | None:
        """Atomically consume a refresh-token record for its subject."""

    async def revoke(self, token_id: UUID) -> bool:
        """Revoke a refresh-token record without deleting its audit state."""


@dataclass(frozen=True, slots=True)
class RefreshResult:
    """Result of a successful refresh-token rotation."""

    subject: str
    access_token: str
    refresh_token: str


class RefreshTokenService:
    """Validate, rotate, and revoke refresh tokens through a store."""

    def __init__(
        self,
        token_service: TokenService,
        refresh_token_store: RefreshTokenStore,
        access_token_lifetime: timedelta,
        refresh_token_lifetime: timedelta,
    ) -> None:
        if access_token_lifetime <= timedelta(0):
            raise ValueError("access_token_lifetime must be positive")
        if refresh_token_lifetime <= timedelta(0):
            raise ValueError("refresh_token_lifetime must be positive")
        self.token_service = token_service
        self.refresh_token_store = refresh_token_store
        self.access_token_lifetime = access_token_lifetime
        self.refresh_token_lifetime = refresh_token_lifetime

    async def issue(self, subject: str, access_token: str | None = None) -> RefreshResult:
        """Issue a persisted refresh token and, when needed, an access token."""
        token_id = uuid4()
        await self.refresh_token_store.create(
            RefreshTokenRecord(token_id, subject, self.refresh_token_lifetime)
        )
        return RefreshResult(
            subject=subject,
            access_token=access_token
            or self.token_service.create(
                subject, self.access_token_lifetime, token_type="access"
            ),
            refresh_token=self.token_service.create(
                subject,
                self.refresh_token_lifetime,
                token_type="refresh",
                claims={"jti": str(token_id)},
            ),
        )

    async def rotate(self, refresh_token: str) -> RefreshResult:
        """Consume a refresh token exactly once and issue its replacement."""
        try:
            payload = self.token_service.decode(refresh_token, expected_type="refresh")
            token_id = UUID(payload["jti"])
            subject = payload["sub"]
        except (TokenError, KeyError, ValueError, TypeError) as exc:
            raise TokenError("Invalid refresh token") from exc

        record = await self.refresh_token_store.consume(token_id, subject)
        if record is None or record.revoked:
            raise TokenError("Invalid refresh token")
        return await self.issue(record.subject)

    async def revoke(self, refresh_token: str) -> bool:
        """Revoke a refresh token without exposing whether it was previously valid."""
        try:
            payload = self.token_service.decode(refresh_token, expected_type="refresh")
            token_id = UUID(payload["jti"])
        except (TokenError, KeyError, ValueError, TypeError) as exc:
            raise TokenError("Invalid refresh token") from exc
        return await self.refresh_token_store.revoke(token_id)
