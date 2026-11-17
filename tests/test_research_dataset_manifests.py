"""Contract tests for deterministic research dataset manifests."""

from stagingnextgenearth.api.research_dataset_manifests import (
    DatasetManifestFile,
    ResearchDatasetManifestRead,
    _manifest_digest,
    router,
)


def test_manifest_route_is_read_only_and_dataset_scoped() -> None:
    route = next(
        item for item in router.routes
        if getattr(item, "path", "").endswith("/{dataset_id}/manifest")
    )
    assert route.methods == {"GET"}
    assert route.response_model == ResearchDatasetManifestRead


def test_manifest_contract_contains_integrity_metadata_not_storage_locations() -> None:
    item = DatasetManifestFile(
        file_id="file-1",
        version=3,
        filename="rainfall.csv",
        media_type="text/csv",
        size_bytes=2048,
        sha256="a" * 64,
    )
    manifest = ResearchDatasetManifestRead(
        dataset_id="dataset-1",
        dataset_version="2.0",
        manifest_sha256="b" * 64,
        file_count=1,
        files=[item],
    )
    payload = manifest.model_dump()
    assert payload["files"][0]["sha256"] == "a" * 64
    assert "storage_key" not in payload
    assert "file_contents" not in payload


def test_manifest_digest_is_order_independent_and_version_sensitive() -> None:
    first = DatasetManifestFile(
        file_id="file-a", version=1, filename="a.csv", media_type="text/csv",
        size_bytes=100, sha256="a" * 64,
    )
    second = DatasetManifestFile(
        file_id="file-b", version=2, filename="b.csv", media_type="text/csv",
        size_bytes=200, sha256="b" * 64,
    )
    digest = _manifest_digest("dataset-1", "1.0", [first, second])
    assert digest == _manifest_digest("dataset-1", "1.0", [second, first])
    assert digest != _manifest_digest("dataset-1", "2.0", [first, second])
    assert digest != _manifest_digest("dataset-2", "1.0", [first, second])
