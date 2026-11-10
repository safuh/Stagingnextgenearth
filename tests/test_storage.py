"""Unit tests for S3-compatible upload policy signing."""

import base64
import json
from urllib.parse import parse_qs, urlsplit

from stagingnextgenearth.storage import S3ObjectStorage


def test_upload_form_policy_restricts_key_type_and_maximum_size() -> None:
    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        endpoint_url="https://objects.example.test",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    form = storage.create_upload_form(
        key="dataset-files/org/dataset/file",
        content_type="text/csv",
        max_bytes=4096,
        expires_seconds=600,
    )

    policy = json.loads(base64.b64decode(form.fields["policy"]))
    conditions = policy["conditions"]
    assert form.url == "https://objects.example.test/research-private"
    assert form.fields["key"] == "dataset-files/org/dataset/file"
    assert form.fields["Content-Type"] == "text/csv"
    assert form.fields["x-amz-algorithm"] == "AWS4-HMAC-SHA256"
    assert len(form.fields["x-amz-signature"]) == 64
    assert {"bucket": "research-private"} in conditions
    assert {"key": "dataset-files/org/dataset/file"} in conditions
    assert {"Content-Type": "text/csv"} in conditions
    assert ["content-length-range", 1, 4096] in conditions


def test_upload_form_uses_bucket_virtual_host_for_aws_s3() -> None:
    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    form = storage.create_upload_form(
        key="dataset-files/file-id",
        content_type="application/pdf",
        max_bytes=1024,
        expires_seconds=300,
    )

    assert form.url == "https://research-private.s3.af-south-1.amazonaws.com/"



def test_upload_form_preserves_custom_endpoint_base_path() -> None:
    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        endpoint_url="https://objects.example.test/s3-gateway",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    form = storage.create_upload_form(
        key="dataset-files/file-id",
        content_type="application/pdf",
        max_bytes=1024,
        expires_seconds=300,
    )

    assert form.url == "https://objects.example.test/s3-gateway/research-private"


def test_download_url_is_short_lived_and_signed_for_private_object() -> None:
    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        endpoint_url="https://objects.example.test/s3-gateway",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    url = storage.create_download_url(
        key="dataset-files/org/dataset/file.pdf",
        expires_seconds=300,
    )
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "objects.example.test"
    assert parsed.path == "/s3-gateway/research-private/dataset-files/org/dataset/file.pdf"
    assert query["X-Amz-Algorithm"] == ["AWS4-HMAC-SHA256"]
    assert query["X-Amz-Expires"] == ["300"]
    assert query["X-Amz-SignedHeaders"] == ["host"]
    assert len(query["X-Amz-Signature"][0]) == 64


def test_download_url_rejects_expiry_over_fifteen_minutes() -> None:
    import pytest

    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    with pytest.raises(ValueError, match="expiry"):
        storage.create_download_url(key="dataset-files/file", expires_seconds=901)


def test_streaming_object_read_uses_bounded_chunks_and_enforces_limit(monkeypatch) -> None:
    import pytest

    class FakeResponse:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.offset = 0
            self.read_sizes: list[int] = []

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return None

        def read(self, size: int) -> bytes:
            self.read_sizes.append(size)
            chunk = self.content[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

    response = FakeResponse(b"abcdefgh")
    monkeypatch.setattr("stagingnextgenearth.storage.urlopen", lambda request, timeout: response)
    storage = S3ObjectStorage(
        bucket="research-private",
        region="af-south-1",
        endpoint_url="https://objects.example.test",
        access_key_id="test-access-key",
        secret_access_key="test-secret-key",
    )

    assert list(
        storage.iter_object_chunks(
            key="dataset-files/file", max_bytes=8, chunk_size=3
        )
    ) == [b"abc", b"def", b"gh"]
    assert response.read_sizes == [3, 3, 3, 3]

    oversized = FakeResponse(b"abcdef")
    monkeypatch.setattr("stagingnextgenearth.storage.urlopen", lambda request, timeout: oversized)
    with pytest.raises(ValueError, match="permitted scan size"):
        list(
            storage.iter_object_chunks(
                key="dataset-files/file", max_bytes=5, chunk_size=3
            )
        )
