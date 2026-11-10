import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_postgresql_connection_and_transaction() -> None:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            result = await connection.execute(text("SELECT current_database()"))
            assert result.scalar_one() == "backbone"
    finally:
        await engine.dispose()
