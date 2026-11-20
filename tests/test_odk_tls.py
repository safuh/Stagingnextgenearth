"""ODK Central TLS policy must keep insecure mode local-only."""

import pytest

from stagingnextgenearth.core.config import Environment, Settings
from stagingnextgenearth.core.odk_tls import odk_tls_verify


def test_self_signed_tls_is_allowed_for_local_central_only() -> None:
    settings = Settings(environment=Environment.DEVELOPMENT, odk_tls_verify=False)

    assert odk_tls_verify("https://local:8443", settings) is False
    assert odk_tls_verify("https://central.localhost:8443", settings) is False


def test_insecure_tls_is_rejected_for_non_local_central_host() -> None:
    settings = Settings(environment=Environment.DEVELOPMENT, odk_tls_verify=False)

    with pytest.raises(ValueError, match="local Central host"):
        odk_tls_verify("https://central.example.org", settings)


def test_production_cannot_disable_odk_tls_verification() -> None:
    with pytest.raises(ValueError, match="ODK_TLS_VERIFY must remain true"):
        Settings(
            environment=Environment.PRODUCTION,
            database_url="postgresql+asyncpg://app:secret@localhost:5432/app",
            public_base_url="https://nextgenforearth.org",
            jwt_secret_key="x" * 48,
            odk_tls_verify=False,
        )
