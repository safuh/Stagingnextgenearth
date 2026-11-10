"""Application factory and composition root."""

from collections.abc import Callable
from datetime import timedelta
from typing import cast

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from .api.router import api_router
from .auth.application import AuthenticationApplication
from .core.config import Settings, get_settings
from .core.errors import (
    BackboneError,
    backbone_error_handler,
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from .core.lifespan import lifespan
from .core.logging import configure_logging
from .core.middleware import RequestContextMiddleware
from .identity import create_sqlalchemy_auth_application

AuthApplicationFactory = Callable[[AsyncSession], AuthenticationApplication]


def create_app(
    settings: Settings | None = None,
    auth_application_factory: AuthApplicationFactory | None = None,
) -> FastAPI:
    """Create a configured FastAPI application with optional auth composition.

    A database-backed authentication application is composed automatically when
    a valid JWT secret is configured. A custom factory may override that default.
    """
    resolved = settings or get_settings()
    configure_logging(resolved)

    app = FastAPI(
        title=resolved.app_name,
        version=resolved.app_version,
        debug=resolved.debug,
        lifespan=lifespan,
    )
    app.state.settings = resolved
    if auth_application_factory is None and resolved.jwt_secret_key is not None:
        secret = resolved.jwt_secret_key.get_secret_value()

        def configured_auth_factory(session: AsyncSession) -> AuthenticationApplication:
            return create_sqlalchemy_auth_application(
                session,
                secret_key=secret,
                access_token_lifetime=timedelta(minutes=resolved.access_token_minutes),
                refresh_token_lifetime=timedelta(days=resolved.refresh_token_days),
            )

        auth_application_factory = configured_auth_factory
    app.state.auth_application_factory = auth_application_factory

    app.add_middleware(RequestContextMiddleware)
    if resolved.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved.cors_origins,
            allow_credentials=resolved.cors_allow_credentials,
            allow_methods=resolved.cors_allow_methods,
            allow_headers=resolved.cors_allow_headers,
        )

    app.add_exception_handler(
        BackboneError,
        cast(ExceptionHandler, backbone_error_handler),
    )
    app.add_exception_handler(
        RequestValidationError,
        cast(ExceptionHandler, validation_error_handler),
    )
    app.add_exception_handler(
        StarletteHTTPException,
        cast(ExceptionHandler, http_error_handler),
    )
    app.add_exception_handler(Exception, unhandled_error_handler)

    app.include_router(api_router, prefix=resolved.api_prefix)
    return app
