from datetime import timedelta
from typing import Any
from unittest.mock import Mock

import pytest

from stagingnextgenearth.auth import (
    AuditEvent,
    AuthenticationApplication,
    AuthenticationError,
    NullAuditSink,
    StructuredAuditSink,
    TokenService,
)


class RecordingAuditSink:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)


class FakeRegistrationService:
    async def register(self, request: Any) -> Any:
        return type("RegistrationResult", (), {"subject": "user-123"})()


class FakeLoginService:
    def __init__(self, result: Any = None, error: Exception | None = None) -> None:
        self.result = result
        self.error = error

    async def login(self, request: Any) -> Any:
        if self.error is not None:
            raise self.error
        return self.result


class FakeRefreshTokenService:
    async def issue(self, subject: str, access_token: str) -> Any:
        return type(
            "RefreshResult",
            (),
            {"subject": subject, "access_token": access_token, "refresh_token": "refresh"},
        )()

    async def rotate(self, refresh_token: str) -> Any:
        return type(
            "RefreshResult",
            (),
            {"subject": "user-123", "access_token": "access", "refresh_token": "replacement"},
        )()

    async def revoke(self, refresh_token: str) -> bool:
        return True


@pytest.mark.asyncio
async def test_successful_identity_operations_emit_structured_events() -> None:
    sink = RecordingAuditSink()
    application = AuthenticationApplication(
        registration_service=FakeRegistrationService(),
        login_service=FakeLoginService(
            result=type("LoginResult", (), {"subject": "user-123", "access_token": "access"})()
        ),
        refresh_token_service=FakeRefreshTokenService(),
        audit_sink=sink,
    )

    await application.register(type("RegistrationRequest", (), {})())
    await application.login(type("LoginRequest", (), {})())
    await application.refresh("refresh")
    await application.logout("refresh")

    assert sink.events == [
        AuditEvent("register", "success", "user-123"),
        AuditEvent("login", "success", "user-123"),
        AuditEvent("refresh", "success", "user-123"),
        AuditEvent("logout", "success"),
    ]


@pytest.mark.asyncio
async def test_authentication_failure_emits_event_without_identifier() -> None:
    sink = RecordingAuditSink()
    application = AuthenticationApplication(
        registration_service=FakeRegistrationService(),
        login_service=FakeLoginService(error=AuthenticationError("Invalid credentials")),
        refresh_token_service=FakeRefreshTokenService(),
        audit_sink=sink,
    )

    with pytest.raises(AuthenticationError):
        await application.login(type("LoginRequest", (), {})())

    assert sink.events == [AuditEvent("login", "failure")]


def test_structured_audit_sink_emits_only_non_sensitive_fields() -> None:
    sink = StructuredAuditSink()
    logger = Mock()
    sink._logger = logger

    sink.emit(AuditEvent("login", "success", "user-123"))

    logger.info.assert_called_once_with(
        "identity_audit",
        audit_action="login",
        audit_outcome="success",
        subject="user-123",
    )
    payload = logger.info.call_args.kwargs
    assert "password" not in payload
    assert "refresh_token" not in payload
    assert "access_token" not in payload


def test_token_service_remains_independent_of_audit_sink() -> None:
    service = TokenService("x" * 32)
    token = service.create("user-123", timedelta(minutes=15))
    assert service.decode(token)["sub"] == "user-123"
    assert isinstance(NullAuditSink(), NullAuditSink)
