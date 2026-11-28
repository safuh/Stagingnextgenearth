"""Google OIDC authorization-code flow and account-linking tests."""

import asyncio
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.api import oauth
from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


class FakeTokenResponse:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"id_token": "signed-google-id-token"}


class FakeGoogleHttpClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout
        self.form: dict[str, str] = {}

    async def __aenter__(self) -> "FakeGoogleHttpClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def post(self, url: str, data: dict[str, str], headers: dict[str, str]):
        assert url == "https://oauth2.googleapis.com/token"
        self.form = data
        assert data["code_verifier"]
        assert headers["Accept"] == "application/json"
        return FakeTokenResponse()


def test_google_oidc_links_only_a_verified_existing_account(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'google-oidc.db'}"
    engine = create_async_engine(database_url)

    async def create_schema() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="google-oidc-test-signing-secret-at-least-32",
        public_base_url="https://nextgen.example.test",
        google_oidc_client_id="client-id.apps.googleusercontent.com",
        google_oidc_client_secret="client-secret",
        google_oidc_redirect_uri="https://nextgen.example.test/api/session/google/callback",
    )
    app = create_app(settings)
    monkeypatch.setattr(oauth.httpx, "AsyncClient", FakeGoogleHttpClient)
    monkeypatch.setattr(
        oauth,
        "_verify_google_id_token",
        lambda token, client_id, nonce: {
            "sub": "google-subject-immutable-123",
            "email": "verified@example.test",
            "email_verified": True,
            "nonce": nonce,
        },
    )

    with TestClient(app) as client:
        registered = client.post(
            "/api/auth/register",
            json={
                "identifier": "verified@example.test",
                "password": "correct horse battery staple",
            },
        )
        assert registered.status_code == 201
        start = client.get("/api/auth/google/start?portal=learner")
        assert start.status_code == 200
        authorization = parse_qs(urlparse(start.json()["authorization_url"]).query)
        assert authorization["code_challenge_method"] == ["S256"]
        assert authorization["nonce"]
        state = authorization["state"][0]

        callback = client.get(
            "/api/auth/google/callback",
            params={"code": "authorization-code", "state": state},
        )
        assert callback.status_code == 200, callback.text
        assert callback.json()["portal"] == "learner"
        assert callback.json()["subject"]
        assert callback.json()["access_token"]
        context = client.get(
            "/api/auth/context",
            headers={"Authorization": f"Bearer {callback.json()['access_token']}"},
        )
        assert context.status_code == 200
        assert context.json()["email_verified"] is True

        replay = client.get(
            "/api/auth/google/callback",
            params={"code": "authorization-code", "state": state},
        )
        assert replay.status_code == 400

        uninvited_start = client.get("/api/auth/google/start")
        uninvited_state = parse_qs(urlparse(uninvited_start.json()["authorization_url"]).query)[
            "state"
        ][0]
        monkeypatch.setattr(
            oauth,
            "_verify_google_id_token",
            lambda token, client_id, nonce: {
                "sub": "another-google-subject",
                "email": "not-invited@example.test",
                "email_verified": True,
                "nonce": nonce,
            },
        )
        denied = client.get(
            "/api/auth/google/callback",
            params={"code": "authorization-code", "state": uninvited_state},
        )
        assert denied.status_code == 403


def test_google_id_token_verification_checks_signature_audience_issuer_nonce_and_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeSigningKey:
        key = "verified-public-key"

    class FakeJwkClient:
        def __init__(self, url: str, timeout: int) -> None:
            assert url == "https://www.googleapis.com/oauth2/v3/certs"
            assert timeout == 10

        def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
            assert token == "signed-token"
            return FakeSigningKey()

    claims = {
        "sub": "google-subject",
        "email": "verified@example.test",
        "email_verified": True,
        "nonce": "expected-nonce",
    }
    decode_arguments: dict[str, object] = {}

    def fake_decode(token: str, key: str, **kwargs: object) -> dict[str, object]:
        decode_arguments.update(kwargs)
        assert key == "verified-public-key"
        return claims

    monkeypatch.setattr(oauth.jwt, "PyJWKClient", FakeJwkClient)
    monkeypatch.setattr(oauth.jwt, "decode", fake_decode)
    result = oauth._verify_google_id_token("signed-token", "google-client-id", "expected-nonce")
    assert result["sub"] == "google-subject"
    assert decode_arguments["algorithms"] == ["RS256"]
    assert decode_arguments["audience"] == "google-client-id"
    assert decode_arguments["issuer"] == ["https://accounts.google.com", "accounts.google.com"]
    assert decode_arguments["options"] == {"require": ["exp", "iat", "iss", "sub", "aud"]}

    claims["nonce"] = "wrong-nonce"
    with pytest.raises(ValueError, match="nonce"):
        oauth._verify_google_id_token("signed-token", "google-client-id", "expected-nonce")
    claims["nonce"] = "expected-nonce"
    claims["email_verified"] = False
    with pytest.raises(ValueError, match="not verified"):
        oauth._verify_google_id_token("signed-token", "google-client-id", "expected-nonce")
