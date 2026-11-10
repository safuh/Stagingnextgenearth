from datetime import timedelta
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from stagingnextgenearth.app import create_app
from stagingnextgenearth.auth import (
    AuthenticationApplication,
    AuthenticationService,
    Credentials,
    IdentifierAlreadyExistsError,
    LoginService,
    PasswordHasher,
    RefreshTokenRecord,
    RefreshTokenService,
    RegistrationService,
    TokenService,
)
from stagingnextgenearth.core.config import Environment, Settings


class MemoryIdentityStore:
    def __init__(self) -> None:
        self.users: dict[str, tuple[str, str]] = {}

    async def get_by_identifier(self, identifier: str) -> Credentials | None:
        user = self.users.get(identifier)
        if user is None:
            return None
        subject, password_hash = user
        return Credentials(subject=subject, password_hash=password_hash)

    async def create(self, identifier: str, password_hash: str) -> str:
        if identifier in self.users:
            raise IdentifierAlreadyExistsError("Identifier is already registered")
        subject = f"user-{len(self.users) + 1}"
        self.users[identifier] = (subject, password_hash)
        return subject


class MemoryRefreshStore:
    def __init__(self) -> None:
        self.records: dict[UUID, RefreshTokenRecord] = {}

    async def create(self, record: RefreshTokenRecord) -> None:
        self.records[record.token_id] = record

    async def consume(self, token_id: UUID, subject: str) -> RefreshTokenRecord | None:
        record = self.records.get(token_id)
        if record is None or record.subject != subject or record.revoked:
            return None
        self.records[token_id] = RefreshTokenRecord(
            token_id=record.token_id,
            subject=record.subject,
            expires_in=record.expires_in,
            revoked=True,
        )
        return record

    async def revoke(self, token_id: UUID) -> bool:
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
def client() -> TestClient:
    identity_store = MemoryIdentityStore()
    refresh_store = MemoryRefreshStore()
    hasher = PasswordHasher()
    token_service = TokenService("x" * 32)

    def application_factory(_session: object) -> AuthenticationApplication:
        authentication = AuthenticationService(
            credential_store=identity_store,
            password_hasher=hasher,
            token_service=token_service,
            access_token_lifetime=timedelta(minutes=15),
        )
        refresh = RefreshTokenService(
            token_service=token_service,
            refresh_token_store=refresh_store,
            access_token_lifetime=timedelta(minutes=15),
            refresh_token_lifetime=timedelta(days=7),
        )
        return AuthenticationApplication(
            registration_service=RegistrationService(identity_store, hasher),
            login_service=LoginService(authentication),
            refresh_token_service=refresh,
        )

    settings = Settings(
        environment=Environment.TEST,
        database_url="sqlite+aiosqlite:///:memory:",
    )
    with TestClient(create_app(settings, application_factory)) as test_client:
        yield test_client


def test_register_login_refresh_and_logout(client: TestClient) -> None:
    registered = client.post(
        "/api/auth/register",
        json={"identifier": "alice", "password": "correct-password"},
    )
    assert registered.status_code == 201
    assert registered.json()["subject"] == "user-1"

    logged_in = client.post(
        "/api/auth/login",
        json={"identifier": "alice", "password": "correct-password"},
    )
    assert logged_in.status_code == 200
    tokens = logged_in.json()
    assert tokens["subject"] == "user-1"

    refreshed = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refreshed.status_code == 200
    replacement = refreshed.json()
    assert replacement["refresh_token"] != tokens["refresh_token"]

    replay = client.post(
        "/api/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert replay.status_code == 401

    logged_out = client.post(
        "/api/auth/logout",
        json={"refresh_token": replacement["refresh_token"]},
    )
    assert logged_out.status_code == 204

    revoked = client.post(
        "/api/auth/refresh",
        json={"refresh_token": replacement["refresh_token"]},
    )
    assert revoked.status_code == 401


def test_login_does_not_reveal_unknown_identifier(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"identifier": "missing", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert response.json()["error"]["message"] == "Invalid credentials"


def test_duplicate_registration_is_conflict(client: TestClient) -> None:
    payload = {"identifier": "alice", "password": "correct-password"}
    assert client.post("/api/auth/register", json=payload).status_code == 201

    response = client.post("/api/auth/register", json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "identifier_exists"


def test_malformed_refresh_token_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": "not-a-jwt"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_refresh_token"
