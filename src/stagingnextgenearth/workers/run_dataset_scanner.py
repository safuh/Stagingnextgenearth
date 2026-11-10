"""Executable polling process for asynchronous research dataset malware scanning."""

import argparse
import asyncio
import logging

from stagingnextgenearth.core.config import get_settings
from stagingnextgenearth.core.database import create_engine, create_session_factory
from stagingnextgenearth.scanning import ClamAVScanner
from stagingnextgenearth.storage import S3ObjectStorage

from .dataset_scanner import scan_pending_dataset_files

logger = logging.getLogger("stagingnextgenearth.dataset_scanner")


async def run_worker(*, batch_size: int, poll_interval_seconds: float) -> None:
    """Run the scanner poller until interrupted by the process supervisor."""
    settings = get_settings()
    if not settings.object_storage_enabled or not settings.malware_scanning_enabled:
        raise RuntimeError(
            "Dataset scanner worker requires object storage and malware scanning"
        )
    if (
        settings.object_storage_bucket is None
        or settings.object_storage_access_key_id is None
        or settings.object_storage_secret_access_key is None
        or settings.clamav_host is None
    ):
        raise RuntimeError("Dataset scanner worker configuration is incomplete")

    storage = S3ObjectStorage(
        bucket=settings.object_storage_bucket,
        region=settings.object_storage_region,
        endpoint_url=settings.object_storage_endpoint_url,
        access_key_id=settings.object_storage_access_key_id.get_secret_value(),
        secret_access_key=settings.object_storage_secret_access_key.get_secret_value(),
    )
    scanner = ClamAVScanner(
        host=settings.clamav_host,
        port=settings.clamav_port,
        timeout_seconds=settings.clamav_timeout_seconds,
    )
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    logger.info("Dataset scanner worker started")
    try:
        while True:
            result = await scan_pending_dataset_files(
                session_factory, storage, scanner, batch_size=batch_size
            )
            if result.scanned or result.rejected or result.failed:
                logger.info(
                    "Dataset scan batch completed: scanned=%s rejected=%s failed=%s",
                    result.scanned,
                    result.rejected,
                    result.failed,
                )
            await asyncio.sleep(poll_interval_seconds)
    finally:
        await engine.dispose()
        logger.info("Dataset scanner worker stopped")


def main() -> None:
    """Parse process options and start the long-running worker."""
    parser = argparse.ArgumentParser(
        description="Poll and malware-scan quarantined research dataset files."
    )
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--poll-interval-seconds", type=float, default=5.0)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 100:
        parser.error("--batch-size must be between 1 and 100")
    if args.poll_interval_seconds <= 0:
        parser.error("--poll-interval-seconds must be positive")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(
        run_worker(
            batch_size=args.batch_size,
            poll_interval_seconds=args.poll_interval_seconds,
        )
    )


if __name__ == "__main__":
    main()
