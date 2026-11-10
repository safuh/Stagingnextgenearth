"""Database-polled worker for asynchronous research dataset file scanning."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.platform.models import ResearchDatasetFile
from stagingnextgenearth.scanning import ClamAVScanner
from stagingnextgenearth.storage import ObjectStorage

_MAX_FILE_BYTES = 100 * 1024 * 1024


class FileScanner(Protocol):
    """Malware scanner contract consumed by the worker."""

    def scan(self, content: bytes) -> bool: ...


@dataclass(frozen=True, slots=True)
class DatasetScanBatchResult:
    """Counts returned by one bounded worker poll."""

    scanned: int
    rejected: int
    failed: int


async def scan_pending_dataset_files(
    session_factory: async_sessionmaker[AsyncSession],
    storage: ObjectStorage,
    scanner: FileScanner | ClamAVScanner,
    *,
    batch_size: int = 10,
) -> DatasetScanBatchResult:
    """Scan a bounded batch of quarantined uploads and release only clean files.

    The database row lock coordinates multiple worker processes on PostgreSQL.
    Each completed file is committed independently so a later failure cannot
    roll back earlier verdicts. Infrastructure failures leave the current file
    quarantined with a pending scan state for a subsequent poll.
    """
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")

    scanned = 0
    rejected = 0
    failed = 0
    async with session_factory() as session:
        records = await session.scalars(
            select(ResearchDatasetFile)
            .where(
                ResearchDatasetFile.status == "quarantined",
                ResearchDatasetFile.scan_status == "pending",
                ResearchDatasetFile.uploaded_at.is_not(None),
            )
            .order_by(ResearchDatasetFile.created_at, ResearchDatasetFile.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        file_records = list(records.all())
        for record in file_records:
            try:
                content = await asyncio.to_thread(
                    storage.get_object,
                    key=record.storage_key,
                    max_bytes=_MAX_FILE_BYTES,
                )
                if len(content) != record.size_bytes:
                    record.status = "rejected"
                    record.scan_status = "pending"
                    record.scanned_at = None
                    await session.commit()
                    rejected += 1
                    continue

                is_clean = await asyncio.to_thread(scanner.scan, content)
                record.sha256_hex = hashlib.sha256(content).hexdigest()
                record.scanned_at = datetime.now(UTC)
                record.scan_status = "clean" if is_clean else "rejected"
                record.status = "available" if is_clean else "rejected"
                await session.commit()
                scanned += 1
                if not is_clean:
                    rejected += 1
            except Exception:
                await session.rollback()
                failed += 1
                # Avoid immediately retrying the same failing row in this poll.
                break

    return DatasetScanBatchResult(scanned=scanned, rejected=rejected, failed=failed)
