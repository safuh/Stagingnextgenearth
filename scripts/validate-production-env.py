"""Validate production deployment settings without disclosing secret values."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet
from pydantic import ValidationError

from stagingnextgenearth.core.config import Settings


def main() -> int:
    env_file = Path(sys.argv[1] if len(sys.argv) > 1 else ".env")
    if not env_file.is_file():
        print(f"Environment file does not exist: {env_file}", file=sys.stderr)
        return 2

    try:
        settings = Settings(_env_file=env_file, environment="production")
    except ValidationError as exc:
        for error in exc.errors(include_input=False):
            location = ".".join(str(part) for part in error["loc"])
            print(f"Invalid production setting {location}: {error['msg']}", file=sys.stderr)
        return 2

    database_password = (urlsplit(settings.database_url).password or "").casefold()
    jwt_secret = settings.jwt_secret_key.get_secret_value() if settings.jwt_secret_key else ""
    placeholders = ("replace", "change-me", "changeme", "example", "your-")
    if any(marker in database_password for marker in placeholders):
        print("DATABASE_URL still contains a placeholder value.", file=sys.stderr)
        return 2
    if any(marker in jwt_secret.casefold() for marker in placeholders):
        print("JWT_SECRET_KEY still contains a placeholder value.", file=sys.stderr)
        return 2

    profile_value = os.environ.get("COMPOSE_PROFILES", "")
    if not profile_value:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("COMPOSE_PROFILES="):
                profile_value = line.split("=", 1)[1].strip().strip("\"'")
                break
    profiles = {item.strip().casefold() for item in profile_value.split(",") if item.strip()}
    if "odk" in profiles:
        if settings.odk_encryption_key is None:
            print(
                "ODK_ENCRYPTION_KEY is required when the odk profile is enabled.",
                file=sys.stderr,
            )
            return 2
        key = settings.odk_encryption_key.get_secret_value()
        if any(marker in key.casefold() for marker in placeholders):
            print("ODK_ENCRYPTION_KEY still contains a placeholder value.", file=sys.stderr)
            return 2
        try:
            Fernet(key.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            print("ODK_ENCRYPTION_KEY is not a valid Fernet key.", file=sys.stderr)
            return 2

    print("Production environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
