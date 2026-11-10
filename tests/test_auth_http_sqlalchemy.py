from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base
from stagingnextgenearth.identity import create_sqlalchemy_auth_application


@pytest.mark.asyncio
async def test_auth_http_uses_sqlalchemy_composition(tmp_path: Path) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}"
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
    finally:
        await engine.dispose()

    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
    )

    def application_factory(session):
        return create_sqlalchemy_auth_application(
            session,
            secret_key="x" * 32,
            access_token_lifetime=timedelta(minutes=15),
            refresh_token_lifetime=timedelta(days=7),
        )

    with TestClient(create_app(settings, application_factory)) as client:
        registered = client.post(
            "/api/auth/register",
            json={"identifier": "alice@example.com", "password": "correct horse"},
        )
        assert registered.status_code == 201

        logged_in = client.post(
            "/api/auth/login",
            json={"identifier": "alice@example.com", "password": "correct horse"},
        )
        assert logged_in.status_code == 200
        tokens = logged_in.json()

        refreshed = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert refreshed.status_code == 200

        replay = client.post(
            "/api/auth/refresh",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert replay.status_code == 401

        logged_out = client.post(
            "/api/auth/logout",
            json={"refresh_token": refreshed.json()["refresh_token"]},
        )
        assert logged_out.status_code == 204

        revoked = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refreshed.json()["refresh_token"]},
        )
        assert revoked.status_code == 401
