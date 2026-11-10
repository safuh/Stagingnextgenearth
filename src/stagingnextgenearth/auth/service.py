"""Application-level authentication service.

The service composes password verification with access-token issuance while
remaining independent of user persistence. Consuming identity modules provide
credentials through the ``CredentialStore`` protocol.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from .passwords import PasswordHasher
from .tokens import TokenService


@dataclass(frozen=True, slots=True)
class Credentials:
    """Persisted credential data required for password authentication."""

    subject: str
    password_hash: str


class CredentialStore(Protocol):
    """Persistence boundary used by the authentication service."""

    async def get_by_identifier(self, identifier: str) -> Credentials | None:
        """Return credentials for an application-defined login identifier."""


@dataclass(frozen=True, slots=True)
class AuthenticationResult:
    """Successful password-authentication result."""

    subject: str
    access_token: str
    password_needs_rehash: bool


class AuthenticationError(ValueError):
    """Raised when supplied credentials cannot authenticate an identity."""


class AuthenticationService:
    """Authenticate credentials and issue a signed access token."""

    def __init__(
        self,
        credential_store: CredentialStore,
        password_hasher: PasswordHasher,
        token_service: TokenService,
        access_token_lifetime: timedelta,
    ) -> None:
        if access_token_lifetime <= timedelta(0):
            raise ValueError("access_token_lifetime must be positive")
        self.credential_store = credential_store
        self.password_hasher = password_hasher
        self.token_service = token_service
        self.access_token_lifetime = access_token_lifetime

    async def authenticate(
        self,
        identifier: str,
        password: str,
    ) -> AuthenticationResult:
        """Verify credentials and issue an access token on success."""
        if not identifier:
            raise AuthenticationError("Invalid credentials")

        credentials = await self.credential_store.get_by_identifier(identifier)
        if credentials is None or not self.password_hasher.verify(
            password, credentials.password_hash
        ):
            raise AuthenticationError("Invalid credentials")

        return AuthenticationResult(
            subject=credentials.subject,
            access_token=self.token_service.create(
                credentials.subject,
                self.access_token_lifetime,
                token_type="access",
            ),
            password_needs_rehash=self.password_hasher.needs_rehash(credentials.password_hash),
        )
