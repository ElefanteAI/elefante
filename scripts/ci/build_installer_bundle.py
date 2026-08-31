#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : build_installer_bundle.py
# PURPOSE : Build a downloadable Elefante installer bundle that carries a full
#           payload plus a platform-specific, customer-legible entrypoint.
# WHEN    : In CI after dashboard assets are built, or locally when validating
#           installer bundle contents before release publication.
# USAGE   : python scripts/ci/build_installer_bundle.py --platform macOS
#           [--output dist/elefante-installer-macOS.zip]
# NOTES   : Requires src/dashboard/ui/dist/index.html to exist. It packages a
#           repo-like payload without .git, .venv*, dist/, node_modules, or data artifacts.
# ─────────────────────────────────────────────────────────────────────────────
"""Build a downloadable Elefante installer bundle."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BOOTSTRAP_SCRIPT = Path("scripts/setup/bootstrap_release_bundle.py")
BUILD_IDENTITY_FILE = "elefante-build.json"
REQUIRED_PATHS = [
    Path("README.md"),
    Path("LICENSE"),
    Path("requirements.txt"),
    Path("requirements.lock"),
    Path("config.yaml"),
    Path("src"),
    Path("src/dashboard/ui/dist/index.html"),
    Path("scripts/setup/install.py"),
    Path("scripts/setup/bootstrap_release_bundle.py"),
    Path("scripts/verify/verify_health.py"),
    Path("scripts/verify/verify_mcp_handshake.py"),
    Path("scripts/pipeline/update_dashboard_data.py"),
    Path(".github/copilot-instructions.md"),
]
TOP_LEVEL_EXCLUDED = {".git", "dist", "data", "logs", "tmp", "lib"}
TOP_LEVEL_PREFIX_EXCLUDED = (".venv",)
ANYWHERE_EXCLUDED = {"__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
FILE_NAME_EXCLUDED = {
    ".DS_Store",
    ".elefante-install.log",
    ".elefante-install-status.txt",
    ".elefante-install-summary.txt",
    "install.log",
    BUILD_IDENTITY_FILE,
}
SUFFIX_EXCLUDED = {".pyc", ".pyo"}
PLATFORM_CHOICES = ["Linux", "macOS", "Windows"]


def normalize_platform_name(platform_name: str | None) -> str:
    if not platform_name:
        if os.name == "nt":
            return "Windows"
        system_name = os.uname().sysname
        return "macOS" if system_name == "Darwin" else "Linux"

    if platform_name not in PLATFORM_CHOICES:
        raise ValueError(f"Unsupported platform: {platform_name}")
    return platform_name


def detect_version(root_dir: Path) -> str:
    readme_text = (root_dir / "README.md").read_text(encoding="utf-8")
    match = re.search(r"\*\*v(\d+\.\d+\.\d+)\*\*", readme_text)
    if match:
        return match.group(1)
    return "unknown"


def source_identity(root_dir: Path) -> dict[str, object]:
    """Describe a developer bundle without pretending it is a release."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root_dir,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=all"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unavailable", "clean": False}
    return {"commit": commit, "clean": not dirty}


def validate_bundle_inputs(root_dir: Path) -> None:
    missing = [str(path) for path in REQUIRED_PATHS if not (root_dir / path).exists()]
    if missing:
        raise FileNotFoundError("Installer bundle inputs missing: " + ", ".join(missing))


def should_exclude(rel_path: Path) -> bool:
    if not rel_path.parts:
        return False

    top_level = rel_path.parts[0]

    if top_level in TOP_LEVEL_EXCLUDED:
        return True

    if any(top_level.startswith(prefix) for prefix in TOP_LEVEL_PREFIX_EXCLUDED):
        return True

    if rel_path.parts[:2] == ("a0-data", "demo_db"):
        return True

    if any(part in ANYWHERE_EXCLUDED for part in rel_path.parts):
        return True

    if rel_path.name in FILE_NAME_EXCLUDED:
        return True

    if rel_path.suffix in SUFFIX_EXCLUDED:
        return True

    return False


def iter_payload_files(root_dir: Path):
    for path in root_dir.rglob("*"):
        if path.is_dir():
            continue
        rel_path = path.relative_to(root_dir)
        if should_exclude(rel_path):
            continue
        yield rel_path


def default_output_path(root_dir: Path, platform_name: str) -> Path:
    return root_dir / "dist" / f"elefante-installer-{platform_name}.zip"


def build_manifest(
    *, platform_name: str, version: str, source: dict[str, object]
) -> dict[str, object]:
    entrypoints = {
        "Windows": ["Install Elefante.bat"],
        "macOS": ["Install Elefante.command", "install.sh"],
        "Linux": ["install.sh"],
    }
    return {
        "product": "Elefante",
        "bundle_kind": "installer",
        "release_profile": "developer",
        "release_channel": "development",
        "platform": platform_name,
        "source": source,
        "version": version,
        "payload_root": "payload/elefante",
        "entrypoints": entrypoints[platform_name],
        "default_install_roots": {
            "Windows": r"%LOCALAPPDATA%\\Elefante\\app\\current",
            "macOS": "~/.elefante/app/current",
            "Linux": "~/.elefante/app/current",
        },
    }


def build_unix_wrapper() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"

find_python() {
    for cmd in python3.13 python3.12 python3.11 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            if "$cmd" -c 'import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)' >/dev/null 2>&1; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

PYTHON_CMD="$(find_python || true)"

if [ -z "$PYTHON_CMD" ]; then
  echo \"[ERROR] Python 3.11+ is required to continue.\" >&2
  exit 1
fi

exec \"$PYTHON_CMD\" \"$ROOT_DIR/scripts/setup/bootstrap_release_bundle.py\" --bundle-root \"$ROOT_DIR\" --python-executable \"$PYTHON_CMD\" \"$@\"
"""


def build_windows_wrapper() -> str:
    wrapper = r"""@echo off
setlocal EnableDelayedExpansion

set "PYTHON_CMD="
for %%P in (python3.13 python3.12 python3.11 python3 python) do (
        where %%P >nul 2>nul
        if !ERRORLEVEL! EQU 0 (
                %%P -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)" >nul 2>nul
                if !ERRORLEVEL! EQU 0 (
                        set "PYTHON_CMD=%%P"
                        goto :run_bundle
                )
        )
)

if not defined PYTHON_CMD (
    echo [ERROR] Python 3.11+ is required to continue.
    pause
    exit /b 1
)

:run_bundle
%PYTHON_CMD% "%~dp0scripts\setup\bootstrap_release_bundle.py" --bundle-root "%~dp0" --python-executable "%PYTHON_CMD%" %*
set EXIT_CODE=%ERRORLEVEL%
pause
exit /b %EXIT_CODE%
"""
    return wrapper.replace("\n", "\r\n")


def build_macos_launcher() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /bin/bash "$ROOT_DIR/install.sh" "$@"
"""


def build_start_here(*, platform_name: str) -> str:
    instructions = {
        "macOS": (
            "1. Double-click \"Install Elefante.command\".\n"
            "2. Keep the Terminal window open while Elefante installs.\n"
            "3. Restart your supported agent host when the installer reports SUCCESS.\n\n"
            "If macOS asks for confirmation, Control-click \"Install Elefante.command\", "
            "choose Open, then choose Open again.\n"
            "Administrator access and Terminal commands are not required.\n"
        ),
        "Windows": (
            "1. Double-click \"Install Elefante.bat\".\n"
            "2. Keep the installer window open while Elefante installs.\n"
            "3. Restart your supported agent host when the installer reports SUCCESS.\n"
        ),
        "Linux": (
            "1. Open a terminal in this folder.\n"
            "2. Run: chmod +x install.sh && ./install.sh\n"
            "3. Restart your supported agent host when the installer reports SUCCESS.\n"
        ),
    }
    return (
        f"ELEFANTE {platform_name.upper()} INSTALLER\n"
        f"{'=' * (20 + len(platform_name))}\n\n"
        f"{instructions[platform_name]}\n"
        "Requires Python 3.11, 3.12, or 3.13 and an internet connection.\n"
        "Elefante installs into your user account; administrator access is not required.\n"
    )


def write_text_entry(
    archive: zipfile.ZipFile,
    arcname: str,
    content: str,
    *,
    executable: bool = False,
) -> None:
    info = zipfile.ZipInfo(arcname)
    info.create_system = 3
    info.create_version = 30
    info.compress_type = zipfile.ZIP_DEFLATED
    now = datetime.now(timezone.utc)
    info.date_time = (now.year, now.month, now.day, now.hour, now.minute, now.second)
    mode = 0o755 if executable else 0o644
    # Finder/Archive Utility requires the Unix regular-file type as well as
    # permission bits. Permission-only metadata survives command-line unzip but
    # can be discarded by the macOS customer extraction path.
    info.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(info, content)


def build_installer_bundle(root_dir: Path, *, platform_name: str, output_path: Path) -> Path:
    validate_bundle_inputs(root_dir)
    version = detect_version(root_dir)
    source = source_identity(root_dir)
    bundle_dir = f"elefante-installer-{platform_name}"
    manifest = build_manifest(platform_name=platform_name, version=version, source=source)
    build_identity = {
        "schema_version": 1,
        "version": version,
        "source_commit": source["commit"],
        "source_clean": source["clean"],
        "release_channel": "development",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_text_entry(
            archive,
            f"{bundle_dir}/installer-manifest.json",
            json.dumps(manifest, indent=2) + "\n",
        )
        write_text_entry(
            archive,
            f"{bundle_dir}/START HERE.txt",
            build_start_here(platform_name=platform_name),
        )
        if platform_name == "Windows":
            write_text_entry(
                archive,
                f"{bundle_dir}/Install Elefante.bat",
                build_windows_wrapper(),
            )
        else:
            write_text_entry(
                archive,
                f"{bundle_dir}/install.sh",
                build_unix_wrapper(),
                executable=True,
            )
            if platform_name == "macOS":
                write_text_entry(
                    archive,
                    f"{bundle_dir}/Install Elefante.command",
                    build_macos_launcher(),
                    executable=True,
                )

        bootstrap_bytes = (root_dir / BOOTSTRAP_SCRIPT).read_bytes()
        archive.writestr(f"{bundle_dir}/{BOOTSTRAP_SCRIPT.as_posix()}", bootstrap_bytes)

        write_text_entry(
            archive,
            f"{bundle_dir}/payload/elefante/{BUILD_IDENTITY_FILE}",
            json.dumps(build_identity, indent=2) + "\n",
        )

        for rel_path in iter_payload_files(root_dir):
            source_path = root_dir / rel_path
            try:
                archive.write(source_path, f"{bundle_dir}/payload/elefante/{rel_path.as_posix()}")
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "Installer bundle build hit a broken symlink or missing local workspace artifact "
                    f"while packaging {rel_path}. Exclude local environment backups like .venv.*. "
                    "Read workspace/postmortems/installation.md Issue #14 for resolution."
                ) from exc

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a downloadable Elefante installer bundle")
    parser.add_argument("--platform", choices=PLATFORM_CHOICES, help="Bundle platform label")
    parser.add_argument("--output", help="Output zip path")
    parser.add_argument("--root-dir", help="Override the Elefante repo root to package")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = Path(args.root_dir).expanduser().resolve() if args.root_dir else ROOT_DIR
    platform_name = normalize_platform_name(args.platform)
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(root_dir, platform_name)
    )

    bundle_path = build_installer_bundle(
        root_dir,
        platform_name=platform_name,
        output_path=output_path,
    )
    print(f"Wrote installer bundle: {bundle_path}")


if __name__ == "__main__":
    main()
