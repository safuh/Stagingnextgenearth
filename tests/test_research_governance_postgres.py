"""PostgreSQL integration coverage for concurrent protocol version allocation."""

from __future__ import annotations

import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.app import create_app
from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.database import Base


@pytest.mark.integration
def test_concurrent_protocol_creations_allocate_distinct_versions() -> None:
    """Exercise SELECT FOR UPDATE with independent PostgreSQL connections."""
    source_url = os.getenv("TEST_DATABASE_URL")
    if not source_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    async def create_database(database_name: str) -> None:
        parts = urlsplit(source_url)
        maintenance_url = urlunsplit(
            (parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment)
        )
        connection = await asyncpg.connect(maintenance_url.replace("+asyncpg", ""))
        try:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
        finally:
            await connection.close()

    async def drop_database(database_name: str) -> None:
        parts = urlsplit(source_url)
        maintenance_url = urlunsplit(
            (parts.scheme, parts.netloc, "/postgres", parts.query, parts.fragment)
        )
        connection = await asyncpg.connect(maintenance_url.replace("+asyncpg", ""))
        try:
            await connection.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = $1 AND pid <> pg_backend_pid()",
                database_name,
            )
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}"')
        finally:
            await connection.close()

    database_name = f"ng_protocol_{uuid.uuid4().hex[:16]}"
    asyncio.run(create_database(database_name))
    parts = urlsplit(source_url)
    database_url = urlunsplit(
        (parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment)
    )
    engine = create_async_engine(database_url)
    settings = Settings(
        environment=Environment.TEST,
        database_url=database_url,
        jwt_secret_key="test-only-signing-secret-that-is-long-enough",
    )

    try:

        async def prepare_schema() -> None:
            async with engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)

        asyncio.run(prepare_schema())
        with TestClient(create_app(settings)) as client:
            lead = client.post(
                "/api/auth/register",
                json={
                    "identifier": "pg-protocol-lead@example.org",
                    "password": "correct horse battery staple",
                },
            )
            assert lead.status_code == 201
            login = client.post(
                "/api/auth/login",
                json={
                    "identifier": "pg-protocol-lead@example.org",
                    "password": "correct horse battery staple",
                },
            )
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
            organization = client.post(
                "/api/organizations",
                headers=headers,
                json={"name": "Concurrency Research Lab", "slug": "concurrency-research-lab"},
            )
            assert organization.status_code == 201
            organization_id = organization.json()["id"]
            study = client.post(
                f"/api/organizations/{organization_id}/research-studies",
                headers=headers,
                json={"title": "Concurrent protocol allocation study"},
            )
            assert study.status_code == 201
            endpoint = (
                f"/api/organizations/{organization_id}/research-studies/"
                f"{study.json()['id']}/protocol-versions"
            )
            payloads = [
                {
                    "title": f"Protocol submission {index}",
                    "objectives": "Measure seasonal rainfall variability.",
                    "methodology": "Analyse validated station observations.",
                }
                for index in range(2)
            ]
            with ThreadPoolExecutor(max_workers=2) as pool:
                responses = list(
                    pool.map(
                        lambda payload: client.post(endpoint, headers=headers, json=payload),
                        payloads,
                    )
                )
            assert [response.status_code for response in responses] == [201, 201]
            assert sorted(response.json()["version_number"] for response in responses) == [1, 2]
            history = client.get(endpoint, headers=headers)
            assert history.status_code == 200
            assert [item["version_number"] for item in history.json()] == [2, 1]
    finally:
        asyncio.run(engine.dispose())
        asyncio.run(drop_database(database_name))
