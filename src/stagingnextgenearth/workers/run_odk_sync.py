"""Executable scheduled ODK Central submission synchronisation worker."""

import argparse
import asyncio
import logging

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.core.database import create_engine, create_session_factory
from stagingnextgenearth.workers.odk_sync import sync_enabled_connections


async def run_worker(*, poll_interval_seconds: float, batch_size: int) -> None:
    settings = get_settings()
    if settings.odk_encryption_key is None:
        raise RuntimeError("ODK sync worker requires ODK_ENCRYPTION_KEY")
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    logging.getLogger(__name__).info("ODK Central sync worker started")
    try:
        while True:
            completed = await sync_enabled_connections(
                session_factory,
                encryption_key=settings.odk_encryption_key.get_secret_value(),
                batch_size=batch_size,
            )
            if completed:
                logging.getLogger(__name__).info(
                    "ODK Central sync connections processed: %s", completed
                )
            await asyncio.sleep(poll_interval_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Poll configured ODK Central projects and import mapped submissions"
    )
    parser.add_argument("--poll-interval-seconds", type=float, default=60)
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    if args.poll_interval_seconds < 5:
        parser.error("--poll-interval-seconds must be at least 5")
    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(
        run_worker(poll_interval_seconds=args.poll_interval_seconds, batch_size=args.batch_size)
    )


if __name__ == "__main__":
    main()
