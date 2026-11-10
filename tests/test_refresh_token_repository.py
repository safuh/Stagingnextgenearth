"""Tests for SQLAlchemy-backed refresh-token persistence."""

from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from stagingnextgenearth.auth import RefreshTokenRecord
from stagingnextgenearth.core.config import Settings
from stagingnextgenearth.core.database import create_engine, create_session_factory
from stagingnextgenearth.identity import RefreshToken, SqlAlchemyRefreshTokenStore


async def _session():
    engine = create_engine(Settings.for_profile("test"))
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(RefreshToken.metadata.create_all)
    session = factory()
    return engine, session


@pytest.mark.asyncio
async def test_refresh_token_store_create_and_consume() -> None:
    engine, session = await _session()
    try:
        store = SqlAlchemyRefreshTokenStore(session)
        token_id = uuid4()
        await store.create(
            RefreshTokenRecord(token_id, "user-123", timedelta(days=7))
        )
        await session.commit()

        consumed = await store.consume(token_id, "user-123")
        await session.commit()

        assert consumed is not None
        assert consumed.token_id == token_id
        assert consumed.subject == "user-123"
        assert not consumed.revoked

        replay = await store.consume(token_id, "user-123")
        assert replay is None
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_token_store_rejects_subject_mismatch_without_consuming() -> None:
    engine, session = await _session()
    try:
        store = SqlAlchemyRefreshTokenStore(session)
        token_id = uuid4()
        await store.create(
            RefreshTokenRecord(token_id, "user-123", timedelta(days=7))
        )
        await session.commit()

        assert await store.consume(token_id, "attacker") is None
        assert await store.consume(token_id, "user-123") is not None
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_token_store_rejects_expired_token() -> None:
    engine, session = await _session()
    try:
        store = SqlAlchemyRefreshTokenStore(session)
        token_id = uuid4()
        await store.create(
            RefreshTokenRecord(token_id, "user-123", timedelta(seconds=-1))
        )
        await session.commit()

        assert await store.consume(token_id, "user-123") is None
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_refresh_token_store_revoke_is_idempotent() -> None:
    engine, session = await _session()
    try:
        store = SqlAlchemyRefreshTokenStore(session)
        token_id = uuid4()
        await store.create(
            RefreshTokenRecord(token_id, "user-123", timedelta(days=7))
        )
        await session.commit()

        assert await store.revoke(token_id)
        await session.commit()
        assert not await store.revoke(token_id)
        assert await store.consume(token_id, "user-123") is None

        persisted = await session.scalar(
            select(RefreshToken).where(RefreshToken.token_id == str(token_id))
        )
        assert persisted is not None
        assert persisted.revoked
    finally:
        await session.close()
        await engine.dispose()
