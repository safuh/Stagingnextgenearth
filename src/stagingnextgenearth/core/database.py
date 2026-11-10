"""Async SQLAlchemy engine, session, and unit-of-work infrastructure."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import Settings


class Base(DeclarativeBase):
    """Base class owned by the consuming application's ORM models."""


def create_engine(settings: Settings) -> AsyncEngine:
    """Create the shared async engine."""
    if settings.database_url.startswith("postgresql+asyncpg://"):
        return create_async_engine(
            settings.database_url,
            echo=settings.database_echo,
            pool_pre_ping=settings.database_pool_pre_ping,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )
    return create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_pre_ping=settings.database_pool_pre_ping,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create the application session factory."""
    return async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


@asynccontextmanager
async def session_scope(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Provide a transaction-scoped session; commit on success, rollback on failure."""
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


class UnitOfWork:
    """Explicit transaction boundary for application services.

    The UoW owns one session and transaction. Repositories should receive the
    session rather than opening independent transactions.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self.session: AsyncSession | None = None

    async def __aenter__(self) -> "UnitOfWork":
        self.session = self._session_factory()
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        assert self.session is not None
        try:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
        finally:
            await self.session.close()


async def get_db(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session and rollback failed requests."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
