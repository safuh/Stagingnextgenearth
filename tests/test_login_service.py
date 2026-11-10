from datetime import timedelta

import pytest

from stagingnextgenearth.auth import (
    AuthenticationError,
    AuthenticationService,
    Credentials,
    LoginRequest,
    LoginService,
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


def make_login_service(credentials: Credentials | None) -> LoginService:
    authentication_service = AuthenticationService(
        InMemoryCredentialStore(credentials),
        PasswordHasher(),
        TokenService("x" * 32),
        timedelta(minutes=15),
    )
    return LoginService(authentication_service)


@pytest.mark.asyncio
async def test_login_returns_transport_neutral_response() -> None:
    hasher = PasswordHasher()
    service = make_login_service(
        Credentials(subject="user-123", password_hash=hasher.hash("correct password"))
    )

    result = await service.login(
        LoginRequest(identifier="alice@example.com", password="correct password")
    )

    assert result.subject == "user-123"
    assert result.access_token
    assert not result.password_needs_rehash

    payload = service.authentication_service.token_service.decode(
        result.access_token,
        expected_type="access",
    )
    assert payload["sub"] == "user-123"


@pytest.mark.asyncio
async def test_login_rejects_missing_identifier() -> None:
    service = make_login_service(None)

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.login(LoginRequest(identifier="", password="password"))


@pytest.mark.asyncio
async def test_login_rejects_missing_password() -> None:
    service = make_login_service(None)

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.login(LoginRequest(identifier="alice@example.com", password=""))


@pytest.mark.asyncio
async def test_login_preserves_authentication_failure_contract() -> None:
    hasher = PasswordHasher()
    service = make_login_service(
        Credentials(subject="user-123", password_hash=hasher.hash("correct password"))
    )

    with pytest.raises(AuthenticationError, match="Invalid credentials"):
        await service.login(
            LoginRequest(identifier="alice@example.com", password="wrong password")
        )
