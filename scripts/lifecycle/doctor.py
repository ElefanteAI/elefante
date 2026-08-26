"""Report Elefante runtime and integration readiness without changing local state."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle.daemon_service import service_status  # noqa: E402
from scripts.setup.host_selection import (  # noqa: E402
    SUPPORTED_HOSTS,
    detect_supported_hosts,
    normalize_manifest_surfaces,
)
from scripts.setup.install_manifest import (  # noqa: E402
    BUILD_IDENTITY_FILE_NAME,
    RELEASE_CHANNELS,
    SOURCE_COMMIT_PATTERN,
    configured_surfaces,
    manifest_path,
    read_runtime_installation,
)
from scripts.verify.verify_mcp_handshake import (  # noqa: E402
    inspect_recall_capability,
)


def _source_version(repo_root: Path) -> str | None:
    """Read the installed payload version without importing product dependencies."""
    try:
        contents = (repo_root / "src" / "__init__.py").read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(
        r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$',
        contents,
        flags=re.MULTILINE,
    )
    return match.group(1) if match else None


def _build_identity(repo_root: Path) -> tuple[dict[str, Any] | None, str | None]:
    """Read immutable identity shipped inside a customer payload."""
    target = repo_root / BUILD_IDENTITY_FILE_NAME
    if not target.is_file():
        return None, "runtime_build_identity_missing"
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "runtime_build_identity_invalid"
    if not isinstance(payload, dict):
        return None, "runtime_build_identity_invalid"
    return payload, None


def _read_manifest(home: Path) -> tuple[dict[str, Any], list[str]]:
    """Return ownership counts and surfaces, never host commands or paths."""
    target = manifest_path(home)
    if not target.exists():
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, []
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    if not isinstance(payload, dict):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    files = payload.get("files", {})
    commands = payload.get("commands", {})
    if not isinstance(files, dict) or not isinstance(commands, dict):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    surfaces = {
        details["surface"]
        for details in [*files.values(), *commands.values()]
        if isinstance(details, dict) and isinstance(details.get("surface"), str)
    }
    return {
        "files": len(files),
        "host_registrations": len(commands),
        "configured_surfaces": sorted(surfaces),
    }, []


def _integration_summary(matrix_path: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Read the declared compatibility contract without probing user hosts."""
    try:
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {"compatible": [], "preview": [], "community": []}, ["integration_matrix_invalid"]
    surfaces = document.get("surfaces") if isinstance(document, dict) else None
    if not isinstance(surfaces, list):
        return {"compatible": [], "preview": [], "community": []}, ["integration_matrix_invalid"]
    compatible, preview, community = [], [], ["generic-mcp-client"]
    for surface in surfaces:
        if not isinstance(surface, dict) or not isinstance(surface.get("id"), str):
            continue
        status = surface.get("status")
        if status == "compatible":
            compatible.append(surface["id"])
        elif status == "community":
            community.append(surface["id"])
        elif isinstance(status, str) and (status.startswith("partial") or status.startswith("planned")):
            preview.append(surface["id"])
    return {
        "compatible": sorted(compatible),
        "preview": sorted(preview),
        "community": sorted(community),
    }, []


def _inspect_recall(repo_root: Path, venv_python: Path) -> dict[str, Any]:
    """Run one bounded read-only capability probe through the customer bridge."""
    return asyncio.run(
        inspect_recall_capability(
            root=repo_root,
            python_executable=str(venv_python),
        )
    )


def build_report(
    *,
    repo_root: Path = REPO_ROOT,
    home: Path | None = None,
    service_inspector: Callable[[Path], dict[str, str | bool]] = service_status,
    host_detector: Callable[..., set[str]] = detect_supported_hosts,
    surface_inspector: Callable[[Path], set[str]] = configured_surfaces,
    recall_inspector: Callable[[Path, Path], dict[str, Any]] = _inspect_recall,
) -> dict:
    """Build a complete read-only readiness report suitable for people and agents."""
    home = home or Path.home()
    diagnostics: list[str] = []
    venv_python = repo_root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    try:
        daemon = service_inspector(home)
    except (OSError, RuntimeError):
        daemon = {"daemon_health": False, "service_runtime": "unavailable"}
        diagnostics.append("daemon_service_unavailable")
    manifest, manifest_diagnostics = _read_manifest(home)
    runtime_installation = read_runtime_installation(home)
    detected_hosts = host_detector(home=home)
    verified_surfaces = normalize_manifest_surfaces(surface_inspector(home))
    uncovered_hosts = sorted(detected_hosts.difference(verified_surfaces))
    integration_matrix = repo_root / "agents/manifests/ide-integration.yaml"
    if integration_matrix.is_file():
        integrations, integration_diagnostics = _integration_summary(integration_matrix)
    else:
        integrations = {
            "compatible": sorted(SUPPORTED_HOSTS),
            "preview": [],
            "community": ["generic-mcp-client"],
        }
        integration_diagnostics = []
    diagnostics.extend(manifest_diagnostics)
    diagnostics.extend(integration_diagnostics)
    if not venv_python.exists():
        diagnostics.append("repository_venv_missing")
    if not (repo_root / "config.yaml").is_file():
        diagnostics.append("repository_config_missing")
    if not daemon.get("daemon_health"):
        diagnostics.append("daemon_unreachable")
    if daemon.get("service_file_ownership") == "modified_or_untracked":
        diagnostics.append("daemon_service_user_managed")
    customer_diagnostics: list[str] = []
    recall_required = "codex-recall-routing" in manifest.get(
        "configured_surfaces",
        [],
    )
    recall_report: dict[str, Any] = {
        "required": recall_required,
        "handshake_ready": None,
        "tool_count": None,
        "tool_present": None,
        "annotations_read_only": None,
        "probe_status": None,
        "probe_read_only": None,
        "ready": None,
        "diagnostic": None,
    }
    if recall_required:
        if not venv_python.exists():
            recall_report.update(
                {
                    "handshake_ready": False,
                    "ready": False,
                    "diagnostic": "recall_probe_runtime_missing",
                }
            )
        else:
            try:
                inspected = recall_inspector(repo_root, venv_python)
            except (OSError, RuntimeError, ValueError, TypeError):
                inspected = {
                    "handshake_ready": False,
                    "recall_ready": False,
                    "diagnostic": "recall_probe_failed",
                }
            for source_key, target_key in (
                ("handshake_ready", "handshake_ready"),
                ("tool_count", "tool_count"),
                ("tool_present", "tool_present"),
                ("annotations_read_only", "annotations_read_only"),
                ("probe_status", "probe_status"),
                ("probe_read_only", "probe_read_only"),
                ("recall_ready", "ready"),
                ("diagnostic", "diagnostic"),
            ):
                if source_key in inspected:
                    recall_report[target_key] = inspected[source_key]
        if recall_report["ready"] is not True:
            customer_diagnostics.append(
                str(recall_report["diagnostic"] or "recall_probe_failed")
            )
    if runtime_installation is None:
        customer_diagnostics.append("runtime_installation_unrecorded")
    else:
        if runtime_installation["scope"] != "customer":
            customer_diagnostics.append("runtime_scope_not_customer")
        if Path(runtime_installation["app_root"]).resolve() != repo_root.resolve():
            customer_diagnostics.append("runtime_root_mismatch")
        provenance_fields = {"source_commit", "release_channel", "source_clean"}
        if not provenance_fields <= runtime_installation.keys():
            customer_diagnostics.append("runtime_provenance_missing")
        else:
            source_commit = runtime_installation["source_commit"]
            release_channel = runtime_installation["release_channel"]
            source_clean = runtime_installation["source_clean"]
            provenance_valid = (
                isinstance(source_commit, str)
                and (
                    SOURCE_COMMIT_PATTERN.fullmatch(source_commit) is not None
                    or (
                        release_channel == "development"
                        and source_commit == "unavailable"
                    )
                )
                and isinstance(release_channel, str)
                and release_channel in RELEASE_CHANNELS
                and isinstance(source_clean, bool)
            )
            if not provenance_valid:
                customer_diagnostics.append("runtime_provenance_invalid")
            installed_version = _source_version(repo_root)
            if installed_version is None:
                customer_diagnostics.append("runtime_version_unreadable")
            elif installed_version != runtime_installation["version"]:
                customer_diagnostics.append("runtime_version_mismatch")

            if runtime_installation["scope"] == "customer":
                if not isinstance(release_channel, str) or release_channel not in {
                    "candidate",
                    "release",
                }:
                    customer_diagnostics.append("runtime_release_channel_invalid")
                if source_clean is not True:
                    customer_diagnostics.append("runtime_source_not_clean")
                payload_identity, identity_diagnostic = _build_identity(repo_root)
                if identity_diagnostic:
                    customer_diagnostics.append(identity_diagnostic)
                elif provenance_valid:
                    expected_identity = {
                        "schema_version": 1,
                        "version": runtime_installation["version"],
                        "source_commit": source_commit,
                        "source_clean": source_clean,
                        "release_channel": release_channel,
                    }
                    if payload_identity != expected_identity:
                        customer_diagnostics.append("runtime_build_identity_mismatch")
    if uncovered_hosts:
        customer_diagnostics.append("detected_hosts_unconfigured")
    if recall_required and "codex" not in verified_surfaces:
        customer_diagnostics.append("codex_recall_routing_unverified")
    runtime_ready = not diagnostics
    return {
        "schema_version": 2,
        "ready": runtime_ready,
        "customer_ready": runtime_ready and not customer_diagnostics,
        "repository": str(repo_root),
        "runtime": {
            "venv_python": str(venv_python),
            "venv_python_exists": venv_python.exists(),
            "config_exists": (repo_root / "config.yaml").is_file(),
        },
        "daemon": daemon,
        "installer_ownership": manifest,
        "installation": runtime_installation,
        "host_coverage": {
            "detected": sorted(detected_hosts),
            "verified": sorted(detected_hosts.intersection(verified_surfaces)),
            "uncovered": uncovered_hosts,
        },
        "integrations": integrations,
        "recall": recall_report,
        "diagnostics": diagnostics,
        "customer_diagnostics": customer_diagnostics,
    }


def _render_text(report: dict) -> str:
    lines = [
        f"ready={report['ready']}",
        f"customer_ready={report['customer_ready']}",
        f"repository={report['repository']}",
    ]
    runtime = report["runtime"]
    lines.extend(
        [
            f"venv_python_exists={runtime['venv_python_exists']}",
            f"config_exists={runtime['config_exists']}",
            f"daemon_health={report['daemon'].get('daemon_health', False)}",
            f"service_runtime={report['daemon'].get('service_runtime', 'unavailable')}",
            f"owned_files={report['installer_ownership']['files']}",
            f"owned_host_registrations={report['installer_ownership']['host_registrations']}",
            "configured_surfaces=" + ",".join(report["installer_ownership"].get("configured_surfaces", [])),
            "detected_hosts=" + ",".join(report["host_coverage"]["detected"]),
            "uncovered_hosts=" + ",".join(report["host_coverage"]["uncovered"]),
            "compatible_hosts=" + ",".join(report["integrations"]["compatible"]),
            "community_hosts=" + ",".join(report["integrations"]["community"]),
            f"recall_required={report['recall']['required']}",
            f"recall_ready={report['recall']['ready']}",
            f"recall_probe_status={report['recall']['probe_status'] or 'not-run'}",
            "diagnostics=" + ",".join(report["diagnostics"] or ["none"]),
            "customer_diagnostics=" + ",".join(report["customer_diagnostics"] or ["none"]),
        ]
    )
    installation = report.get("installation")
    if isinstance(installation, dict):
        lines.extend(
            [
                f"installation_version={installation.get('version', 'unknown')}",
                f"release_channel={installation.get('release_channel', 'unknown')}",
                f"source_commit={installation.get('source_commit', 'unknown')}",
            ]
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit the complete machine-readable report")
    args = parser.parse_args(argv)
    report = build_report()
    print(json.dumps(report, indent=2, sort_keys=True) if args.json else _render_text(report))
    return 0 if report["customer_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
