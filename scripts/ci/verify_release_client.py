#!/usr/bin/env python3
"""Reject an Elefante Release Client Candidate archive that leaks developer material."""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

BUNDLE_DIRECTORY = "elefante-release-client-candidate-1.0-macOS"
PAYLOAD_PREFIX = f"{BUNDLE_DIRECTORY}/payload/elefante/"
ROOT_FILES = {
    "installer-manifest.json",
    "START HERE.txt",
    "install.sh",
    "Install Elefante.command",
    "scripts/setup/bootstrap_release_bundle.py",
}
RUNTIME_FILES = {
    "LICENSE",
    "config.yaml",
    "requirements.client.txt",
    "requirements.client.lock",
}
RUNTIME_SCRIPTS = {
    "scripts/setup/install.py",
    "scripts/setup/init_databases.py",
    "scripts/setup/configure_vscode_bob.py",
    "scripts/setup/configure_antigravity.py",
    "scripts/setup/configure_cursor_kiro.py",
    "scripts/setup/configure_cli_agents.py",
    "scripts/setup/host_selection.py",
    "scripts/setup/install_manifest.py",
    "scripts/lifecycle/backup_elefante_data.py",
    "scripts/lifecycle/daemon_service.py",
    "scripts/lifecycle/doctor.py",
    "scripts/lifecycle/restart_elefante.py",
    "scripts/lifecycle/restore_elefante_data.py",
    "scripts/lifecycle/uninstall_elefante.py",
    "scripts/pipeline/export_memories.py",
    "scripts/pipeline/update_dashboard_data.py",
    "scripts/verify/verify_health.py",
    "scripts/verify/verify_mcp_handshake.py",
}
DEV_DEPENDENCIES = ("black", "mypy", "pytest", "pytest-asyncio", "ruff")
FORBIDDEN_PARTS = {
    ".github",
    "agents",
    "docs",
    "examples",
    "tests",
    "workspace",
}
FORBIDDEN_SCRIPT_AREAS = {"ci", "debug", "demo", "privileged"}


def _is_safe_archive_name(name: str) -> bool:
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts and "" not in path.parts


def _payload_path_is_allowed(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    if relative_path in RUNTIME_FILES or relative_path in RUNTIME_SCRIPTS:
        return True
    if len(path.parts) >= 2 and path.parts[0] == "src" and path.suffix == ".py":
        return True
    return len(path.parts) >= 5 and path.parts[:4] == (
        "src",
        "dashboard",
        "ui",
        "dist",
    )


def validate_release_client_archive(archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        names = [name for name in archive.namelist() if not name.endswith("/")]
        if not names:
            raise ValueError("Release Client Candidate archive is empty")
        if any(not _is_safe_archive_name(name) for name in names):
            raise ValueError(
                "Release Client Candidate archive contains an unsafe archive path"
            )

        roots = {PurePosixPath(name).parts[0] for name in names}
        if roots != {BUNDLE_DIRECTORY}:
            raise ValueError(
                f"Expected one archive root {BUNDLE_DIRECTORY!r}; found {sorted(roots)!r}"
            )

        relative_names = {name.removeprefix(f"{BUNDLE_DIRECTORY}/") for name in names}
        missing_root_files = ROOT_FILES - relative_names
        if missing_root_files:
            raise ValueError(
                "Missing client bundle files: " + ", ".join(sorted(missing_root_files))
            )

        for relative_name in relative_names:
            parts = PurePosixPath(relative_name).parts
            if any(part in FORBIDDEN_PARTS for part in parts):
                raise ValueError(
                    f"Developer material leaked into client archive: {relative_name}"
                )
            if (
                len(parts) >= 2
                and parts[0] == "scripts"
                and parts[1] in FORBIDDEN_SCRIPT_AREAS
            ):
                raise ValueError(
                    f"Developer script leaked into client archive: {relative_name}"
                )
            if relative_name.startswith(
                PAYLOAD_PREFIX.removeprefix(f"{BUNDLE_DIRECTORY}/")
            ):
                payload_relative = relative_name.removeprefix("payload/elefante/")
                if not _payload_path_is_allowed(payload_relative):
                    raise ValueError(
                        f"Unexpected client payload file: {payload_relative}"
                    )
            elif relative_name not in ROOT_FILES:
                raise ValueError(f"Unexpected client bundle file: {relative_name}")

        required_payload_files = {
            *RUNTIME_FILES,
            *RUNTIME_SCRIPTS,
            "src/__init__.py",
            "src/dashboard/ui/dist/index.html",
        }
        missing_payload = {
            path
            for path in required_payload_files
            if f"payload/elefante/{path}" not in relative_names
        }
        if missing_payload:
            raise ValueError(
                "Missing client payload files: " + ", ".join(sorted(missing_payload))
            )

        manifest = json.loads(
            archive.read(f"{BUNDLE_DIRECTORY}/installer-manifest.json").decode("utf-8")
        )
        required_manifest = {
            "product": "Elefante Release Client Candidate",
            "candidate": "1.0",
            "bundle_kind": "client-runtime-installer",
            "release_profile": "client",
            "platform": "macOS",
            "payload_root": "payload/elefante",
        }
        invalid_manifest = {
            key: value
            for key, value in required_manifest.items()
            if manifest.get(key) != value
        }
        if invalid_manifest:
            raise ValueError(f"Invalid client bundle manifest: {invalid_manifest!r}")
        if not re.fullmatch(r"\d+\.\d+\.\d+", str(manifest.get("version", ""))):
            raise ValueError(
                "Client bundle manifest does not contain a semantic product version"
            )

        lock_contents = archive.read(
            f"{PAYLOAD_PREFIX}requirements.client.lock"
        ).decode("utf-8")
        leaked_dependencies = [
            dependency
            for dependency in DEV_DEPENDENCIES
            if re.search(
                rf"^{re.escape(dependency)}==", lock_contents, flags=re.MULTILINE
            )
        ]
        if leaked_dependencies:
            raise ValueError(
                "Client dependency lock includes development dependencies: "
                + ", ".join(leaked_dependencies)
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify a clean Elefante Release Client Candidate archive"
    )
    parser.add_argument(
        "--archive", required=True, help="Client candidate ZIP to validate"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = Path(args.archive).expanduser().resolve()
    validate_release_client_archive(archive_path)
    print(f"Verified clean release client candidate: {archive_path}")


if __name__ == "__main__":
    main()
