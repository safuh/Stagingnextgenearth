"""Cross-cutting HTTP middleware."""

from collections import OrderedDict
from collections.abc import Awaitable, Callable
from contextlib import suppress
from time import monotonic
from uuid import UUID, uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

_REQUEST_ID_HEADER = "X-Request-ID"
log = structlog.get_logger(__name__)


def _valid_request_id(value: str | None) -> str | None:
    if not value or len(value) > 128:
        return None
    with suppress(ValueError):
        UUID(value)
        return value
    return None


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a bounded request ID to every request and response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = _valid_request_id(request.headers.get(_REQUEST_ID_HEADER)) or str(uuid4())
        request.state.request_id = request_id
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
            response.headers[_REQUEST_ID_HEADER] = request_id
            return response
        except Exception:
            log.exception(
                "request_failed",
                method=request.method,
                path=request.url.path,
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")


class AuthenticationRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply a bounded per-client fixed-window limit to credential endpoints.

    This process-local guard is a first layer, not a distributed rate limiter.
    Production deployments with multiple workers/replicas must also enforce
    equivalent limits at the trusted ingress or API gateway.
    """

    _AUTH_SUFFIXES = frozenset(
        {
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/auth/logout",
        }
    )
    _MAX_TRACKED_CLIENTS = 20_000

    def __init__(
        self,
        app: object,
        *,
        requests: int = 30,
        window_seconds: int = 60,
        api_prefix: str = "/api",
    ) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.requests = requests
        self.window_seconds = window_seconds
        self.auth_paths = frozenset(
            f"{api_prefix.rstrip('/')}{suffix}" for suffix in self._AUTH_SUFFIXES
        )
        self._buckets: OrderedDict[str, tuple[float, int]] = OrderedDict()

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.method != "POST" or request.url.path not in self.auth_paths:
            return await call_next(request)

        client_host = request.client.host if request.client is not None else "unknown"
        key = f"{client_host}:{request.url.path}"
        now = monotonic()
        bucket = self._buckets.get(key)
        if bucket is None or now - bucket[0] >= self.window_seconds:
            count = 1
            started = now
        else:
            started, previous_count = bucket
            count = previous_count + 1

        self._buckets[key] = (started, count)
        self._buckets.move_to_end(key)
        while len(self._buckets) > self._MAX_TRACKED_CLIENTS:
            self._buckets.popitem(last=False)

        remaining = max(0, self.requests - count)
        if count > self.requests:
            retry_after = max(1, int(self.window_seconds - (now - started)))
            response: Response = JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "authentication_rate_limited",
                        "message": "Too many authentication requests. Try again later.",
                    }
                },
                headers={"Retry-After": str(retry_after)},
            )
        else:
            response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response
