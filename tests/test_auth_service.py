from datetime import timedelta

import pytest

from stagingnextgenearth.auth import (
    AuthenticationError,
    AuthenticationService,
    Credentials,
    PasswordHasher,
    TokenService,
)


class InMemoryCredentialStore:
    def __init__(self, credentials: Credentials | None) -> None:
        self.credentials = credentials

    async def get_by_identifier(self, identifier: str) -> Credentials | None:
        if self.credentials is not None and identifier == "alice@example.com":
            return self.credentials
        return None


def make_service(credentials: Credentials | None) -> AuthenticationService:
    return AuthenticationService(
        InMemoryCredentialStore(credentials),
        PasswordHasher(),
        TokenService("x" * 32),
        timedelta(minutes=15),
    )


@pytest.mark.asyncio
async def test_authenticate_returns_access_token() -> None:
    hasher = PasswordHasher()
    service = make_service(
        Credentials(subject="user-123", password_hash=hasher.hash("correct password"))
    )

    result = await service.authenticate("alice@example.com", "correct password")

    assert result.subject == "user-123"
    assert result.access_token
    assert not result.password_needs_rehash

    payload = service.token_service.decode(result.access_token, expected_type="access")
    assert payload["sub"] == "user-123"


@pytest.mark.asyncio
async def test_authenticate_rejects_unknown_identifier() -> None:
    service = make_service(None)

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.authenticate("missing@example.com", "password")


@pytest.mark.asyncio
async def test_authenticate_rejects_wrong_password() -> None:
    hasher = PasswordHasher()
    service = make_service(
        Credentials(subject="user-123", password_hash=hasher.hash("correct password"))
    )

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.authenticate("alice@example.com", "wrong password")


@pytest.mark.asyncio
async def test_authenticate_rejects_empty_identifier() -> None:
    service = make_service(None)

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.authenticate("", "password")


def test_service_rejects_non_positive_access_token_lifetime() -> None:
    with pytest.raises(ValueError, match="access_token_lifetime must be positive"):
        AuthenticationService(
            InMemoryCredentialStore(None),
            PasswordHasher(),
            TokenService("x" * 32),
            timedelta(0),
        )
