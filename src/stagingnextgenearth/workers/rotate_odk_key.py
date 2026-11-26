"""Transactional rotation of encrypted ODK Central connection credentials."""

import argparse
import asyncio
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.core.database import create_engine, create_session_factory
from stagingnextgenearth.platform.models import ODKConnection

logger = logging.getLogger(__name__)


async def rotate_odk_credentials(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    old_key: str,
    new_key: str,
    dry_run: bool = False,
) -> int:
    """Verify or re-encrypt every saved ODK credential in one transaction.

    The row locks prevent a concurrent connection update from being overwritten.
    Any undecryptable row aborts the transaction; the operation never partially
    rotates a tenant's credentials.
    """
    if old_key == new_key:
        raise ValueError("The old and new ODK encryption keys must be different")
    old_cipher = Fernet(old_key.encode())
    new_cipher = Fernet(new_key.encode())
    rotated = 0
    async with session_factory() as session:
        async with session.begin():
            rows = (
                await session.scalars(
                    select(ODKConnection).order_by(ODKConnection.id).with_for_update()
                )
            ).all()
            for row in rows:
                try:
                    plaintext = old_cipher.decrypt(row.encrypted_password.encode())
                except InvalidToken as exc:
                    raise RuntimeError(
                        "ODK credential decryption failed for connection "
                        f"{row.id}; no credentials were changed"
                    ) from exc
                encrypted = new_cipher.encrypt(plaintext)
                if new_cipher.decrypt(encrypted) != plaintext:
                    raise RuntimeError("New ODK encryption key verification failed")
                if not dry_run:
                    row.encrypted_password = encrypted.decode()
                rotated += 1
    return rotated


async def _run(*, dry_run: bool) -> int:
    settings = get_settings()
    if settings.odk_encryption_key is None:
        raise RuntimeError("ODK_ENCRYPTION_KEY must contain the new Fernet key")
    old_key = os.environ.get("ODK_ENCRYPTION_KEY_OLD")
    if not old_key:
        raise RuntimeError("ODK_ENCRYPTION_KEY_OLD must contain the current Fernet key")
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        return await rotate_odk_credentials(
            factory,
            old_key=old_key,
            new_key=settings.odk_encryption_key.get_secret_value(),
            dry_run=dry_run,
        )
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Verify or rotate encrypted ODK Central connection credentials"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "verify every credential can be decrypted and re-encrypted "
            "without changing the database"
        ),
    )
    args = parser.parse_args()
    count = asyncio.run(_run(dry_run=args.dry_run))
    action = "Verified" if args.dry_run else "Re-encrypted"
    print(f"{action} {count} ODK Central connection credential(s).")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
