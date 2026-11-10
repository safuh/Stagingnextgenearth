"""Application-level exception taxonomy and HTTP error handling."""

from dataclasses import dataclass
from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


@dataclass(slots=True)
class BackboneError(Exception):
    """A safe, structured error intended for the HTTP boundary."""

    code: str
    message: str
    status_code: int = 400
    details: Any | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)


def _payload(
    request: Request,
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        },
        "request_id": getattr(request.state, "request_id", None),
    }
    if details is not None:
        body["error"]["details"] = details
    return body


async def backbone_error_handler(request: Request, exc: BackboneError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, exc.code, exc.message, exc.details),
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=_payload(
            request,
            "validation_error",
            "Request validation failed",
            exc.errors(),
        ),
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code = "http_error"
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP request failed"
    if exc.status_code == 404:
        code = "not_found"
    elif exc.status_code == 405:
        code = "method_not_allowed"
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(request, code, detail),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a stable public error without leaking implementation details."""
    return JSONResponse(
        status_code=500,
        content=_payload(request, "internal_error", "An unexpected error occurred"),
    )
