"""Persistence adapters for the optional identity module."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from stagingnextgenearth.auth import Credentials, IdentifierAlreadyExistsError

from .models import User


class UserCredentialRepository:
    """Adapt persisted users to the authentication credential contract."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_identifier(self, identifier: str) -> Credentials | None:
        """Return authentication credentials for an identifier, if present."""
        result = await self.session.execute(
            select(User.id, User.password_hash).where(User.identifier == identifier)
        )
        row = result.one_or_none()
        if row is None:
            return None
        return Credentials(subject=row.id, password_hash=row.password_hash)

    async def create(self, identifier: str, password_hash: str) -> str:
        """Persist a new user and return its generated subject identifier."""
        user = User(identifier=identifier, password_hash=password_hash)
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            await self.session.rollback()
            raise IdentifierAlreadyExistsError("Identifier is already registered") from exc
        return user.id
