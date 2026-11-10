"""Tests for application-level refresh-token rotation."""

from datetime import timedelta
from uuid import UUID

import pytest

from stagingnextgenearth.auth.refresh import (
    RefreshTokenRecord,
    RefreshTokenService,
)
from stagingnextgenearth.auth.tokens import TokenError, TokenService


class InMemoryRefreshTokenStore:
    """Minimal refresh-token store used by application-level tests."""

    def __init__(self) -> None:
        self.records: dict[UUID, RefreshTokenRecord] = {}

    async def create(self, record: RefreshTokenRecord) -> None:
        """Persist a newly issued refresh-token record."""
        self.records[record.token_id] = record

    async def consume(
        self, token_id: UUID, subject: str
    ) -> RefreshTokenRecord | None:
        """Consume a matching refresh-token record exactly once."""
        record = self.records.get(token_id)
        if record is None or record.revoked or record.subject != subject:
            return None
        del self.records[token_id]
        return record

    async def revoke(self, token_id: UUID) -> bool:
        """Revoke a refresh-token record without deleting it."""
        record = self.records.get(token_id)
        if record is None or record.revoked:
            return False
        self.records[token_id] = RefreshTokenRecord(
            token_id=record.token_id,
            subject=record.subject,
            expires_in=record.expires_in,
            revoked=True,
        )
        return True


@pytest.fixture
def service() -> RefreshTokenService:
    """Build a refresh-token service backed by an in-memory store."""
    store = InMemoryRefreshTokenStore()
    token_service = TokenService("test-secret-key-that-is-at-least-32-bytes")
    return RefreshTokenService(
        refresh_token_store=store,
        token_service=token_service,
        refresh_token_lifetime=timedelta(days=7),
        access_token_lifetime=timedelta(minutes=15),
    )


@pytest.mark.asyncio
async def test_access_token_cannot_be_used_for_refresh(
    service: RefreshTokenService,
) -> None:
    await service.issue("user-123")
    with pytest.raises(TokenError, match="Invalid refresh token"):
        await service.rotate(
            service.token_service.create(
                "user-123", timedelta(minutes=15), token_type="access"
            )
        )


@pytest.mark.asyncio
async def test_refresh_subject_mismatch_is_rejected(
    service: RefreshTokenService,
) -> None:
    issued = await service.issue("user-123")
    token_id = next(iter(service.refresh_token_store.records))
    token = service.token_service.create(
        "attacker",
        timedelta(days=7),
        token_type="refresh",
        claims={"jti": str(token_id)},
    )

    with pytest.raises(TokenError, match="Invalid refresh token"):
        await service.rotate(token)
    assert token_id in service.refresh_token_store.records
    assert issued.subject == "user-123"


@pytest.mark.asyncio
async def test_refresh_token_can_only_be_consumed_once(
    service: RefreshTokenService,
) -> None:
    issued = await service.issue("user-123")

    rotated = await service.rotate(issued.refresh_token)

    assert rotated.subject == "user-123"
    assert rotated.refresh_token != issued.refresh_token
    with pytest.raises(TokenError, match="Invalid refresh token"):
        await service.rotate(issued.refresh_token)


@pytest.mark.asyncio
async def test_refresh_token_can_be_revoked(
    service: RefreshTokenService,
) -> None:
    issued = await service.issue("user-123")
    token_id = next(iter(service.refresh_token_store.records))

    assert await service.revoke(issued.refresh_token) is True
    assert service.refresh_token_store.records[token_id].revoked is True
    assert await service.revoke(issued.refresh_token) is False

    with pytest.raises(TokenError, match="Invalid refresh token"):
        await service.rotate(issued.refresh_token)


@pytest.mark.asyncio
async def test_revoke_rejects_malformed_refresh_token(
    service: RefreshTokenService,
) -> None:
    with pytest.raises(TokenError, match="Invalid refresh token"):
        await service.revoke("not-a-jwt")
