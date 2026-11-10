"""Authentication primitives and extension points."""

from .application import AuthenticationApplication
from .audit import AuditEvent, AuditSink, NullAuditSink, StructuredAuditSink
from .login import LoginRequest, LoginResponse, LoginService
from .passwords import PasswordHasher
from .refresh import RefreshResult, RefreshTokenRecord, RefreshTokenService, RefreshTokenStore
from .registration import (
    IdentifierAlreadyExistsError,
    RegistrationError,
    RegistrationRequest,
    RegistrationResponse,
    RegistrationService,
    UserRegistrationStore,
)
from .service import (
    AuthenticationError,
    AuthenticationResult,
    AuthenticationService,
    Credentials,
    CredentialStore,
)
from .tokens import TokenError, TokenService

__all__ = [
    "AuditEvent",
    "AuditSink",
    "AuthenticationApplication",
    "AuthenticationError",
    "AuthenticationResult",
    "AuthenticationService",
    "CredentialStore",
    "Credentials",
    "IdentifierAlreadyExistsError",
    "LoginRequest",
    "LoginResponse",
    "LoginService",
    "NullAuditSink",
    "PasswordHasher",
    "RefreshResult",
    "RefreshTokenRecord",
    "RefreshTokenService",
    "RefreshTokenStore",
    "RegistrationError",
    "RegistrationRequest",
    "RegistrationResponse",
    "RegistrationService",
    "StructuredAuditSink",
    "TokenError",
    "TokenService",
    "UserRegistrationStore",
]
