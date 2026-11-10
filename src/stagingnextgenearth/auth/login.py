"""Application-level login use case."""

from dataclasses import dataclass

from .service import AuthenticationError, AuthenticationService


@dataclass(frozen=True, slots=True)
class LoginRequest:
    """Credentials supplied to the application login flow."""

    identifier: str
    password: str


@dataclass(frozen=True, slots=True)
class LoginResponse:
    """Transport-neutral result returned by a successful login."""

    subject: str
    access_token: str
    password_needs_rehash: bool


class LoginService:
    """Execute the password login use case without owning persistence."""

    def __init__(self, authentication_service: AuthenticationService) -> None:
        self.authentication_service = authentication_service

    async def login(self, request: LoginRequest) -> LoginResponse:
        """Authenticate a login request and return its application result."""
        if not request.identifier or not request.password:
            raise AuthenticationError("Invalid credentials")

        result = await self.authentication_service.authenticate(
            request.identifier,
            request.password,
        )
        return LoginResponse(
            subject=result.subject,
            access_token=result.access_token,
            password_needs_rehash=result.password_needs_rehash,
        )
