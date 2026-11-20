"""Repository checks for the synthetic ODK climate XLSForm and fixtures."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_odk_climate_demo_assets_are_valid() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/validate_odk_climate_demo.py")],
        cwd=ROOT,
        capture_output=True,
        check=True,
        text=True,
    )
    assert "2 synthetic submissions" in result.stdout
