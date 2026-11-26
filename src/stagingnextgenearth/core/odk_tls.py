"""TLS verification policy for ODK Central connections."""

from urllib.parse import urlsplit

from stagingnextgenearth.core.config import Environment, Settings, get_settings

_LOCAL_ODK_HOSTS = {"localhost", "127.0.0.1", "::1", "local"}


def odk_tls_verify(base_url: str, settings: Settings | None = None) -> bool:
    """Allow self-signed TLS only for explicit local-development Central hosts."""
    config = settings or get_settings()
    if config.odk_tls_verify:
        return True
    if config.environment is Environment.PRODUCTION:
        raise ValueError("ODK TLS verification cannot be disabled in production")
    hostname = (urlsplit(base_url).hostname or "").lower()
    if hostname not in _LOCAL_ODK_HOSTS and not hostname.endswith(".localhost"):
        raise ValueError("ODK TLS verification may only be disabled for a local Central host")
    return False
