"""Unit tests for S3-compatible upload policy signing."""

import base64
import json

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
