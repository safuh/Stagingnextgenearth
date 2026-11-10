from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from stagingnextgenearth.auth import PasswordHasher
from stagingnextgenearth.core.config import Settings
from stagingnextgenearth.core.database import create_engine, create_session_factory
from stagingnextgenearth.identity import User, UserCredentialRepository


async def _session() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession], AsyncSession]:
    engine = create_engine(Settings.for_profile("test"))
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(User.metadata.create_all)
    session = factory()
    return engine, factory, session


async def test_user_credential_repository_returns_credentials() -> None:
    engine, _, session = await _session()
    try:
        hasher = PasswordHasher()
        user = User(identifier="alice@example.com", password_hash=hasher.hash("secret"))
        session.add(user)
        await session.commit()

        credentials = await UserCredentialRepository(session).get_by_identifier(
            "alice@example.com"
        )

        assert credentials is not None
        assert credentials.subject == user.id
        assert credentials.password_hash == user.password_hash
        assert hasher.verify("secret", credentials.password_hash)
    finally:
        await session.close()
        await engine.dispose()


async def test_user_credential_repository_returns_none_for_unknown_identifier() -> None:
    engine, _, session = await _session()
    try:
        assert (
            await UserCredentialRepository(session).get_by_identifier("missing@example.com")
            is None
        )
    finally:
        await session.close()
        await engine.dispose()


async def test_user_identifier_is_unique() -> None:
    engine, _, session = await _session()
    try:
        session.add_all(
            [
                User(identifier="duplicate@example.com", password_hash="hash-a"),
                User(identifier="duplicate@example.com", password_hash="hash-b"),
            ]
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
        else:
            raise AssertionError("duplicate identifiers must be rejected")
    finally:
        await session.close()
        await engine.dispose()
