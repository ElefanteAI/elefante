#!/usr/bin/env python3
"""Reject customer installers that leak developer material or break their platform contract."""

from __future__ import annotations

import argparse
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

CLIENT_CANDIDATE_LANE = "Release Client Candidate 1.0"
PLATFORM_CHOICES = ("Linux", "macOS", "Windows")
PUBLICATION_STATUSES = ("candidate", "release")
RUNTIME_FILES = {
    "LICENSE",
    "config.yaml",
    "elefante-build.json",
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
    "scripts/setup/configure_additional_hosts.py",
    "scripts/setup/host_selection.py",
    "scripts/setup/install_manifest.py",
    "scripts/lifecycle/backup_elefante_data.py",
    "scripts/lifecycle/daemon_service.py",
    "scripts/lifecycle/doctor.py",
    "scripts/lifecycle/restart_elefante.py",
    "scripts/lifecycle/restore_elefante_data.py",
    "scripts/lifecycle/uninstall_elefante.py",
    "scripts/pipeline/export_memories.py",
    "scripts/pipeline/import_memories.py",
    "scripts/pipeline/session_intelligence.py",
    "scripts/pipeline/team_sync.py",
    "scripts/pipeline/update_dashboard_data.py",
    "scripts/verify/verify_health.py",
    "scripts/verify/verify_mcp_handshake.py",
}
DEV_DEPENDENCIES = ("black", "mypy", "pytest", "pytest-asyncio", "ruff")
FORBIDDEN_PARTS = {".github", "agents", "docs", "examples", "tests", "workspace"}
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


def _root_files(platform_name: str) -> set[str]:
    files = {
        "installer-manifest.json",
        "START HERE.txt",
        "scripts/setup/bootstrap_release_bundle.py",
    }
    if platform_name == "Windows":
        files.update({"Install Elefante.bat", "Uninstall Elefante.bat"})
    else:
        files.update({"install.sh", "uninstall.sh"})
        if platform_name == "macOS":
            files.update({"Install Elefante.command", "Uninstall Elefante.command"})
    return files


def _entrypoints(platform_name: str) -> list[str]:
    return {
        "Linux": ["install.sh", "uninstall.sh"],
        "macOS": [
            "Install Elefante.command",
            "Uninstall Elefante.command",
            "install.sh",
            "uninstall.sh",
        ],
        "Windows": ["Install Elefante.bat", "Uninstall Elefante.bat"],
    }[platform_name]


def _require_executable(archive: zipfile.ZipFile, name: str) -> None:
    mode = archive.getinfo(name).external_attr >> 16
    if not stat.S_ISREG(mode) or not mode & 0o111:
        raise ValueError(f"Customer launcher is not executable: {name}")


def validate_release_client_archive(
    archive_path: Path,
    *,
    require_clean_source: bool = False,
    expected_publication_status: str | None = None,
    expected_platform: str | None = None,
) -> None:
    with zipfile.ZipFile(archive_path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        names = [info.filename for info in infos]
        if not names:
            raise ValueError("Customer installer archive is empty")
        if any(not _is_safe_archive_name(name) for name in names):
            raise ValueError("Customer installer contains an unsafe archive path")
        if any(info.date_time[0] < 2026 for info in infos):
            raise ValueError(
                "Customer installer contains misleading pre-release timestamps"
            )

        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ValueError(f"Expected one archive root; found {sorted(roots)!r}")
        bundle_directory = roots.pop()
        match = re.fullmatch(
            r"elefante-installer-(Linux|macOS|Windows)", bundle_directory
        )
        if not match:
            raise ValueError(f"Invalid customer installer root: {bundle_directory!r}")
        platform_name = match.group(1)
        if expected_platform and platform_name != expected_platform:
            raise ValueError(
                f"Expected {expected_platform} installer; found {platform_name}"
            )

        root_prefix = f"{bundle_directory}/"
        payload_prefix = f"{root_prefix}payload/elefante/"
        relative_names = {name.removeprefix(root_prefix) for name in names}
        root_files = _root_files(platform_name)
        missing_root_files = root_files - relative_names
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
            if relative_name.startswith("payload/elefante/"):
                payload_relative = relative_name.removeprefix("payload/elefante/")
                if not _payload_path_is_allowed(payload_relative):
                    raise ValueError(
                        f"Unexpected client payload file: {payload_relative}"
                    )
            elif relative_name not in root_files:
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
            archive.read(f"{root_prefix}installer-manifest.json").decode("utf-8")
        )
        publication_status = manifest.get("publication_status")
        required_manifest = {
            "product": "Elefante",
            "bundle_kind": "client-runtime-installer",
            "release_profile": "client",
            "platform": platform_name,
            "payload_root": "payload/elefante",
            "entrypoints": _entrypoints(platform_name),
        }
        invalid_manifest = {
            key: value
            for key, value in required_manifest.items()
            if manifest.get(key) != value
        }
        if invalid_manifest:
            raise ValueError(f"Invalid client bundle manifest: {invalid_manifest!r}")
        if publication_status not in PUBLICATION_STATUSES:
            raise ValueError("Invalid client publication status")
        if (
            expected_publication_status
            and publication_status != expected_publication_status
        ):
            raise ValueError(
                f"Expected {expected_publication_status} installer; found {publication_status}"
            )
        contract = manifest.get("customer_contract")
        if (
            not isinstance(contract, dict)
            or contract.get("publication_status") != publication_status
        ):
            raise ValueError(
                "Client customer contract does not match publication status"
            )
        if contract.get("includes_development_tools") is not False:
            raise ValueError("Client manifest permits development tools")
        if contract.get("includes_developer_workspace") is not False:
            raise ValueError("Client manifest permits developer workspace")

        version = str(manifest.get("version", ""))
        if not re.fullmatch(r"\d+\.\d+\.\d+", version):
            raise ValueError("Client bundle manifest lacks a semantic product version")
        if publication_status == "candidate":
            expected_candidate = f"v{version}-rc.1"
            if manifest.get("candidate") != expected_candidate:
                raise ValueError("Invalid client candidate version")
            if manifest.get("candidate_lane") != CLIENT_CANDIDATE_LANE:
                raise ValueError("Invalid client candidate lane")
        elif "candidate" in manifest or "candidate_lane" in manifest:
            raise ValueError("Released customer installer contains candidate metadata")

        source = manifest.get("source")
        if not isinstance(source, dict):
            raise ValueError("Client bundle manifest is missing source identity")
        commit = source.get("commit")
        if commit != "unavailable" and not re.fullmatch(r"[0-9a-f]{40}", str(commit)):
            raise ValueError("Client bundle manifest has an invalid source commit")
        if not isinstance(source.get("clean"), bool):
            raise ValueError(
                "Client bundle manifest has an invalid source cleanliness flag"
            )
        if require_clean_source and (
            commit == "unavailable" or source["clean"] is not True
        ):
            raise ValueError(
                "Publishable client installer requires a clean identified source"
            )

        build_identity = json.loads(
            archive.read(f"{payload_prefix}elefante-build.json").decode("utf-8")
        )
        expected_identity = {
            "schema_version": 1,
            "version": version,
            "source_commit": commit,
            "source_clean": source["clean"],
            "release_channel": publication_status,
        }
        if build_identity != expected_identity:
            raise ValueError(
                "Installed payload identity does not match the client archive manifest"
            )

        if platform_name == "Windows":
            launcher_name = f"{root_prefix}Install Elefante.bat"
            launcher = archive.read(launcher_name)
            if any(byte < 32 and byte not in (9, 10, 13) for byte in launcher):
                raise ValueError("Windows launcher contains invalid control bytes")
            if any(
                byte == 10 and (index == 0 or launcher[index - 1] != 13)
                for index, byte in enumerate(launcher)
            ):
                raise ValueError("Windows launcher contains bare LF line endings")
            if b"scripts\\setup\\bootstrap_release_bundle.py" not in launcher:
                raise ValueError("Windows launcher does not target bundled bootstrap")
            uninstall_launcher = archive.read(f"{root_prefix}Uninstall Elefante.bat")
            if b"--uninstall-interactive" not in uninstall_launcher:
                raise ValueError("Windows uninstall launcher does not use verified package uninstall")
        else:
            _require_executable(archive, f"{root_prefix}install.sh")
            _require_executable(archive, f"{root_prefix}uninstall.sh")
            if b"--uninstall-interactive" not in archive.read(f"{root_prefix}uninstall.sh"):
                raise ValueError("Unix uninstall launcher does not use verified package uninstall")
            if platform_name == "macOS":
                _require_executable(archive, f"{root_prefix}Install Elefante.command")
                _require_executable(archive, f"{root_prefix}Uninstall Elefante.command")

        lock_contents = archive.read(
            f"{payload_prefix}requirements.client.lock"
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
        description="Verify a clean Elefante customer installer"
    )
    parser.add_argument(
        "--archive", required=True, help="Customer installer ZIP to validate"
    )
    parser.add_argument(
        "--require-clean-source",
        action="store_true",
        help="reject archives not built from a clean identified Git commit",
    )
    parser.add_argument("--expected-publication-status", choices=PUBLICATION_STATUSES)
    parser.add_argument("--expected-platform", choices=PLATFORM_CHOICES)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    archive_path = Path(args.archive).expanduser().resolve()
    validate_release_client_archive(
        archive_path,
        require_clean_source=args.require_clean_source,
        expected_publication_status=args.expected_publication_status,
        expected_platform=args.expected_platform,
    )
    print(f"Verified clean customer installer: {archive_path}")


if __name__ == "__main__":
    main()
