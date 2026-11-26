"""Regression tests for the production deployment environment preflight."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-production-env.py"


def _valid_environment_file(tmp_path: Path) -> Path:
    source = (ROOT / ".env.production.example").read_text(encoding="utf-8")
    source = source.replace("replace-db-password", "test-db-password-9f31")
    source = source.replace(
        "replace-with-a-unique-random-secret-of-at-least-32-characters",
        "0123456789abcdef0123456789abcdef0123456789abcdef",
    )
    source = source.replace(
        "replace-with-generated-fernet-key", Fernet.generate_key().decode("ascii")
    )
    path = tmp_path / ".env.production"
    path.write_text(source + "\nCOMPOSE_PROFILES=odk\n", encoding="utf-8")
    return path


def _run_validator(path: Path) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment.pop("COMPOSE_PROFILES", None)
    return subprocess.run(
        [sys.executable, str(VALIDATOR), str(path)],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_environment_accepts_valid_odk_profile(tmp_path: Path) -> None:
    result = _run_validator(_valid_environment_file(tmp_path))

    assert result.returncode == 0, result.stderr
    assert "validation passed" in result.stdout


def test_production_environment_rejects_missing_odk_key(tmp_path: Path) -> None:
    path = _valid_environment_file(tmp_path)
    content = path.read_text(encoding="utf-8")
    content = "\n".join(
        line for line in content.splitlines() if not line.startswith("ODK_ENCRYPTION_KEY=")
    )
    path.write_text(content, encoding="utf-8")

    result = _run_validator(path)

    assert result.returncode == 2
    assert "ODK_ENCRYPTION_KEY is required" in result.stderr
    assert "secret" not in result.stderr.casefold()


def test_production_environment_rejects_placeholder_database_secret(tmp_path: Path) -> None:
    path = _valid_environment_file(tmp_path)
    content = path.read_text(encoding="utf-8").replace(
        "test-db-password-9f31", "replace-db-password"
    )
    path.write_text(content, encoding="utf-8")

    result = _run_validator(path)

    assert result.returncode == 2
    assert "DATABASE_URL still contains a placeholder" in result.stderr
    assert "replace-db-password" not in result.stderr


def test_production_environment_rejects_invalid_fernet_key(tmp_path: Path) -> None:
    path = _valid_environment_file(tmp_path)
    content = path.read_text(encoding="utf-8").replace(
        next(
            line.split("=", 1)[1]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.startswith("ODK_ENCRYPTION_KEY=")
        ),
        "not-a-fernet-key",
    )
    path.write_text(content, encoding="utf-8")

    result = _run_validator(path)

    assert result.returncode == 2
    assert "ODK_ENCRYPTION_KEY is not a valid Fernet key" in result.stderr


def test_production_environment_rejects_missing_file(tmp_path: Path) -> None:
    result = _run_validator(tmp_path / "missing.env")

    assert result.returncode == 2
    assert "Environment file does not exist" in result.stderr
