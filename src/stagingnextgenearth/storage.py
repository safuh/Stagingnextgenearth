"""Private object-storage adapters for research dataset files."""

from dataclasses import dataclass
from typing import Protocol

import boto3
from botocore.config import Config


@dataclass(frozen=True, slots=True)
class UploadForm:
    """Presigned browser upload form."""

    url: str
    fields: dict[str, str]


@dataclass(frozen=True, slots=True)
class StoredObject:
    """Object properties verified directly against the storage provider."""

    size_bytes: int
    content_type: str


class ObjectStorage(Protocol):
    """Minimal private-object storage contract."""

    def create_upload_form(
        self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
    ) -> UploadForm: ...

    def inspect(self, *, key: str) -> StoredObject | None: ...


class S3ObjectStorage:
    """S3-compatible private bucket adapter using short-lived presigned POST forms."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        endpoint_url: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            config=Config(signature_version="s3v4"),
        )

    def create_upload_form(
        self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
    ) -> UploadForm:
        """Create a constrained POST; the bucket remains private."""
        result = self._client.generate_presigned_post(
            Bucket=self._bucket,
            Key=key,
            Fields={"Content-Type": content_type},
            Conditions=[
                {"Content-Type": content_type},
                ["content-length-range", 1, max_bytes],
            ],
            ExpiresIn=expires_seconds,
        )
        return UploadForm(url=result["url"], fields=result["fields"])

    def inspect(self, *, key: str) -> StoredObject | None:
        """Read object metadata after upload; missing objects return None."""
        try:
            result = self._client.head_object(Bucket=self._bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            return None
        except Exception as exc:
            if getattr(exc, "response", {}).get("ResponseMetadata", {}).get(
                "HTTPStatusCode"
            ) == 404:
                return None
            raise
        return StoredObject(
            size_bytes=int(result["ContentLength"]),
            content_type=str(result.get("ContentType", "")),
        )
