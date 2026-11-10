"""Password hashing primitives.

The backbone provides a small, algorithm-backed password hashing abstraction.
Application identity modules should store only the resulting encoded hash and
must never persist or log plaintext passwords.
"""

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError


class PasswordHasher:
    """Hash and verify passwords using pwdlib's Argon2-backed defaults."""

    def __init__(self) -> None:
        self._hasher = PasswordHash.recommended()

    def hash(self, password: str) -> str:
        """Return a salted password hash suitable for persistence."""
        return self._hasher.hash(password)

    def verify(self, password: str, password_hash: str) -> bool:
        """Return whether ``password`` matches the encoded hash."""
        try:
            return self._hasher.verify(password, password_hash)
        except UnknownHashError:
            return False

    def needs_rehash(self, password_hash: str) -> bool:
        """Return whether a stored hash should be upgraded on successful login."""
        return self._hasher.current_hasher.check_needs_rehash(password_hash)
