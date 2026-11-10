from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from stagingnextgenearth.auth import LoginRequest, RegistrationRequest, TokenError
from stagingnextgenearth.auth.tokens import TokenService
from stagingnextgenearth.core.database import Base, create_session_factory
from stagingnextgenearth.identity import (
    RefreshToken,
    User,
    create_sqlalchemy_auth_application,
)


@pytest.mark.asyncio
async def test_sqlalchemy_auth_composition_persists_full_lifecycle() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    session_factory = create_session_factory(engine)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with session_factory() as session:
            application = create_sqlalchemy_auth_application(
                session,
                secret_key="x" * 32,
                access_token_lifetime=timedelta(minutes=15),
                refresh_token_lifetime=timedelta(days=7),
            )

            registration = await application.register(
                RegistrationRequest(identifier="alice@example.com", password="correct horse")
            )
            await session.commit()

            login = await application.login(
                LoginRequest(identifier="alice@example.com", password="correct horse")
            )
            await session.commit()

            refreshed = await application.refresh(login.refresh_token)
            await session.commit()

            with pytest.raises(TokenError, match="Invalid refresh token"):
                await application.refresh(login.refresh_token)
            await session.rollback()

            assert refreshed.subject == registration.subject
            assert TokenService("x" * 32).decode(
                refreshed.access_token, expected_type="access"
            )["sub"] == registration.subject
            assert refreshed.refresh_token != login.refresh_token

            assert await application.logout(refreshed.refresh_token)
            await session.commit()

            with pytest.raises(TokenError, match="Invalid refresh token"):
                await application.refresh(refreshed.refresh_token)
            await session.rollback()

            user = await session.get(User, registration.subject)
            assert user is not None
            assert user.identifier == "alice@example.com"
            assert user.password_hash != "correct horse"

            refresh_rows = await session.execute(
                select(RefreshToken).order_by(RefreshToken.token_id)
            )
            assert len(refresh_rows.scalars().all()) == 2
    finally:
        await engine.dispose()
