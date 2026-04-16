#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : bootstrap_release_bundle.py
# VERSION : 2.7.2
# CHANGED : 2026-04-16
# PURPOSE : Place a shipped Elefante installer bundle into a stable install
#           location, then delegate the real install work to scripts/setup/install.py.
# WHEN    : Running a downloadable Elefante installer bundle outside a source checkout.
# USAGE   : python scripts/setup/bootstrap_release_bundle.py [--install-root PATH]
#           [--venv-mode ask|fresh|backup|reuse|abort] [--dry-run]
# NOTES   : Does not duplicate dependency, database, or IDE setup logic. It only
#           copies the payload into a durable path and hands off to install.py.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Bootstrap a shipped Elefante installer bundle into a stable install root."""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


DEFAULT_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE_NAME = "installer-manifest.json"
PAYLOAD_RELATIVE_ROOT = Path("payload") / "elefante"
INSTALL_SCRIPT_RELATIVE_PATH = Path("scripts") / "setup" / "install.py"
INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"
VENV_CHOICES = ["ask", "fresh", "backup", "reuse", "abort"]


def resolve_bundle_root(provided_path: str | None) -> Path:
    if provided_path:
        return Path(provided_path).expanduser().resolve()
    return DEFAULT_BUNDLE_ROOT


def get_default_install_root(
    *,
    os_name: str | None = None,
    env: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    """Return the durable install path for the current platform."""
    env_map = env or os.environ
    system_name = os_name or ("Windows" if os.name == "nt" else os.uname().sysname)
    home_dir = Path(home or Path.home())

    if system_name == "Windows":
        local_app_data = env_map.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Elefante" / "app" / "current"
        return home_dir / "AppData" / "Local" / "Elefante" / "app" / "current"

    return home_dir / ".elefante" / "app" / "current"


def load_manifest(bundle_root: Path) -> dict[str, object]:
    manifest_path = bundle_root / MANIFEST_FILE_NAME
    if not manifest_path.exists():
        return {}

    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def get_payload_root(bundle_root: Path) -> Path:
    return bundle_root / PAYLOAD_RELATIVE_ROOT


def ensure_bundle_layout(bundle_root: Path) -> Path:
    payload_root = get_payload_root(bundle_root)
    required_paths = [
        payload_root,
        payload_root / INSTALL_SCRIPT_RELATIVE_PATH,
        payload_root / "requirements.txt",
        bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py",
    ]

    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Installer bundle is incomplete. Missing required paths: " + ", ".join(missing)
        )

    return payload_root


def build_backup_dir(install_root: Path) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = install_root.parent / f"current.backup.{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = install_root.parent / f"current.backup.{stamp}.{suffix}"
        suffix += 1
    return candidate


def place_payload(payload_root: Path, install_root: Path) -> Path | None:
    """Copy the shipped payload into the durable install root."""
    install_root.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    staging_root = install_root.parent / f".elefante-staging.{stamp}"
    backup_root: Path | None = None

    if staging_root.exists():
        shutil.rmtree(staging_root, ignore_errors=True)

    shutil.copytree(payload_root, staging_root)

    try:
        if install_root.exists():
            backup_root = build_backup_dir(install_root)
            shutil.move(str(install_root), str(backup_root))
        shutil.move(str(staging_root), str(install_root))
    except Exception:
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        if backup_root and backup_root.exists() and not install_root.exists():
            shutil.move(str(backup_root), str(install_root))
            backup_root = None
        raise

    return backup_root


def build_install_command(
    install_root: Path,
    *,
    python_executable: str,
    venv_mode: str,
    verbose: bool = False,
) -> list[str]:
    install_root = Path(install_root)
    cmd = [
        python_executable,
        str(install_root / INSTALL_SCRIPT_RELATIVE_PATH),
        "--log-file",
        str(install_root / INSTALL_LOG_FILE_NAME),
        "--status-file",
        str(install_root / INSTALL_STATUS_FILE_NAME),
        "--summary-file",
        str(install_root / INSTALL_SUMMARY_FILE_NAME),
        "--venv-mode",
        venv_mode,
    ]
    if verbose:
        cmd.append("--verbose")
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Place a shipped Elefante bundle in a stable location and run the installer"
    )
    parser.add_argument("--bundle-root", help="Override the unpacked installer bundle root")
    parser.add_argument("--install-root", help="Override the durable install root")
    parser.add_argument(
        "--venv-mode",
        choices=VENV_CHOICES,
        default="ask",
        help="Pass through the repository .venv handling mode to install.py",
    )
    parser.add_argument(
        "--python-executable",
        default=sys.executable,
        help="Python interpreter used to launch the delegated installer",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate bundle layout and print the delegated install command without executing it",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full subprocess output during installation (passed through to install.py)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = resolve_bundle_root(args.bundle_root)
    payload_root = ensure_bundle_layout(bundle_root)
    manifest = load_manifest(bundle_root)
    install_root = (
        Path(args.install_root).expanduser().resolve()
        if args.install_root
        else get_default_install_root().resolve()
    )

    print("=" * 68)
    print("ELEFANTE INSTALLER BUNDLE")
    print("=" * 68)
    if manifest.get("version"):
        print(f"Version: {manifest['version']}")
    if manifest.get("platform"):
        print(f"Bundle Platform: {manifest['platform']}")
    print(f"Bundle Root: {bundle_root}")
    print(f"Payload Root: {payload_root}")
    print(f"Install Root: {install_root}")

    backup_root = place_payload(payload_root, install_root)
    if backup_root:
        print(f"Previous install moved to: {backup_root}")
    print(f"Payload placed at: {install_root}")

    install_command = build_install_command(
        install_root,
        python_executable=args.python_executable,
        venv_mode=args.venv_mode,
        verbose=args.verbose,
    )

    if args.dry_run:
        print("Dry run only. Delegated installer command:")
        print(" ".join(install_command))
        return

    result = subprocess.run(install_command, cwd=install_root, check=False)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()