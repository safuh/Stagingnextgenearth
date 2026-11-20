"""Authenticated password-change and refresh-session revocation tests."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import create_sqlalchemy_auth_application


@pytest.mark.asyncio
async def test_password_change_revokes_all_refresh_sessions(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'password-change.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    secret = "x" * 32
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key=SecretStr(secret),
    )

    def application_factory(session):
        return create_sqlalchemy_auth_application(
            session,
            secret_key=secret,
            access_token_lifetime=timedelta(minutes=15),
            refresh_token_lifetime=timedelta(days=7),
        )

    with TestClient(create_app(settings, application_factory)) as client:
        credentials = {
            "identifier": "account@example.org",
            "password": "original-password",
        }
        assert client.post("/api/auth/register", json=credentials).status_code == 201
        first_login = client.post("/api/auth/login", json=credentials)
        second_login = client.post("/api/auth/login", json=credentials)
        assert first_login.status_code == second_login.status_code == 200
        first_tokens = first_login.json()
        second_tokens = second_login.json()

        changed = client.post(
            "/api/auth/change-password",
            headers={"Authorization": f"Bearer {first_tokens['access_token']}"},
            json={
                "current_password": "original-password",
                "new_password": "replacement-password",
            },
        )
        assert changed.status_code == 200
        assert changed.json()["revoked_refresh_sessions"] == 2

        for token in (first_tokens["refresh_token"], second_tokens["refresh_token"]):
            revoked = client.post("/api/auth/refresh", json={"refresh_token": token})
            assert revoked.status_code == 401

        old_password = client.post("/api/auth/login", json=credentials)
        assert old_password.status_code == 401

        new_login = client.post(
            "/api/auth/login",
            json={
                "identifier": "account@example.org",
                "password": "replacement-password",
            },
        )
        assert new_login.status_code == 200


@pytest.mark.asyncio
async def test_password_change_requires_authentication(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'password-auth.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    secret = "y" * 32
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key=SecretStr(secret),
    )

    def application_factory(session):
        return create_sqlalchemy_auth_application(
            session,
            secret_key=secret,
            access_token_lifetime=timedelta(minutes=15),
            refresh_token_lifetime=timedelta(days=7),
        )

    with TestClient(create_app(settings, application_factory)) as client:
        response = client.post(
            "/api/auth/change-password",
            json={
                "current_password": "old-password",
                "new_password": "replacement-password",
            },
        )
        assert response.status_code == 401
