"""Report Elefante runtime and integration readiness without changing local state."""

from __future__ import annotations

import argparse
import json
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
    configured_surfaces,
    manifest_path,
    read_runtime_installation,
)


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


def build_report(
    *,
    repo_root: Path = REPO_ROOT,
    home: Path | None = None,
    service_inspector: Callable[[Path], dict[str, str | bool]] = service_status,
    host_detector: Callable[..., set[str]] = detect_supported_hosts,
    surface_inspector: Callable[[Path], set[str]] = configured_surfaces,
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
    if runtime_installation is None:
        customer_diagnostics.append("runtime_installation_unrecorded")
    else:
        if runtime_installation["scope"] != "customer":
            customer_diagnostics.append("runtime_scope_not_customer")
        if Path(runtime_installation["app_root"]).resolve() != repo_root.resolve():
            customer_diagnostics.append("runtime_root_mismatch")
    if uncovered_hosts:
        customer_diagnostics.append("detected_hosts_unconfigured")
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
            "diagnostics=" + ",".join(report["diagnostics"] or ["none"]),
            "customer_diagnostics=" + ",".join(report["customer_diagnostics"] or ["none"]),
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
