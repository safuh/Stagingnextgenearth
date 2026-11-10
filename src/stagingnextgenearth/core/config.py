"""Typed, environment-driven application configuration."""

from enum import StrEnum
from functools import lru_cache

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(StrEnum):
    DEVELOPMENT = "development"
    TEST = "test"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """Runtime configuration with explicit development/test/production profiles.

    Environment variables are the final override layer. The ``environment`` field
    selects the profile defaults, while explicit values always win.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        case_sensitive=False,
        extra="ignore",
        validate_default=True,
    )

    app_name: str = Field(default="Stagingnextgenearth", min_length=1)
    app_version: str = "0.1.0"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    api_prefix: str = "/api"
    database_url: str = "sqlite+aiosqlite:///./backbone.db"
    database_echo: bool = False
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    database_pool_pre_ping: bool = True
    jwt_secret_key: SecretStr | None = Field(default=None, min_length=32)
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=14, ge=1, le=90)
    log_level: str = "INFO"
    log_json: bool = False
    object_storage_enabled: bool = False
    object_storage_bucket: str | None = None
    object_storage_region: str = "af-south-1"
    object_storage_endpoint_url: str | None = None
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    cors_allow_credentials: bool = False
    cors_allow_methods: list[str] = Field(
        default_factory=lambda: [
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS",
        ]
    )
    cors_allow_headers: list[str] = Field(
        default_factory=lambda: ["Authorization", "Content-Type", "X-Request-ID"]
    )

    @model_validator(mode="after")
    def validate_profile(self) -> "Settings":
        if self.environment is Environment.PRODUCTION:
            if self.debug:
                raise ValueError("debug must be false in production")
            if not self.database_url.startswith("postgresql+asyncpg://"):
                raise ValueError("production requires a PostgreSQL asyncpg DATABASE_URL")
            self.log_json = True
            if self.jwt_secret_key is None or len(self.jwt_secret_key.get_secret_value()) < 32:
                raise ValueError("production requires JWT_SECRET_KEY with at least 32 characters")
        if self.object_storage_enabled and not self.object_storage_bucket:
            raise ValueError("OBJECT_STORAGE_BUCKET is required when object storage is enabled")
        if self.environment is Environment.TEST:
            self.debug = False
        return self

    @classmethod
    def for_profile(cls, profile: Environment | str) -> "Settings":
        """Build deterministic settings for tests, local development, or production."""
        environment = Environment(profile)
        if environment is Environment.TEST:
            return cls(
                environment=environment,
                database_url="sqlite+aiosqlite:///:memory:",
                log_json=False,
            )
        if environment is Environment.PRODUCTION:
            return cls(
                environment=environment,
                database_url="postgresql+asyncpg://backbone:backbone@localhost:5432/backbone",
                log_json=True,
            )
        return cls(environment=environment)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object."""
    return Settings()
