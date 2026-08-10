"""Black-box acceptance for dependency-free installer startup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_installer_help_starts_without_installed_product_dependencies() -> None:
    result = subprocess.run(
        [sys.executable, "-S", str(ROOT / "scripts" / "setup" / "install.py"), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "usage:" in result.stdout.casefold()
    assert "ModuleNotFoundError" not in result.stderr
