"""Application lifespan and resource lifecycle."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from .config import Settings
from .database import create_engine, create_session_factory


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create shared infrastructure at startup and dispose it at shutdown."""
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.db_engine = engine
    app.state.db_session_factory = session_factory
    app.state.startup_complete = False

    try:
        if settings.environment.value != "test":
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        app.state.startup_complete = True
        yield
    finally:
        app.state.startup_complete = False
        await engine.dispose()
