"""JWT token service.

This module deliberately handles cryptographic token mechanics only. User
persistence, refresh-token rotation/revocation, roles, and permissions belong
to the consuming application's identity module and will be layered on top.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from jwt import InvalidTokenError


class TokenError(ValueError):
    """Raised when a token cannot be created or validated."""


class TokenService:
    """Create and validate signed JWT access/refresh tokens."""

    def __init__(self, secret_key: str, algorithm: str = "HS256") -> None:
        if len(secret_key) < 32:
            raise ValueError("JWT secret_key must contain at least 32 characters")
        self.secret_key = secret_key
        self.algorithm = algorithm

    def create(
        self,
        subject: str,
        expires_in: timedelta,
        *,
        token_type: str = "access",
        claims: dict[str, Any] | None = None,
    ) -> str:
        if not subject:
            raise ValueError("JWT subject is required")
        if expires_in <= timedelta(0):
            raise ValueError("JWT expires_in must be positive")
        if not token_type:
            raise ValueError("JWT token_type is required")

        now = datetime.now(UTC)
        payload: dict[str, Any] = dict(claims or {})
        # These claims define the token's security semantics and cannot be
        # overridden by application-provided custom claims.
        payload.update(
            {
                "sub": subject,
                "iat": now,
                "exp": now + expires_in,
                "type": token_type,
            }
        )
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode(self, token: str, *, expected_type: str | None = None) -> dict[str, Any]:
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
        except InvalidTokenError as exc:
            raise TokenError("Invalid or expired token") from exc

        if not payload.get("sub"):
            raise TokenError("Token subject is required")
        if expected_type is not None and payload.get("type") != expected_type:
            raise TokenError("Unexpected token type")
        return payload
