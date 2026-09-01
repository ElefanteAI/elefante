"""Report Elefante runtime and integration readiness without changing local state."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Callable

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.lifecycle.daemon_service import service_status  # noqa: E402
from scripts.setup.host_selection import (  # noqa: E402
    CERTIFIED_CUSTOMER_HOSTS,
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


_INTEGRATION_STATUS_RE = re.compile(
    r"^(?:compatible|community|deprecated|partial|planned)"
    r"(?:-[a-z0-9][a-z0-9._-]*)?$"
)
_SURFACE_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
# Manifest surfaces can also describe installer-owned control-plane records.
# They are not host integrations and must not create drift diagnostics.
_INTERNAL_SURFACES = frozenset({"codex-recall-routing", "daemon-service"})


def _empty_integrations() -> dict[str, list[str]]:
    """Return a fresh, stable integration summary shape."""
    return {"compatible": [], "preview": [], "community": []}


def _status_family(status: object) -> str | None:
    """Return the governed status family, rejecting untrusted status text."""
    if not isinstance(status, str) or _INTEGRATION_STATUS_RE.fullmatch(status) is None:
        return None
    if status.startswith("partial"):
        return "partial"
    if status.startswith("planned"):
        return "planned"
    return status


def _safe_surface_id(value: object) -> bool:
    """Accept only identifier-shaped surface names for diagnostic output."""
    return isinstance(value, str) and _SURFACE_ID_RE.fullmatch(value) is not None


def _parse_integration_declarations(
    document: object,
) -> tuple[dict[str, str], list[str]]:
    """Validate matrix rows without retaining paths, commands, or config values."""
    if not isinstance(document, dict):
        return {}, ["integration_matrix_invalid"]
    if "schema_version" in document and document["schema_version"] != 1:
        return {}, ["integration_matrix_schema_unknown"]
    surfaces = document.get("surfaces")
    if not isinstance(surfaces, list):
        return {}, ["integration_matrix_invalid"]

    declarations: dict[str, str] = {}
    seen_ids: set[str] = set()
    diagnostics: set[str] = set()
    for surface in surfaces:
        if not isinstance(surface, dict):
            diagnostics.add("integration_matrix_invalid")
            continue
        surface_id = surface.get("id")
        if not _safe_surface_id(surface_id):
            diagnostics.add("integration_matrix_invalid")
            continue
        if surface_id in seen_ids:
            diagnostics.add("integration_matrix_duplicate_id")
            continue
        seen_ids.add(surface_id)
        status = surface.get("status")
        if not isinstance(status, str):
            diagnostics.add("integration_matrix_invalid")
            continue
        if _status_family(status) is None:
            diagnostics.add("integration_matrix_unknown_status")
            continue
        declarations[surface_id] = status
    return declarations, sorted(diagnostics)


def _integration_summary_for_declarations(
    declarations: Mapping[str, str],
) -> dict[str, list[str]]:
    """Bucket validated matrix declarations while preserving the old report shape."""
    compatible: list[str] = []
    preview: list[str] = []
    community: set[str] = {"generic-mcp-client"}
    for surface_id, status in declarations.items():
        family = _status_family(status)
        if family == "compatible":
            compatible.append(surface_id)
        elif family in {"partial", "planned"}:
            preview.append(surface_id)
        elif family == "community":
            community.add(surface_id)
    return {
        "compatible": sorted(set(compatible)),
        "preview": sorted(set(preview)),
        "community": sorted(community),
    }


def _compare_integration_surfaces(
    declared_statuses: Mapping[str, str],
    installer_surfaces: Iterable[object],
) -> dict[str, Any]:
    """Compare static matrix declarations to normalized installer-owned IDs.

    This helper is deliberately pure. It does not read host configuration,
    execute commands, or return any manifest-owned paths or values.
    """
    diagnostics: set[str] = set()
    customer_diagnostics: set[str] = set()
    valid_declarations: dict[str, str] = {}
    for surface_id, status in declared_statuses.items():
        if not _safe_surface_id(surface_id) or _status_family(status) is None:
            diagnostics.add("integration_matrix_invalid")
            continue
        valid_declarations[surface_id] = status

    valid_installer_surfaces: list[str] = []
    try:
        candidates = iter(installer_surfaces)
    except TypeError:
        candidates = iter(())
        diagnostics.add("install_manifest_surface_invalid")
    for surface in candidates:
        if not _safe_surface_id(surface):
            diagnostics.add("install_manifest_surface_invalid")
            continue
        valid_installer_surfaces.append(surface)

    normalized = normalize_manifest_surfaces(valid_installer_surfaces)
    normalized.difference_update(_INTERNAL_SURFACES)
    declared_ids = set(valid_declarations)
    unknown_installer = normalized.difference(declared_ids)
    non_customer_ready = {
        surface_id
        for surface_id in normalized.intersection(declared_ids)
        if _status_family(valid_declarations[surface_id]) != "compatible"
    }
    unknown_compatible = {
        surface_id
        for surface_id, status in valid_declarations.items()
        if _status_family(status) == "compatible"
        and surface_id not in set(SUPPORTED_HOSTS)
    }

    if unknown_installer:
        diagnostics.add("install_manifest_surface_unknown")
    if unknown_compatible:
        diagnostics.add("integration_matrix_unknown_surface")
    if non_customer_ready.intersection(CERTIFIED_CUSTOMER_HOSTS):
        customer_diagnostics.add("integration_surface_not_customer_ready")

    return {
        "matrix_ids": sorted(declared_ids),
        "matrix_statuses": {
            surface_id: valid_declarations[surface_id]
            for surface_id in sorted(valid_declarations)
        },
        "installer_owned_surfaces": sorted(normalized),
        "unknown_installer_surfaces": sorted(unknown_installer),
        "unknown_compatible_matrix_surfaces": sorted(unknown_compatible),
        "non_customer_ready_surfaces": sorted(non_customer_ready),
        "diagnostics": sorted(diagnostics),
        "customer_diagnostics": sorted(customer_diagnostics),
    }


class _DuplicateManifestKey(ValueError):
    """Internal marker used to reject duplicate JSON keys without echoing them."""


def _reject_duplicate_manifest_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateManifestKey
        result[key] = value
    return result


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


def _safe_daemon_report(daemon: object) -> dict[str, str | bool]:
    """Keep service status useful without returning a host service path."""
    if not isinstance(daemon, dict):
        return {"daemon_health": False, "service_runtime": "unavailable"}
    result: dict[str, str | bool] = {}
    if daemon.get("platform") in {"Darwin", "Linux", "Windows"}:
        result["platform"] = daemon["platform"]
    if isinstance(daemon.get("service_file_exists"), bool):
        result["service_file_exists"] = daemon["service_file_exists"]
    if daemon.get("service_file_ownership") in {
        "absent",
        "owned",
        "modified_or_untracked",
    }:
        result["service_file_ownership"] = daemon["service_file_ownership"]
    if daemon.get("service_runtime") in {
        "active",
        "inactive",
        "registered",
        "not_registered",
        "unavailable",
    }:
        result["service_runtime"] = daemon["service_runtime"]
    if isinstance(daemon.get("daemon_health"), bool):
        result["daemon_health"] = daemon["daemon_health"]
    return result


def _safe_installation_report(
    installation: dict[str, str | bool] | None,
) -> dict[str, str | bool] | None:
    """Return installation identity without user-home or runtime paths."""
    if not isinstance(installation, dict):
        return None
    result: dict[str, str | bool] = {}
    if installation.get("scope") in {"customer", "developer"}:
        result["scope"] = installation["scope"]
    if isinstance(installation.get("version"), str) and re.fullmatch(
        r"\d+\.\d+\.\d+", installation["version"]
    ):
        result["version"] = installation["version"]
    source_commit = installation.get("source_commit")
    if isinstance(source_commit, str) and (
        SOURCE_COMMIT_PATTERN.fullmatch(source_commit) is not None
        or source_commit == "unavailable"
    ):
        result["source_commit"] = source_commit
    if installation.get("release_channel") in RELEASE_CHANNELS:
        result["release_channel"] = installation["release_channel"]
    if isinstance(installation.get("source_clean"), bool):
        result["source_clean"] = installation["source_clean"]
    return result


def _read_manifest(home: Path) -> tuple[dict[str, Any], list[str]]:
    """Return ownership counts and surfaces, never host commands or paths."""
    target = manifest_path(home)
    if not target.exists():
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, []
    try:
        payload = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_manifest_keys,
        )
    except _DuplicateManifestKey:
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, [
            "install_manifest_duplicate_key"
        ]
    except (OSError, json.JSONDecodeError):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    if not isinstance(payload, dict):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    files = payload.get("files", {})
    commands = payload.get("commands", {})
    if not isinstance(files, dict) or not isinstance(commands, dict):
        return {"files": 0, "host_registrations": 0, "configured_surfaces": []}, ["install_manifest_invalid"]
    diagnostics: set[str] = set()
    surfaces: set[str] = set()
    for details in [*files.values(), *commands.values()]:
        if not isinstance(details, dict) or not _safe_surface_id(details.get("surface")):
            diagnostics.add("install_manifest_entry_invalid")
            continue
        surfaces.add(details["surface"])
    if "runtime" in payload and not isinstance(payload["runtime"], dict):
        diagnostics.add("install_manifest_runtime_invalid")
    return {
        "files": len(files),
        "host_registrations": len(commands),
        "configured_surfaces": sorted(surfaces),
    }, sorted(diagnostics)


def _read_integration_declarations(
    matrix_path: Path,
) -> tuple[dict[str, str], list[str]]:
    """Read and validate the repository matrix without touching host state."""
    try:
        document = yaml.safe_load(matrix_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}, ["integration_matrix_invalid"]
    return _parse_integration_declarations(document)


def _integration_summary(matrix_path: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Read the declared compatibility contract without probing user hosts."""
    declarations, diagnostics = _read_integration_declarations(matrix_path)
    return _integration_summary_for_declarations(declarations), diagnostics


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
    daemon = _safe_daemon_report(daemon)
    manifest, manifest_diagnostics = _read_manifest(home)
    runtime_installation = read_runtime_installation(home)
    customer_runtime = bool(
        runtime_installation is not None
        and runtime_installation.get("scope") == "customer"
    )
    detected_hosts = host_detector(home=home)
    verified_surfaces = normalize_manifest_surfaces(surface_inspector(home))
    uncovered_hosts = sorted(detected_hosts.difference(verified_surfaces))
    certified_required = (
        set(CERTIFIED_CUSTOMER_HOSTS) if customer_runtime else set()
    )
    certified_verified = certified_required.intersection(
        detected_hosts,
        verified_surfaces,
    )
    certified_uncovered = sorted(certified_required.difference(certified_verified))
    compatibility_uncovered = sorted(
        detected_hosts.difference(verified_surfaces).difference(certified_required)
    )
    integration_matrix = repo_root / "agents/manifests/ide-integration.yaml"
    if integration_matrix.is_file():
        declared_statuses, integration_diagnostics = _read_integration_declarations(
            integration_matrix
        )
        integrations = _integration_summary_for_declarations(declared_statuses)
    else:
        declared_statuses = {host: "compatible" for host in SUPPORTED_HOSTS}
        integrations = {
            "compatible": sorted(SUPPORTED_HOSTS),
            "preview": [],
            "community": ["generic-mcp-client"],
        }
        integration_diagnostics = []
    integration_contract = _compare_integration_surfaces(
        declared_statuses,
        manifest.get("configured_surfaces", []),
    )
    diagnostics.extend(manifest_diagnostics)
    diagnostics.extend(integration_diagnostics)
    diagnostics.extend(integration_contract["diagnostics"])
    if not venv_python.exists():
        diagnostics.append("repository_venv_missing")
    if not (repo_root / "config.yaml").is_file():
        diagnostics.append("repository_config_missing")
    if not daemon.get("daemon_health"):
        diagnostics.append("daemon_unreachable")
    if daemon.get("service_file_ownership") == "modified_or_untracked":
        diagnostics.append("daemon_service_user_managed")
    customer_diagnostics: list[str] = list(
        integration_contract["customer_diagnostics"]
    )
    configured_manifest_surfaces = set(manifest.get("configured_surfaces", []))
    recall_required = customer_runtime or "codex-recall-routing" in (
        configured_manifest_surfaces
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
                    value = inspected[source_key]
                    if target_key in {"probe_status", "diagnostic"} and not (
                        value is None
                        or (
                            isinstance(value, str)
                            and _SURFACE_ID_RE.fullmatch(value) is not None
                        )
                    ):
                        value = None
                    recall_report[target_key] = value
        if recall_report["ready"] is not True:
            customer_diagnostics.append(
                str(recall_report["diagnostic"] or "recall_probe_failed")
            )
    if runtime_installation is None:
        customer_diagnostics.append("runtime_installation_unrecorded")
        if uncovered_hosts:
            customer_diagnostics.append("detected_hosts_unconfigured")
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
    if certified_uncovered:
        customer_diagnostics.append("certified_host_unconfigured")
    if customer_runtime and "codex-recall-routing" not in configured_manifest_surfaces:
        customer_diagnostics.append("codex_recall_guidance_unverified")
    if recall_required and "codex" not in verified_surfaces:
        customer_diagnostics.append("codex_recall_routing_unverified")
    runtime_ready = not diagnostics
    host_coverage = {
        "detected": sorted(detected_hosts),
        "verified": sorted(detected_hosts.intersection(verified_surfaces)),
        "uncovered": uncovered_hosts,
    }
    if customer_runtime:
        host_coverage.update(
            {
                "certified_required": sorted(certified_required),
                "certified_verified": sorted(certified_verified),
                "certified_uncovered": certified_uncovered,
                "compatibility_uncovered": compatibility_uncovered,
            }
        )
    return {
        "schema_version": 2,
        "ready": runtime_ready,
        "customer_ready": runtime_ready and not customer_diagnostics,
        "repository_present": repo_root.is_dir(),
        "runtime": {
            "venv_python_exists": venv_python.exists(),
            "config_exists": (repo_root / "config.yaml").is_file(),
        },
        "daemon": daemon,
        "installer_ownership": manifest,
        "installation": _safe_installation_report(runtime_installation),
        "host_coverage": host_coverage,
        "integrations": integrations,
        "integration_contract": integration_contract,
        "recall": recall_report,
        "diagnostics": diagnostics,
        "customer_diagnostics": customer_diagnostics,
    }


def _render_text(report: dict) -> str:
    lines = [
        f"ready={report['ready']}",
        f"customer_ready={report['customer_ready']}",
        f"repository_present={report.get('repository_present', False)}",
    ]
    runtime = report["runtime"]
    integration_contract = report.get("integration_contract", {})
    matrix_statuses = integration_contract.get("matrix_statuses", {})
    matrix_status_text = ",".join(
        f"{surface_id}:{matrix_statuses[surface_id]}"
        for surface_id in sorted(matrix_statuses)
    )
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
            "certified_hosts="
            + ",".join(report["host_coverage"].get("certified_required", [])),
            "certified_uncovered="
            + ",".join(report["host_coverage"].get("certified_uncovered", [])),
            "compatible_hosts=" + ",".join(report["integrations"]["compatible"]),
            "community_hosts=" + ",".join(report["integrations"]["community"]),
            "integration_matrix_statuses=" + matrix_status_text,
            "integration_installer_surfaces="
            + ",".join(integration_contract.get("installer_owned_surfaces", [])),
            "integration_diagnostics="
            + ",".join(integration_contract.get("diagnostics", []) or ["none"]),
            "integration_customer_diagnostics="
            + ",".join(
                integration_contract.get("customer_diagnostics", []) or ["none"]
            ),
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
