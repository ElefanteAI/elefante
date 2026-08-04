#!/usr/bin/env python3
"""Build the macOS Elefante Release Client Candidate 1.0 archive.

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
import zipfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
CLIENT_CANDIDATE = "1.0"
PLATFORM = "macOS"
BUNDLE_DIRECTORY = "elefante-release-client-candidate-1.0-macOS"
PAYLOAD_ROOT = Path("payload") / "elefante"
BOOTSTRAP_SCRIPT = Path("scripts/setup/bootstrap_release_bundle.py")
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


def build_manifest(root_dir: Path) -> dict[str, object]:
    return {
        "product": "Elefante Release Client Candidate",
        "candidate": CLIENT_CANDIDATE,
        "bundle_kind": "client-runtime-installer",
        "release_profile": "client",
        "platform": PLATFORM,
        "version": source_version(root_dir),
        "payload_root": PAYLOAD_ROOT.as_posix(),
        "entrypoints": ["Install Elefante.command", "install.sh"],
        "default_install_root": "~/.elefante/app/current",
        "first_install": {
            "network_required": True,
            "downloads_local_embedding_model": True,
            "administrator_access_required": False,
        },
        "customer_contract": {
            "includes_development_tools": False,
            "includes_developer_workspace": False,
            "publication_status": "candidate-not-for-public-download",
        },
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


def build_start_here() -> str:
    return """ELEFANTE RELEASE CLIENT CANDIDATE 1.0 — macOS
===================================================

1. Double-click "Install Elefante.command".
2. Keep the Terminal window open until it reports INSTALLATION COMPLETE.
3. Restart the selected AI host.

Requirements: Python 3.11, 3.12, or 3.13 and an internet connection.
The first installation downloads Elefante's local embedding model. Elefante
installs in your user account; administrator access is not required.

If macOS blocks the launcher, open Terminal in this folder and run:
chmod +x "Install Elefante.command" install.sh && ./"Install Elefante.command"

This candidate is for validation. It contains the runtime only: no test suite,
developer workspace, migration utilities, or development tooling.
"""


def write_text_entry(
    archive: zipfile.ZipFile,
    arcname: str,
    content: str,
    *,
    executable: bool = False,
) -> None:
    info = zipfile.ZipInfo(arcname)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = (0o755 if executable else 0o644) << 16
    archive.writestr(info, content)


def default_output_path(root_dir: Path) -> Path:
    return root_dir / "dist" / f"{BUNDLE_DIRECTORY}.zip"


def build_release_client(root_dir: Path, *, output_path: Path) -> Path:
    validate_client_inputs(root_dir)
    payload_paths = client_payload_paths(root_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        write_text_entry(
            archive,
            f"{BUNDLE_DIRECTORY}/installer-manifest.json",
            json.dumps(build_manifest(root_dir), indent=2) + "\n",
        )
        write_text_entry(
            archive,
            f"{BUNDLE_DIRECTORY}/START HERE.txt",
            build_start_here(),
        )
        write_text_entry(
            archive,
            f"{BUNDLE_DIRECTORY}/install.sh",
            build_unix_wrapper(),
            executable=True,
        )
        write_text_entry(
            archive,
            f"{BUNDLE_DIRECTORY}/Install Elefante.command",
            build_macos_launcher(),
            executable=True,
        )
        archive.write(
            root_dir / BOOTSTRAP_SCRIPT,
            f"{BUNDLE_DIRECTORY}/{BOOTSTRAP_SCRIPT.as_posix()}",
        )
        for relative_path in payload_paths:
            archive.write(
                root_dir / relative_path,
                f"{BUNDLE_DIRECTORY}/{PAYLOAD_ROOT.as_posix()}/{relative_path.as_posix()}",
            )

    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Elefante Release Client Candidate 1.0 macOS archive"
    )
    parser.add_argument("--platform", default=PLATFORM, choices=[PLATFORM])
    parser.add_argument("--output", help="Output ZIP path")
    parser.add_argument("--root-dir", help="Override the Elefante repository root")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root_dir = Path(args.root_dir).expanduser().resolve() if args.root_dir else ROOT_DIR
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else default_output_path(root_dir)
    )
    bundle_path = build_release_client(root_dir, output_path=output_path)
    print(f"Wrote release client candidate: {bundle_path}")


if __name__ == "__main__":
    main()
