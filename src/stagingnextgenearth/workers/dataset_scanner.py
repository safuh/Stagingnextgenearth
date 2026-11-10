"""Database-polled worker for asynchronous research dataset file scanning."""

import asyncio
import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.platform.models import ResearchDatasetFile

_MAX_FILE_BYTES = 100 * 1024 * 1024


class ObjectReader(Protocol):
    """Read-only object storage contract needed by the scanning worker."""

    def get_object(self, *, key: str, max_bytes: int) -> bytes: ...


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
    storage: ObjectReader,
    scanner: FileScanner,
    *,
    batch_size: int = 10,
) -> DatasetScanBatchResult:
    """Scan a bounded batch of quarantined uploads and release only clean files.

    Each iteration claims one row with FOR UPDATE SKIP LOCKED. The row lock is
    held while the object is read and scanned, then released by that file's
    commit. This prevents two PostgreSQL workers from scanning the same file.
    Infrastructure failures leave the current file quarantined for a later poll.
    """
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")

    scanned = 0
    rejected = 0
    failed = 0
    async with session_factory() as session:
        for _ in range(batch_size):
            record = await session.scalar(
                select(ResearchDatasetFile)
                .where(
                    ResearchDatasetFile.status == "quarantined",
                    ResearchDatasetFile.scan_status == "pending",
                    ResearchDatasetFile.uploaded_at.is_not(None),
                )
                .order_by(ResearchDatasetFile.created_at, ResearchDatasetFile.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if record is None:
                break

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
                break

    return DatasetScanBatchResult(scanned=scanned, rejected=rejected, failed=failed)
