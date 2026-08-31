#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : bootstrap_release_bundle.py
# PURPOSE : Place a shipped Elefante installer bundle into a stable install
#           location, then delegate the real install work to scripts/setup/install.py.
# WHEN    : Running a downloadable Elefante installer bundle outside a source checkout.
# USAGE   : python scripts/setup/bootstrap_release_bundle.py [--install-root PATH]
#           [--venv-mode ask|fresh|backup|reuse|abort] [--dry-run]
# NOTES   : Does not duplicate dependency, database, or IDE setup logic. It only
#           copies the payload into a durable path and hands off to install.py.
# ─────────────────────────────────────────────────────────────────────────────
"""Bootstrap a shipped Elefante installer bundle into a stable install root."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen
from uuid import uuid4


DEFAULT_BUNDLE_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_FILE_NAME = "installer-manifest.json"
BUILD_IDENTITY_FILE_NAME = "elefante-build.json"
PAYLOAD_RELATIVE_ROOT = Path("payload") / "elefante"
INSTALL_SCRIPT_RELATIVE_PATH = Path("scripts") / "setup" / "install.py"
DAEMON_SERVICE_RELATIVE_PATH = Path("scripts") / "lifecycle" / "daemon_service.py"
BACKUP_SCRIPT_RELATIVE_PATH = Path("scripts") / "lifecycle" / "backup_elefante_data.py"
DOCTOR_SCRIPT_RELATIVE_PATH = Path("scripts") / "lifecycle" / "doctor.py"
RESTORE_SCRIPT_RELATIVE_PATH = Path("scripts") / "lifecycle" / "restore_elefante_data.py"
UNINSTALL_SCRIPT_RELATIVE_PATH = Path("scripts") / "lifecycle" / "uninstall_elefante.py"
INSTALL_LOG_FILE_NAME = ".elefante-install.log"
INSTALL_STATUS_FILE_NAME = ".elefante-install-status.txt"
INSTALL_SUMMARY_FILE_NAME = ".elefante-install-summary.txt"
PACKAGE_RECEIPT_FILE_NAME = ".elefante-package-receipt.json"
FIRST_RUN_RECEIPT_FILE_NAME = ".elefante-first-run-receipt.json"
RETAINED_CODE_RECEIPT_FILE_NAME = ".elefante-retained-code.json"
INSTALL_MANIFEST_FILE_NAME = "install-manifest.json"
DATA_PRESERVATION_FILE_NAME = "data-preservation.json"
UNINSTALL_RECEIPTS_DIRECTORY = "receipts"
MAX_LIFECYCLE_JSON_BYTES = 64 * 1024
PAYLOAD_FINGERPRINT_EXCLUDED = {
    RETAINED_CODE_RECEIPT_FILE_NAME,
    PACKAGE_RECEIPT_FILE_NAME,
    FIRST_RUN_RECEIPT_FILE_NAME,
    INSTALL_LOG_FILE_NAME,
    INSTALL_STATUS_FILE_NAME,
    INSTALL_SUMMARY_FILE_NAME,
}
PACKAGE_FAILED_STAGES = frozenset(
    {
        "0a",
        "0b",
        "1",
        "2",
        "2a",
        "3",
        "3a",
        "3b",
        "4",
        "4a",
        "5",
        "5a",
        "5b",
        "5c",
        "delegated_installer",
        "first_run_acceptance",
        "package_verification",
        "retained_rollback",
        "unknown",
    }
)
VENV_CHOICES = ["ask", "fresh", "backup", "reuse", "abort"]
RELEASE_PROFILE_DEVELOPER = "developer"
RELEASE_PROFILE_CLIENT = "client"
RELEASE_PROFILES = {RELEASE_PROFILE_DEVELOPER, RELEASE_PROFILE_CLIENT}
RELEASE_CHANNELS = {"candidate", "development", "release"}
SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+")
SOURCE_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
SUPPORTED_PYTHON_MIN = (3, 11)
SUPPORTED_PYTHON_MAX = (3, 14)


def resolve_bundle_root(provided_path: str | None) -> Path:
    if provided_path:
        return Path(provided_path).expanduser().resolve()
    return DEFAULT_BUNDLE_ROOT


def _python_version(executable: str) -> tuple[int, int, int] | None:
    try:
        result = subprocess.run(
            [
                executable,
                "-c",
                "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}.{sys.version_info[2]}')",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return None

    if result.returncode != 0:
        return None

    raw = result.stdout.strip()
    try:
        major, minor, patch = (int(part) for part in raw.split(".", 2))
    except ValueError:
        return None
    return major, minor, patch


def _python_is_supported(executable: str) -> bool:
    version = _python_version(executable)
    if version is None:
        return False
    return SUPPORTED_PYTHON_MIN <= version[:2] < SUPPORTED_PYTHON_MAX


def resolve_install_python(provided_executable: str | None) -> str:
    candidates: list[str] = []
    seen: set[str] = set()

    def add(candidate: str | None) -> None:
        if not candidate:
            return
        normalized = str(Path(candidate).expanduser()) if any(sep in candidate for sep in ("/", "\\")) else candidate
        if normalized in seen:
            return
        seen.add(normalized)
        candidates.append(normalized)

    add(provided_executable)
    add(sys.executable)

    if os.name != "nt":
        for candidate in (
            "/opt/homebrew/bin/python3.13",
            "/opt/homebrew/bin/python3.12",
            "/opt/homebrew/bin/python3.11",
            "/usr/local/bin/python3.13",
            "/usr/local/bin/python3.12",
            "/usr/local/bin/python3.11",
            "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3",
            "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3",
            "/usr/bin/python3",
        ):
            if Path(candidate).exists():
                add(candidate)

    for command_name in ("python3.13", "python3.12", "python3.11", "python3", "python"):
        add(shutil.which(command_name))

    for candidate in candidates:
        if _python_is_supported(candidate):
            return candidate

    raise RuntimeError(
        "No compatible Python found. Elefante requires Python 3.11, 3.12, or 3.13."
    )


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


def _json_object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _stable_sha256(payload: object) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _strict_json_file(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("Lifecycle state file is missing or unsafe")
    if path.stat().st_size > MAX_LIFECYCLE_JSON_BYTES:
        raise ValueError("Lifecycle state file is too large")
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, UnicodeDecodeError, ValueError) as error:
        raise ValueError("Lifecycle state file is invalid") from error
    if not isinstance(payload, dict):
        raise ValueError("Lifecycle state file is invalid")
    return payload


def _write_private_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("Lifecycle receipt target is unsafe")
    os.chmod(path.parent, 0o700)
    temporary = path.parent / f".{path.name}.{uuid4().hex}.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return path


def data_preservation_path(home: Path) -> Path:
    return Path(home).expanduser().resolve() / ".elefante" / DATA_PRESERVATION_FILE_NAME


def read_data_preservation_receipt(
    *,
    home: Path,
    install_root: Path,
) -> dict[str, object] | None:
    """Read only a completed receipt bound to this exact app root."""
    target = data_preservation_path(home)
    if not target.exists():
        return None
    try:
        payload = _strict_json_file(target)
    except ValueError:
        return None
    data_state = payload.get("data_state")
    raw_app_root = payload.get("app_root")
    raw_data_root = payload.get("data_root")
    if (
        payload.get("schema_version") != 1
        or payload.get("operation") != "uninstall"
        or payload.get("status") != "VERIFIED_COMPLETE"
        or not isinstance(raw_app_root, str)
        or not Path(raw_app_root).is_absolute()
        or Path(raw_app_root).expanduser().resolve()
        != Path(install_root).expanduser().resolve()
        or not isinstance(raw_data_root, str)
        or not Path(raw_data_root).is_absolute()
        or not isinstance(data_state, dict)
        or not isinstance(data_state.get("present"), bool)
        or not isinstance(data_state.get("file_count"), int)
        or not isinstance(data_state.get("total_bytes"), int)
        or not isinstance(data_state.get("source_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", str(data_state["source_sha256"])) is None
    ):
        return None
    data_root = Path(raw_data_root).expanduser()
    if data_root.is_symlink():
        return None
    return payload


def consume_data_preservation_receipt(
    *,
    home: Path,
    install_root: Path,
    data_root: Path,
) -> bool:
    """Remove only the exact completed pointer after verified reinstall."""
    target = data_preservation_path(home)
    payload = read_data_preservation_receipt(
        home=home,
        install_root=install_root,
    )
    if payload is None:
        return False
    if Path(str(payload["data_root"])).expanduser().resolve() != Path(data_root).resolve():
        return False
    target.unlink()
    return True


def resolve_managed_data_dir(
    install_root: Path,
    *,
    home: Path | None = None,
) -> Path:
    """Resolve the installed product's exact data root without opening its content."""
    install_root = Path(install_root).expanduser().resolve()
    home = Path(home or Path.home()).expanduser().resolve()
    default = home / ".elefante" / "data"
    manifest_path = home / ".elefante" / INSTALL_MANIFEST_FILE_NAME
    if not manifest_path.exists():
        preserved = read_data_preservation_receipt(
            home=home,
            install_root=install_root,
        )
        if data_preservation_path(home).exists() and preserved is None:
            raise RuntimeError("Elefante data-preservation receipt is invalid")
        return (
            Path(str(preserved["data_root"])).expanduser().resolve()
            if preserved is not None
            else default
        )
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise RuntimeError("Elefante install manifest is missing or unsafe")
    try:
        payload = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Elefante install manifest is invalid") from error
    runtime = payload.get("runtime") if isinstance(payload, dict) else None
    if not isinstance(runtime, dict):
        preserved = read_data_preservation_receipt(
            home=home,
            install_root=install_root,
        )
        if preserved is not None:
            return Path(str(preserved["data_root"])).expanduser().resolve()
        if data_preservation_path(home).exists():
            raise RuntimeError("Elefante data-preservation receipt is invalid")
        raise RuntimeError("Elefante install manifest has no runtime identity")
    raw_app_root = runtime.get("app_root")
    raw_data_root = runtime.get("data_root")
    if not isinstance(raw_app_root, str) or not Path(raw_app_root).is_absolute():
        raise RuntimeError("Elefante install manifest has an invalid app root")
    if Path(raw_app_root).expanduser().resolve() != install_root:
        raise RuntimeError("Elefante install manifest belongs to a different app root")
    if not isinstance(raw_data_root, str) or not Path(raw_data_root).is_absolute():
        raise RuntimeError("Elefante install manifest has an invalid data root")
    data_root = Path(raw_data_root).expanduser()
    if data_root.is_symlink():
        raise RuntimeError("Managed Elefante data directory cannot be a symlink")
    return data_root.resolve()


def managed_backup_dir(data_root: Path) -> Path:
    """Derive the one customer backup directory from the managed data layout."""
    return Path(data_root).expanduser().resolve().parent / "backups"


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


def get_release_profile(manifest: dict[str, object]) -> str:
    """Return the declared installer profile, rejecting unknown bundle contracts."""
    profile = manifest.get("release_profile", RELEASE_PROFILE_DEVELOPER)
    if profile not in RELEASE_PROFILES:
        raise ValueError(f"Installer bundle has an unsupported release profile: {profile!r}")
    return str(profile)


def ensure_bundle_layout(bundle_root: Path, *, release_profile: str) -> Path:
    payload_root = get_payload_root(bundle_root)
    dependency_files = (
        [payload_root / "requirements.client.txt", payload_root / "requirements.client.lock"]
        if release_profile == RELEASE_PROFILE_CLIENT
        else [payload_root / "requirements.txt", payload_root / "requirements.lock"]
    )
    required_paths = [
        payload_root,
        payload_root / INSTALL_SCRIPT_RELATIVE_PATH,
        *dependency_files,
        bundle_root / "scripts" / "setup" / "bootstrap_release_bundle.py",
    ]
    # Customer bundles are never accepted without an exact build identity.
    # Developer bundles built by the current pipeline carry one too, but old
    # developer archives remain dry-run compatible for local recovery and
    # historical acceptance fixtures.
    if release_profile == RELEASE_PROFILE_CLIENT:
        required_paths.insert(1, payload_root / BUILD_IDENTITY_FILE_NAME)
        required_paths.extend(
            [
                payload_root / DAEMON_SERVICE_RELATIVE_PATH,
                payload_root / BACKUP_SCRIPT_RELATIVE_PATH,
                payload_root / RESTORE_SCRIPT_RELATIVE_PATH,
                payload_root / UNINSTALL_SCRIPT_RELATIVE_PATH,
                payload_root / DOCTOR_SCRIPT_RELATIVE_PATH,
            ]
        )

    missing = [str(path) for path in required_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Installer bundle is incomplete. Missing required paths: " + ", ".join(missing)
        )

    return payload_root


def load_build_identity(
    bundle_root: Path,
    manifest: dict[str, object],
    *,
    release_profile: str,
) -> dict[str, object] | None:
    """Validate that archive metadata and the payload identify the same build."""
    identity_path = get_payload_root(bundle_root) / BUILD_IDENTITY_FILE_NAME
    if not identity_path.exists() and release_profile == RELEASE_PROFILE_DEVELOPER:
        return None
    try:
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Installer payload has invalid build identity") from error
    if not isinstance(identity, dict) or identity.get("schema_version") != 1:
        raise ValueError("Installer payload has unsupported build identity")

    version = identity.get("version")
    commit = identity.get("source_commit")
    clean = identity.get("source_clean")
    channel = identity.get("release_channel")
    if not isinstance(version, str) or not SEMVER_PATTERN.fullmatch(version):
        raise ValueError("Installer payload has invalid semantic version identity")
    if not isinstance(clean, bool) or channel not in RELEASE_CHANNELS:
        raise ValueError("Installer payload has invalid source provenance")
    if not isinstance(commit, str) or not (
        SOURCE_COMMIT_PATTERN.fullmatch(commit)
        or (channel == "development" and commit == "unavailable")
    ):
        raise ValueError("Installer payload has invalid source commit identity")

    source = manifest.get("source")
    expected_channel = (
        manifest.get("publication_status")
        if release_profile == RELEASE_PROFILE_CLIENT
        else manifest.get("release_channel")
    )
    if (
        manifest.get("version") != version
        or not isinstance(source, dict)
        or source.get("commit") != commit
        or source.get("clean") is not clean
        or expected_channel != channel
    ):
        raise ValueError("Installer archive and payload build identities do not match")

    if release_profile == RELEASE_PROFILE_CLIENT and (
        channel not in {"candidate", "release"}
        or not SOURCE_COMMIT_PATTERN.fullmatch(commit)
        or clean is not True
    ):
        raise ValueError("Customer installer requires clean identified candidate or release source")
    return identity


def _read_installed_build_identity(install_root: Path) -> dict[str, object] | None:
    identity_path = Path(install_root) / BUILD_IDENTITY_FILE_NAME
    if not identity_path.is_file() or identity_path.is_symlink():
        return None
    try:
        payload = json.loads(identity_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    version = payload.get("version")
    commit = payload.get("source_commit")
    if not isinstance(version, str) or SEMVER_PATTERN.fullmatch(version) is None:
        return None
    if not isinstance(commit, str) or not (
        SOURCE_COMMIT_PATTERN.fullmatch(commit) or commit == "unavailable"
    ):
        return None
    return {"version": version, "source_commit": commit}


def _matches_incomplete_fresh_install(
    install_root: Path,
    build_identity: dict[str, object],
) -> bool:
    """Recognize one exact, safely retryable first-install failure receipt."""
    target = Path(install_root) / PACKAGE_RECEIPT_FILE_NAME
    if target.is_symlink() or not target.is_file():
        return False
    try:
        if target.stat().st_size > 64 * 1024:
            return False
        receipt = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, ValueError):
        return False
    return bool(
        isinstance(receipt, dict)
        and receipt.get("schema_version") == 1
        and receipt.get("authority") == "verified_official_package"
        and receipt.get("operation") == "install"
        and receipt.get("status") == "NEEDS_HUMAN"
        and receipt.get("previous_version") is None
        and receipt.get("target_version") == build_identity.get("version")
    )


def classify_package_operation(
    install_root: Path,
    build_identity: dict[str, object] | None,
) -> str:
    """Classify the customer-visible package operation before changing files."""
    install_root = Path(install_root)
    if not install_root.exists():
        return "install"
    installed = _read_installed_build_identity(install_root)
    if installed is None or build_identity is None:
        return "repair"
    installed_version = tuple(int(part) for part in str(installed["version"]).split("."))
    candidate_version = tuple(int(part) for part in str(build_identity["version"]).split("."))
    if candidate_version < installed_version:
        return "rollback"
    if (
        candidate_version == installed_version
        and build_identity.get("source_commit") == installed.get("source_commit")
    ):
        if _matches_incomplete_fresh_install(install_root, build_identity):
            return "install"
        return "repair"
    return "update"


def build_code_rollback_confirmation(
    installed_identity: dict[str, object],
    candidate_identity: dict[str, object],
) -> str:
    """Bind explicit rollback authority to the exact current and target builds."""
    payload = {
        "current": {
            "version": installed_identity.get("version"),
            "source_commit": installed_identity.get("source_commit"),
        },
        "target": {
            "version": candidate_identity.get("version"),
            "source_commit": candidate_identity.get("source_commit"),
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def describe_package_operation(
    install_root: Path,
    build_identity: dict[str, object] | None,
) -> dict[str, object]:
    """Return one bounded, read-only operation description for every installer UI."""
    installed_identity = _read_installed_build_identity(install_root)
    operation = classify_package_operation(install_root, build_identity)
    titles = {
        "install": "Install Elefante",
        "repair": "Repair Elefante",
        "update": "Update Elefante",
        "rollback": "Roll Back Elefante",
    }
    completion = {
        "install": "Installation verified — Elefante, agent connection, and Recall are ready.",
        "repair": "Repair verified — Elefante, agent connection, and Recall are ready.",
        "update": "Update verified — Elefante, agent connection, and Recall are ready.",
        "rollback": "Code rollback verified — Elefante, agent connection, and Recall are ready.",
    }
    confirmation_token = None
    if operation == "rollback" and installed_identity is not None and build_identity is not None:
        confirmation_token = build_code_rollback_confirmation(
            installed_identity,
            build_identity,
        )
    retained_rollback = describe_retained_code_rollback(install_root)
    return {
        "schema_version": 1,
        "operation": operation,
        "title": titles[operation],
        "current_version": (
            str(installed_identity["version"])
            if installed_identity is not None
            else None
        ),
        "target_version": (
            str(build_identity["version"])
            if build_identity is not None
            else None
        ),
        "requires_confirmation": operation == "rollback",
        "confirmation_token": confirmation_token,
        "data_effect": "preserved_not_restored",
        "completion": completion[operation],
        "retained_rollback": retained_rollback,
    }


def _read_customer_build_identity(root: Path) -> dict[str, object] | None:
    """Read the complete clean customer identity required for retained rollback."""
    identity_path = Path(root) / BUILD_IDENTITY_FILE_NAME
    if identity_path.is_symlink() or not identity_path.is_file():
        return None
    try:
        payload = json.loads(
            identity_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        return None
    version = payload.get("version")
    commit = payload.get("source_commit")
    channel = payload.get("release_channel")
    if (
        not isinstance(version, str)
        or SEMVER_PATTERN.fullmatch(version) is None
        or not isinstance(commit, str)
        or SOURCE_COMMIT_PATTERN.fullmatch(commit) is None
        or payload.get("source_clean") is not True
        or channel not in {"candidate", "release"}
    ):
        return None
    return {
        "version": version,
        "source_commit": commit,
        "source_clean": True,
        "release_channel": channel,
    }


def _customer_identity_from_package(
    build_identity: dict[str, object] | None,
) -> dict[str, object] | None:
    if build_identity is None:
        return None
    identity = {
        "version": build_identity.get("version"),
        "source_commit": build_identity.get("source_commit"),
        "source_clean": build_identity.get("source_clean"),
        "release_channel": build_identity.get("release_channel"),
    }
    if (
        not isinstance(identity["version"], str)
        or SEMVER_PATTERN.fullmatch(str(identity["version"])) is None
        or not isinstance(identity["source_commit"], str)
        or SOURCE_COMMIT_PATTERN.fullmatch(str(identity["source_commit"])) is None
        or identity["source_clean"] is not True
        or identity["release_channel"] not in {"candidate", "release"}
    ):
        return None
    return identity


def _path_is_within(path: Path, parent: Path) -> bool:
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
    except ValueError:
        return False
    return True


def fingerprint_preserved_data(
    data_root: Path,
    *,
    home: Path,
    install_root: Path,
) -> dict[str, object]:
    """Hash the exact data tree without returning names or customer content."""
    raw_data_root = Path(data_root).expanduser()
    home = Path(home).expanduser().resolve()
    install_root = Path(install_root).expanduser().resolve()
    if raw_data_root.is_symlink():
        raise ValueError("Managed Elefante data directory cannot be a symlink")
    data_root = raw_data_root.resolve()
    if data_root in {Path(data_root.anchor), home, home / ".elefante", install_root}:
        raise ValueError("Managed Elefante data directory is too broad or unsafe")
    if _path_is_within(install_root, data_root):
        raise ValueError("Managed Elefante data directory cannot contain the app root")
    if not data_root.exists():
        return {
            "present": False,
            "file_count": 0,
            "total_bytes": 0,
            "source_sha256": _stable_sha256([]),
        }
    if not data_root.is_dir():
        raise ValueError("Managed Elefante data path is not a directory")

    entries: list[dict[str, object]] = []
    for path in sorted(
        data_root.rglob("*"),
        key=lambda item: item.relative_to(data_root).as_posix(),
    ):
        relative = path.relative_to(data_root)
        if relative.parts and relative.parts[0] == "backups":
            continue
        if path.is_symlink():
            raise ValueError("Managed Elefante data contains a symlink")
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError("Managed Elefante data contains an unsupported entry")
        size = path.stat().st_size
        entries.append(
            {
                "path": relative.as_posix(),
                "size": size,
                "sha256": _file_sha256(path),
            }
        )
    return {
        "present": True,
        "file_count": len(entries),
        "total_bytes": sum(int(entry["size"]) for entry in entries),
        "source_sha256": _stable_sha256(entries),
    }


def _uninstall_manifest_state(
    *,
    home: Path,
    install_root: Path,
    installed_identity: dict[str, object],
) -> tuple[Path, Path, dict[str, object]]:
    manifest_path = Path(home).expanduser().resolve() / ".elefante" / INSTALL_MANIFEST_FILE_NAME
    manifest = _strict_json_file(manifest_path)
    runtime = manifest.get("runtime")
    files = manifest.get("files")
    commands = manifest.get("commands", {})
    if (
        manifest.get("schema_version") != 3
        or not isinstance(runtime, dict)
        or not isinstance(files, dict)
        or not isinstance(commands, dict)
        or runtime.get("scope") != "customer"
        or runtime.get("version") != installed_identity.get("version")
        or runtime.get("source_commit") != installed_identity.get("source_commit")
        or runtime.get("source_clean") is not True
        or runtime.get("release_channel") != installed_identity.get("release_channel")
    ):
        raise ValueError("Install manifest does not match the installed customer product")
    raw_app_root = runtime.get("app_root")
    raw_data_root = runtime.get("data_root")
    if (
        not isinstance(raw_app_root, str)
        or not Path(raw_app_root).is_absolute()
        or Path(raw_app_root).expanduser().resolve()
        != Path(install_root).expanduser().resolve()
        or not isinstance(raw_data_root, str)
        or not Path(raw_data_root).is_absolute()
    ):
        raise ValueError("Install manifest has invalid managed paths")
    data_root = Path(raw_data_root).expanduser()
    if data_root.is_symlink():
        raise ValueError("Managed Elefante data directory cannot be a symlink")
    return manifest_path, data_root.resolve(), manifest


def build_uninstall_confirmation(state: dict[str, object]) -> str:
    """Bind uninstall authority to one exact package, install, manifest, and data state."""
    return _stable_sha256({"operation": "uninstall", "state": state})


def _unavailable_uninstall(reason_code: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "uninstall",
        "title": "Uninstall Elefante",
        "available": False,
        "reason_code": reason_code,
        "data_effect": "preserved",
        "requires_confirmation": True,
    }


def describe_package_uninstall(
    install_root: Path,
    build_identity: dict[str, object] | None,
    *,
    release_profile: str,
    home: Path,
) -> dict[str, object]:
    """Return one read-only exact uninstall plan for the matching official package."""
    install_root = Path(install_root).expanduser().resolve()
    home = Path(home).expanduser().resolve()
    if release_profile != RELEASE_PROFILE_CLIENT:
        return _unavailable_uninstall("OFFICIAL_CLIENT_PACKAGE_REQUIRED")
    package_identity = _customer_identity_from_package(build_identity)
    if package_identity is None:
        return _unavailable_uninstall("PACKAGE_IDENTITY_INVALID")
    if install_root.is_symlink() or not install_root.is_dir():
        return _unavailable_uninstall("INSTALLED_PRODUCT_NOT_FOUND")
    installed_identity = _read_customer_build_identity(install_root)
    if installed_identity is None:
        return _unavailable_uninstall("INSTALLED_IDENTITY_INVALID")
    if installed_identity != package_identity:
        return _unavailable_uninstall("MATCHING_OFFICIAL_PACKAGE_REQUIRED")
    try:
        manifest_path, data_root, manifest = _uninstall_manifest_state(
            home=home,
            install_root=install_root,
            installed_identity=installed_identity,
        )
        data_state = fingerprint_preserved_data(
            data_root,
            home=home,
            install_root=install_root,
        )
    except (OSError, ValueError):
        return _unavailable_uninstall("INSTALLATION_STATE_INVALID")
    state = {
        "installed_identity": installed_identity,
        "package_identity": package_identity,
        "install_root": str(install_root),
        "data_root": str(data_root),
        "install_manifest_sha256": _file_sha256(manifest_path),
        "owned_file_records": len(manifest["files"]),
        "owned_command_records": len(manifest.get("commands", {})),
        "data_state": data_state,
    }
    return {
        "schema_version": 1,
        "operation": "uninstall",
        "title": "Uninstall Elefante",
        "available": True,
        "current_version": installed_identity["version"],
        "package_version": package_identity["version"],
        "requires_confirmation": True,
        "confirmation_token": build_uninstall_confirmation(state),
        "data_effect": "preserved",
        "data_present": data_state["present"],
        "data_file_count": data_state["file_count"],
        "data_total_bytes": data_state["total_bytes"],
        "verified_backup_required": data_state["present"],
        "support_report_recommended": True,
        "completion": "Uninstall verified — app removed and memories preserved for reinstall.",
    }


def fingerprint_payload_tree(root: Path) -> dict[str, object]:
    """Fingerprint one dormant payload without following its expected venv symlinks."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Payload fingerprint root is missing or unsafe")
    digest = hashlib.sha256()
    entries = 0
    bytes_count = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        if relative in PAYLOAD_FINGERPRINT_EXCLUDED:
            continue
        if path.is_symlink():
            target = os.readlink(path)
            encoded_target = target.encode("utf-8", errors="surrogateescape")
            digest.update(b"L\0" + relative.encode("utf-8") + b"\0" + encoded_target + b"\0")
            entries += 1
            bytes_count += len(encoded_target)
            continue
        if path.is_dir():
            digest.update(b"D\0" + relative.encode("utf-8") + b"\0")
            entries += 1
            continue
        if not path.is_file():
            raise ValueError("Payload contains an unsupported filesystem entry")
        size = path.stat().st_size
        digest.update(b"F\0" + relative.encode("utf-8") + b"\0" + str(size).encode("ascii") + b"\0")
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
        entries += 1
        bytes_count += size
    return {
        "tree_sha256": digest.hexdigest(),
        "entries": entries,
        "bytes": bytes_count,
    }


def write_retained_code_receipt(
    backup_root: Path,
    *,
    operation_id: str,
    retained_identity: dict[str, object],
    replacement_identity: dict[str, object],
) -> Path:
    """Mark one exact, previously verified payload as an eligible rollback target."""
    backup_root = Path(backup_root)
    if (
        backup_root.is_symlink()
        or not backup_root.is_dir()
        or not backup_root.name.startswith("current.backup.")
        or _read_customer_build_identity(backup_root) != retained_identity
    ):
        raise ValueError("Retained code target is missing, unsafe, or has changed identity")
    fingerprint = fingerprint_payload_tree(backup_root)
    receipt = {
        "schema_version": 1,
        "status": "VERIFIED_PREVIOUS_PRODUCT",
        "operation_id": operation_id,
        "backup_name": backup_root.name,
        "verified_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "retained_identity": retained_identity,
        "replacement_identity": replacement_identity,
        "data_effect": "none",
        "fingerprint": fingerprint,
    }
    target = backup_root / RETAINED_CODE_RECEIPT_FILE_NAME
    temporary = backup_root / f".{RETAINED_CODE_RECEIPT_FILE_NAME}.{operation_id}.tmp"
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)
    return target


def _read_retained_code_receipt(backup_root: Path) -> dict[str, object] | None:
    receipt_path = Path(backup_root) / RETAINED_CODE_RECEIPT_FILE_NAME
    if receipt_path.is_symlink() or not receipt_path.is_file():
        return None
    try:
        payload = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (OSError, ValueError):
        return None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("status") != "VERIFIED_PREVIOUS_PRODUCT"
        or payload.get("backup_name") != Path(backup_root).name
        or payload.get("data_effect") != "none"
    ):
        return None
    retained_identity = payload.get("retained_identity")
    replacement_identity = payload.get("replacement_identity")
    fingerprint = payload.get("fingerprint")
    if (
        not isinstance(retained_identity, dict)
        or not isinstance(replacement_identity, dict)
        or not isinstance(fingerprint, dict)
        or not isinstance(fingerprint.get("tree_sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", str(fingerprint["tree_sha256"]))
        or not isinstance(fingerprint.get("entries"), int)
        or not isinstance(fingerprint.get("bytes"), int)
        or _read_customer_build_identity(backup_root) != retained_identity
    ):
        return None
    return payload


def verify_retained_code_receipt(backup_root: Path) -> dict[str, object] | None:
    """Recompute the retained payload proof immediately before any lifecycle change."""
    receipt = _read_retained_code_receipt(backup_root)
    if receipt is None:
        return None
    try:
        actual = fingerprint_payload_tree(backup_root)
    except (OSError, ValueError):
        return None
    return receipt if actual == receipt.get("fingerprint") else None


def build_retained_rollback_confirmation(
    current_identity: dict[str, object],
    receipt: dict[str, object],
) -> str:
    payload = {
        "current_identity": current_identity,
        "backup_name": receipt.get("backup_name"),
        "retained_identity": receipt.get("retained_identity"),
        "operation_id": receipt.get("operation_id"),
        "tree_sha256": (
            receipt.get("fingerprint", {}).get("tree_sha256")
            if isinstance(receipt.get("fingerprint"), dict)
            else None
        ),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def describe_retained_code_rollback(install_root: Path) -> dict[str, object]:
    """Describe the newest exact verified code backup without returning a path."""
    install_root = Path(install_root)
    current_identity = _read_customer_build_identity(install_root)
    if current_identity is None or not install_root.parent.is_dir():
        return {"available": False}
    for candidate in sorted(
        install_root.parent.glob("current.backup.*"),
        key=lambda path: path.name,
        reverse=True,
    ):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        receipt = _read_retained_code_receipt(candidate)
        if receipt is None:
            continue
        retained_identity = receipt["retained_identity"]
        if (
            not isinstance(retained_identity, dict)
            or receipt.get("replacement_identity") != current_identity
        ):
            continue
        return {
            "available": True,
            "backup_name": candidate.name,
            "current_version": current_identity["version"],
            "target_version": retained_identity["version"],
            "confirmation_token": build_retained_rollback_confirmation(
                current_identity,
                receipt,
            ),
            "data_effect": "preserved_not_restored",
        }
    return {"available": False}


def build_backup_dir(install_root: Path) -> Path:
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = install_root.parent / f"current.backup.{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = install_root.parent / f"current.backup.{stamp}.{suffix}"
        suffix += 1
    return candidate


def build_failed_dir(install_root: Path) -> Path:
    """Reserve a sibling location that preserves one failed candidate payload."""
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate = install_root.parent / f"current.failed.{stamp}"
    suffix = 1
    while candidate.exists():
        candidate = install_root.parent / f"current.failed.{stamp}.{suffix}"
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
    except (Exception, KeyboardInterrupt):
        if staging_root.exists():
            shutil.rmtree(staging_root, ignore_errors=True)
        if backup_root and backup_root.exists() and not install_root.exists():
            shutil.move(str(backup_root), str(install_root))
            backup_root = None
        raise

    return backup_root


def restore_previous_payload(install_root: Path, backup_root: Path) -> Path:
    """Quarantine a failed candidate and restore the exact previous payload."""
    install_root = Path(install_root)
    backup_root = Path(backup_root)
    if (
        backup_root.is_symlink()
        or not backup_root.is_dir()
        or backup_root.parent.resolve() != install_root.parent.resolve()
        or not backup_root.name.startswith("current.backup.")
    ):
        raise ValueError("Previous Elefante payload backup is missing or unsafe")

    failed_root = build_failed_dir(install_root)
    candidate_moved = False
    try:
        if install_root.exists():
            shutil.move(str(install_root), str(failed_root))
            candidate_moved = True
        shutil.move(str(backup_root), str(install_root))
    except (Exception, KeyboardInterrupt):
        if candidate_moved and failed_root.exists() and not install_root.exists():
            shutil.move(str(failed_root), str(install_root))
        raise
    return failed_root


def switch_to_retained_payload(install_root: Path, target_root: Path) -> Path:
    """Switch exact sibling payloads while preserving the displaced current version."""
    install_root = Path(install_root)
    target_root = Path(target_root)
    if (
        install_root.is_symlink()
        or not install_root.is_dir()
        or target_root.is_symlink()
        or not target_root.is_dir()
        or target_root.parent.resolve() != install_root.parent.resolve()
        or not target_root.name.startswith("current.backup.")
    ):
        raise ValueError("Retained code switch target is missing or unsafe")
    displaced_root = build_backup_dir(install_root)
    current_moved = False
    try:
        shutil.move(str(install_root), str(displaced_root))
        current_moved = True
        shutil.move(str(target_root), str(install_root))
    except (Exception, KeyboardInterrupt):
        if current_moved and displaced_root.exists() and not install_root.exists():
            shutil.move(str(displaced_root), str(install_root))
        raise
    return displaced_root


def restore_displaced_payload(
    install_root: Path,
    displaced_root: Path,
    target_root: Path,
) -> None:
    """Reverse a retained-code switch without deleting either payload."""
    install_root = Path(install_root)
    displaced_root = Path(displaced_root)
    target_root = Path(target_root)
    if (
        not install_root.is_dir()
        or install_root.is_symlink()
        or not displaced_root.is_dir()
        or displaced_root.is_symlink()
        or target_root.exists()
        or target_root.parent.resolve() != install_root.parent.resolve()
    ):
        raise ValueError("Retained code rollback paths are missing or unsafe")
    target_moved = False
    try:
        shutil.move(str(install_root), str(target_root))
        target_moved = True
        shutil.move(str(displaced_root), str(install_root))
    except (Exception, KeyboardInterrupt):
        if target_moved and target_root.exists() and not install_root.exists():
            shutil.move(str(target_root), str(install_root))
        raise


def update_runtime_manifest_identity(
    manifest_path: Path,
    *,
    install_root: Path,
    data_dir: Path,
    identity: dict[str, object],
    operation_id: str,
) -> tuple[bytes, int]:
    """Atomically activate one exact customer build while preserving manifest ownership."""
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Elefante install manifest is missing or unsafe")
    original = manifest_path.read_bytes()
    original_mode = manifest_path.stat().st_mode & 0o777
    try:
        payload = json.loads(
            original.decode("utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ValueError("Elefante install manifest is invalid") from error
    runtime = payload.get("runtime") if isinstance(payload, dict) else None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 3
        or not isinstance(runtime, dict)
        or runtime.get("scope") != "customer"
        or Path(str(runtime.get("app_root") or "")).expanduser().resolve()
        != Path(install_root).expanduser().resolve()
        or Path(str(runtime.get("data_root") or "")).expanduser().resolve()
        != Path(data_dir).expanduser().resolve()
    ):
        raise ValueError("Elefante install manifest does not match the active customer product")
    required_identity = {
        "version",
        "source_commit",
        "source_clean",
        "release_channel",
    }
    if set(identity) != required_identity or identity.get("source_clean") is not True:
        raise ValueError("Retained customer build identity is invalid")
    payload["runtime"] = {
        **runtime,
        "app_root": str(Path(install_root).expanduser().resolve()),
        "data_root": str(Path(data_dir).expanduser().resolve()),
        "scope": "customer",
        **identity,
    }
    temporary = manifest_path.parent / f".{manifest_path.name}.{operation_id}.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, original_mode)
        os.replace(temporary, manifest_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return original, original_mode


def restore_runtime_manifest_snapshot(
    manifest_path: Path,
    original: bytes,
    original_mode: int,
    *,
    operation_id: str,
) -> None:
    """Restore exact manifest bytes and mode through an atomic replacement."""
    manifest_path = Path(manifest_path)
    if manifest_path.is_symlink():
        raise ValueError("Elefante install manifest became unsafe")
    temporary = manifest_path.parent / f".{manifest_path.name}.{operation_id}.restore.tmp"
    try:
        temporary.write_bytes(original)
        os.chmod(temporary, original_mode)
        os.replace(temporary, manifest_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def reactivate_previous_install(
    install_root: Path,
    *,
    python_executable: str,
    runner=subprocess.run,
    health_check=None,
    timeout_seconds: float = 15.0,
) -> bool:
    """Ask the restored lifecycle owner to refresh the existing user service."""
    service_script = Path(install_root) / DAEMON_SERVICE_RELATIVE_PATH
    if not service_script.is_file():
        return False
    try:
        result = runner(
            [python_executable, str(service_script), "install", "--apply"],
            cwd=Path(install_root),
            check=False,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    check = health_check or daemon_healthy
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if check():
            return True
        time.sleep(0.25)
    return False


def daemon_healthy() -> bool:
    """Verify the exact bounded loopback health contract after reactivation."""
    try:
        with urlopen("http://127.0.0.1:8765/health", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False
    return payload == {
        "status": "ok",
        "service": "elefante-daemon",
        "transport": "streamable-http",
    }


def _run_payload_lifecycle(
    payload_root: Path,
    relative_script: Path,
    arguments: list[str],
    *,
    python_executable: str,
    runner=subprocess.run,
) -> bool:
    script = Path(payload_root) / relative_script
    if not script.is_file():
        return False
    try:
        result = runner(
            [python_executable, str(script), *arguments],
            cwd=Path(payload_root),
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0


def prepare_existing_install(
    payload_root: Path,
    install_root: Path,
    *,
    python_executable: str,
    home: Path | None = None,
    data_dir: Path | None = None,
    runner=subprocess.run,
    reactivator=reactivate_previous_install,
    product_verifier=None,
) -> bool:
    """Pause an existing managed install and create a verified data backup."""
    install_root = Path(install_root)
    if not install_root.exists():
        return False
    if install_root.is_symlink() or not install_root.is_dir():
        raise RuntimeError("Existing Elefante install root is unsafe")

    home = Path(home or Path.home()).expanduser().resolve()
    elefante_home = home / ".elefante"
    raw_data_dir = Path(
        data_dir
        if data_dir is not None
        else resolve_managed_data_dir(install_root, home=home)
    ).expanduser()
    if raw_data_dir.is_symlink():
        raise RuntimeError("Managed Elefante data directory cannot be a symlink")
    data_dir = raw_data_dir.resolve()

    def restore_unchanged_product() -> bool:
        verifier = product_verifier or verify_installed_product
        return bool(
            reactivator(
                install_root,
                python_executable=python_executable,
                runner=runner,
            )
            and verifier(install_root)
        )

    try:
        stopped = _run_payload_lifecycle(
            payload_root,
            DAEMON_SERVICE_RELATIVE_PATH,
            ["stop", "--apply"],
            python_executable=python_executable,
            runner=runner,
        )
    except KeyboardInterrupt:
        if not restore_unchanged_product():
            raise RuntimeError(
                "Repair/update was interrupted and the unchanged product could not be verified"
            ) from None
        raise
    if not stopped:
        raise RuntimeError("Existing Elefante service could not be stopped safely")

    if not data_dir.exists():
        return True
    try:
        backed_up = _run_payload_lifecycle(
            payload_root,
            BACKUP_SCRIPT_RELATIVE_PATH,
            [
                "--elefante-home",
                str(elefante_home),
                "--data-dir",
                str(data_dir),
                "--out-dir",
                str(managed_backup_dir(data_dir)),
            ],
            python_executable=python_executable,
            runner=runner,
        )
    except KeyboardInterrupt:
        if not restore_unchanged_product():
            raise RuntimeError(
                "Repair/update was interrupted and the unchanged product could not be verified"
            ) from None
        raise
    if backed_up:
        return True
    if not restore_unchanged_product():
        raise RuntimeError(
            "Verified safety backup failed and the unchanged product could not be verified"
        )
    raise RuntimeError("Verified safety backup failed; the existing install was left unchanged")


def verify_installed_product(
    install_root: Path,
    *,
    runner=subprocess.run,
) -> bool:
    """Prove the installed runtime, service, host connection, and Recall path."""
    install_root = Path(install_root)
    python_path = install_root / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    doctor_path = install_root / DOCTOR_SCRIPT_RELATIVE_PATH
    if not python_path.is_file() or not doctor_path.is_file():
        return False
    try:
        result = runner(
            [str(python_path), str(doctor_path), "--json"],
            cwd=install_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        report = json.loads(result.stdout)
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(report, dict):
        return False
    recall = report.get("recall")
    recall_ready = isinstance(recall, dict) and (
        recall.get("required") is not True or recall.get("ready") is True
    )
    return bool(
        result.returncode == 0
        and report.get("ready") is True
        and report.get("customer_ready") is True
        and recall_ready
    )


def verify_first_run_acceptance(install_root: Path) -> bool:
    """Independently verify the content-free fresh-install acceptance receipt."""
    target = Path(install_root) / FIRST_RUN_RECEIPT_FILE_NAME
    try:
        receipt = _strict_json_file(target)
    except ValueError:
        return False
    if os.name != "nt" and target.stat().st_mode & 0o777 != 0o600:
        return False
    expected_fields = {
        "schema_version",
        "operation",
        "status",
        "finished_at",
        "checks",
        "acceptance_operation_id",
        "backup_operation_id",
        "initial_backup",
        "memory_content_included",
        "project_path_included",
        "next_action",
    }
    checks = receipt.get("checks")
    expected_checks = {
        "project_isolation",
        "disposable_recall",
        "acceptance_cleanup",
        "initial_backup",
    }
    if not (
        set(receipt) == expected_fields
        and receipt.get("schema_version") == 1
        and receipt.get("operation") == "first_run_acceptance"
        and receipt.get("status") == "VERIFIED_COMPLETE"
        and receipt.get("memory_content_included") is False
        and receipt.get("project_path_included") is False
        and receipt.get("next_action") == "open_elefante_home"
        and isinstance(receipt.get("finished_at"), str)
        and isinstance(receipt.get("acceptance_operation_id"), str)
        and isinstance(receipt.get("backup_operation_id"), str)
        and isinstance(checks, list)
        and len(checks) == len(expected_checks)
        and {
            str(check.get("name"))
            for check in checks
            if isinstance(check, dict)
            and set(check) == {"name", "passed", "code"}
            and check.get("passed") is True
            and isinstance(check.get("code"), str)
        }
        == expected_checks
    ):
        return False
    backup = receipt.get("initial_backup")
    return bool(
        isinstance(backup, dict)
        and set(backup) == {"archive_name", "archive_sha256"}
        and isinstance(backup.get("archive_name"), str)
        and bool(str(backup["archive_name"]).strip())
        and "/" not in str(backup["archive_name"])
        and "\\" not in str(backup["archive_name"])
        and isinstance(backup.get("archive_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", str(backup["archive_sha256"]))
        is not None
    )


def _create_uninstall_safety_backup(
    *,
    payload_root: Path,
    home: Path,
    data_root: Path,
    python_executable: str,
    runner=subprocess.run,
) -> Path | None:
    """Create and independently preflight one new verified backup."""
    if not data_root.exists():
        return None
    backup_dir = managed_backup_dir(data_root)
    before = set(backup_dir.glob("elefante_data_backup_*.zip")) if backup_dir.is_dir() else set()
    backed_up = _run_payload_lifecycle(
        payload_root,
        BACKUP_SCRIPT_RELATIVE_PATH,
        [
            "--elefante-home",
            str(Path(home) / ".elefante"),
            "--data-dir",
            str(data_root),
            "--out-dir",
            str(backup_dir),
        ],
        python_executable=python_executable,
        runner=runner,
    )
    if not backed_up:
        raise RuntimeError("Verified uninstall safety backup failed")
    after = set(backup_dir.glob("elefante_data_backup_*.zip"))
    created = sorted(after - before)
    if len(created) != 1 or created[0].is_symlink() or created[0].stat().st_size <= 0:
        raise RuntimeError("Uninstall backup did not produce one safe archive")
    archive = created[0]
    verified = _run_payload_lifecycle(
        payload_root,
        RESTORE_SCRIPT_RELATIVE_PATH,
        [
            "--elefante-home",
            str(Path(home) / ".elefante"),
            "--archive",
            str(archive),
        ],
        python_executable=python_executable,
        runner=runner,
    )
    if not verified:
        raise RuntimeError("Uninstall backup failed independent restore preflight")
    return archive


def _detach_owned_surfaces_for_uninstall(
    *,
    payload_root: Path,
    home: Path,
    python_executable: str,
    runner=subprocess.run,
) -> dict[str, object]:
    script = Path(payload_root) / UNINSTALL_SCRIPT_RELATIVE_PATH
    if not script.is_file() or script.is_symlink():
        raise RuntimeError("Official package has no safe uninstaller")
    try:
        result = runner(
            [
                python_executable,
                str(script),
                "--apply",
                "--home",
                str(home),
                "--json",
            ],
            cwd=Path(payload_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError as error:
        raise RuntimeError("Owned integrations could not be detached") from error
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    try:
        payload = json.loads(lines[-1]) if lines else None
    except json.JSONDecodeError as error:
        raise RuntimeError("Uninstaller returned an invalid receipt") from error
    if (
        result.returncode != 0
        or not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("operation") != "detach_owned_surfaces"
        or payload.get("applied") is not True
    ):
        raise RuntimeError("Owned integrations could not be detached")
    count_fields = (
        "removed_command_count",
        "preserved_command_count",
        "removed_file_count",
        "preserved_file_count",
    )
    if any(not isinstance(payload.get(field), int) for field in count_fields):
        raise RuntimeError("Uninstaller returned invalid ownership counts")
    return {field: int(payload[field]) for field in count_fields}


def _clear_runtime_manifest_for_uninstall(
    *,
    home: Path,
    install_root: Path,
    data_root: Path,
    installed_identity: dict[str, object],
    operation_id: str,
) -> tuple[Path, bytes, int]:
    manifest_path, manifest_data_root, payload = _uninstall_manifest_state(
        home=home,
        install_root=install_root,
        installed_identity=installed_identity,
    )
    if manifest_data_root != data_root:
        raise ValueError("Install manifest data root changed during uninstall")
    original = manifest_path.read_bytes()
    original_mode = manifest_path.stat().st_mode & 0o777
    payload.pop("runtime", None)
    temporary = manifest_path.parent / f".{manifest_path.name}.{operation_id}.uninstall.tmp"
    try:
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.chmod(temporary, original_mode)
        os.replace(temporary, manifest_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return manifest_path, original, original_mode


def _write_uninstall_receipts(
    *,
    home: Path,
    operation_id: str,
    status: str,
    installed_identity: dict[str, object],
    install_root: Path,
    data_root: Path,
    data_state: dict[str, object],
    backup_path: Path | None,
    ownership: dict[str, object],
    app_removed: bool,
    next_action: str,
) -> tuple[Path, Path]:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    backup = (
        {
            "name": backup_path.name,
            "sha256": _file_sha256(backup_path),
        }
        if backup_path is not None
        else None
    )
    pointer = {
        "schema_version": 1,
        "operation": "uninstall",
        "operation_id": operation_id,
        "status": status,
        "authority": "verified_official_package",
        "recorded_at": now,
        "app_root": str(Path(install_root).resolve()),
        "data_root": str(Path(data_root).resolve()),
        "installed_identity": installed_identity,
        "data_state": data_state,
        "backup": backup,
        "app_removed": app_removed,
        "next_action": next_action,
    }
    pointer_path = _write_private_json(data_preservation_path(home), pointer)
    receipt_payload = {
        "schema_version": 1,
        "operation": "uninstall",
        "operation_id": operation_id,
        "status": status,
        "authority": "verified_official_package",
        "recorded_at": now,
        "version": installed_identity["version"],
        "data_preserved": data_state.get("present") is True,
        "data_file_count": data_state.get("file_count"),
        "data_total_bytes": data_state.get("total_bytes"),
        "backup_verified": backup is not None or data_state.get("present") is False,
        "app_removed": app_removed,
        **ownership,
        "next_action": next_action,
    }
    receipts_dir = Path(home) / ".elefante" / UNINSTALL_RECEIPTS_DIRECTORY
    receipt_path = _write_private_json(
        receipts_dir / f"uninstall-{operation_id}.json",
        receipt_payload,
    )
    return pointer_path, receipt_path


def execute_package_uninstall(
    *,
    payload_root: Path,
    install_root: Path,
    build_identity: dict[str, object] | None,
    release_profile: str,
    confirmation_token: str,
    python_executable: str,
    home: Path,
    runner=subprocess.run,
) -> dict[str, object]:
    """Execute one exact data-preserving official-package uninstall."""
    install_root = Path(install_root).expanduser().resolve()
    payload_root = Path(payload_root).expanduser().resolve()
    home = Path(home).expanduser().resolve()
    plan = describe_package_uninstall(
        install_root,
        build_identity,
        release_profile=release_profile,
        home=home,
    )
    if plan.get("available") is not True:
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_NO_CHANGE",
            "reason_code": plan.get("reason_code"),
            "next_action": "use_matching_official_package",
        }
    if confirmation_token != plan.get("confirmation_token"):
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_NO_CHANGE",
            "reason_code": "CONFIRMATION_MISMATCH",
            "next_action": "review_uninstall_plan",
        }
    if (
        payload_root.is_symlink()
        or not payload_root.is_dir()
        or _path_is_within(payload_root, install_root)
        or _path_is_within(install_root, payload_root)
    ):
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_NO_CHANGE",
            "reason_code": "PACKAGE_LOCATION_UNSAFE",
            "next_action": "extract_matching_package_outside_elefante_app",
        }

    installed_identity = _read_customer_build_identity(install_root)
    if installed_identity is None:
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_NO_CHANGE",
            "reason_code": "INSTALLATION_STATE_CHANGED",
            "next_action": "review_uninstall_plan",
        }
    try:
        _, data_root, _ = _uninstall_manifest_state(
            home=home,
            install_root=install_root,
            installed_identity=installed_identity,
        )
        expected_data_state = fingerprint_preserved_data(
            data_root,
            home=home,
            install_root=install_root,
        )
    except (OSError, ValueError):
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_NO_CHANGE",
            "reason_code": "INSTALLATION_STATE_CHANGED",
            "next_action": "review_uninstall_plan",
        }
    operation_id = str(uuid4())
    ownership: dict[str, object] = {
        "removed_command_count": 0,
        "preserved_command_count": 0,
        "removed_file_count": 0,
        "preserved_file_count": 0,
    }
    backup_path: Path | None = None
    detachment_started = False
    detachment_completed = False

    def exact_pre_removal_rollback_verified(restored: bool) -> bool:
        if not restored:
            return False
        if not detachment_started:
            return True
        return bool(
            detachment_completed
            and ownership["removed_command_count"] == 0
            and ownership["removed_file_count"] == 0
        )

    stopped = _run_payload_lifecycle(
        payload_root,
        DAEMON_SERVICE_RELATIVE_PATH,
        ["stop", "--apply"],
        python_executable=python_executable,
        runner=runner,
    )
    if not stopped:
        return {
            "success": False,
            "operation": "uninstall",
            "status": "NEEDS_HUMAN",
            "reason_code": "SERVICE_STOP_NOT_VERIFIED",
            "next_action": "create_support_report",
        }
    try:
        after_stop_plan = describe_package_uninstall(
            install_root,
            build_identity,
            release_profile=release_profile,
            home=home,
        )
        if after_stop_plan.get("confirmation_token") != confirmation_token:
            raise RuntimeError("Uninstall plan became stale after the service stopped")
        backup_path = _create_uninstall_safety_backup(
            payload_root=payload_root,
            home=home,
            data_root=data_root,
            python_executable=python_executable,
            runner=runner,
        )
        detachment_started = True
        ownership = _detach_owned_surfaces_for_uninstall(
            payload_root=payload_root,
            home=home,
            python_executable=python_executable,
            runner=runner,
        )
        detachment_completed = True
        if fingerprint_preserved_data(
            data_root,
            home=home,
            install_root=install_root,
        ) != expected_data_state:
            raise RuntimeError("Managed data changed during uninstall preparation")
    except (OSError, RuntimeError, ValueError) as error:
        restored = bool(
            reactivate_previous_install(
                install_root,
                python_executable=python_executable,
                runner=runner,
            )
            and verify_installed_product(install_root, runner=runner)
        )
        rolled_back = exact_pre_removal_rollback_verified(restored)
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_ROLLED_BACK" if rolled_back else "NEEDS_HUMAN",
            "reason_code": "UNINSTALL_PREPARATION_FAILED",
            "detail": str(error),
            "next_action": (
                "repair_with_matching_official_package"
                if rolled_back
                else "create_support_report"
            ),
        }

    try:
        _write_uninstall_receipts(
            home=home,
            operation_id=operation_id,
            status="RUNNING",
            installed_identity=installed_identity,
            install_root=install_root,
            data_root=data_root,
            data_state=expected_data_state,
            backup_path=backup_path,
            ownership=ownership,
            app_removed=False,
            next_action="complete_uninstall",
        )
    except (OSError, ValueError) as error:
        restored = bool(
            reactivate_previous_install(
                install_root,
                python_executable=python_executable,
                runner=runner,
            )
            and verify_installed_product(install_root, runner=runner)
        )
        rolled_back = exact_pre_removal_rollback_verified(restored)
        return {
            "success": False,
            "operation": "uninstall",
            "status": "FAILED_ROLLED_BACK" if rolled_back else "NEEDS_HUMAN",
            "reason_code": "UNINSTALL_RECEIPT_NOT_WRITABLE",
            "detail": str(error),
            "next_action": (
                "repair_with_matching_official_package"
                if rolled_back
                else "create_support_report"
            ),
        }
    quarantine = install_root.parent / f"current.uninstall.{operation_id}"
    manifest_snapshot: tuple[Path, bytes, int] | None = None
    moved = False
    try:
        if quarantine.exists() or quarantine.is_symlink():
            raise RuntimeError("Uninstall quarantine target already exists")
        shutil.move(str(install_root), str(quarantine))
        moved = True
        manifest_snapshot = _clear_runtime_manifest_for_uninstall(
            home=home,
            install_root=install_root,
            data_root=data_root,
            installed_identity=installed_identity,
            operation_id=operation_id,
        )
        if install_root.exists():
            raise RuntimeError("Installed app root remained after removal")
        if fingerprint_preserved_data(
            data_root,
            home=home,
            install_root=install_root,
        ) != expected_data_state:
            raise RuntimeError("Managed data changed while app code was removed")
        shutil.rmtree(quarantine)
    except (OSError, RuntimeError, ValueError) as error:
        if moved and quarantine.is_dir() and not install_root.exists():
            try:
                if manifest_snapshot is not None:
                    restore_runtime_manifest_snapshot(
                        manifest_snapshot[0],
                        manifest_snapshot[1],
                        manifest_snapshot[2],
                        operation_id=operation_id,
                    )
                shutil.move(str(quarantine), str(install_root))
                restored = bool(
                    reactivate_previous_install(
                        install_root,
                        python_executable=python_executable,
                        runner=runner,
                    )
                    and verify_installed_product(install_root, runner=runner)
                )
            except (OSError, ValueError):
                restored = False
        else:
            restored = False
        rolled_back = exact_pre_removal_rollback_verified(restored)
        status = "FAILED_ROLLED_BACK" if rolled_back else "NEEDS_HUMAN"
        next_action = (
            "repair_with_matching_official_package"
            if rolled_back
            else "create_support_report"
        )
        try:
            _write_uninstall_receipts(
                home=home,
                operation_id=operation_id,
                status=status,
                installed_identity=installed_identity,
                install_root=install_root,
                data_root=data_root,
                data_state=expected_data_state,
                backup_path=backup_path,
                ownership=ownership,
                app_removed=not install_root.exists(),
                next_action=next_action,
            )
        except (OSError, ValueError):
            pass
        return {
            "success": False,
            "operation": "uninstall",
            "status": status,
            "reason_code": "APP_REMOVAL_NOT_VERIFIED",
            "detail": str(error),
            "next_action": next_action,
        }

    try:
        pointer_path, receipt_path = _write_uninstall_receipts(
            home=home,
            operation_id=operation_id,
            status="VERIFIED_COMPLETE",
            installed_identity=installed_identity,
            install_root=install_root,
            data_root=data_root,
            data_state=expected_data_state,
            backup_path=backup_path,
            ownership=ownership,
            app_removed=True,
            next_action="reinstall_from_official_package_when_ready",
        )
    except (OSError, ValueError) as error:
        return {
            "success": False,
            "operation": "uninstall",
            "status": "NEEDS_HUMAN",
            "reason_code": "FINAL_RECEIPT_NOT_VERIFIED",
            "detail": str(error),
            "data_preserved": True,
            "app_removed": True,
            "next_action": "retain_backup_and_reinstall_from_matching_package",
        }
    return {
        "success": True,
        "operation": "uninstall",
        "status": "VERIFIED_COMPLETE",
        "data_preserved": True,
        "backup_verified": backup_path is not None or expected_data_state["present"] is False,
        "app_removed": True,
        **ownership,
        "data_preservation_receipt": str(pointer_path),
        "receipt": str(receipt_path),
        "next_action": "reinstall_from_official_package_when_ready",
    }


def read_failed_installer_stage(install_root: Path) -> str:
    """Read one allowlisted failed stage from the delegated install summary."""
    summary = Path(install_root) / INSTALL_SUMMARY_FILE_NAME
    if (
        summary.is_symlink()
        or not summary.is_file()
        or summary.stat().st_size > MAX_LIFECYCLE_JSON_BYTES
    ):
        return "unknown"
    try:
        lines = summary.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return "unknown"
    for line in lines:
        fields = line.split("|", 3)
        if len(fields) < 3 or fields[2] not in {"FAILED", "BLOCKED", "CANCELLED"}:
            continue
        stage = fields[0].strip()
        if stage in PACKAGE_FAILED_STAGES:
            return stage
    return "unknown"


def write_package_receipt(
    root: Path,
    *,
    operation_id: str,
    operation: str,
    status: str,
    started_at: str,
    previous_version: str | None,
    target_version: str | None,
    safety_backup: str,
    product_verification: bool,
    rollback: str,
    recoverable: bool,
    next_action: str,
    failed_candidate_name: str | None = None,
    first_run_verification: bool | None = None,
    failed_stage: str | None = None,
) -> Path:
    """Write one content-free package acceptance receipt beside installer evidence."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    normalized_failed_stage = None if status == "VERIFIED_COMPLETE" else str(
        failed_stage or "unknown"
    )
    if normalized_failed_stage is not None and normalized_failed_stage not in PACKAGE_FAILED_STAGES:
        raise ValueError("Package failed stage is invalid")
    finished_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    receipt = {
        "schema_version": 1,
        "operation_id": operation_id,
        "operation": operation,
        "status": status,
        "authority": "verified_official_package",
        "started_at": started_at,
        "finished_at": finished_at,
        "previous_version": previous_version,
        "target_version": target_version,
        "checks": [
            {
                "name": "safety_backup",
                "passed": safety_backup in {"VERIFIED", "NOT_REQUIRED"},
                "attempts": 1,
                "code": f"SAFETY_BACKUP_{safety_backup}",
            },
            {
                "name": "product_readiness",
                "passed": product_verification,
                "attempts": 1,
                "code": (
                    "RUNTIME_AGENT_RECALL_VERIFIED"
                    if product_verification
                    else "RUNTIME_AGENT_RECALL_NOT_VERIFIED"
                ),
            },
            {
                "name": "first_run_acceptance",
                "passed": first_run_verification is not False,
                "attempts": 1,
                "code": (
                    "FIRST_RUN_ACCEPTANCE_VERIFIED"
                    if first_run_verification is True
                    else "FIRST_RUN_ACCEPTANCE_NOT_REQUIRED"
                    if first_run_verification is None
                    else "FIRST_RUN_ACCEPTANCE_NOT_VERIFIED"
                ),
            },
        ],
        "error_codes": [] if status == "VERIFIED_COMPLETE" else [status],
        "changed": status == "VERIFIED_COMPLETE",
        "rollback": rollback,
        "recoverable": recoverable,
        "next_action": next_action,
        "failed_candidate_name": failed_candidate_name,
        "failed_stage": normalized_failed_stage,
    }
    target = root / PACKAGE_RECEIPT_FILE_NAME
    temporary = root / f".{PACKAGE_RECEIPT_FILE_NAME}.{operation_id}.tmp"
    temporary.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)

    summary = root / INSTALL_SUMMARY_FILE_NAME
    with summary.open("a", encoding="utf-8") as stream:
        stream.write("\nPACKAGE ACCEPTANCE RECEIPT\n")
        stream.write(f"Operation: {operation.title()}\n")
        stream.write(f"Status: {status}\n")
        stream.write(f"Safety backup: {safety_backup}\n")
        stream.write(
            "Runtime, agent connection, and Recall: "
            f"{'VERIFIED' if product_verification else 'NOT VERIFIED'}\n"
        )
        stream.write(
            "First-run project Recall, cleanup, and backup: "
            f"{'VERIFIED' if first_run_verification is True else 'NOT REQUIRED' if first_run_verification is None else 'NOT VERIFIED'}\n"
        )
        stream.write(f"Rollback: {rollback}\n")
        stream.write(f"Failed stage: {normalized_failed_stage or 'none'}\n")
        stream.write(f"Next action: {next_action}\n")
    return target


def build_install_artifact_paths(install_root: Path) -> dict[str, Path]:
    install_root = Path(install_root)
    return {
        "log": install_root / INSTALL_LOG_FILE_NAME,
        "status": install_root / INSTALL_STATUS_FILE_NAME,
        "summary": install_root / INSTALL_SUMMARY_FILE_NAME,
    }


def render_install_artifact_paths(install_root: Path) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Persistent installer files:",
        f"Log file: {paths['log']}",
        f"Status file: {paths['status']}",
        f"Summary file: {paths['summary']}",
    ]


def render_failed_install_guidance(install_root: Path) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    return [
        "Delegated installer failed. Read these persisted files in order:",
        f"1. Summary file: {paths['summary']}",
        f"2. Status file: {paths['status']}",
        f"3. Log file: {paths['log']}",
    ]


def build_install_command(
    install_root: Path,
    *,
    python_executable: str,
    venv_mode: str,
    release_profile: str = RELEASE_PROFILE_DEVELOPER,
    build_identity: dict[str, object] | None = None,
    verbose: bool = False,
    hosts: list[str] | None = None,
    projects: list[str] | None = None,
) -> list[str]:
    paths = build_install_artifact_paths(install_root)
    cmd = [
        python_executable,
        str(Path(install_root) / INSTALL_SCRIPT_RELATIVE_PATH),
        "--log-file",
        str(paths["log"]),
        "--status-file",
        str(paths["status"]),
        "--summary-file",
        str(paths["summary"]),
        "--venv-mode",
        venv_mode,
        "--installation-scope",
        "customer" if release_profile == RELEASE_PROFILE_CLIENT else "developer",
    ]
    if build_identity is not None:
        cmd.extend(
            [
                "--expected-version",
                str(build_identity["version"]),
                "--source-commit",
                str(build_identity["source_commit"]),
                "--release-channel",
                str(build_identity["release_channel"]),
            ]
        )
        if build_identity.get("source_clean") is True:
            cmd.append("--source-clean")
    if release_profile == RELEASE_PROFILE_CLIENT:
        cmd.extend(["--release-profile", RELEASE_PROFILE_CLIENT])
    if verbose:
        cmd.append("--verbose")
    for host in hosts or []:
        cmd.extend(["--host", host])
    for project in projects or []:
        cmd.extend(["--project", project])
    return cmd


def execute_retained_code_rollback(
    *,
    payload_root: Path,
    install_root: Path,
    package_identity: dict[str, object],
    confirmation_token: str,
    python_executable: str,
    home: Path | None = None,
) -> int:
    """Restore the exact prior verified code while leaving memory data in place."""
    install_root = Path(install_root).expanduser().resolve()
    home = Path(home or Path.home()).expanduser().resolve()
    current_identity = _read_customer_build_identity(install_root)
    package_version = package_identity.get("version")
    package_commit = package_identity.get("source_commit")
    if (
        current_identity is None
        or package_version != current_identity.get("version")
        or package_commit != current_identity.get("source_commit")
    ):
        print("ERROR: Retained rollback requires the official package matching current code.")
        return 1
    description = describe_retained_code_rollback(install_root)
    if description.get("available") is not True:
        print("ERROR: No exact verified previous product is available for code rollback.")
        return 1
    expected_confirmation = description.get("confirmation_token")
    if not isinstance(expected_confirmation, str) or confirmation_token != expected_confirmation:
        print("ERROR: Retained code rollback confirmation is missing or stale.")
        return 1
    backup_name = description.get("backup_name")
    if not isinstance(backup_name, str) or not backup_name.startswith("current.backup."):
        print("ERROR: Retained code rollback target is invalid.")
        return 1
    target_root = install_root.parent / backup_name
    retained_receipt = verify_retained_code_receipt(target_root)
    target_identity = _read_customer_build_identity(target_root)
    if (
        retained_receipt is None
        or target_identity is None
        or retained_receipt.get("retained_identity") != target_identity
    ):
        print("ERROR: Retained code rollback target changed after planning.")
        return 1

    try:
        data_dir = resolve_managed_data_dir(install_root, home=home)
    except RuntimeError as error:
        print(f"ERROR: Retained rollback precondition failed: {error}")
        return 1
    data_present = data_dir.is_dir()
    current_product_verified = verify_installed_product(install_root)
    operation_id = str(uuid4())
    started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    manifest_path = home / ".elefante" / INSTALL_MANIFEST_FILE_NAME
    if manifest_path.is_symlink() or not manifest_path.is_file():
        print("ERROR: Retained rollback requires a safe customer install manifest.")
        return 1
    original_manifest = manifest_path.read_bytes()
    original_manifest_mode = manifest_path.stat().st_mode & 0o777

    try:
        prepare_existing_install(
            payload_root,
            install_root,
            python_executable=python_executable,
            home=home,
            data_dir=data_dir,
        )
    except (RuntimeError, KeyboardInterrupt) as error:
        print(f"ERROR: Retained rollback preparation failed: {error}")
        return 1

    displaced_root: Path | None = None
    manifest_changed = False
    product_verified = False
    try:
        displaced_root = switch_to_retained_payload(install_root, target_root)
        update_runtime_manifest_identity(
            manifest_path,
            install_root=install_root,
            data_dir=data_dir,
            identity=target_identity,
            operation_id=operation_id,
        )
        manifest_changed = True
        if not reactivate_previous_install(
            install_root,
            python_executable=python_executable,
        ):
            raise RuntimeError("retained product service did not become healthy")
        if not verify_installed_product(install_root):
            raise RuntimeError("retained product failed Doctor or Recall verification")
        product_verified = True
        retained_newer_receipt: Path | None = None
        if current_product_verified:
            retained_newer_receipt = write_retained_code_receipt(
                displaced_root,
                operation_id=operation_id,
                retained_identity=current_identity,
                replacement_identity=target_identity,
            )
        write_package_receipt(
            install_root,
            operation_id=operation_id,
            operation="rollback",
            status="VERIFIED_COMPLETE",
            started_at=started_at,
            previous_version=str(current_identity["version"]),
            target_version=str(target_identity["version"]),
            safety_backup="VERIFIED" if data_present else "NOT_REQUIRED",
            product_verification=True,
            rollback=(
                "verified_replaced_product_available"
                if retained_newer_receipt is not None
                else "replaced_product_retained_unverified"
            ),
            recoverable=retained_newer_receipt is not None,
            next_action="reopen_home_check_health",
        )
    except (OSError, RuntimeError, ValueError, KeyboardInterrupt) as error:
        print(f"ERROR: Retained code rollback failed verification: {error}")
        rollback_verified = False
        if displaced_root is not None:
            try:
                if not _run_payload_lifecycle(
                    install_root,
                    DAEMON_SERVICE_RELATIVE_PATH,
                    ["stop", "--apply"],
                    python_executable=python_executable,
                ):
                    raise RuntimeError("failed retained product could not be stopped safely")
                restore_displaced_payload(install_root, displaced_root, target_root)
                if manifest_changed:
                    restore_runtime_manifest_snapshot(
                        manifest_path,
                        original_manifest,
                        original_manifest_mode,
                        operation_id=operation_id,
                    )
                rollback_verified = bool(
                    reactivate_previous_install(
                        install_root,
                        python_executable=python_executable,
                    )
                    and verify_installed_product(install_root)
                )
            except (OSError, RuntimeError, ValueError):
                rollback_verified = False
        else:
            rollback_verified = bool(
                reactivate_previous_install(
                    install_root,
                    python_executable=python_executable,
                )
                and verify_installed_product(install_root)
            )
        receipt_root = target_root if target_root.is_dir() else install_root
        try:
            write_package_receipt(
                receipt_root,
                operation_id=operation_id,
                operation="rollback",
                status="FAILED_ROLLED_BACK" if rollback_verified else "NEEDS_HUMAN",
                started_at=started_at,
                previous_version=str(current_identity["version"]),
                target_version=str(target_identity["version"]),
                safety_backup="VERIFIED" if data_present else "NOT_REQUIRED",
                product_verification=False,
                rollback=(
                    "previous_product_restored"
                    if rollback_verified
                    else "manual_recovery_required"
                ),
                recoverable=rollback_verified,
                next_action=(
                    "review_retained_rollback_receipt"
                    if rollback_verified
                    else "create_support_report"
                ),
                failed_candidate_name=(target_root.name if target_root.is_dir() else None),
                failed_stage="retained_rollback",
            )
        except OSError:
            pass
        return 1

    if not product_verified:
        return 1
    print(
        "Code rollback verified: "
        f"{current_identity['version']} -> {target_identity['version']}. Memory data was preserved."
    )
    return 0


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
        "--describe-operation",
        action="store_true",
        help="Print the read-only package operation description as JSON and exit",
    )
    parser.add_argument(
        "--print-managed-backup-path",
        action="store_true",
        help="Print the customer-visible managed backup path and exit",
    )
    parser.add_argument(
        "--describe-uninstall",
        action="store_true",
        help="Print the read-only data-preserving uninstall plan as JSON and exit",
    )
    parser.add_argument(
        "--uninstall",
        metavar="CONFIRMATION_TOKEN",
        help="Run the exact matching package uninstall with its plan token",
    )
    parser.add_argument(
        "--uninstall-interactive",
        action="store_true",
        help="Preview and confirm a data-preserving uninstall interactively",
    )
    parser.add_argument(
        "--confirm-code-rollback",
        help="Exact confirmation token emitted for an older official package",
    )
    parser.add_argument(
        "--rollback-retained",
        metavar="CONFIRMATION_TOKEN",
        help="Restore the locally retained exact previous product with its bound token",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show full subprocess output during installation (passed through to install.py)",
    )
    parser.add_argument(
        "--host",
        action="append",
        help=(
            "Connect an additional detected compatibility-preview host. "
            "Codex is always required and configured for the certified customer lane."
        ),
    )
    parser.add_argument(
        "--project",
        action="append",
        help="Register a fresh-install project as NAME=ABSOLUTE_PATH; repeat as needed.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    bundle_root = resolve_bundle_root(args.bundle_root)
    manifest = load_manifest(bundle_root)
    try:
        release_profile = get_release_profile(manifest)
        payload_root = ensure_bundle_layout(bundle_root, release_profile=release_profile)
        build_identity = load_build_identity(
            bundle_root,
            manifest,
            release_profile=release_profile,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc
    try:
        install_python = resolve_install_python(args.python_executable)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc

    install_root = (
        Path(args.install_root).expanduser().resolve()
        if args.install_root
        else get_default_install_root().resolve()
    )
    customer_home = Path.home().expanduser().resolve()
    if sum(
        bool(selected)
        for selected in (
            args.describe_operation,
            args.describe_uninstall,
            args.print_managed_backup_path,
        )
    ) > 1:
        print("ERROR: Choose one package description operation.")
        raise SystemExit(1)
    if args.print_managed_backup_path:
        try:
            data_root = resolve_managed_data_dir(
                install_root,
                home=customer_home,
            )
        except RuntimeError as error:
            print(f"ERROR: Managed backup path is unavailable: {error}")
            raise SystemExit(1) from error
        print(managed_backup_dir(data_root))
        return
    if args.describe_uninstall:
        print(
            json.dumps(
                describe_package_uninstall(
                    install_root,
                    build_identity,
                    release_profile=release_profile,
                    home=customer_home,
                ),
                sort_keys=True,
            )
        )
        return
    if args.uninstall is not None or args.uninstall_interactive:
        if any(
            (
                args.dry_run,
                args.confirm_code_rollback is not None,
                args.rollback_retained is not None,
                args.uninstall is not None and args.uninstall_interactive,
            )
        ):
            print("ERROR: Uninstall cannot be combined with install or rollback options.")
            raise SystemExit(1)
        confirmation_token = args.uninstall
        if args.uninstall_interactive:
            uninstall_plan = describe_package_uninstall(
                install_root,
                build_identity,
                release_profile=release_profile,
                home=customer_home,
            )
            if uninstall_plan.get("available") is not True:
                print(
                    "ERROR: Data-preserving uninstall is unavailable: "
                    f"{uninstall_plan.get('reason_code', 'UNKNOWN')}"
                )
                raise SystemExit(1)
            print("UNINSTALL ELEFANTE")
            print("- A verified backup will be created first.")
            print("- App files and unchanged Elefante-owned connections will be removed.")
            print("- Memories remain on this computer for reinstall.")
            print("- Modified customer configuration will be preserved.")
            print("Create a support report first if you are diagnosing a problem.")
            try:
                confirmed = input("Type UNINSTALL to continue: ").strip()
            except EOFError:
                confirmed = ""
            if confirmed != "UNINSTALL":
                print("Uninstall cancelled; nothing changed.")
                return
            confirmation_token = str(uninstall_plan["confirmation_token"])
        if not isinstance(confirmation_token, str) or not confirmation_token:
            print("ERROR: Uninstall confirmation is missing or invalid.")
            raise SystemExit(1)
        result = execute_package_uninstall(
            payload_root=payload_root,
            install_root=install_root,
            build_identity=build_identity,
            release_profile=release_profile,
            confirmation_token=confirmation_token,
            python_executable=install_python,
            home=customer_home,
        )
        print(json.dumps(result, sort_keys=True))
        raise SystemExit(0 if result.get("success") is True else 1)

    operation = classify_package_operation(install_root, build_identity)
    previous_identity = _read_installed_build_identity(install_root)
    previous_customer_identity = _read_customer_build_identity(install_root)
    target_customer_identity = (
        {
            "version": build_identity["version"],
            "source_commit": build_identity["source_commit"],
            "source_clean": True,
            "release_channel": build_identity["release_channel"],
        }
        if release_profile == RELEASE_PROFILE_CLIENT and build_identity is not None
        else None
    )
    operation_description = describe_package_operation(install_root, build_identity)
    if args.describe_operation:
        print(json.dumps(operation_description, sort_keys=True))
        return
    operation_id = str(uuid4())
    operation_started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    previous_version = (
        str(previous_identity["version"])
        if previous_identity is not None
        else None
    )
    target_version_value = (
        str(build_identity["version"])
        if build_identity is not None
        else str(manifest.get("version") or "") or None
    )
    try:
        preserved_data_receipt = read_data_preservation_receipt(
            home=customer_home,
            install_root=install_root,
        )
        managed_data_dir = (
            resolve_managed_data_dir(install_root, home=customer_home)
            if install_root.exists() or preserved_data_receipt is not None
            else customer_home / ".elefante" / "data"
        )
    except RuntimeError as error:
        print(f"ERROR: Repair/update precondition failed: {error}")
        raise SystemExit(1) from error
    existing_data_present = managed_data_dir.is_dir()

    print("=" * 68)
    print("ELEFANTE INSTALLER BUNDLE")
    print("=" * 68)
    if manifest.get("version"):
        print(f"Version: {manifest['version']}")
    if manifest.get("platform"):
        print(f"Bundle Platform: {manifest['platform']}")
    if release_profile == RELEASE_PROFILE_CLIENT:
        print("Release Profile: Client (runtime-only payload)")
    if build_identity is not None:
        print(f"Release Channel: {build_identity['release_channel']}")
        print(f"Source Commit: {str(build_identity['source_commit'])[:12]}")
    print(f"Bundle Root: {bundle_root}")
    print(f"Payload Root: {payload_root}")
    print(f"Install Root: {install_root}")
    print(f"Operation: {operation.title()}")
    print(f"Installer Python: {install_python}")

    if args.rollback_retained is not None:
        if args.confirm_code_rollback is not None:
            print("ERROR: Choose retained rollback or older-package rollback, not both.")
            raise SystemExit(1)
        if release_profile != RELEASE_PROFILE_CLIENT or build_identity is None:
            print("ERROR: Retained rollback requires an identified official client package.")
            raise SystemExit(1)
        raise SystemExit(
            execute_retained_code_rollback(
                payload_root=payload_root,
                install_root=install_root,
                package_identity=build_identity,
                confirmation_token=args.rollback_retained,
                python_executable=install_python,
                home=customer_home,
            )
        )

    if operation == "rollback":
        expected_confirmation = operation_description.get("confirmation_token")
        print("Product code rollback does not restore or reverse memory data.")
        print(
            "Elefante will create a verified data backup and restore the current code "
            "automatically if the target fails verification."
        )
        if args.dry_run:
            print(f"Code rollback confirmation: {expected_confirmation}")
        elif (
            not isinstance(expected_confirmation, str)
            or args.confirm_code_rollback != expected_confirmation
        ):
            print("ERROR: Explicit code rollback confirmation is required.")
            print(
                "Review the current and target versions, then re-run with "
                f"--confirm-code-rollback {expected_confirmation}"
            )
            raise SystemExit(1)
    elif args.confirm_code_rollback is not None:
        print("ERROR: Code rollback confirmation is valid only for an older package.")
        raise SystemExit(1)

    first_run_required = (
        release_profile == RELEASE_PROFILE_CLIENT and operation == "install"
    )
    selected_projects = list(getattr(args, "project", None) or [])
    if selected_projects and not first_run_required:
        print("ERROR: Project folders can be selected only for a fresh customer install.")
        raise SystemExit(1)
    existing_registry = managed_data_dir / "projects.json"
    if (
        first_run_required
        and not selected_projects
        and not existing_registry.is_file()
        and not args.dry_run
        and not sys.stdin.isatty()
    ):
        print(
            "ERROR: A fresh unattended install requires at least one "
            "--project NAME=ABSOLUTE_PATH selection."
        )
        raise SystemExit(1)

    install_command = build_install_command(
        install_root,
        python_executable=install_python,
        venv_mode=args.venv_mode,
        release_profile=release_profile,
        build_identity=build_identity,
        verbose=args.verbose,
        hosts=args.host,
        projects=selected_projects,
    )

    if args.dry_run:
        print("Dry run only. No files were changed.")
        print("Delegated installer command:")
        print(" ".join(install_command))
        return

    previous_product_verified = False
    if (
        operation in {"update", "rollback"}
        and previous_customer_identity is not None
        and target_customer_identity is not None
    ):
        previous_product_verified = verify_installed_product(install_root)
        print(
            "Previous product rollback eligibility: "
            f"{'VERIFIED' if previous_product_verified else 'NOT VERIFIED'}"
        )

    first_run_verified: bool | None = False if first_run_required else None
    failed_stage: str | None = None
    try:
        existing_prepared = prepare_existing_install(
            payload_root,
            install_root,
            python_executable=install_python,
            home=customer_home,
            data_dir=managed_data_dir,
        )
    except RuntimeError as error:
        print(f"ERROR: Repair/update precondition failed: {error}")
        raise SystemExit(1) from error
    except KeyboardInterrupt as error:
        print("Repair/update cancelled before product files changed.")
        raise SystemExit(130) from error

    try:
        backup_root = place_payload(payload_root, install_root)
    except KeyboardInterrupt as error:
        if existing_prepared:
            reactivate_previous_install(
                install_root,
                python_executable=install_python,
            )
        print("Installer payload placement interrupted; previous product state retained.")
        raise SystemExit(130) from error
    except Exception as error:
        if existing_prepared:
            reactivate_previous_install(
                install_root,
                python_executable=install_python,
            )
        print(f"ERROR: Installer payload placement failed: {error}")
        raise SystemExit(1) from error
    if backup_root:
        print(f"Previous install moved to: {backup_root}")
    print(f"Payload placed at: {install_root}")
    for line in render_install_artifact_paths(install_root):
        print(line)

    try:
        result = subprocess.run(
            install_command,
            cwd=install_root,
            env={**os.environ, "ELEFANTE_DATA_DIR": str(managed_data_dir)},
            check=False,
        )
        returncode = result.returncode
        if returncode != 0:
            failed_stage = read_failed_installer_stage(install_root)
    except KeyboardInterrupt:
        print("Installer interrupted; restoring the previous product state.")
        returncode = 130
        failed_stage = read_failed_installer_stage(install_root)
    except OSError as error:
        print(f"Delegated installer could not start: {error}")
        returncode = 1
        failed_stage = "delegated_installer"
    if returncode == 0 and not verify_installed_product(install_root):
        print("Installed product verification failed; restoring the previous product state.")
        returncode = 1
        failed_stage = "package_verification"
    if returncode == 0 and first_run_required:
        first_run_verified = verify_first_run_acceptance(install_root)
        if not first_run_verified:
            print(
                "Fresh-install project Recall, cleanup, or initial-backup "
                "verification failed."
            )
            returncode = 1
            failed_stage = "first_run_acceptance"
    receipt_path: Path | None = None
    retained_code_receipt: Path | None = None
    if (
        returncode == 0
        and backup_root is not None
        and previous_product_verified
        and previous_customer_identity is not None
        and target_customer_identity is not None
    ):
        try:
            retained_code_receipt = write_retained_code_receipt(
                backup_root,
                operation_id=operation_id,
                retained_identity=previous_customer_identity,
                replacement_identity=target_customer_identity,
            )
        except (OSError, ValueError) as error:
            print(f"ERROR: Verified code rollback target could not be recorded: {error}")
            returncode = 1
            failed_stage = "package_verification"
    if returncode == 0:
        try:
            receipt_path = write_package_receipt(
                install_root,
                operation_id=operation_id,
                operation=operation,
                status="VERIFIED_COMPLETE",
                started_at=operation_started_at,
                previous_version=previous_version,
                target_version=target_version_value,
                safety_backup=(
                    "VERIFIED"
                    if existing_prepared and existing_data_present
                    else "NOT_REQUIRED"
                ),
                product_verification=True,
                rollback=(
                    "verified_previous_product_available"
                    if retained_code_receipt is not None
                    else "previous_product_retained_unverified"
                    if backup_root is not None
                    else "not_required"
                ),
                recoverable=retained_code_receipt is not None,
                next_action="reopen_home_check_health",
                first_run_verification=first_run_verified,
            )
        except OSError as error:
            print(f"ERROR: Package acceptance receipt could not be written: {error}")
            returncode = 1
            failed_stage = "package_verification"
    if returncode == 0 and preserved_data_receipt is not None:
        try:
            consumed = consume_data_preservation_receipt(
                home=customer_home,
                install_root=install_root,
                data_root=managed_data_dir,
            )
        except OSError as error:
            print(f"WARN: Reinstall data pointer could not be retired: {error}")
        else:
            if consumed:
                print("Preserved memory data was reattached and verified for this install.")
    if returncode != 0:
        print("")
        guidance_root = install_root
        rollback_verified = False
        if backup_root is not None:
            try:
                failed_root = restore_previous_payload(install_root, backup_root)
            except (OSError, ValueError) as error:
                print(f"CRITICAL: Previous install could not be restored: {error}")
            else:
                guidance_root = failed_root
                print(f"Failed candidate preserved at: {failed_root}")
                print(f"Previous install restored to: {install_root}")
                reactivated = reactivate_previous_install(
                    install_root,
                    python_executable=install_python,
                )
                if reactivated and verify_installed_product(install_root):
                    rollback_verified = True
                    print("Previous Elefante product restored and verified.")
                elif reactivated:
                    print(
                        "ERROR: Previous files and service were restored, but full product "
                        "verification failed."
                    )
                else:
                    print("ERROR: Previous files were restored, but service reactivation failed.")
        for line in render_failed_install_guidance(guidance_root):
            print(line)
        try:
            write_package_receipt(
                guidance_root,
                operation_id=operation_id,
                operation=operation,
                status="FAILED_ROLLED_BACK" if rollback_verified else "NEEDS_HUMAN",
                started_at=operation_started_at,
                previous_version=previous_version,
                target_version=target_version_value,
                safety_backup=(
                    "VERIFIED"
                    if existing_prepared and existing_data_present
                    else "NOT_REQUIRED"
                    if not existing_data_present
                    else "NOT_VERIFIED"
                ),
                product_verification=False,
                rollback=(
                    "previous_product_restored"
                    if rollback_verified
                    else "manual_recovery_required"
                ),
                recoverable=rollback_verified,
                next_action=(
                    "review_failed_candidate_receipt"
                    if rollback_verified
                    else "create_support_report"
                ),
                failed_candidate_name=(
                    guidance_root.name if guidance_root != install_root else None
                ),
                first_run_verification=first_run_verified,
                failed_stage=failed_stage,
            )
        except OSError as error:
            print(f"ERROR: Package receipt could not be written: {error}")
        if rollback_verified and guidance_root != install_root:
            try:
                write_package_receipt(
                    install_root,
                    operation_id=operation_id,
                    operation=operation,
                    status="FAILED_ROLLED_BACK",
                    started_at=operation_started_at,
                    previous_version=previous_version,
                    target_version=target_version_value,
                    safety_backup=(
                        "VERIFIED"
                        if existing_prepared and existing_data_present
                        else "NOT_REQUIRED"
                    ),
                    product_verification=True,
                    rollback="previous_product_restored",
                    recoverable=True,
                    next_action="create_support_report",
                    first_run_verification=first_run_verified,
                    failed_stage=failed_stage,
                )
            except OSError as error:
                print(
                    "ERROR: Restored product could not record the failed package "
                    f"handoff: {error}"
                )
    elif receipt_path is not None:
        print(f"Package acceptance receipt: {receipt_path}")
    raise SystemExit(returncode)


if __name__ == "__main__":
    main()
