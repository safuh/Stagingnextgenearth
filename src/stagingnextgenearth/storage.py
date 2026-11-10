"""Private S3-compatible object storage with dependency-free SigV4 signing."""

import base64
import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Iterator
from typing import Protocol
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen


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

    def iter_object_chunks(
        self, *, key: str, max_bytes: int, chunk_size: int = 64 * 1024
    ) -> Iterator[bytes]: ...

    def get_object(self, *, key: str, max_bytes: int) -> bytes: ...

    def create_download_url(self, *, key: str, expires_seconds: int) -> str: ...


class S3ObjectStorage:
    """S3-compatible private bucket adapter using AWS Signature Version 4."""

    def __init__(
        self,
        *,
        bucket: str,
        region: str,
        access_key_id: str,
        secret_access_key: str,
        endpoint_url: str | None = None,
    ) -> None:
        if not access_key_id or not secret_access_key:
            raise ValueError("S3-compatible storage requires explicit access credentials")
        self._bucket = bucket
        self._region = region
        self._access_key = access_key_id
        self._secret_key = secret_access_key
        self._endpoint = (endpoint_url or f"https://s3.{region}.amazonaws.com").rstrip("/")

    @staticmethod
    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    def _signing_key(self, date_stamp: str) -> bytes:
        date_key = self._sign(("AWS4" + self._secret_key).encode("utf-8"), date_stamp)
        region_key = self._sign(date_key, self._region)
        service_key = self._sign(region_key, "s3")
        return self._sign(service_key, "aws4_request")

    def create_upload_form(
        self, *, key: str, content_type: str, max_bytes: int, expires_seconds: int
    ) -> UploadForm:
        """Create a short-lived POST policy with content-type and size constraints."""
        now = datetime.now(UTC)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        credential = (
            f"{self._access_key}/{date_stamp}/{self._region}/s3/aws4_request"
        )
        policy = {
            "expiration": datetime.fromtimestamp(
                now.timestamp() + expires_seconds, UTC
            ).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "conditions": [
                {"bucket": self._bucket},
                {"key": key},
                {"Content-Type": content_type},
                {"x-amz-algorithm": "AWS4-HMAC-SHA256"},
                {"x-amz-credential": credential},
                {"x-amz-date": amz_date},
                ["content-length-range", 1, max_bytes],
            ],
        }
        encoded_policy = base64.b64encode(
            json.dumps(policy, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        signature = hmac.new(
            self._signing_key(date_stamp),
            encoded_policy.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        fields = {
            "key": key,
            "Content-Type": content_type,
            "x-amz-algorithm": "AWS4-HMAC-SHA256",
            "x-amz-credential": credential,
            "x-amz-date": amz_date,
            "policy": encoded_policy,
            "x-amz-signature": signature,
        }
        endpoint = urlsplit(self._endpoint)
        if endpoint.netloc.endswith("amazonaws.com") and endpoint.netloc.startswith("s3."):
            upload_url = f"https://{self._bucket}.{endpoint.netloc}/"
        else:
            upload_path = (
                f"{endpoint.path.rstrip('/')}/{quote(self._bucket, safe='')}"
            )
            upload_url = f"{endpoint.scheme}://{endpoint.netloc}{upload_path}"
        return UploadForm(url=upload_url, fields=fields)

    def inspect(self, *, key: str) -> StoredObject | None:
        """Issue a signed HEAD request and return provider-reported object metadata."""
        now = datetime.now(UTC)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        endpoint = urlsplit(self._endpoint)
        if endpoint.netloc.endswith("amazonaws.com") and endpoint.netloc.startswith("s3."):
            host = f"{self._bucket}.{endpoint.netloc}"
            path = f"/{quote(key, safe='/')}"
            url = f"https://{host}{path}"
        else:
            host = endpoint.netloc
            path = (
                f"{endpoint.path.rstrip('/')}/{quote(self._bucket, safe='')}/"
                f"{quote(key, safe='/')}"
            )
            url = f"{self._endpoint}/{quote(self._bucket, safe='')}/{quote(key, safe='/')}"
        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            ["HEAD", path, "", canonical_headers, signed_headers, payload_hash]
        )
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self._access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = Request(
            url,
            method="HEAD",
            headers={
                "Host": host,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
                "Authorization": authorization,
            },
        )
        try:
            with urlopen(request, timeout=10) as response:
                return StoredObject(
                    size_bytes=int(response.headers["Content-Length"]),
                    content_type=response.headers.get("Content-Type", ""),
                )
        except HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    def iter_object_chunks(
        self, *, key: str, max_bytes: int, chunk_size: int = 64 * 1024
    ) -> Iterator[bytes]:
        """Stream a private object in bounded chunks without buffering the object."""
        if max_bytes < 1 or chunk_size < 1:
            raise ValueError("max_bytes and chunk_size must be positive")
        now = datetime.now(UTC)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        endpoint = urlsplit(self._endpoint)
        encoded_key = quote(key, safe="/")
        if endpoint.netloc.endswith("amazonaws.com") and endpoint.netloc.startswith("s3."):
            host = f"{self._bucket}.{endpoint.netloc}"
            path = f"/{encoded_key}"
            url = f"https://{host}{path}"
        else:
            host = endpoint.netloc
            path = (
                f"{endpoint.path.rstrip('/')}/{quote(self._bucket, safe='')}/"
                f"{encoded_key}"
            )
            url = f"{self._endpoint}/{quote(self._bucket, safe='')}/{encoded_key}"
        payload_hash = hashlib.sha256(b"").hexdigest()
        canonical_headers = (
            f"host:{host}\n"
            f"x-amz-content-sha256:{payload_hash}\n"
            f"x-amz-date:{amz_date}\n"
        )
        signed_headers = "host;x-amz-content-sha256;x-amz-date"
        canonical_request = "\n".join(
            ["GET", path, "", canonical_headers, signed_headers, payload_hash]
        )
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        authorization = (
            "AWS4-HMAC-SHA256 "
            f"Credential={self._access_key}/{scope}, "
            f"SignedHeaders={signed_headers}, Signature={signature}"
        )
        request = Request(
            url,
            method="GET",
            headers={
                "Host": host,
                "x-amz-content-sha256": payload_hash,
                "x-amz-date": amz_date,
                "Authorization": authorization,
            },
        )
        total = 0
        with urlopen(request, timeout=30) as response:
            while chunk := response.read(chunk_size):
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("Stored object exceeds the permitted scan size")
                yield chunk

    def get_object(self, *, key: str, max_bytes: int) -> bytes:
        """Fetch an object with a hard limit; prefer iter_object_chunks for scanning."""
        return b"".join(self.iter_object_chunks(key=key, max_bytes=max_bytes))

    def create_download_url(self, *, key: str, expires_seconds: int) -> str:
        """Create a short-lived SigV4 presigned GET URL for a private object."""
        if not 1 <= expires_seconds <= 900:
            raise ValueError("Download URL expiry must be between 1 and 900 seconds")
        now = datetime.now(UTC)
        date_stamp = now.strftime("%Y%m%d")
        amz_date = now.strftime("%Y%m%dT%H%M%SZ")
        scope = f"{date_stamp}/{self._region}/s3/aws4_request"
        credential = f"{self._access_key}/{scope}"
        endpoint = urlsplit(self._endpoint)
        encoded_key = quote(key, safe="/")
        if endpoint.netloc.endswith("amazonaws.com") and endpoint.netloc.startswith("s3."):
            host = f"{self._bucket}.{endpoint.netloc}"
            path = f"/{encoded_key}"
            base_url = f"https://{host}{path}"
        else:
            host = endpoint.netloc
            path = (
                f"{endpoint.path.rstrip('/')}/{quote(self._bucket, safe='')}/"
                f"{encoded_key}"
            )
            base_url = f"{self._endpoint}/{quote(self._bucket, safe='')}/{encoded_key}"
        query_parameters = {
            "X-Amz-Algorithm": "AWS4-HMAC-SHA256",
            "X-Amz-Credential": credential,
            "X-Amz-Date": amz_date,
            "X-Amz-Expires": str(expires_seconds),
            "X-Amz-SignedHeaders": "host",
        }
        canonical_query = "&".join(
            f"{quote(name, safe='')}={quote(value, safe='~-._')}"
            for name, value in sorted(query_parameters.items())
        )
        canonical_request = "\n".join(
            [
                "GET",
                path,
                canonical_query,
                f"host:{host}\n",
                "host",
                "UNSIGNED-PAYLOAD",
            ]
        )
        string_to_sign = "\n".join(
            [
                "AWS4-HMAC-SHA256",
                amz_date,
                scope,
                hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
            ]
        )
        signature = hmac.new(
            self._signing_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return f"{base_url}?{canonical_query}&X-Amz-Signature={signature}"
