import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.core.config import Settings
from stagingnextgenearth.core.database import (
    UnitOfWork,
    create_engine,
    create_session_factory,
    session_scope,
)


@pytest.mark.asyncio
async def test_session_scope_commits() -> None:
    engine = create_engine(Settings.for_profile("test"))
    factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
            )
        async with session_scope(factory) as session:
            await session.execute(text("INSERT INTO items (name) VALUES ('one')"))
        async with factory() as session:
            result = await session.execute(text("SELECT name FROM items"))
            assert result.scalar_one() == "one"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_unit_of_work_rolls_back_on_error() -> None:
    engine = create_engine(Settings.for_profile("test"))
    factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
            )
        with pytest.raises(RuntimeError):
            async with UnitOfWork(factory) as uow:
                assert isinstance(uow.session, AsyncSession)
                await uow.session.execute(
                    text("INSERT INTO items (name) VALUES ('one')")
                )
                raise RuntimeError("boom")
        async with factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM items"))
            assert result.scalar_one() == 0
    finally:
        await engine.dispose()
