"""SQLAlchemy persistence for refresh-token rotation state."""

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import DateTime, delete, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from stagingnextgenearth.auth.refresh import RefreshTokenRecord, RefreshTokenStore
from stagingnextgenearth.core.database import Base


class RefreshToken(Base):
    """Persisted refresh-token state used for single-use rotation."""

    __tablename__ = "refresh_tokens"

    token_id: Mapped[str] = mapped_column(primary_key=True)
    subject: Mapped[str] = mapped_column(nullable=False, index=True)
    # Existing schema uses TIMESTAMP WITHOUT TIME ZONE. Values are stored as
    # naive UTC consistently; convert to aware UTC at the application boundary.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), nullable=False, index=True
    )
    revoked: Mapped[bool] = mapped_column(nullable=False, default=False)


class SqlAlchemyRefreshTokenStore(RefreshTokenStore):
    """Persist refresh-token records without owning the transaction."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, record: RefreshTokenRecord) -> None:
        """Persist a newly issued refresh-token record."""
        expires_at = datetime.now(UTC).replace(tzinfo=None) + record.expires_in
        self.session.add(
            RefreshToken(
                token_id=str(record.token_id),
                subject=record.subject,
                expires_at=expires_at,
                revoked=record.revoked,
            )
        )

    async def consume(
        self, token_id: UUID, subject: str
    ) -> RefreshTokenRecord | None:
        """Atomically consume a valid, unexpired token for its subject."""
        now_utc = datetime.now(UTC)
        now_db = now_utc.replace(tzinfo=None)
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.token_id == str(token_id),
                    RefreshToken.subject == subject,
                    RefreshToken.revoked.is_(False),
                    RefreshToken.expires_at > now_db,
                )
                .values(revoked=True)
            ),
        )
        if result.rowcount != 1:
            return None

        record = await self.session.scalar(
            select(RefreshToken).where(RefreshToken.token_id == str(token_id))
        )
        if record is None:
            return None
        expires_at = record.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return RefreshTokenRecord(
            token_id=UUID(record.token_id),
            subject=record.subject,
            expires_in=max(expires_at - now_utc, timedelta(0)),
        )

    async def revoke(self, token_id: UUID) -> bool:
        """Revoke a refresh token without deleting its audit state."""
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.token_id == str(token_id),
                    RefreshToken.revoked.is_(False),
                )
                .values(revoked=True)
            ),
        )
        return result.rowcount == 1

    async def delete(self, token_id: UUID) -> bool:
        """Delete a refresh-token record when retention is no longer required."""
        result = cast(
            CursorResult[Any],
            await self.session.execute(
                delete(RefreshToken).where(RefreshToken.token_id == str(token_id))
            ),
        )
        return result.rowcount == 1
