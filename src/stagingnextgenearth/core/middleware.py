"""Cross-cutting HTTP middleware."""

from collections.abc import Awaitable, Callable
from contextlib import suppress
from uuid import UUID, uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

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
