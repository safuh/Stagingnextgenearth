"""Database-polled worker for asynchronous research dataset file scanning."""

import asyncio
import hashlib
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from stagingnextgenearth.platform.models import ResearchDatasetFile

_MAX_FILE_BYTES = 100 * 1024 * 1024


class ObjectReader(Protocol):
    """Streaming read-only object storage contract."""

    def iter_object_chunks(
        self, *, key: str, max_bytes: int, chunk_size: int = 64 * 1024
    ) -> Iterator[bytes]: ...


class FileScanner(Protocol):
    """Streaming malware scanner contract."""

    def scan_chunks(self, chunks: Iterable[bytes]) -> bool: ...


@dataclass(frozen=True, slots=True)
class DatasetScanBatchResult:
    """Counts returned by one bounded worker poll."""

    scanned: int
    rejected: int
    failed: int


@dataclass(frozen=True, slots=True)
class _ScanResult:
    is_clean: bool
    size_bytes: int
    sha256_hex: str


def _scan_stream(
    storage: ObjectReader, scanner: FileScanner, key: str
) -> _ScanResult:
    """Pipe bounded storage chunks into the scanner while hashing the stream."""
    digest = hashlib.sha256()
    total = 0

    def tracked_chunks() -> Iterator[bytes]:
        nonlocal total
        for chunk in storage.iter_object_chunks(key=key, max_bytes=_MAX_FILE_BYTES):
            total += len(chunk)
            digest.update(chunk)
            yield chunk

    is_clean = scanner.scan_chunks(tracked_chunks())
    return _ScanResult(
        is_clean=is_clean,
        size_bytes=total,
        sha256_hex=digest.hexdigest(),
    )


async def scan_pending_dataset_files(
    session_factory: async_sessionmaker[AsyncSession],
    storage: ObjectReader,
    scanner: FileScanner,
    *,
    batch_size: int = 10,
) -> DatasetScanBatchResult:
    """Scan quarantined uploads in bounded batches and release only clean files.

    Each iteration claims one row with FOR UPDATE SKIP LOCKED. The row lock is
    held while the object is streamed and scanned, then released by that file's
    commit. Infrastructure failures leave the current file quarantined.
    """
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")

    scanned = 0
    rejected = 0
    failed = 0
    failed_ids: set[str] = set()
    async with session_factory() as session:
        for _ in range(batch_size):
            conditions = [
                ResearchDatasetFile.status == "quarantined",
                ResearchDatasetFile.scan_status == "pending",
                ResearchDatasetFile.uploaded_at.is_not(None),
            ]
            if failed_ids:
                conditions.append(ResearchDatasetFile.id.not_in(failed_ids))
            record = await session.scalar(
                select(ResearchDatasetFile)
                .where(*conditions)
                .order_by(ResearchDatasetFile.created_at, ResearchDatasetFile.id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            if record is None:
                break

            try:
                result = await asyncio.to_thread(
                    _scan_stream, storage, scanner, record.storage_key
                )
                if result.size_bytes != record.size_bytes:
                    record.status = "rejected"
                    record.scan_status = "pending"
                    record.scanned_at = None
                    record.sha256_hex = None
                    await session.commit()
                    rejected += 1
                    continue

                record.sha256_hex = result.sha256_hex
                record.scanned_at = datetime.now(UTC)
                record.scan_status = "clean" if result.is_clean else "rejected"
                record.status = "available" if result.is_clean else "rejected"
                await session.commit()
                scanned += 1
                if not result.is_clean:
                    rejected += 1
            except Exception:
                failed_ids.add(record.id)
                await session.rollback()
                failed += 1

    return DatasetScanBatchResult(scanned=scanned, rejected=rejected, failed=failed)
