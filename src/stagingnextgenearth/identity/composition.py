"""Database-backed authentication composition helpers."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.auth import (
    AuthenticationApplication,
    AuthenticationService,
    LoginService,
    PasswordHasher,
    RefreshTokenService,
    RegistrationService,
    StructuredAuditSink,
    TokenService,
)

from .refresh_tokens import SqlAlchemyRefreshTokenStore
from .repository import UserCredentialRepository


def create_sqlalchemy_auth_application(
    session: AsyncSession,
    *,
    secret_key: str,
    access_token_lifetime: timedelta,
    refresh_token_lifetime: timedelta,
    password_hasher: PasswordHasher | None = None,
) -> AuthenticationApplication:
    """Compose the standard authentication application over SQLAlchemy persistence.

    Token secrets and lifetimes remain explicit inputs so the backbone never
    invents security-sensitive production configuration.
    """
    hasher = password_hasher or PasswordHasher()
    token_service = TokenService(secret_key)
    user_repository = UserCredentialRepository(session)
    refresh_store = SqlAlchemyRefreshTokenStore(session)

    authentication_service = AuthenticationService(
        credential_store=user_repository,
        password_hasher=hasher,
        token_service=token_service,
        access_token_lifetime=access_token_lifetime,
    )
    registration_service = RegistrationService(
        user_store=user_repository,
        password_hasher=hasher,
    )
    login_service = LoginService(authentication_service)
    refresh_token_service = RefreshTokenService(
        token_service=token_service,
        refresh_token_store=refresh_store,
        access_token_lifetime=access_token_lifetime,
        refresh_token_lifetime=refresh_token_lifetime,
    )

    return AuthenticationApplication(
        registration_service=registration_service,
        login_service=login_service,
        refresh_token_service=refresh_token_service,
        audit_sink=StructuredAuditSink(),
    )
