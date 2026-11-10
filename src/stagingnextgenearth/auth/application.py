"""Application facade for the complete password authentication lifecycle."""

from dataclasses import dataclass, field

from .audit import AuditEvent, AuditSink, NullAuditSink
from .login import LoginRequest, LoginService
from .refresh import RefreshResult, RefreshTokenService
from .registration import (
    RegistrationError,
    RegistrationRequest,
    RegistrationResponse,
    RegistrationService,
)
from .service import AuthenticationError
from .tokens import TokenError


@dataclass(frozen=True, slots=True)
class AuthenticationApplication:
    """Compose registration, login, refresh, and logout use cases."""

    registration_service: RegistrationService
    login_service: LoginService
    refresh_token_service: RefreshTokenService
    audit_sink: AuditSink = field(default_factory=NullAuditSink)

    def _audit(self, action: str, outcome: str, subject: str | None = None) -> None:
        """Emit a non-sensitive identity audit event."""
        self.audit_sink.emit(AuditEvent(action=action, outcome=outcome, subject=subject))

    async def register(self, request: RegistrationRequest) -> RegistrationResponse:
        """Register a new password-authenticated identity."""
        try:
            result = await self.registration_service.register(request)
        except RegistrationError:
            self._audit("register", "failure")
            raise
        self._audit("register", "success", result.subject)
        return result

    async def login(self, request: LoginRequest) -> RefreshResult:
        """Authenticate credentials and issue an access/refresh-token pair."""
        try:
            login = await self.login_service.login(request)
            result = await self.refresh_token_service.issue(login.subject, login.access_token)
        except AuthenticationError:
            self._audit("login", "failure")
            raise
        self._audit("login", "success", result.subject)
        return result

    async def refresh(self, refresh_token: str) -> RefreshResult:
        """Rotate a refresh token and issue its replacement pair."""
        try:
            result = await self.refresh_token_service.rotate(refresh_token)
        except TokenError:
            self._audit("refresh", "failure")
            raise
        self._audit("refresh", "success", result.subject)
        return result

    async def logout(self, refresh_token: str) -> bool:
        """Revoke the supplied refresh token."""
        try:
            result = await self.refresh_token_service.revoke(refresh_token)
        except TokenError:
            self._audit("logout", "failure")
            raise
        self._audit("logout", "success")
        return result
