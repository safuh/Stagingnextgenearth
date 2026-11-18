"""ODK Central connection credential handling and tenant authorization."""

import asyncio
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.api import odk_connections
from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.platform.models import Base, ODKConnection


def _auth(client: TestClient, identifier: str) -> dict[str, str]:
    password = "correct horse battery staple"
    response = client.post(
        "/api/auth/register", json={"identifier": identifier, "password": password}
    )
    assert response.status_code == 201
    response = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_connection_password_is_encrypted_and_never_returned(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-connections.db'}"
    key = Fernet.generate_key().decode()
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
        odk_encryption_key=key,
    )
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "odk-config-owner@example.org")
        outsider = _auth(client, "odk-config-outsider@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "ODK Config Team", "slug": "odk-config-team"},
        )
        assert org.status_code == 201
        organization_id = org.json()["id"]
        base = f"/api/organizations/{organization_id}/odk"
        payload = {
            "base_url": "https://central.example.org",
            "project_id": 12,
            "account_email": "field.admin@example.org",
            "password": "sensitive-odk-password",
            "form_mappings": {
                "rainfall-v1": {
                    "observed_at": "date",
                    "variable": "measure",
                    "value": "reading",
                    "unit": "unit",
                    "latitude": "lat",
                    "longitude": "lon",
                }
            },
            "enabled": True,
        }
        saved = client.put(f"{base}/connection", headers=owner, json=payload)
        assert saved.status_code == 200, saved.text
        assert saved.json()["configured"] is True
        assert saved.json()["mapped_forms"] == ["rainfall-v1"]
        assert "password" not in saved.text
        assert "encrypted_password" not in saved.text
        assert "sensitive-odk-password" not in saved.text

        retrieved = client.get(f"{base}/connection", headers=owner)
        assert retrieved.status_code == 200
        assert retrieved.json()["account_email"] == "field.admin@example.org"
        assert "sensitive-odk-password" not in retrieved.text
        assert client.get(f"{base}/connection", headers=outsider).status_code == 404
        assert client.put(f"{base}/connection", headers=outsider, json=payload).status_code == 404

        async def inspect_secret() -> str:
            db_engine = create_async_engine(url)
            try:
                from sqlalchemy.ext.asyncio import async_sessionmaker

                factory = async_sessionmaker(db_engine, expire_on_commit=False)
                async with factory() as session:
                    record = await session.scalar(
                        select(ODKConnection).where(
                            ODKConnection.organization_id == organization_id
                        )
                    )
                    assert record is not None
                    return record.encrypted_password
            finally:
                await db_engine.dispose()

        encrypted = asyncio.run(inspect_secret())
        assert encrypted != payload["password"]
        assert Fernet(key.encode()).decrypt(encrypted.encode()).decode() == payload["password"]


def test_form_discovery_uses_saved_central_credentials(monkeypatch, tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-forms.db'}"
    key = Fernet.generate_key().decode()
    engine = create_async_engine(url)

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
        odk_encryption_key=key,
    )
    calls: list[dict[str, object]] = []

    async def fake_list_forms(**kwargs):
        calls.append(kwargs)
        return [{"xmlFormId": "tree-survival", "name": "Tree survival", "version": "2"}]

    monkeypatch.setattr(odk_connections, "_authenticate_and_list_forms", fake_list_forms)
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "odk-form-owner@example.org")
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "ODK Form Team", "slug": "odk-form-team"},
        )
        base = f"/api/organizations/{org.json()['id']}/odk"
        payload = {
            "base_url": "https://central.example.org",
            "project_id": 7,
            "account_email": "forms@example.org",
            "password": "secret-for-test-only",
        }
        assert client.put(f"{base}/connection", headers=owner, json=payload).status_code == 200
        forms = client.get(f"{base}/forms", headers=owner)
        assert forms.status_code == 200
        assert forms.json() == [
            {"xml_form_id": "tree-survival", "name": "Tree survival", "version": "2", "state": None}
        ]
        assert calls[0]["password"] == "secret-for-test-only"
        assert calls[0]["project_id"] == 7


def test_odk_connection_management_requires_admin_membership(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-connection-rbac.db'}"
    engine = create_async_engine(url)
    key = Fernet.generate_key().decode()

    async def prepare() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(prepare())
    settings = Settings(
        environment=Environment.TEST,
        database_url=url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
        odk_encryption_key=key,
    )
    with TestClient(create_app(settings)) as client:
        owner = _auth(client, "odk-rbac-owner@example.org")
        learner_password = "correct horse battery staple"
        registration = client.post(
            "/api/auth/register",
            json={"identifier": "odk-rbac-learner@example.org", "password": learner_password},
        )
        assert registration.status_code == 201
        learner_user_id = registration.json()["subject"]
        login = client.post(
            "/api/auth/login",
            json={"identifier": "odk-rbac-learner@example.org", "password": learner_password},
        )
        learner = {"Authorization": f"Bearer {login.json()['access_token']}"}
        org = client.post(
            "/api/organizations",
            headers=owner,
            json={"name": "ODK RBAC Team", "slug": "odk-rbac-team"},
        )
        organization_id = org.json()["id"]

        async def add_learner_membership() -> None:
            db_engine = create_async_engine(url)
            try:
                from sqlalchemy.ext.asyncio import async_sessionmaker

                factory = async_sessionmaker(db_engine, expire_on_commit=False)
                async with factory() as session:
                    from stagingnextgenearth.platform.models import Membership

                    session.add(
                        Membership(
                            organization_id=organization_id,
                            user_id=learner_user_id,
                            role="learner",
                            status="active",
                        )
                    )
                    await session.commit()
            finally:
                await db_engine.dispose()

        asyncio.run(add_learner_membership())
        base = f"/api/organizations/{organization_id}/odk"
        payload = {
            "base_url": "https://central.example.org",
            "project_id": 3,
            "account_email": "learner@example.org",
            "password": "not-a-real-password",
        }
        assert client.put(f"{base}/connection", headers=learner, json=payload).status_code == 403
        assert client.post(f"{base}/connection/test", headers=learner, json={}).status_code == 403
        assert client.get(f"{base}/forms", headers=learner).status_code == 403
        assert client.delete(f"{base}/connection", headers=learner).status_code == 403
