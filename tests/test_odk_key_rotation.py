"""Transactional ODK Central credential-key rotation tests."""

import asyncio
from pathlib import Path

import pytest
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from stagingnextgenearth.core.database import Base
from stagingnextgenearth.platform.models import ODKConnection
from stagingnextgenearth.workers.rotate_odk_key import rotate_odk_credentials


def test_rotation_dry_run_and_commit_preserve_credentials(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-key-rotation.db'}"
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    old_cipher = Fernet(old_key.encode())
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def exercise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all(
                [
                    ODKConnection(
                        organization_id=f"org-{index}",
                        base_url="https://central.example.org",
                        project_id=index + 1,
                        account_email=f"field-{index}@example.org",
                        encrypted_password=old_cipher.encrypt(
                            f"password-{index}".encode()
                        ).decode(),
                        created_by=f"user-{index}",
                    )
                    for index in range(2)
                ]
            )
            await session.commit()

        checked = await rotate_odk_credentials(
            factory, old_key=old_key, new_key=new_key, dry_run=True
        )
        assert checked == 2
        async with factory() as session:
            rows = list((await session.scalars(select(ODKConnection))).all())
            assert all(old_cipher.decrypt(row.encrypted_password.encode()) for row in rows)

        rotated = await rotate_odk_credentials(factory, old_key=old_key, new_key=new_key)
        assert rotated == 2
        new_cipher = Fernet(new_key.encode())
        async with factory() as session:
            rows = list((await session.scalars(select(ODKConnection))).all())
            assert len(rows) == 2
            assert {
                new_cipher.decrypt(row.encrypted_password.encode()).decode() for row in rows
            } == {
                "password-0",
                "password-1",
            }
            with pytest.raises(InvalidToken):
                old_cipher.decrypt(rows[0].encrypted_password.encode())
        await engine.dispose()

    asyncio.run(exercise())


def test_rotation_aborts_without_partial_updates_when_one_ciphertext_is_corrupt(
    tmp_path: Path,
) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-key-rotation-failure.db'}"
    old_key = Fernet.generate_key().decode()
    new_key = Fernet.generate_key().decode()
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def exercise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            session.add_all(
                [
                    ODKConnection(
                        id="a-valid-first",
                        organization_id="org-one",
                        base_url="https://central.example.org",
                        project_id=1,
                        account_email="field@example.org",
                        encrypted_password=Fernet(old_key.encode())
                        .encrypt(b"preserve-me")
                        .decode(),
                        created_by="user-one",
                    ),
                    ODKConnection(
                        id="z-corrupt-second",
                        organization_id="org-two",
                        base_url="https://central.example.org",
                        project_id=2,
                        account_email="field-two@example.org",
                        encrypted_password="corrupt-ciphertext",
                        created_by="user-two",
                    ),
                ]
            )
            await session.commit()
        with pytest.raises(RuntimeError, match="no credentials were changed"):
            await rotate_odk_credentials(factory, old_key=old_key, new_key=new_key)
        async with factory() as session:
            rows = list(
                (await session.scalars(select(ODKConnection).order_by(ODKConnection.id))).all()
            )
            assert len(rows) == 2
            assert (
                Fernet(old_key.encode()).decrypt(rows[0].encrypted_password.encode())
                == b"preserve-me"
            )
            assert rows[1].encrypted_password == "corrupt-ciphertext"
        await engine.dispose()

    asyncio.run(exercise())


def test_rotation_rejects_identical_keys(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{tmp_path / 'odk-key-rotation-same.db'}"
    key = Fernet.generate_key().decode()
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def exercise() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        with pytest.raises(ValueError, match="must be different"):
            await rotate_odk_credentials(factory, old_key=key, new_key=key)
        await engine.dispose()

    asyncio.run(exercise())
