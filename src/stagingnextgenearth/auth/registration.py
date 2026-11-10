"""Application-level user registration use case."""

from dataclasses import dataclass
from typing import Protocol

from .passwords import PasswordHasher


class RegistrationError(ValueError):
    """Raised when a registration request cannot create an identity."""


class IdentifierAlreadyExistsError(RegistrationError):
    """Raised when the requested identifier is already registered."""


class UserRegistrationStore(Protocol):
    """Persistence boundary for creating password-authenticated identities."""

    async def create(self, identifier: str, password_hash: str) -> str:
        """Persist a new identity and return its subject identifier."""


@dataclass(frozen=True, slots=True)
class RegistrationRequest:
    """Transport-neutral registration input."""

    identifier: str
    password: str


@dataclass(frozen=True, slots=True)
class RegistrationResponse:
    """Transport-neutral registration result."""

    subject: str


class RegistrationService:
    """Validate registration input, hash the password, and persist the identity."""

    def __init__(
        self,
        user_store: UserRegistrationStore,
        password_hasher: PasswordHasher,
    ) -> None:
        self.user_store = user_store
        self.password_hasher = password_hasher

    async def register(self, request: RegistrationRequest) -> RegistrationResponse:
        """Create a new identity without ever persisting the plaintext password."""
        if not request.identifier or not request.password:
            raise RegistrationError("Identifier and password are required")

        subject = await self.user_store.create(
            request.identifier,
            self.password_hasher.hash(request.password),
        )
        return RegistrationResponse(subject=subject)
