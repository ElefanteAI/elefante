"""Black-box acceptance for the installer dry-run mutation boundary."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_installer_dry_run_does_not_create_install_destination(tmp_path: Path) -> None:
    bundle_root = tmp_path / "downloaded-installer"
    payload_root = bundle_root / "payload" / "elefante"
    (payload_root / "scripts" / "setup").mkdir(parents=True)
    (bundle_root / "scripts" / "setup").mkdir(parents=True)
    (payload_root / "scripts" / "setup" / "install.py").write_text(
        "raise SystemExit('dry-run must not execute this file')\n",
        encoding="utf-8",
    )
    (payload_root / "requirements.txt").write_text("", encoding="utf-8")
    (payload_root / "requirements.lock").write_text("", encoding="utf-8")
    (bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py").write_text(
        "fixture marker\n",
        encoding="utf-8",
    )

    install_root = tmp_path / "new-global-install" / "current"
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "setup" / "bootstrap_release_bundle.py"),
            "--bundle-root",
            str(bundle_root),
            "--install-root",
            str(install_root),
            "--python-executable",
            sys.executable,
            "--dry-run",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert not install_root.exists(), "dry-run created the requested install destination"
    assert not install_root.parent.exists(), "dry-run mutated the destination parent"
