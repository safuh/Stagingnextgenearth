"""Optional database-backed identity persistence."""

from .composition import create_sqlalchemy_auth_application
from .models import ExternalIdentity, IdentityActionToken, ResearcherProfile, User
from .refresh_tokens import RefreshToken, SqlAlchemyRefreshTokenStore
from .repository import UserCredentialRepository

__all__ = [
    "ExternalIdentity",
    "IdentityActionToken",
    "ResearcherProfile",
    "RefreshToken",
    "SqlAlchemyRefreshTokenStore",
    "User",
    "UserCredentialRepository",
    "create_sqlalchemy_auth_application",
]
