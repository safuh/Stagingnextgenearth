"""Tests for asynchronous research dataset file scanning."""

from datetime import UTC, datetime

import pytest

from stagingnextgenearth.core.config import Settings
from stagingnextgenearth.core.database import Base, create_engine, create_session_factory
from stagingnextgenearth.identity.models import User
from stagingnextgenearth.platform.models import (
    Organization,
    ResearchDataset,
    ResearchDatasetFile,
)
from stagingnextgenearth.workers.dataset_scanner import scan_pending_dataset_files


class FakeStorage:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects

    def iter_object_chunks(
        self, *, key: str, max_bytes: int, chunk_size: int = 64 * 1024
    ):
        content = self.objects[key]
        if len(content) > max_bytes:
            raise ValueError("object too large")
        for offset in range(0, len(content), chunk_size):
            yield content[offset : offset + chunk_size]


class FakeScanner:
    def scan_chunks(self, chunks) -> bool:
        return b"".join(chunks) != b"infected"


@pytest.mark.asyncio
async def test_worker_releases_clean_files_and_rejects_infected_files(tmp_path) -> None:
    settings = Settings.for_profile("test").model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'worker.db'}"}
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            user = User(
                id="user-1",
                identifier="worker@example.org",
                password_hash="not-used",
            )
            organization = Organization(
                id="org-1",
                name="Worker Lab",
                slug="worker-lab",
                owner_user_id=user.id,
            )
            dataset = ResearchDataset(
                id="dataset-1",
                organization_id=organization.id,
                title="Rainfall observations",
                version="1.0",
                format="CSV",
                source="Field station",
                data_dictionary={},
                owner_user_id=user.id,
            )
            session.add_all([user, organization, dataset])
            await session.flush()
            session.add_all(
                [
                    ResearchDatasetFile(
                        id="clean-file",
                        dataset_id=dataset.id,
                        version=1,
                        original_filename="clean.csv",
                        media_type="text/csv",
                        size_bytes=5,
                        storage_key="clean-key",
                        status="quarantined",
                        scan_status="pending",
                        uploaded_at=datetime.now(UTC),
                        created_by=user.id,
                    ),
                    ResearchDatasetFile(
                        id="infected-file",
                        dataset_id=dataset.id,
                        version=2,
                        original_filename="infected.csv",
                        media_type="text/csv",
                        size_bytes=8,
                        storage_key="infected-key",
                        status="quarantined",
                        scan_status="pending",
                        uploaded_at=datetime.now(UTC),
                        created_by=user.id,
                    ),
                ]
            )
            await session.commit()

        result = await scan_pending_dataset_files(
            factory,
            FakeStorage({"clean-key": b"clean", "infected-key": b"infected"}),
            FakeScanner(),
            batch_size=5,
        )
        assert result.scanned == 2
        assert result.rejected == 1
        assert result.failed == 0

        async with factory() as session:
            clean = await session.get(ResearchDatasetFile, "clean-file")
            infected = await session.get(ResearchDatasetFile, "infected-file")
            assert clean is not None
            assert clean.status == "available"
            assert clean.scan_status == "clean"
            assert clean.sha256_hex is not None
            assert clean.scanned_at is not None
            assert infected is not None
            assert infected.status == "rejected"
            assert infected.scan_status == "rejected"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_worker_keeps_file_quarantined_when_scanner_fails(tmp_path) -> None:
    settings = Settings.for_profile("test").model_copy(
        update={"database_url": f"sqlite+aiosqlite:///{tmp_path / 'worker-fail.db'}"}
    )
    engine = create_engine(settings)
    factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            user = User(
                id="user-1",
                identifier="worker-fail@example.org",
                password_hash="not-used",
            )
            organization = Organization(
                id="org-1",
                name="Worker Failure Lab",
                slug="worker-failure-lab",
                owner_user_id=user.id,
            )
            dataset = ResearchDataset(
                id="dataset-1",
                organization_id=organization.id,
                title="Rainfall observations",
                version="1.0",
                format="CSV",
                source="Field station",
                data_dictionary={},
                owner_user_id=user.id,
            )
            session.add_all([user, organization, dataset])
            await session.flush()
            session.add_all(
                [
                    ResearchDatasetFile(
                        id="file-1",
                        dataset_id=dataset.id,
                        version=1,
                        original_filename="pending.csv",
                        media_type="text/csv",
                        size_bytes=3,
                        storage_key="broken-key",
                        status="quarantined",
                        scan_status="pending",
                        uploaded_at=datetime.now(UTC),
                        created_by=user.id,
                    ),
                    ResearchDatasetFile(
                        id="file-2",
                        dataset_id=dataset.id,
                        version=2,
                        original_filename="good.csv",
                        media_type="text/csv",
                        size_bytes=5,
                        storage_key="good-key",
                        status="quarantined",
                        scan_status="pending",
                        uploaded_at=datetime.now(UTC),
                        created_by=user.id,
                    ),
                ]
            )
            await session.commit()

        class IntermittentScanner:
            def scan_chunks(self, chunks) -> bool:
                content = b"".join(chunks)
                if content == b"bad":
                    raise RuntimeError("scanner unavailable")
                return True

        result = await scan_pending_dataset_files(
            factory,
            FakeStorage({"broken-key": b"bad", "good-key": b"clean"}),
            IntermittentScanner(),
            batch_size=5,
        )
        assert result.failed == 1
        assert result.scanned == 1
        async with factory() as session:
            failed_record = await session.get(ResearchDatasetFile, "file-1")
            clean_record = await session.get(ResearchDatasetFile, "file-2")
            assert failed_record is not None
            assert failed_record.status == "quarantined"
            assert failed_record.scan_status == "pending"
            assert failed_record.sha256_hex is None
            assert clean_record is not None
            assert clean_record.status == "available"
            assert clean_record.scan_status == "clean"
    finally:
        await engine.dispose()
