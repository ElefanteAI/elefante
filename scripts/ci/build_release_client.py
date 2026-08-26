#!/usr/bin/env python3
"""Build a runtime-only Elefante customer installer archive.

This builder is deliberately separate from the historical installer-bundle
builder. Its allowlist is the customer contract: source, runtime scripts,
prebuilt dashboard assets, and the client dependency lock. Development plans,
tests, migration utilities, repository instructions, and build tools cannot
enter this archive.
"""

from __future__ import annotations

import argparse
import json
import re
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CLIENT_CANDIDATE_LANE = "Release Client Candidate 1.0"
PLATFORM_CHOICES = ("Linux", "macOS", "Windows")
PUBLICATION_STATUSES = ("candidate", "release")
FALLBACK_ARCHIVE_TIMESTAMP = (2026, 8, 5, 12, 0, 0)
PAYLOAD_ROOT = Path("payload") / "elefante"
BOOTSTRAP_SCRIPT = Path("scripts/setup/bootstrap_release_bundle.py")
BUILD_IDENTITY_FILE = "elefante-build.json"
CLIENT_RUNTIME_FILES = (
    Path("LICENSE"),
    Path("config.yaml"),
    Path("requirements.client.txt"),
    Path("requirements.client.lock"),
)
CLIENT_RUNTIME_SCRIPTS = (
    Path("scripts/setup/install.py"),
    Path("scripts/setup/init_databases.py"),
    Path("scripts/setup/configure_vscode_bob.py"),
    Path("scripts/setup/configure_antigravity.py"),
    Path("scripts/setup/configure_cursor_kiro.py"),
    Path("scripts/setup/configure_cli_agents.py"),
    Path("scripts/setup/host_selection.py"),
    Path("scripts/setup/install_manifest.py"),
    Path("scripts/lifecycle/backup_elefante_data.py"),
    Path("scripts/lifecycle/daemon_service.py"),
    Path("scripts/lifecycle/doctor.py"),
    Path("scripts/lifecycle/restart_elefante.py"),
    Path("scripts/lifecycle/restore_elefante_data.py"),
    Path("scripts/lifecycle/uninstall_elefante.py"),
    Path("scripts/pipeline/export_memories.py"),
    Path("scripts/pipeline/update_dashboard_data.py"),
    Path("scripts/verify/verify_health.py"),
    Path("scripts/verify/verify_mcp_handshake.py"),
)
DEV_DEPENDENCIES = ("black", "mypy", "pytest", "pytest-asyncio", "ruff")


def source_version(root_dir: Path) -> str:
    init_file = root_dir / "src" / "__init__.py"
    match = re.search(
        r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$',
        init_file.read_text(encoding="utf-8"),
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError(f"Could not read a semantic version from {init_file}")
    return match.group(1)


def client_payload_paths(root_dir: Path) -> list[Path]:
    """Return the complete, intentionally small set of customer payload files."""
    payload_paths = list(CLIENT_RUNTIME_FILES) + list(CLIENT_RUNTIME_SCRIPTS)
    payload_paths.extend(
        sorted(path.relative_to(root_dir) for path in (root_dir / "src").rglob("*.py"))
    )

    dashboard_dist = root_dir / "src" / "dashboard" / "ui" / "dist"
    payload_paths.extend(
        sorted(
            path.relative_to(root_dir)
            for path in dashboard_dist.rglob("*")
            if path.is_file()
        )
    )
    return sorted(set(payload_paths))


def validate_client_inputs(root_dir: Path) -> None:
    required_paths = [
        *CLIENT_RUNTIME_FILES,
        *CLIENT_RUNTIME_SCRIPTS,
        BOOTSTRAP_SCRIPT,
        Path("src/__init__.py"),
        Path("src/dashboard/ui/dist/index.html"),
    ]
    missing = [str(path) for path in required_paths if not (root_dir / path).is_file()]
    if missing:
        raise FileNotFoundError(
            "Release Client Candidate inputs missing: " + ", ".join(missing)
        )

    lock_contents = (root_dir / "requirements.client.lock").read_text(encoding="utf-8")
    leaked_dependencies = [
        dependency
        for dependency in DEV_DEPENDENCIES
        if re.search(rf"^{re.escape(dependency)}==", lock_contents, flags=re.MULTILINE)
    ]
    if leaked_dependencies:
        raise ValueError(
            "Client runtime lock contains development dependencies: "
            + ", ".join(leaked_dependencies)
        )


def source_identity(root_dir: Path) -> dict[str, object]:
    """Return auditable source identity without making local dirty builds impossible."""
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
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, subprocess.CalledProcessError):
        return {"commit": "unavailable", "clean": False}
    return {"commit": commit, "clean": not dirty}


def source_timestamp(root_dir: Path) -> tuple[int, int, int, int, int, int]:
    """Use the source commit time for truthful, reproducible Finder dates."""
    try:
        epoch = int(
            subprocess.run(
                ["git", "show", "-s", "--format=%ct", "HEAD"],
                cwd=root_dir,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
        )
    except (OSError, ValueError, subprocess.CalledProcessError):
        return FALLBACK_ARCHIVE_TIMESTAMP
    timestamp = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return (
        timestamp.year,
        timestamp.month,
        timestamp.day,
        timestamp.hour,
        timestamp.minute,
        timestamp.second - (timestamp.second % 2),
    )


def bundle_directory(platform_name: str) -> str:
    if platform_name not in PLATFORM_CHOICES:
        raise ValueError(f"Unsupported client platform: {platform_name}")
    return f"elefante-installer-{platform_name}"


def build_manifest(
    root_dir: Path, *, platform_name: str, publication_status: str
) -> dict[str, object]:
    if publication_status not in PUBLICATION_STATUSES:
        raise ValueError(f"Unsupported publication status: {publication_status}")
    entrypoints = {
        "Linux": ["install.sh"],
        "macOS": ["Install Elefante.command", "install.sh"],
        "Windows": ["Install Elefante.bat"],
    }
    default_install_roots = {
        "Linux": "~/.elefante/app/current",
        "macOS": "~/.elefante/app/current",
        "Windows": r"%LOCALAPPDATA%\Elefante\app\current",
    }
    manifest: dict[str, object] = {
        "product": "Elefante",
        "version": source_version(root_dir),
        "bundle_kind": "client-runtime-installer",
        "release_profile": "client",
        "publication_status": publication_status,
        "platform": platform_name,
        "source": source_identity(root_dir),
        "payload_root": PAYLOAD_ROOT.as_posix(),
        "entrypoints": entrypoints[platform_name],
        "default_install_root": default_install_roots[platform_name],
        "first_install": {
            "network_required": True,
            "downloads_local_embedding_model": True,
            "administrator_access_required": False,
        },
        "customer_contract": {
            "includes_development_tools": False,
            "includes_developer_workspace": False,
            "publication_status": publication_status,
        },
    }
    if publication_status == "candidate":
        manifest["candidate"] = f"v{manifest['version']}-rc.1"
        manifest["candidate_lane"] = CLIENT_CANDIDATE_LANE
    return manifest


def build_identity(manifest: dict[str, object]) -> dict[str, object]:
    """Bind the installed payload to the exact archive source identity."""
    source = manifest["source"]
    if not isinstance(source, dict):
        raise ValueError("Client manifest source identity is invalid")
    return {
        "schema_version": 1,
        "version": manifest["version"],
        "source_commit": source["commit"],
        "source_clean": source["clean"],
        "release_channel": manifest["publication_status"],
    }


def build_unix_wrapper() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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
  echo "[ERROR] Python 3.11, 3.12, or 3.13 is required." >&2
  exit 1
fi

exec "$PYTHON_CMD" "$ROOT_DIR/scripts/setup/bootstrap_release_bundle.py" --bundle-root "$ROOT_DIR" --python-executable "$PYTHON_CMD" "$@"
"""


def build_macos_launcher() -> str:
    return """#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec /bin/bash "$ROOT_DIR/install.sh" "$@"
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
    echo [ERROR] Python 3.11, 3.12, or 3.13 is required.
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


def build_start_here(
    *, platform_name: str, publication_status: str, product_version: str
) -> str:
    instructions = {
        "macOS": (
            '1. Double-click "Install Elefante.command".\n'
            "2. Keep the Terminal window open until installation completes.\n"
            "3. Restart your detected AI hosts.\n\n"
            "If macOS cannot verify the developer, Control-click the installer,\n"
            "choose Open, then choose Open again. The package is not yet notarized.\n"
        ),
        "Windows": (
            '1. Double-click "Install Elefante.bat".\n'
            "2. Keep the installer window open until installation completes.\n"
            "3. Restart your detected AI hosts.\n"
        ),
        "Linux": (
            "1. Open a terminal in this folder.\n"
            "2. Run: chmod +x install.sh && ./install.sh\n"
            "3. Restart your detected AI hosts.\n"
        ),
    }
    status_line = (
        "This is a validation candidate and is not a public release.\n"
        if publication_status == "candidate"
        else "This is the released customer runtime.\n"
    )
    return (
        f"ELEFANTE v{product_version} — {platform_name}\n"
        f"{'=' * (18 + len(platform_name))}\n\n"
        f"{instructions[platform_name]}\n"
        "Requirements: Python 3.11, 3.12, or 3.13 and an internet connection.\n"
        "The first installation downloads Elefante's local embedding model. Elefante\n"
        "installs in your user account; administrator access is not required.\n\n"
        f"{status_line}"
        "The package contains only the customer runtime: no tests, development plans,\n"
        "migration utilities, or internal build tools.\n"
    )


def write_text_entry(
    archive: zipfile.ZipFile,
    arcname: str,
    content: str,
    *,
    timestamp: tuple[int, int, int, int, int, int],
    executable: bool = False,
) -> None:
    info = zipfile.ZipInfo(arcname)
    info.date_time = timestamp
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    mode = 0o755 if executable else 0o644
    info.external_attr = (stat.S_IFREG | mode) << 16
    archive.writestr(info, content)


def write_file_entry(
    archive: zipfile.ZipFile,
    arcname: str,
    source: Path,
    *,
    timestamp: tuple[int, int, int, int, int, int],
) -> None:
    info = zipfile.ZipInfo(arcname)
    info.date_time = timestamp
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (stat.S_IFREG | 0o644) << 16
    archive.writestr(info, source.read_bytes())


def default_output_path(root_dir: Path, platform_name: str) -> Path:
    return root_dir / "dist" / f"{bundle_directory(platform_name)}.zip"


def build_release_client(
    root_dir: Path,
    *,
    platform_name: str,
    publication_status: str,
    output_path: Path,
) -> Path:
    validate_client_inputs(root_dir)
    payload_paths = client_payload_paths(root_dir)
    bundle_dir = bundle_directory(platform_name)
    timestamp = source_timestamp(root_dir)
    manifest = build_manifest(
        root_dir,
        platform_name=platform_name,
        publication_status=publication_status,
    )
    identity = build_identity(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_text_entry(
            archive,
            f"{bundle_dir}/installer-manifest.json",
            json.dumps(manifest, indent=2) + "\n",
            timestamp=timestamp,
        )
        write_text_entry(
            archive,
            f"{bundle_dir}/START HERE.txt",
            build_start_here(
                platform_name=platform_name,
                publication_status=publication_status,
                product_version=source_version(root_dir),
            ),
            timestamp=timestamp,
        )
        if platform_name == "Windows":
            write_text_entry(
                archive,
                f"{bundle_dir}/Install Elefante.bat",
                build_windows_wrapper(),
                timestamp=timestamp,
            )
        else:
            write_text_entry(
                archive,
                f"{bundle_dir}/install.sh",
                build_unix_wrapper(),
                timestamp=timestamp,
                executable=True,
            )
            if platform_name == "macOS":
                write_text_entry(
                    archive,
                    f"{bundle_dir}/Install Elefante.command",
                    build_macos_launcher(),
                    timestamp=timestamp,
                    executable=True,
                )
        write_file_entry(
            archive,
            f"{bundle_dir}/{BOOTSTRAP_SCRIPT.as_posix()}",
            root_dir / BOOTSTRAP_SCRIPT,
            timestamp=timestamp,
        )
        write_text_entry(
            archive,
            f"{bundle_dir}/{PAYLOAD_ROOT.as_posix()}/{BUILD_IDENTITY_FILE}",
            json.dumps(identity, indent=2) + "\n",
            timestamp=timestamp,
        )
        for relative_path in payload_paths:
            write_file_entry(
                archive,
                f"{bundle_dir}/{PAYLOAD_ROOT.as_posix()}/{relative_path.as_posix()}",
                root_dir / relative_path,
                timestamp=timestamp,
            )

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a runtime-only Elefante customer installer archive"
    )
    parser.add_argument("--platform", default="macOS", choices=PLATFORM_CHOICES)
    parser.add_argument(
        "--publication-status",
        default="candidate",
        choices=PUBLICATION_STATUSES,
    )
    parser.add_argument("--output", help="Output ZIP path")
    parser.add_argument("--root-dir", help="Override the Elefante repository root")
    parser.add_argument(
        "--print-version",
        action="store_true",
        help="Print the package version without importing product dependencies",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = Path(args.root_dir).expanduser().resolve() if args.root_dir else ROOT_DIR
    if args.print_version:
        print(source_version(root_dir))
        return
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(root_dir, args.platform)
    )
    bundle_path = build_release_client(
        root_dir,
        platform_name=args.platform,
        publication_status=args.publication_status,
        output_path=output_path,
    )
    print(f"Wrote {args.publication_status} client installer: {bundle_path}")


if __name__ == "__main__":
    main()
