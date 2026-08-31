"""Verified self-service lifecycle operations for Elefante Recover.

Backup and data restore share one product contract: one managed storage layout,
an exclusive write boundary, closed database handles, independent read-back,
database checks, automatic rollback, and bounded content-free receipts.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import sqlite3
import tempfile
from typing import Any, ContextManager, Protocol
from uuid import UUID, uuid4
import zipfile

from scripts.lifecycle.backup_elefante_data import (
    build_backup_manifest,
    create_backup,
)
from scripts.lifecycle.restore_elefante_data import (
    read_verified_manifest,
    restore_archive,
)
from scripts.setup.host_selection import (
    CERTIFIED_CUSTOMER_HOSTS,
    HOST_LABELS,
    SUPPORTED_HOSTS,
)
from src.core.verified_operation import (
    VerifiedOperationCheck,
    VerifiedOperationStatus,
)
from src.utils.atomic_json import read_json_strict, write_json_atomically


RECOVERY_HISTORY_LIMIT = 50
RECOVERY_BACKUP_LIST_LIMIT = 50
SUPPORT_REPORT_MAX_BYTES = 1024 * 1024
SUPPORT_REPORT_FILE_NAME = "support-report.json"
SUPPORT_REPORT_ARCHIVE_PREFIX = "elefante_support_"
PACKAGE_RECEIPT_FILE_NAME = ".elefante-package-receipt.json"

SUPPORT_REPORT_INCLUDED = (
    "product and build identity",
    "operating system and Python version",
    "agent connection and Recall readiness",
    "diagnostic codes",
    "backup validity counts",
    "content-free lifecycle receipts",
)
SUPPORT_REPORT_EXCLUDED = (
    "memory content",
    "project names and paths",
    "prompts, questions, answers, and transcripts",
    "credentials and environment values",
    "host configuration contents",
    "application logs",
)


class RecoveryWriteGuard(Protocol):
    acquired: bool


WriteGuardFactory = Callable[[], ContextManager[RecoveryWriteGuard]]
QuiesceDatabases = Callable[[], Awaitable[None]]
BackupCreator = Callable[..., Path]
RestoreVerifier = Callable[[str], Awaitable[tuple[VerifiedOperationCheck, ...]]]
HealthInspector = Callable[[], Awaitable[Mapping[str, Any]]]
EnvironmentInspector = Callable[[], Mapping[str, Any]]


_HEALTH_DIAGNOSTIC_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,79}$")
_SUPPORT_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_SUPPORT_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
_SUPPORT_COMMIT_PATTERN = re.compile(r"^(?:[0-9a-f]{40}|unavailable)$")
_SUPPORT_TIMESTAMP_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})$"
)
_SUPPORT_UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_SUPPORT_ENVIRONMENT_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+ -]{0,79}$")
_SUPPORT_RECEIPT_OPERATIONS = frozenset(
    {"backup", "restore", "support_report", "install", "repair", "update", "rollback"}
)
_SUPPORT_RECEIPT_STATUSES = frozenset(
    {
        "RUNNING",
        "VERIFIED_COMPLETE",
        "FAILED_NO_CHANGE",
        "FAILED_ROLLED_BACK",
        "NEEDS_HUMAN",
        "UNSAFE",
    }
)
_SUPPORT_SURFACES = frozenset(
    {*SUPPORTED_HOSTS, "codex-recall-routing", "daemon-service"}
)
_SUPPORT_RECEIPT_AUTHORITIES = frozenset(
    {"user_directed", "workflow_managed", "verified_official_package"}
)
_SUPPORT_RECEIPT_NEXT_ACTIONS = frozenset({"create_support_report"})
_SUPPORT_RECEIPT_FAILED_STAGES = frozenset(
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
_SUPPORT_RECEIPT_ROLLBACKS = frozenset(
    {
        "not_required",
        "verified",
        "incomplete",
        "verified_previous_product_available",
        "previous_product_retained_unverified",
        "previous_product_restored",
        "manual_recovery_required",
        "verified_replaced_product_available",
        "replaced_product_retained_unverified",
    }
)
_SUPPORT_RECEIPT_CHECK_NAMES = frozenset(
    {
        "active_kuzu_integrity",
        "active_manifest",
        "active_sqlite_integrity",
        "agent_connection",
        "allowlist_manifest",
        "archive_readback",
        "daemon_connection",
        "first_run_acceptance",
        "kuzu_integrity",
        "private_file",
        "recall_path",
        "recall_verification",
        "rollback_kuzu_integrity",
        "rollback_manifest",
        "rollback_quiesce",
        "rollback_snapshot_refresh",
        "rollback_sqlite_integrity",
        "rollback_switch",
        "runtime_readiness",
        "safety_backup",
        "safety_archive_readback",
        "safety_kuzu_integrity",
        "safety_manifest",
        "safety_sqlite_integrity",
        "product_readiness",
        "snapshot_refresh",
        "staged_kuzu_integrity",
        "staged_manifest",
        "staged_restore",
        "staged_sqlite_integrity",
        "verified_backup",
    }
)
_SUPPORT_RECEIPT_CODES = frozenset(
    {
        "AGENT_CONNECTED",
        "AGENT_NOT_CONNECTED",
        "ARCHIVE_READBACK_MISMATCH",
        "ARCHIVE_READBACK_OK",
        "BACKUP_MISSING",
        "BACKUP_READY",
        "DAEMON_NOT_READY",
        "DAEMON_READY",
        "FIRST_RUN_ACCEPTANCE_NOT_REQUIRED",
        "FIRST_RUN_ACCEPTANCE_NOT_VERIFIED",
        "FIRST_RUN_ACCEPTANCE_VERIFIED",
        "KUZU_NOT_PRESENT",
        "KUZU_OK",
        "KUZU_OPEN_FAILED",
        "RECALL_FAILED",
        "RECALL_NOT_READY",
        "RECALL_NOT_REQUIRED",
        "RECALL_OK",
        "RECALL_READY",
        "RECOVERY_ARCHIVE_CHANGED",
        "RECOVERY_ARCHIVE_INVALID",
        "RECOVERY_ARCHIVE_NAME_INVALID",
        "RECOVERY_ARCHIVE_NOT_FOUND",
        "RECOVERY_ARCHIVE_UNSAFE",
        "RECOVERY_BACKUP_FAILED",
        "RECOVERY_BACKUP_TARGET_UNSAFE",
        "RECOVERY_BACKUP_VERIFICATION_FAILED",
        "RECOVERY_DATA_NOT_FOUND",
        "RECOVERY_HISTORY_INVALID",
        "RECOVERY_HISTORY_TARGET_UNSAFE",
        "RECOVERY_PLAN_BLOCKED",
        "RECOVERY_PLAN_STALE",
        "RECOVERY_POST_VERIFICATION_FAILED",
        "RECOVERY_POST_VERIFICATION_INVALID",
        "RECOVERY_RESTORE_ACTIVE_VERIFICATION_FAILED",
        "RECOVERY_RESTORE_FAILED",
        "RECOVERY_RESTORE_INTERRUPTED",
        "RECOVERY_RESTORE_STAGING_VERIFICATION_FAILED",
        "RECOVERY_RESTORE_SWITCH_UNVERIFIED",
        "RECOVERY_RESTORE_VERIFIER_UNAVAILABLE",
        "RECOVERY_SAFETY_BACKUP_VERIFICATION_FAILED",
        "RECOVERY_SOURCE_INSPECTION_FAILED",
        "RECOVERY_STORAGE_LAYOUT_UNSUPPORTED",
        "RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID",
        "RECOVERY_SUPPORT_REPORT_BLOCKED",
        "RECOVERY_SUPPORT_REPORT_FAILED",
        "RECOVERY_SUPPORT_REPORT_PLAN_STALE",
        "RECOVERY_SUPPORT_REPORT_TARGET_EXISTS",
        "RECOVERY_SUPPORT_REPORT_TARGET_INVALID",
        "RECOVERY_SUPPORT_REPORT_TARGET_UNSAFE",
        "RECOVERY_SUPPORT_REPORT_TARGET_UNSUPPORTED",
        "RECOVERY_SUPPORT_REPORT_TOO_LARGE",
        "RECOVERY_SUPPORT_REPORT_VERIFICATION_FAILED",
        "RECOVERY_WRITE_LOCK_BUSY",
        "ROLLBACK_QUIESCE_FAILED",
        "ROLLBACK_QUIESCE_OK",
        "ROLLBACK_SWITCH_FAILED",
        "ROLLBACK_SWITCH_OK",
        "RUNTIME_AGENT_RECALL_NOT_VERIFIED",
        "RUNTIME_AGENT_RECALL_VERIFIED",
        "RUNTIME_NOT_READY",
        "RUNTIME_READY",
        "SAFETY_ARCHIVE_READBACK_MISMATCH",
        "SAFETY_ARCHIVE_READBACK_OK",
        "SAFETY_BACKUP_NOT_REQUIRED",
        "SAFETY_BACKUP_VERIFIED",
        "SNAPSHOT_REFRESH_FAILED",
        "SNAPSHOT_REFRESH_OK",
        "SQLITE_FILE_UNREADABLE",
        "SQLITE_INTEGRITY_FAILED",
        "SQLITE_NOT_PRESENT",
        "SQLITE_OK",
        "STAGED_RESTORE_MISMATCH",
        "SUPPORT_ALLOWLIST_MISMATCH",
        "SUPPORT_ALLOWLIST_OK",
        "SUPPORT_ARCHIVE_MISMATCH",
        "SUPPORT_ARCHIVE_OK",
        "SUPPORT_FILE_MODE_UNSAFE",
        "SUPPORT_FILE_PRIVATE",
    }
)
_UNSUPPORTED_HEALTH_CODES = frozenset(
    {
        "daemon_service_unavailable",
        "integration_matrix_unknown_surface",
        "integration_surface_not_customer_ready",
    }
)
_RECOVERY_HEALTH_CODES = frozenset(
    {
        "data_manifest_invalid",
        "kuzu_integrity_failed",
        "recovery_operation_unsafe",
        "restore_incomplete",
        "vector_integrity_failed",
    }
)
_UNSAFE_RUNTIME_HEALTH_CODES = frozenset(
    {
        "daemon_service_user_managed",
        "install_manifest_duplicate_key",
        "install_manifest_invalid",
        "runtime_build_identity_mismatch",
        "runtime_provenance_invalid",
        "runtime_source_not_clean",
        "runtime_version_mismatch",
    }
)


@dataclass(frozen=True)
class VerifiedBackupArchive:
    """One content-free configured backup candidate shown to the customer."""

    archive_name: str
    valid: bool
    reason_code: str | None
    archive_sha256: str | None
    source_sha256: str | None
    created_at: str | None
    files: int
    bytes: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerifiedRecoveryHealth:
    """One bounded customer state derived from doctor and backup evidence."""

    schema_version: int
    state: str
    summary: str
    next_action: str
    checked_at: str
    diagnostic_codes: tuple[str, ...]
    checks: tuple[VerifiedOperationCheck, ...]
    connected_agents: tuple[str, ...]
    recall_verified_at: str | None
    valid_backups: int
    invalid_backups: int
    latest_verified_backup_at: str | None
    backup_directory: str
    package_maintenance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "diagnostic_codes": list(self.diagnostic_codes),
            "checks": [check.to_dict() for check in self.checks],
            "connected_agents": list(self.connected_agents),
        }


@dataclass(frozen=True)
class VerifiedRecoveryPlan:
    schema_version: int
    action: str
    applicable: bool
    reason_code: str | None
    reason: str
    layout_sha256: str
    storage_layout: str
    data_directory: str
    backup_directory: str
    estimated_files: int
    estimated_bytes: int
    irreversible: bool
    archive_name: str | None = None
    archive_sha256: str | None = None
    source_sha256: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VerifiedRecoveryReceipt:
    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    authority: str
    started_at: str
    finished_at: str
    layout_sha256: str
    source_sha256: str | None
    archive_sha256: str | None
    archive_name: str | None
    files: int
    bytes: int
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    changed: bool
    rollback: str
    recoverable: bool
    next_action: str
    safety_archive_name: str | None = None
    safety_archive_sha256: str | None = None
    staging_name: str | None = None
    previous_data_name: str | None = None
    failed_restore_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
        }


@dataclass(frozen=True)
class VerifiedRecoveryResult:
    status: VerifiedOperationStatus
    plan: VerifiedRecoveryPlan
    receipt: VerifiedRecoveryReceipt

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
        }


@dataclass(frozen=True)
class VerifiedSupportReportPlan:
    """One read-only, content-free support report preview."""

    schema_version: int
    action: str
    applicable: bool
    reason_code: str | None
    reason: str
    report_sha256: str
    preview: dict[str, Any]
    included: tuple[str, ...]
    excluded: tuple[str, ...]
    estimated_bytes: int
    irreversible: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "included": list(self.included),
            "excluded": list(self.excluded),
        }


@dataclass(frozen=True)
class VerifiedSupportReportReceipt:
    """Content-free proof for one local support-report export."""

    schema_version: int
    operation_id: str
    operation: str
    status: VerifiedOperationStatus
    authority: str
    started_at: str
    finished_at: str
    report_sha256: str
    archive_sha256: str | None
    archive_name: str | None
    files: int
    bytes: int
    checks: tuple[VerifiedOperationCheck, ...]
    error_codes: tuple[str, ...]
    changed: bool
    rollback: str
    recoverable: bool
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "status": self.status.value,
            "checks": [check.to_dict() for check in self.checks],
            "error_codes": list(self.error_codes),
        }


@dataclass(frozen=True)
class VerifiedSupportReportResult:
    status: VerifiedOperationStatus
    plan: VerifiedSupportReportPlan
    receipt: VerifiedSupportReportReceipt

    @property
    def success(self) -> bool:
        return self.status is VerifiedOperationStatus.VERIFIED_COMPLETE

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "receipt": self.receipt.to_dict(),
        }


def _stable_sha256(payload: Any) -> str:
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


def _safe_support_code(value: object) -> str | None:
    if isinstance(value, str) and _SUPPORT_CODE_PATTERN.fullmatch(value) is not None:
        return value
    return None


def _safe_support_codes(value: object, *, limit: int = 32) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted(
        {
            code
            for item in value
            if (code := _safe_support_code(item)) is not None
        }
    )[:limit]


def _safe_support_surfaces(value: object, *, limit: int = 32) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return sorted(
        {
            item
            for item in value
            if isinstance(item, str) and item in _SUPPORT_SURFACES
        }
    )[:limit]


def _safe_support_timestamp(value: object) -> str | None:
    if (
        isinstance(value, str)
        and _SUPPORT_TIMESTAMP_PATTERN.fullmatch(value) is not None
    ):
        return value
    return None


def _safe_support_checks(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []
    checks: list[dict[str, Any]] = []
    for item in value[:16]:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        code = item.get("code")
        passed = item.get("passed")
        attempts = item.get("attempts")
        if (
            name not in _SUPPORT_RECEIPT_CHECK_NAMES
            or code not in _SUPPORT_RECEIPT_CODES
            or not isinstance(passed, bool)
        ):
            continue
        checks.append(
            {
                "name": name,
                "passed": passed,
                "attempts": (
                    min(max(attempts, 0), 100)
                    if isinstance(attempts, int) and not isinstance(attempts, bool)
                    else 0
                ),
                "code": code,
            }
        )
    return checks


def _safe_support_receipt(value: object) -> dict[str, Any] | None:
    """Allowlist one lifecycle receipt without carrying arbitrary text or paths."""
    if not isinstance(value, Mapping):
        return None
    operation = value.get("operation")
    status = value.get("status")
    if operation not in _SUPPORT_RECEIPT_OPERATIONS or status not in _SUPPORT_RECEIPT_STATUSES:
        return None
    receipt: dict[str, Any] = {
        "operation": operation,
        "status": status,
        "checks": _safe_support_checks(value.get("checks")),
        "error_codes": [
            code
            for code in _safe_support_codes(value.get("error_codes"))
            if code in _SUPPORT_RECEIPT_CODES
        ],
    }
    operation_id = value.get("operation_id")
    if (
        isinstance(operation_id, str)
        and _SUPPORT_UUID_PATTERN.fullmatch(operation_id) is not None
    ):
        receipt["operation_id"] = operation_id
    for key in ("started_at", "finished_at", "verified_at"):
        if (timestamp := _safe_support_timestamp(value.get(key))) is not None:
            receipt[key] = timestamp
    if value.get("authority") in _SUPPORT_RECEIPT_AUTHORITIES:
        receipt["authority"] = value["authority"]
    if value.get("rollback") in _SUPPORT_RECEIPT_ROLLBACKS:
        receipt["rollback"] = value["rollback"]
    for key in ("changed", "recoverable"):
        if isinstance(value.get(key), bool):
            receipt[key] = value[key]
    if value.get("next_action") in _SUPPORT_RECEIPT_NEXT_ACTIONS:
        receipt["next_action"] = value["next_action"]
    if value.get("failed_stage") in _SUPPORT_RECEIPT_FAILED_STAGES:
        receipt["failed_stage"] = value["failed_stage"]
    for key in ("previous_version", "target_version"):
        version = value.get(key)
        if version is None or (
            isinstance(version, str)
            and _SUPPORT_VERSION_PATTERN.fullmatch(version) is not None
        ):
            receipt[key] = version
    return receipt


def _default_environment_report() -> Mapping[str, Any]:
    return {
        "operating_system": platform.system(),
        "os_release": platform.release(),
        "architecture": platform.machine(),
        "python_version": platform.python_version(),
    }


def _safe_support_environment(value: object) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, str] = {}
    for key in (
        "operating_system",
        "os_release",
        "architecture",
        "python_version",
    ):
        item = value.get(key)
        if (
            isinstance(item, str)
            and _SUPPORT_ENVIRONMENT_PATTERN.fullmatch(item) is not None
        ):
            result[key] = item
    return result


def _safe_support_doctor_report(value: object) -> dict[str, Any]:
    """Project only documented readiness facts; never copy a doctor object wholesale."""
    report = value if isinstance(value, Mapping) else {}
    diagnostics = sorted(
        set(_safe_support_codes(report.get("diagnostics")))
        | set(_safe_support_codes(report.get("customer_diagnostics")))
    )[:32]
    installation = report.get("installation")
    product: dict[str, Any] = {"recorded": isinstance(installation, Mapping)}
    if isinstance(installation, Mapping):
        if installation.get("scope") in {"customer", "developer"}:
            product["scope"] = installation["scope"]
        version = installation.get("version")
        if isinstance(version, str) and _SUPPORT_VERSION_PATTERN.fullmatch(version):
            product["version"] = version
        commit = installation.get("source_commit")
        if isinstance(commit, str) and _SUPPORT_COMMIT_PATTERN.fullmatch(commit):
            product["source_commit"] = commit
        if installation.get("release_channel") in {
            "development",
            "candidate",
            "release",
        }:
            product["release_channel"] = installation["release_channel"]
        if isinstance(installation.get("source_clean"), bool):
            product["source_clean"] = installation["source_clean"]

    daemon = report.get("daemon")
    daemon_status: dict[str, Any] = {}
    if isinstance(daemon, Mapping):
        if daemon.get("platform") in {"Darwin", "Linux", "Windows"}:
            daemon_status["platform"] = daemon["platform"]
        for key in ("service_file_exists", "daemon_health"):
            if isinstance(daemon.get(key), bool):
                daemon_status[key] = daemon[key]
        if daemon.get("service_file_ownership") in {
            "absent",
            "owned",
            "modified_or_untracked",
        }:
            daemon_status["service_file_ownership"] = daemon[
                "service_file_ownership"
            ]
        if daemon.get("service_runtime") in {
            "active",
            "inactive",
            "registered",
            "not_registered",
            "unavailable",
        }:
            daemon_status["service_runtime"] = daemon["service_runtime"]

    runtime = report.get("runtime")
    runtime_status: dict[str, bool] = {}
    if isinstance(runtime, Mapping):
        for key in ("venv_python_exists", "config_exists"):
            if isinstance(runtime.get(key), bool):
                runtime_status[key] = runtime[key]

    coverage = report.get("host_coverage")
    agent_connection = {
        "detected": [],
        "verified": [],
        "uncovered": [],
        "certified_required": [],
        "certified_verified": [],
        "certified_uncovered": [],
        "compatibility_uncovered": [],
    }
    if isinstance(coverage, Mapping):
        for key in agent_connection:
            agent_connection[key] = _safe_support_surfaces(
                coverage.get(key),
                limit=16,
            )

    recall = report.get("recall")
    recall_status: dict[str, Any] = {}
    if isinstance(recall, Mapping):
        for key in (
            "required",
            "handshake_ready",
            "tool_present",
            "annotations_read_only",
            "probe_read_only",
            "ready",
        ):
            if isinstance(recall.get(key), bool) or recall.get(key) is None:
                recall_status[key] = recall.get(key)
        tool_count = recall.get("tool_count")
        if isinstance(tool_count, int) and not isinstance(tool_count, bool):
            recall_status["tool_count"] = min(max(tool_count, 0), 1000)
        for key in ("probe_status", "diagnostic"):
            if (code := _safe_support_code(recall.get(key))) is not None:
                recall_status[key] = code

    ownership = report.get("installer_ownership")
    installer_ownership: dict[str, Any] = {}
    if isinstance(ownership, Mapping):
        for key in ("files", "host_registrations"):
            count = ownership.get(key)
            if isinstance(count, int) and not isinstance(count, bool):
                installer_ownership[key] = min(max(count, 0), 10000)
        installer_ownership["configured_surfaces"] = _safe_support_surfaces(
            ownership.get("configured_surfaces"),
            limit=32,
        )

    return {
        "product": product,
        "readiness": {
            "ready": report.get("ready") if isinstance(report.get("ready"), bool) else None,
            "customer_ready": (
                report.get("customer_ready")
                if isinstance(report.get("customer_ready"), bool)
                else None
            ),
            "runtime": runtime_status,
            "daemon": daemon_status,
            "recall": recall_status,
        },
        "agent_connection": agent_connection,
        "installer_ownership": installer_ownership,
        "diagnostic_codes": diagnostics,
    }


def _support_report_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=True, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


def _build_support_report_zip(payload: Mapping[str, Any]) -> bytes:
    report_bytes = _support_report_json_bytes(payload)
    if len(report_bytes) > SUPPORT_REPORT_MAX_BYTES:
        raise ValueError("RECOVERY_SUPPORT_REPORT_TOO_LARGE")
    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        info = zipfile.ZipInfo(SUPPORT_REPORT_FILE_NAME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o600 << 16
        archive.writestr(info, report_bytes)
    return output.getvalue()


def _read_support_report_zip(payload: bytes) -> dict[str, Any]:
    if not payload or len(payload) > SUPPORT_REPORT_MAX_BYTES:
        raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
    try:
        with zipfile.ZipFile(io.BytesIO(payload), mode="r") as archive:
            members = archive.infolist()
            if len(members) != 1 or members[0].filename != SUPPORT_REPORT_FILE_NAME:
                raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
            member = members[0]
            if member.is_dir() or member.file_size > SUPPORT_REPORT_MAX_BYTES:
                raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
            def reject_duplicates(
                pairs: list[tuple[str, Any]],
            ) -> dict[str, Any]:
                result: dict[str, Any] = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError("duplicate support-report key")
                    result[key] = value
                return result

            decoded = json.loads(
                archive.read(member).decode("utf-8"),
                object_pairs_hook=reject_duplicates,
            )
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        zipfile.BadZipFile,
    ) as error:
        raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID") from error
    if not isinstance(decoded, dict):
        raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
    return decoded


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _manifest_details(manifest: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, int, str]:
    files = manifest.get("files")
    if not isinstance(files, list) or any(not isinstance(item, Mapping) for item in files):
        raise ValueError("Recovery archive manifest has an invalid file list")
    entries = [dict(item) for item in files]
    try:
        bytes_count = sum(int(item["size"]) for item in entries)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("Recovery archive manifest has invalid file sizes") from error
    return entries, len(entries), bytes_count, _stable_sha256(entries)


def _prefixed_checks(
    checks: tuple[VerifiedOperationCheck, ...],
    prefix: str,
) -> tuple[VerifiedOperationCheck, ...]:
    return tuple(
        VerifiedOperationCheck(
            name=f"{prefix}{check.name}",
            passed=check.passed,
            attempts=check.attempts,
            code=check.code,
        )
        for check in checks
    )


class VerifiedRecoveryService:
    """Own the plan, execution, proof, and receipt for Recover operations."""

    def __init__(
        self,
        *,
        data_dir: Path,
        vector_path: Path,
        graph_path: Path,
        backup_dir: Path,
        history_path: Path,
        write_guard: WriteGuardFactory,
        quiesce_databases: QuiesceDatabases,
        backup_creator: BackupCreator = create_backup,
        verify_restored_data: RestoreVerifier | None = None,
        health_inspector: HealthInspector | None = None,
        report_dir: Path | None = None,
        app_root: Path | None = None,
        environment_inspector: EnvironmentInspector = _default_environment_report,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.vector_path = Path(vector_path).expanduser().resolve()
        self.graph_path = Path(graph_path).expanduser().resolve()
        self.backup_dir = Path(backup_dir).expanduser().resolve()
        self.history_path = Path(history_path).expanduser().resolve()
        configured_report_dir = (
            Path(report_dir).expanduser()
            if report_dir is not None
            else self.data_dir.parent / "support"
        )
        self.report_dir = configured_report_dir.absolute()
        self.app_root = (
            Path(app_root).expanduser().resolve() if app_root is not None else None
        )
        self.write_guard = write_guard
        self.quiesce_databases = quiesce_databases
        self.backup_creator = backup_creator
        self.verify_restored_data = verify_restored_data
        self.health_inspector = health_inspector
        self.environment_inspector = environment_inspector
        self.now = now

    def _layout_payload(self) -> dict[str, str]:
        return {
            "data_dir": str(self.data_dir),
            "vector_path": str(self.vector_path),
            "graph_path": str(self.graph_path),
            "backup_dir": str(self.backup_dir),
            "history_path": str(self.history_path),
        }

    def _layout_sha256(self) -> str:
        return _stable_sha256(self._layout_payload())

    def _layout_error(self) -> tuple[str, str] | None:
        if not self.data_dir.is_dir():
            return (
                "RECOVERY_DATA_NOT_FOUND",
                "Elefante durable data is not available at the configured managed location.",
            )
        if not _is_within(self.vector_path, self.data_dir) or not _is_within(
            self.graph_path,
            self.data_dir,
        ):
            return (
                "RECOVERY_STORAGE_LAYOUT_UNSUPPORTED",
                "Recover supports the official managed storage layout; one configured database is outside it.",
            )
        if _is_within(self.backup_dir, self.data_dir):
            return (
                "RECOVERY_BACKUP_TARGET_UNSAFE",
                "The configured backup destination is inside Elefante durable data.",
            )
        if _is_within(self.history_path, self.data_dir):
            return (
                "RECOVERY_HISTORY_TARGET_UNSAFE",
                "The recovery receipt store must remain outside Elefante durable data.",
            )
        try:
            self._read_history()
        except (OSError, ValueError):
            return (
                "RECOVERY_HISTORY_INVALID",
                "The recovery operation history is invalid and must be repaired before lifecycle changes.",
            )
        return None

    def _read_history(self) -> list[dict[str, Any]]:
        if not self.history_path.exists():
            return []
        payload = read_json_strict(self.history_path)
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != 1
            or not isinstance(payload.get("operations"), list)
            or any(not isinstance(item, dict) for item in payload["operations"])
        ):
            raise ValueError("Recovery history is invalid")
        return [dict(item) for item in payload["operations"]]

    def _write_history(self, receipt: Mapping[str, Any]) -> None:
        operations = self._read_history()
        operation_id = str(receipt.get("operation_id") or "")
        operations = [
            item
            for item in operations
            if str(item.get("operation_id") or "") != operation_id
        ]
        operations.append(dict(receipt))
        write_json_atomically(
            self.history_path,
            {
                "schema_version": 1,
                "operations": operations[-RECOVERY_HISTORY_LIMIT:],
            },
        )

    def history(self) -> tuple[dict[str, Any], ...]:
        """Return bounded content-free lifecycle receipts newest first."""
        return tuple(reversed(self._read_history()))

    def _configured_archive_path(self, archive_name: str) -> Path:
        """Resolve one direct, regular archive from the configured backup directory."""
        selected = str(archive_name).strip()
        if (
            not selected
            or len(selected) > 255
            or selected != Path(selected).name
            or "/" in selected
            or "\\" in selected
            or not selected.lower().endswith(".zip")
        ):
            raise ValueError("RECOVERY_ARCHIVE_NAME_INVALID")
        candidate = self.backup_dir / selected
        if candidate.is_symlink():
            raise ValueError("RECOVERY_ARCHIVE_UNSAFE")
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError as error:
            raise FileNotFoundError("RECOVERY_ARCHIVE_NOT_FOUND") from error
        if resolved.parent != self.backup_dir or not resolved.is_file():
            raise ValueError("RECOVERY_ARCHIVE_UNSAFE")
        return resolved

    def _inspect_backup_archive(self, archive_name: str) -> VerifiedBackupArchive:
        selected = str(archive_name).strip()
        try:
            archive_path = self._configured_archive_path(selected)
            manifest = read_verified_manifest(archive_path)
            _entries, files, bytes_count, source_sha256 = _manifest_details(manifest)
            created_at = manifest.get("created_at")
            if not isinstance(created_at, str) or len(created_at) > 80:
                created_at = None
            return VerifiedBackupArchive(
                archive_name=selected,
                valid=True,
                reason_code=None,
                archive_sha256=_file_sha256(archive_path),
                source_sha256=source_sha256,
                created_at=created_at,
                files=files,
                bytes=bytes_count,
            )
        except FileNotFoundError:
            reason_code = "RECOVERY_ARCHIVE_NOT_FOUND"
        except (OSError, ValueError):
            reason_code = "RECOVERY_ARCHIVE_INVALID"
        return VerifiedBackupArchive(
            archive_name=selected,
            valid=False,
            reason_code=reason_code,
            archive_sha256=None,
            source_sha256=None,
            created_at=None,
            files=0,
            bytes=0,
        )

    def available_backups(self) -> tuple[VerifiedBackupArchive, ...]:
        """List bounded configured backup candidates without accepting paths."""
        if not self.backup_dir.is_dir():
            return ()
        try:
            candidates = sorted(
                (
                    candidate.name
                    for candidate in self.backup_dir.iterdir()
                    if candidate.name.lower().endswith(".zip")
                ),
                reverse=True,
            )[:RECOVERY_BACKUP_LIST_LIMIT]
        except OSError:
            return ()
        return tuple(self._inspect_backup_archive(name) for name in candidates)

    def _workflow_backup_receipt(
        self,
        archive_name: str,
        expected_archive_sha256: str,
        backup_operation_id: str,
    ) -> dict[str, Any] | None:
        """Resolve one live, unconsumed workflow backup from bounded history."""
        try:
            UUID(str(backup_operation_id))
        except (TypeError, ValueError):
            return None
        expected_digest = str(expected_archive_sha256).casefold()
        if len(expected_digest) != 64 or any(
            character not in "0123456789abcdef" for character in expected_digest
        ):
            return None
        try:
            history = self._read_history()
        except (OSError, ValueError):
            return None
        matching = [
            receipt
            for receipt in history
            if receipt.get("operation_id") == str(backup_operation_id)
            and receipt.get("operation") == "backup"
            and receipt.get("status") == VerifiedOperationStatus.VERIFIED_COMPLETE.value
            and receipt.get("authority") == "workflow_managed"
            and receipt.get("archive_name") == archive_name
            and receipt.get("archive_sha256") == expected_digest
            and receipt.get("recoverable") is True
            and receipt.get("archive_consumed") is not True
        ]
        return dict(matching[0]) if len(matching) == 1 else None

    async def verify_workflow_backup(
        self,
        archive_name: str,
        *,
        expected_archive_sha256: str,
        backup_operation_id: str,
    ) -> bool:
        """Prove the exact temporary rollback archive still exists before mutation."""
        receipt = self._workflow_backup_receipt(
            archive_name,
            expected_archive_sha256,
            backup_operation_id,
        )
        if receipt is None:
            return False
        try:
            archive = self._configured_archive_path(archive_name)
            digest = await asyncio.to_thread(_file_sha256, archive)
            return digest == str(expected_archive_sha256).casefold()
        except (OSError, ValueError):
            return False

    async def discard_workflow_backup(
        self,
        archive_name: str,
        *,
        expected_archive_sha256: str,
        backup_operation_id: str,
        consumed_by: str,
    ) -> bool:
        """Destroy one exact workflow backup after its rollback duty is complete."""
        if consumed_by != "permanent_delete":
            return False
        expected_digest = str(expected_archive_sha256).casefold()
        try:
            with self.write_guard() as guard:
                if not guard.acquired:
                    return False
                original = self._workflow_backup_receipt(
                    archive_name,
                    expected_digest,
                    backup_operation_id,
                )
                if original is None:
                    return False
                archive = self._configured_archive_path(archive_name)
                if _file_sha256(archive) != expected_digest:
                    return False
                consumed = dict(original)
                consumed["archive_consumed"] = True
                consumed["archive_consumed_at"] = self.now().isoformat()
                consumed["archive_consumed_by"] = consumed_by
                consumed["recoverable"] = False
                self._write_history(consumed)
                try:
                    await asyncio.to_thread(archive.unlink)
                    if archive.exists():
                        raise OSError("RECOVERY_ARCHIVE_DELETE_FAILED")
                except OSError:
                    try:
                        self._write_history(original)
                    except (OSError, ValueError):
                        pass
                    return False
        except (OSError, ValueError):
            return False
        return True

    async def check_health(self) -> VerifiedRecoveryHealth:
        """Translate bounded doctor and backup evidence into one customer state."""
        report: Mapping[str, Any] | None = None
        inspector_failed = False
        if self.health_inspector is not None:
            try:
                inspected = await self.health_inspector()
                if isinstance(inspected, Mapping):
                    report = inspected
                else:
                    inspector_failed = True
            except Exception:
                inspector_failed = True
        else:
            inspector_failed = True

        diagnostic_codes: set[str] = set()
        if report is not None:
            for key in ("diagnostics", "customer_diagnostics"):
                values = report.get(key)
                if not isinstance(values, list):
                    continue
                for value in values:
                    if (
                        isinstance(value, str)
                        and _HEALTH_DIAGNOSTIC_PATTERN.fullmatch(value) is not None
                    ):
                        diagnostic_codes.add(value)
        if inspector_failed:
            diagnostic_codes.add("health_inspector_unavailable")

        backups = self.available_backups()
        valid_backups = tuple(item for item in backups if item.valid)
        invalid_backups = len(backups) - len(valid_backups)
        latest_backup_at = next(
            (
                item.created_at
                for item in valid_backups
                if isinstance(item.created_at, str) and item.created_at
            ),
            None,
        )
        backup_ready = bool(valid_backups)
        if not backup_ready:
            diagnostic_codes.add("verified_backup_missing")

        report_valid = (
            report is not None
            and isinstance(report.get("ready"), bool)
            and isinstance(report.get("customer_ready"), bool)
            and isinstance(report.get("daemon"), Mapping)
            and isinstance(report.get("host_coverage"), Mapping)
            and isinstance(report.get("recall"), Mapping)
        )
        if not report_valid:
            diagnostic_codes.add("health_report_invalid")

        runtime_ready = bool(report_valid and report.get("ready") is True)
        customer_ready = bool(report_valid and report.get("customer_ready") is True)
        daemon_report = report.get("daemon") if report_valid else {}
        daemon_ready = bool(
            isinstance(daemon_report, Mapping)
            and daemon_report.get("daemon_health") is True
        )
        host_coverage = report.get("host_coverage") if report_valid else {}
        verified_hosts = (
            host_coverage.get("verified")
            if isinstance(host_coverage, Mapping)
            else None
        )
        verified_host_ids = tuple(
            sorted(
                {
                    item
                    for item in verified_hosts
                    if isinstance(item, str) and item in SUPPORTED_HOSTS
                }
            )
        ) if isinstance(verified_hosts, list) else ()
        connected_agents = tuple(HOST_LABELS[item] for item in verified_host_ids)
        agent_ready = CERTIFIED_CUSTOMER_HOSTS.issubset(verified_host_ids)
        if not agent_ready:
            diagnostic_codes.add("certified_agent_missing")
        recall_report = report.get("recall") if report_valid else {}
        recall_required = bool(
            isinstance(recall_report, Mapping)
            and recall_report.get("required") is True
        )
        recall_ready = bool(
            isinstance(recall_report, Mapping)
            and recall_required
            and recall_report.get("ready") is True
        )
        if not recall_ready:
            diagnostic_codes.add("recall_not_ready")
        checked_at = self.now().isoformat()

        checks = (
            VerifiedOperationCheck(
                "runtime_readiness",
                runtime_ready and customer_ready,
                1,
                "RUNTIME_READY" if runtime_ready and customer_ready else "RUNTIME_NOT_READY",
            ),
            VerifiedOperationCheck(
                "daemon_connection",
                daemon_ready,
                1,
                "DAEMON_READY" if daemon_ready else "DAEMON_NOT_READY",
            ),
            VerifiedOperationCheck(
                "agent_connection",
                agent_ready,
                1,
                "AGENT_CONNECTED" if agent_ready else "AGENT_NOT_CONNECTED",
            ),
            VerifiedOperationCheck(
                "recall_path",
                recall_ready,
                1,
                "RECALL_READY" if recall_ready else "RECALL_NOT_READY",
            ),
            VerifiedOperationCheck(
                "verified_backup",
                backup_ready,
                1,
                "BACKUP_READY" if backup_ready else "BACKUP_MISSING",
            ),
        )

        unsafe_codes = diagnostic_codes & _UNSAFE_RUNTIME_HEALTH_CODES
        recovery_codes = diagnostic_codes & _RECOVERY_HEALTH_CODES
        unsupported_codes = diagnostic_codes & _UNSUPPORTED_HEALTH_CODES
        package_maintenance_internal = {
            "authority": "official_package",
            "handoff_required": True,
            **self._support_package_receipt(),
        }
        package_receipt = package_maintenance_internal.get("receipt")
        package_followup_required = bool(
            package_maintenance_internal.get("status") == "invalid"
            or isinstance(package_receipt, Mapping)
            and package_receipt.get("status")
            in {"FAILED_ROLLED_BACK", "NEEDS_HUMAN", "UNSAFE"}
            and package_receipt.get("next_action") == "create_support_report"
        )
        if package_followup_required:
            diagnostic_codes.add("package_followup_required")
        package_maintenance = dict(package_maintenance_internal)
        if isinstance(package_receipt, Mapping):
            visible_package_receipt = dict(package_receipt)
            visible_package_receipt.pop("next_action", None)
            package_maintenance["receipt"] = visible_package_receipt

        if all(check.passed for check in checks):
            if package_followup_required:
                state = "NEEDS_ATTENTION"
                summary = (
                    "Elefante is ready, but the last package operation needs one "
                    "content-free follow-up."
                )
                next_action = "create_support_report"
            else:
                state = "READY"
                summary = (
                    "Elefante, the connected agent, Recall, and a verified backup are ready."
                )
                next_action = "none"
        elif unsupported_codes:
            state = "UNSUPPORTED"
            summary = "This installation is outside the supported self-service boundary."
            next_action = "use_supported_setup"
        elif recovery_codes or unsafe_codes:
            state = "RECOVERY_REQUIRED"
            summary = "Elefante cannot prove a safe current product state."
            next_action = (
                "restore" if recovery_codes and backup_ready else "create_support_report"
            )
        else:
            state = "NEEDS_ATTENTION"
            summary = "Elefante found one or more readiness checks that need attention."
            next_action = (
                "back_up_now"
                if runtime_ready
                and customer_ready
                and daemon_ready
                and agent_ready
                and recall_ready
                and not backup_ready
                else "repair"
                if report_valid
                else "create_support_report"
            )

        return VerifiedRecoveryHealth(
            schema_version=1,
            state=state,
            summary=summary,
            next_action=next_action,
            checked_at=checked_at,
            diagnostic_codes=tuple(sorted(diagnostic_codes))[:32],
            checks=checks,
            connected_agents=connected_agents,
            recall_verified_at=checked_at if recall_ready else None,
            valid_backups=len(valid_backups),
            invalid_backups=invalid_backups,
            latest_verified_backup_at=latest_backup_at,
            backup_directory=str(self.backup_dir),
            package_maintenance=package_maintenance,
        )

    def _support_report_target_error(self) -> tuple[str, str] | None:
        """Keep support exports in one managed sibling directory."""
        try:
            expected_parent = self.data_dir.parent.resolve()
            actual_parent = self.report_dir.parent.resolve()
        except OSError:
            return (
                "RECOVERY_SUPPORT_REPORT_TARGET_INVALID",
                "The managed support-report destination cannot be resolved safely.",
            )
        if actual_parent != expected_parent or self.report_dir.name != "support":
            return (
                "RECOVERY_SUPPORT_REPORT_TARGET_UNSUPPORTED",
                "Support reports can only be exported to Elefante's managed support folder.",
            )
        if self.report_dir.is_symlink() or (
            self.report_dir.exists() and not self.report_dir.is_dir()
        ):
            return (
                "RECOVERY_SUPPORT_REPORT_TARGET_UNSAFE",
                "The managed support-report destination is not a safe directory.",
            )
        return None

    def _support_package_receipt(self) -> dict[str, Any]:
        if self.app_root is None:
            return {"status": "not_configured"}
        target = self.app_root / PACKAGE_RECEIPT_FILE_NAME
        if not target.exists():
            return {"status": "not_found"}
        try:
            if (
                target.is_symlink()
                or not target.is_file()
                or target.stat().st_size > 64 * 1024
            ):
                raise ValueError("invalid package receipt")
            safe = _safe_support_receipt(read_json_strict(target))
        except (OSError, ValueError):
            return {"status": "invalid"}
        if safe is None:
            return {"status": "invalid"}
        return {"status": "available", "receipt": safe}

    async def _support_report_preview(self) -> dict[str, Any]:
        diagnostic_additions: set[str] = set()
        try:
            inspected = (
                await self.health_inspector()
                if self.health_inspector is not None
                else {}
            )
        except Exception:
            inspected = {}
            diagnostic_additions.add("health_inspector_unavailable")
        safe_doctor = _safe_support_doctor_report(inspected)

        try:
            environment = _safe_support_environment(self.environment_inspector())
        except Exception:
            environment = {}
            diagnostic_additions.add("support_environment_unavailable")

        backups = self.available_backups()
        valid_backups = [item for item in backups if item.valid]
        latest_verified_at = next(
            (
                item.created_at
                for item in valid_backups
                if _safe_support_timestamp(item.created_at) is not None
            ),
            None,
        )

        history_status = "available"
        omitted_receipts = 0
        safe_history: list[dict[str, Any]] = []
        try:
            history = self.history()[:10]
        except (OSError, ValueError):
            history = ()
            history_status = "invalid"
            diagnostic_additions.add("recovery_history_invalid")
        for item in history:
            safe = _safe_support_receipt(item)
            if safe is None:
                omitted_receipts += 1
            else:
                safe_history.append(safe)

        safe_doctor["diagnostic_codes"] = sorted(
            set(safe_doctor["diagnostic_codes"]) | diagnostic_additions
        )[:32]
        return {
            "schema_version": 1,
            "product": safe_doctor["product"],
            "environment": environment,
            "readiness": safe_doctor["readiness"],
            "agent_connection": safe_doctor["agent_connection"],
            "installer_ownership": safe_doctor["installer_ownership"],
            "diagnostic_codes": safe_doctor["diagnostic_codes"],
            "backups": {
                "valid": len(valid_backups),
                "invalid": len(backups) - len(valid_backups),
                "latest_verified_at": latest_verified_at,
            },
            "operation_receipts": {
                "package": self._support_package_receipt(),
                "recovery_history_status": history_status,
                "recovery": safe_history,
                "omitted_invalid_receipts": omitted_receipts,
            },
        }

    async def plan_support_report(self) -> VerifiedSupportReportPlan:
        """Preview the exact allowlisted evidence categories before export."""
        preview = await self._support_report_preview()
        report_sha256 = _stable_sha256(preview)
        target_error = self._support_report_target_error()
        reason_code = target_error[0] if target_error else None
        reason = (
            target_error[1]
            if target_error
            else (
                "Elefante will create one local diagnostic ZIP from only the previewed "
                "allowlisted facts. It will not read or transmit memories, projects, "
                "prompts, credentials, configuration contents, or logs."
            )
        )
        final_preview = {
            "schema_version": 1,
            "created_at": self.now().isoformat(),
            "report_sha256": report_sha256,
            "privacy": {
                "included": list(SUPPORT_REPORT_INCLUDED),
                "excluded": list(SUPPORT_REPORT_EXCLUDED),
                "transmission": "none",
            },
            "evidence": preview,
        }
        return VerifiedSupportReportPlan(
            schema_version=1,
            action="support_report",
            applicable=target_error is None,
            reason_code=reason_code,
            reason=reason,
            report_sha256=report_sha256,
            preview=preview,
            included=SUPPORT_REPORT_INCLUDED,
            excluded=SUPPORT_REPORT_EXCLUDED,
            estimated_bytes=len(_support_report_json_bytes(final_preview)),
            irreversible=False,
        )

    def _support_report_receipt(
        self,
        *,
        operation_id: str,
        status: VerifiedOperationStatus,
        authority: str,
        started_at: str,
        report_sha256: str,
        archive_sha256: str | None,
        archive_name: str | None,
        bytes_count: int,
        checks: tuple[VerifiedOperationCheck, ...],
        error_codes: tuple[str, ...],
        changed: bool,
        rollback: str,
        next_action: str,
    ) -> VerifiedSupportReportReceipt:
        return VerifiedSupportReportReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation="support_report",
            status=status,
            authority=authority,
            started_at=started_at,
            finished_at=self.now().isoformat(),
            report_sha256=report_sha256,
            archive_sha256=archive_sha256,
            archive_name=archive_name,
            files=1 if archive_name is not None else 0,
            bytes=bytes_count,
            checks=checks,
            error_codes=error_codes,
            changed=changed,
            rollback=rollback,
            recoverable=status is VerifiedOperationStatus.VERIFIED_COMPLETE,
            next_action=next_action,
        )

    async def execute_support_report(
        self,
        *,
        expected_report_sha256: str,
        authority: str = "user_directed",
    ) -> VerifiedSupportReportResult:
        """Export exactly the previewed allowlist or leave no unverified ZIP."""
        if authority not in {"user_directed", "workflow_managed"}:
            raise ValueError("Recovery authority is invalid")
        plan = await self.plan_support_report()
        operation_id = str(uuid4())
        started_at = self.now().isoformat()

        def receipt(
            *,
            status: VerifiedOperationStatus,
            archive_sha256: str | None = None,
            archive_name: str | None = None,
            bytes_count: int = 0,
            checks: tuple[VerifiedOperationCheck, ...] = (),
            error_codes: tuple[str, ...] = (),
            changed: bool = False,
            rollback: str = "not_required",
            next_action: str,
        ) -> VerifiedSupportReportReceipt:
            return self._support_report_receipt(
                operation_id=operation_id,
                status=status,
                authority=authority,
                started_at=started_at,
                report_sha256=plan.report_sha256,
                archive_sha256=archive_sha256,
                archive_name=archive_name,
                bytes_count=bytes_count,
                checks=checks,
                error_codes=error_codes,
                changed=changed,
                rollback=rollback,
                next_action=next_action,
            )

        if not plan.applicable:
            failed = receipt(
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                error_codes=(plan.reason_code or "RECOVERY_SUPPORT_REPORT_BLOCKED",),
                next_action="inspect_support_report_setup",
            )
            return VerifiedSupportReportResult(failed.status, plan, failed)
        if expected_report_sha256 != plan.report_sha256:
            stale = receipt(
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                error_codes=("RECOVERY_SUPPORT_REPORT_PLAN_STALE",),
                next_action="preview_support_report_again",
            )
            return VerifiedSupportReportResult(stale.status, plan, stale)

        created_at = self.now().isoformat()
        payload = {
            "schema_version": 1,
            "created_at": created_at,
            "report_sha256": plan.report_sha256,
            "privacy": {
                "included": list(plan.included),
                "excluded": list(plan.excluded),
                "transmission": "none",
            },
            "evidence": plan.preview,
        }
        safe_timestamp = re.sub(r"[^0-9]", "", created_at)[:14]
        archive_name = (
            f"{SUPPORT_REPORT_ARCHIVE_PREFIX}{safe_timestamp}_{operation_id[:8]}.zip"
        )
        target = self.report_dir / archive_name
        temporary: Path | None = None
        checks: tuple[VerifiedOperationCheck, ...] = ()
        changed = False
        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            if self.report_dir.is_symlink() or not self.report_dir.is_dir():
                raise RuntimeError("RECOVERY_SUPPORT_REPORT_TARGET_UNSAFE")
            os.chmod(self.report_dir, 0o700)
            if target.exists() or target.is_symlink():
                raise RuntimeError("RECOVERY_SUPPORT_REPORT_TARGET_EXISTS")

            archive_bytes = _build_support_report_zip(payload)
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".elefante-support.",
                suffix=".tmp",
                dir=self.report_dir,
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as output:
                output.write(archive_bytes)
                output.flush()
                os.fsync(output.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, target)
            temporary = None
            changed = True

            readback_bytes = target.read_bytes()
            decoded = _read_support_report_zip(readback_bytes)
            checks = (
                VerifiedOperationCheck(
                    "allowlist_manifest",
                    decoded == payload,
                    1,
                    "SUPPORT_ALLOWLIST_OK" if decoded == payload else "SUPPORT_ALLOWLIST_MISMATCH",
                ),
                VerifiedOperationCheck(
                    "archive_readback",
                    readback_bytes == archive_bytes,
                    1,
                    "SUPPORT_ARCHIVE_OK" if readback_bytes == archive_bytes else "SUPPORT_ARCHIVE_MISMATCH",
                ),
                VerifiedOperationCheck(
                    "private_file",
                    (target.stat().st_mode & 0o777) == 0o600,
                    1,
                    "SUPPORT_FILE_PRIVATE" if (target.stat().st_mode & 0o777) == 0o600 else "SUPPORT_FILE_MODE_UNSAFE",
                ),
            )
            if not all(check.passed for check in checks):
                raise RuntimeError("RECOVERY_SUPPORT_REPORT_VERIFICATION_FAILED")
            completed = receipt(
                status=VerifiedOperationStatus.VERIFIED_COMPLETE,
                archive_sha256=hashlib.sha256(readback_bytes).hexdigest(),
                archive_name=archive_name,
                bytes_count=len(readback_bytes),
                checks=checks,
                changed=True,
                next_action="download_support_report",
            )
            try:
                self._write_history(completed.to_dict())
            except (OSError, ValueError):
                pass
            return VerifiedSupportReportResult(completed.status, plan, completed)
        except Exception as error:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            code = str(error)
            if not code.startswith("RECOVERY_"):
                code = "RECOVERY_SUPPORT_REPORT_FAILED"
            rollback = "not_required"
            status = VerifiedOperationStatus.FAILED_NO_CHANGE
            if changed or target.exists():
                try:
                    target.unlink(missing_ok=True)
                    changed = False
                    rollback = "verified"
                    status = VerifiedOperationStatus.FAILED_ROLLED_BACK
                except OSError:
                    rollback = "incomplete"
                    status = VerifiedOperationStatus.UNSAFE
            failed = receipt(
                status=status,
                checks=checks,
                error_codes=(code,),
                changed=changed,
                rollback=rollback,
                next_action=(
                    "preview_support_report_again"
                    if status is not VerifiedOperationStatus.UNSAFE
                    else "inspect_support_report_folder"
                ),
            )
            try:
                self._write_history(failed.to_dict())
            except (OSError, ValueError):
                pass
            return VerifiedSupportReportResult(failed.status, plan, failed)

    def support_report_bytes(self, archive_name: str) -> bytes:
        """Read one generated support ZIP for authenticated Home download."""
        selected = str(archive_name).strip()
        if (
            not selected.startswith(SUPPORT_REPORT_ARCHIVE_PREFIX)
            or not selected.endswith(".zip")
            or selected != Path(selected).name
            or "/" in selected
            or "\\" in selected
            or len(selected) > 120
        ):
            raise ValueError("RECOVERY_SUPPORT_REPORT_NAME_INVALID")
        target = self.report_dir / selected
        if target.is_symlink() or not target.is_file():
            raise FileNotFoundError(selected)
        if target.stat().st_size > SUPPORT_REPORT_MAX_BYTES:
            raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
        payload = target.read_bytes()
        decoded = _read_support_report_zip(payload)
        if (
            decoded.get("schema_version") != 1
            or not isinstance(decoded.get("evidence"), dict)
            or not isinstance(decoded.get("privacy"), dict)
            or decoded["privacy"].get("included") != list(SUPPORT_REPORT_INCLUDED)
            or decoded["privacy"].get("excluded") != list(SUPPORT_REPORT_EXCLUDED)
            or decoded["privacy"].get("transmission") != "none"
            or not isinstance(decoded.get("report_sha256"), str)
            or re.fullmatch(r"[0-9a-f]{64}", decoded["report_sha256"]) is None
        ):
            raise ValueError("RECOVERY_SUPPORT_REPORT_ARCHIVE_INVALID")
        return payload

    def plan_restore(self, archive_name: str) -> VerifiedRecoveryPlan:
        """Inspect one configured archive and current layout without changing state."""
        layout_sha256 = self._layout_sha256()
        layout_error = self._layout_error()
        summary = self._inspect_backup_archive(archive_name)
        reason_code: str | None = None
        reason = (
            "Elefante will verify the selected archive, create a verified safety backup "
            "of current data, stage and verify the restore, switch once, test Recall, "
            "and restore the exact previous data if any postcondition fails."
        )
        storage_layout = "managed"
        if layout_error is not None:
            reason_code, reason = layout_error
            storage_layout = "unsupported"
        elif self.verify_restored_data is None:
            reason_code = "RECOVERY_RESTORE_VERIFIER_UNAVAILABLE"
            reason = "Restore verification is unavailable in this runtime."
        elif not summary.valid:
            reason_code = summary.reason_code or "RECOVERY_ARCHIVE_INVALID"
            reason = "The selected configured backup is missing, unsafe, or invalid."

        return VerifiedRecoveryPlan(
            schema_version=1,
            action="restore",
            applicable=reason_code is None,
            reason_code=reason_code,
            reason=reason,
            layout_sha256=layout_sha256,
            storage_layout=storage_layout,
            data_directory=str(self.data_dir),
            backup_directory=str(self.backup_dir),
            estimated_files=summary.files,
            estimated_bytes=summary.bytes,
            irreversible=False,
            archive_name=summary.archive_name or None,
            archive_sha256=summary.archive_sha256,
            source_sha256=summary.source_sha256,
        )

    def plan_backup(self) -> VerifiedRecoveryPlan:
        layout_sha256 = self._layout_sha256()
        layout_error = self._layout_error()
        if layout_error is not None:
            code, reason = layout_error
            return VerifiedRecoveryPlan(
                schema_version=1,
                action="backup",
                applicable=False,
                reason_code=code,
                reason=reason,
                layout_sha256=layout_sha256,
                storage_layout="unsupported",
                data_directory=str(self.data_dir),
                backup_directory=str(self.backup_dir),
                estimated_files=0,
                estimated_bytes=0,
                irreversible=False,
            )

        try:
            manifest = build_backup_manifest(self.data_dir)
        except (OSError, ValueError):
            return VerifiedRecoveryPlan(
                schema_version=1,
                action="backup",
                applicable=False,
                reason_code="RECOVERY_SOURCE_INSPECTION_FAILED",
                reason="Elefante could not safely inspect the managed data tree.",
                layout_sha256=layout_sha256,
                storage_layout="managed",
                data_directory=str(self.data_dir),
                backup_directory=str(self.backup_dir),
                estimated_files=0,
                estimated_bytes=0,
                irreversible=False,
            )

        return VerifiedRecoveryPlan(
            schema_version=1,
            action="backup",
            applicable=True,
            reason_code=None,
            reason=(
                "Elefante will pause writes, close database handles, create one local archive, "
                "read it back, stage a restore, and verify the databases before completion."
            ),
            layout_sha256=layout_sha256,
            storage_layout="managed",
            data_directory=str(self.data_dir),
            backup_directory=str(self.backup_dir),
            estimated_files=int(manifest["file_count"]),
            estimated_bytes=int(manifest["total_bytes"]),
            irreversible=False,
        )

    @staticmethod
    def _running_history(
        *,
        operation: str,
        operation_id: str,
        started_at: str,
        layout_sha256: str,
        authority: str,
        archive_name: str | None = None,
        archive_sha256: str | None = None,
        staging_name: str | None = None,
        previous_data_name: str | None = None,
        failed_restore_name: str | None = None,
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "operation_id": operation_id,
            "operation": operation,
            "status": "RUNNING",
            "authority": authority,
            "started_at": started_at,
            "finished_at": None,
            "layout_sha256": layout_sha256,
            "source_sha256": None,
            "archive_sha256": archive_sha256,
            "archive_name": archive_name,
            "files": 0,
            "bytes": 0,
            "checks": [],
            "error_codes": [],
            "changed": False,
            "rollback": "not_required",
            "recoverable": False,
            "next_action": "wait_or_reopen_recover",
            "safety_archive_name": None,
            "safety_archive_sha256": None,
            "staging_name": staging_name,
            "previous_data_name": previous_data_name,
            "failed_restore_name": failed_restore_name,
        }

    def _verify_sqlite(self, staged_data: Path) -> VerifiedOperationCheck:
        sqlite_files: list[Path] = []
        for path in sorted(staged_data.rglob("*")):
            if not path.is_file():
                continue
            try:
                with path.open("rb") as source:
                    if source.read(16) == b"SQLite format 3\x00":
                        sqlite_files.append(path)
            except OSError:
                return VerifiedOperationCheck(
                    "sqlite_integrity",
                    False,
                    1,
                    "SQLITE_FILE_UNREADABLE",
                )

        try:
            for database in sqlite_files:
                # A plain read-only connection to a WAL-mode database can create
                # ``-wal`` and ``-shm`` sidecars.  Recovery verification must not
                # mutate the staged tree or the active manifest will no longer
                # match the archive after the atomic switch.
                uri = f"file:{database.as_posix()}?mode=ro&immutable=1"
                with sqlite3.connect(uri, uri=True) as connection:
                    result = connection.execute("PRAGMA quick_check").fetchone()
                if result != ("ok",):
                    raise ValueError("quick_check failed")
        except (OSError, sqlite3.Error, ValueError):
            return VerifiedOperationCheck(
                "sqlite_integrity",
                False,
                1,
                "SQLITE_INTEGRITY_FAILED",
            )
        return VerifiedOperationCheck(
            "sqlite_integrity",
            True,
            1,
            "SQLITE_OK" if sqlite_files else "SQLITE_NOT_PRESENT",
        )

    def _verify_kuzu(self, staged_data: Path) -> VerifiedOperationCheck:
        relative_graph = self.graph_path.relative_to(self.data_dir)
        staged_graph = staged_data / relative_graph
        if not staged_graph.exists():
            return VerifiedOperationCheck(
                "kuzu_integrity",
                True,
                1,
                "KUZU_NOT_PRESENT",
            )
        database = None
        connection = None
        try:
            import kuzu

            database = kuzu.Database(str(staged_graph), read_only=True)
            connection = kuzu.Connection(database)
        except Exception:
            return VerifiedOperationCheck(
                "kuzu_integrity",
                False,
                1,
                "KUZU_OPEN_FAILED",
            )
        finally:
            close_connection = getattr(connection, "close", None)
            if callable(close_connection):
                close_connection()
            close_database = getattr(database, "close", None)
            if callable(close_database):
                close_database()
        return VerifiedOperationCheck(
            "kuzu_integrity",
            True,
            1,
            "KUZU_OK",
        )

    def _verify_restorable(
        self,
        archive_path: Path,
        source_manifest: Mapping[str, Any],
        *,
        prefix: str = "",
    ) -> tuple[VerifiedOperationCheck, ...]:
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".elefante-backup-verify.",
            dir=self.backup_dir,
        ) as temporary_name:
            staged_data = Path(temporary_name) / "data"
            restored = restore_archive(archive_path, staged_data, apply=True)
            checks = self._verify_data_tree(
                staged_data,
                source_manifest,
                manifest_check_name="staged_restore",
            )
            if restored.get("applied") is not True:
                checks = (
                    VerifiedOperationCheck(
                        "staged_restore",
                        False,
                        1,
                        "STAGED_RESTORE_MISMATCH",
                    ),
                    *checks[1:],
                )
            return _prefixed_checks(checks, prefix)

    def _verify_data_tree(
        self,
        data_dir: Path,
        source_manifest: Mapping[str, Any],
        *,
        manifest_check_name: str,
    ) -> tuple[VerifiedOperationCheck, ...]:
        exact_before = False
        expected_entries: list[dict[str, Any]] = []
        expected_sha256 = ""
        try:
            expected_entries, _files, _bytes, expected_sha256 = _manifest_details(
                source_manifest
            )
            before_manifest = build_backup_manifest(data_dir)
            before_entries, _files, _bytes, before_sha256 = _manifest_details(
                before_manifest
            )
            exact_before = (
                before_entries == expected_entries
                and before_sha256 == expected_sha256
            )
        except (OSError, ValueError):
            pass

        sqlite_check = self._verify_sqlite(data_dir)
        kuzu_check = self._verify_kuzu(data_dir)

        exact_after = False
        try:
            after_manifest = build_backup_manifest(data_dir)
            after_entries, _files, _bytes, after_sha256 = _manifest_details(
                after_manifest
            )
            exact_after = (
                after_entries == expected_entries
                and after_sha256 == expected_sha256
            )
        except (OSError, ValueError):
            pass
        exact = exact_before and exact_after
        manifest_check = VerifiedOperationCheck(
            manifest_check_name,
            exact,
            1,
            (
                f"{manifest_check_name.upper()}_OK"
                if exact
                else f"{manifest_check_name.upper()}_MISMATCH"
            ),
        )
        return (
            manifest_check,
            sqlite_check,
            kuzu_check,
        )

    def _create_verified_safety_backup(
        self,
        source_manifest: Mapping[str, Any],
    ) -> tuple[Path, tuple[VerifiedOperationCheck, ...]]:
        archive_path = self.backup_creator(
            self.data_dir,
            self.backup_dir,
            source_manifest=source_manifest,
        )
        verified_manifest = read_verified_manifest(archive_path)
        expected_entries, _files, _bytes, _source = _manifest_details(source_manifest)
        verified_entries, _files, _bytes, _source = _manifest_details(verified_manifest)
        archive_check = VerifiedOperationCheck(
            "safety_archive_readback",
            verified_entries == expected_entries,
            1,
            (
                "SAFETY_ARCHIVE_READBACK_OK"
                if verified_entries == expected_entries
                else "SAFETY_ARCHIVE_READBACK_MISMATCH"
            ),
        )
        checks = (
            archive_check,
            *self._verify_restorable(
                archive_path,
                source_manifest,
                prefix="safety_",
            ),
        )
        if not all(check.passed for check in checks):
            raise RuntimeError("RECOVERY_SAFETY_BACKUP_VERIFICATION_FAILED")
        return archive_path, checks

    async def _rollback_restored_data(
        self,
        *,
        previous_path: Path,
        failed_restore_path: Path,
        original_manifest: Mapping[str, Any],
    ) -> tuple[bool, tuple[VerifiedOperationCheck, ...]]:
        checks: list[VerifiedOperationCheck] = []
        try:
            await self.quiesce_databases()
            checks.append(
                VerifiedOperationCheck(
                    "rollback_quiesce",
                    True,
                    1,
                    "ROLLBACK_QUIESCE_OK",
                )
            )
        except Exception:
            checks.append(
                VerifiedOperationCheck(
                    "rollback_quiesce",
                    False,
                    1,
                    "ROLLBACK_QUIESCE_FAILED",
                )
            )
            return False, tuple(checks)

        try:
            if failed_restore_path.exists() or not previous_path.is_dir():
                raise RuntimeError("rollback paths are unsafe")
            if self.data_dir.exists():
                self.data_dir.rename(failed_restore_path)
            previous_path.rename(self.data_dir)
            checks.append(
                VerifiedOperationCheck(
                    "rollback_switch",
                    True,
                    1,
                    "ROLLBACK_SWITCH_OK",
                )
            )
        except Exception:
            if (
                not self.data_dir.exists()
                and failed_restore_path.exists()
                and not previous_path.exists()
            ):
                try:
                    failed_restore_path.rename(self.data_dir)
                except OSError:
                    pass
            checks.append(
                VerifiedOperationCheck(
                    "rollback_switch",
                    False,
                    1,
                    "ROLLBACK_SWITCH_FAILED",
                )
            )
            return False, tuple(checks)

        verification = _prefixed_checks(
            self._verify_data_tree(
                self.data_dir,
                original_manifest,
                manifest_check_name="manifest",
            ),
            "rollback_",
        )
        checks.extend(verification)
        verified = all(check.passed for check in checks)
        if verified and failed_restore_path.exists():
            try:
                shutil.rmtree(failed_restore_path)
            except OSError:
                pass
        return verified, tuple(checks)

    def _receipt(
        self,
        *,
        operation: str,
        operation_id: str,
        status: VerifiedOperationStatus,
        started_at: str,
        finished_at: str,
        layout_sha256: str,
        source_sha256: str | None,
        archive_sha256: str | None,
        archive_name: str | None,
        files: int,
        bytes_count: int,
        checks: tuple[VerifiedOperationCheck, ...],
        error_codes: tuple[str, ...],
        changed: bool,
        rollback: str,
        recoverable: bool,
        next_action: str,
        authority: str,
        safety_archive_name: str | None = None,
        safety_archive_sha256: str | None = None,
        staging_name: str | None = None,
        previous_data_name: str | None = None,
        failed_restore_name: str | None = None,
    ) -> VerifiedRecoveryReceipt:
        return VerifiedRecoveryReceipt(
            schema_version=1,
            operation_id=operation_id,
            operation=operation,
            status=status,
            authority=authority,
            started_at=started_at,
            finished_at=finished_at,
            layout_sha256=layout_sha256,
            source_sha256=source_sha256,
            archive_sha256=archive_sha256,
            archive_name=archive_name,
            files=files,
            bytes=bytes_count,
            checks=checks,
            error_codes=error_codes,
            changed=changed,
            rollback=rollback,
            recoverable=recoverable,
            next_action=next_action,
            safety_archive_name=safety_archive_name,
            safety_archive_sha256=safety_archive_sha256,
            staging_name=staging_name,
            previous_data_name=previous_data_name,
            failed_restore_name=failed_restore_name,
        )

    async def execute_backup(
        self,
        *,
        expected_layout_sha256: str,
        authority: str = "user_directed",
    ) -> VerifiedRecoveryResult:
        if authority not in {"user_directed", "workflow_managed"}:
            raise ValueError("Recovery authority is invalid")
        plan = self.plan_backup()
        operation_id = str(uuid4())
        started_at = self.now().isoformat()
        layout_sha256 = self._layout_sha256()
        if not plan.applicable:
            receipt = self._receipt(
                operation="backup",
                operation_id=operation_id,
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                started_at=started_at,
                finished_at=self.now().isoformat(),
                layout_sha256=layout_sha256,
                source_sha256=None,
                archive_sha256=None,
                archive_name=None,
                files=0,
                bytes_count=0,
                checks=(),
                error_codes=(plan.reason_code or "RECOVERY_PLAN_BLOCKED",),
                changed=False,
                rollback="not_required",
                recoverable=False,
                next_action="repair_recovery_configuration",
                authority=authority,
            )
            return VerifiedRecoveryResult(receipt.status, plan, receipt)
        if expected_layout_sha256 != layout_sha256:
            receipt = self._receipt(
                operation="backup",
                operation_id=operation_id,
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                started_at=started_at,
                finished_at=self.now().isoformat(),
                layout_sha256=layout_sha256,
                source_sha256=None,
                archive_sha256=None,
                archive_name=None,
                files=0,
                bytes_count=0,
                checks=(),
                error_codes=("RECOVERY_PLAN_STALE",),
                changed=False,
                rollback="not_required",
                recoverable=False,
                next_action="inspect_backup_again",
                authority=authority,
            )
            return VerifiedRecoveryResult(receipt.status, plan, receipt)

        self._write_history(
            self._running_history(
                operation="backup",
                operation_id=operation_id,
                started_at=started_at,
                layout_sha256=layout_sha256,
                authority=authority,
            )
        )
        archive_path: Path | None = None
        source_manifest: dict[str, Any] | None = None
        checks: tuple[VerifiedOperationCheck, ...] = ()
        error_codes: tuple[str, ...] = ()
        rollback = "not_required"
        changed = False
        status = VerifiedOperationStatus.FAILED_NO_CHANGE
        next_action = "retry_backup"
        recoverable = False
        try:
            with self.write_guard() as guard:
                if not guard.acquired:
                    raise RuntimeError("RECOVERY_WRITE_LOCK_BUSY")
                await self.quiesce_databases()
                source_manifest = await asyncio.to_thread(
                    build_backup_manifest,
                    self.data_dir,
                )
                archive_path = await asyncio.to_thread(
                    self.backup_creator,
                    self.data_dir,
                    self.backup_dir,
                    source_manifest=source_manifest,
                )
                changed = True
                verified_manifest = await asyncio.to_thread(
                    read_verified_manifest,
                    archive_path,
                )
                archive_check = VerifiedOperationCheck(
                    "archive_readback",
                    verified_manifest.get("files") == source_manifest.get("files"),
                    1,
                    (
                        "ARCHIVE_READBACK_OK"
                        if verified_manifest.get("files") == source_manifest.get("files")
                        else "ARCHIVE_READBACK_MISMATCH"
                    ),
                )
                staged_checks = await asyncio.to_thread(
                    self._verify_restorable,
                    archive_path,
                    source_manifest,
                )
                checks = (archive_check, *staged_checks)
                if not all(check.passed for check in checks):
                    raise RuntimeError("RECOVERY_BACKUP_VERIFICATION_FAILED")
                status = VerifiedOperationStatus.VERIFIED_COMPLETE
                recoverable = True
                next_action = "none"
        except Exception as error:
            code = str(error)
            if not code.startswith("RECOVERY_"):
                code = "RECOVERY_BACKUP_FAILED"
            error_codes = (code,)
            if archive_path is not None and archive_path.exists():
                try:
                    archive_path.unlink()
                    changed = False
                    rollback = "verified"
                    status = VerifiedOperationStatus.FAILED_ROLLED_BACK
                except OSError:
                    rollback = "incomplete"
                    status = VerifiedOperationStatus.UNSAFE
                    next_action = "inspect_recovery_history"

        archive_sha256 = (
            _file_sha256(archive_path)
            if status is VerifiedOperationStatus.VERIFIED_COMPLETE
            and archive_path is not None
            and archive_path.is_file()
            else None
        )
        receipt = self._receipt(
            operation="backup",
            operation_id=operation_id,
            status=status,
            started_at=started_at,
            finished_at=self.now().isoformat(),
            layout_sha256=layout_sha256,
            source_sha256=(
                str(source_manifest.get("source_sha256"))
                if source_manifest is not None
                else None
            ),
            archive_sha256=archive_sha256,
            archive_name=(archive_path.name if archive_sha256 else None),
            files=(int(source_manifest.get("file_count", 0)) if source_manifest else 0),
            bytes_count=(int(source_manifest.get("total_bytes", 0)) if source_manifest else 0),
            checks=checks,
            error_codes=error_codes,
            changed=changed,
            rollback=rollback,
            recoverable=recoverable,
            next_action=next_action,
            authority=authority,
        )
        self._write_history(receipt.to_dict())
        return VerifiedRecoveryResult(receipt.status, plan, receipt)

    async def execute_restore(
        self,
        archive_name: str,
        *,
        expected_layout_sha256: str,
        expected_archive_sha256: str,
        verification_question: str,
        authority: str = "user_directed",
    ) -> VerifiedRecoveryResult:
        """Restore one configured archive or prove the exact prior data was recovered."""
        if authority not in {"user_directed", "workflow_managed"}:
            raise ValueError("Recovery authority is invalid")
        safe_question = str(verification_question).strip()
        if not 1 <= len(safe_question) <= 500:
            raise ValueError("Restore verification question must be from 1 to 500 characters")

        plan = self.plan_restore(archive_name)
        operation_id = str(uuid4())
        started_at = self.now().isoformat()
        layout_sha256 = self._layout_sha256()

        def make_receipt(
            *,
            status: VerifiedOperationStatus,
            checks: tuple[VerifiedOperationCheck, ...] = (),
            error_codes: tuple[str, ...] = (),
            changed: bool = False,
            rollback: str = "not_required",
            recoverable: bool = False,
            next_action: str,
            safety_archive: Path | None = None,
            staging_name: str | None = None,
            previous_data_name: str | None = None,
            failed_restore_name: str | None = None,
        ) -> VerifiedRecoveryReceipt:
            return self._receipt(
                operation="restore",
                operation_id=operation_id,
                status=status,
                started_at=started_at,
                finished_at=self.now().isoformat(),
                layout_sha256=layout_sha256,
                source_sha256=plan.source_sha256,
                archive_sha256=plan.archive_sha256,
                archive_name=plan.archive_name,
                files=plan.estimated_files,
                bytes_count=plan.estimated_bytes,
                checks=checks,
                error_codes=error_codes,
                changed=changed,
                rollback=rollback,
                recoverable=recoverable,
                next_action=next_action,
                authority=authority,
                safety_archive_name=(safety_archive.name if safety_archive else None),
                safety_archive_sha256=(
                    _file_sha256(safety_archive)
                    if safety_archive is not None and safety_archive.is_file()
                    else None
                ),
                staging_name=staging_name,
                previous_data_name=previous_data_name,
                failed_restore_name=failed_restore_name,
            )

        if not plan.applicable:
            receipt = make_receipt(
                status=VerifiedOperationStatus.FAILED_NO_CHANGE,
                error_codes=(plan.reason_code or "RECOVERY_PLAN_BLOCKED",),
                next_action="inspect_restore_plan",
            )
            return VerifiedRecoveryResult(receipt.status, plan, receipt)
        if (
            expected_layout_sha256 != layout_sha256
            or expected_archive_sha256 != plan.archive_sha256
        ):
            receipt = make_receipt(
                status=VerifiedOperationStatus.NEEDS_HUMAN,
                error_codes=("RECOVERY_PLAN_STALE",),
                next_action="inspect_restore_again",
            )
            return VerifiedRecoveryResult(receipt.status, plan, receipt)

        staging_path = self.data_dir.parent / f".data.restore.{operation_id}"
        previous_path = self.data_dir.parent / f"data.pre_restore.{operation_id}"
        failed_restore_path = self.data_dir.parent / f"data.failed_restore.{operation_id}"
        self._write_history(
            self._running_history(
                operation="restore",
                operation_id=operation_id,
                started_at=started_at,
                layout_sha256=layout_sha256,
                authority=authority,
                archive_name=plan.archive_name,
                archive_sha256=plan.archive_sha256,
                staging_name=staging_path.name,
                previous_data_name=previous_path.name,
                failed_restore_name=failed_restore_path.name,
            )
        )

        checks: tuple[VerifiedOperationCheck, ...] = ()
        original_manifest: dict[str, Any] | None = None
        target_manifest: dict[str, Any] | None = None
        safety_archive: Path | None = None
        switched = False
        try:
            with self.write_guard() as guard:
                if not guard.acquired:
                    raise RuntimeError("RECOVERY_WRITE_LOCK_BUSY")
                await self.quiesce_databases()

                target_archive = self._configured_archive_path(archive_name)
                if _file_sha256(target_archive) != expected_archive_sha256:
                    raise RuntimeError("RECOVERY_ARCHIVE_CHANGED")
                target_manifest = read_verified_manifest(target_archive)
                _entries, _files, _bytes, target_source = _manifest_details(
                    target_manifest
                )
                if target_source != plan.source_sha256:
                    raise RuntimeError("RECOVERY_ARCHIVE_CHANGED")

                original_manifest = build_backup_manifest(self.data_dir)
                safety_archive, safety_checks = self._create_verified_safety_backup(
                    original_manifest
                )
                checks = safety_checks
                running = self._running_history(
                    operation="restore",
                    operation_id=operation_id,
                    started_at=started_at,
                    layout_sha256=layout_sha256,
                    authority=authority,
                    archive_name=plan.archive_name,
                    archive_sha256=plan.archive_sha256,
                    staging_name=staging_path.name,
                    previous_data_name=previous_path.name,
                    failed_restore_name=failed_restore_path.name,
                )
                running["safety_archive_name"] = safety_archive.name
                running["safety_archive_sha256"] = _file_sha256(safety_archive)
                running["recoverable"] = True
                self._write_history(running)

                staged_checks: tuple[VerifiedOperationCheck, ...] = ()

                def verify_staged(staged_data: Path) -> None:
                    nonlocal staged_checks
                    staged_checks = _prefixed_checks(
                        self._verify_data_tree(
                            staged_data,
                            target_manifest,
                            manifest_check_name="manifest",
                        ),
                        "staged_",
                    )
                    if not all(check.passed for check in staged_checks):
                        raise RuntimeError("RECOVERY_RESTORE_STAGING_VERIFICATION_FAILED")

                restored = restore_archive(
                    target_archive,
                    self.data_dir,
                    apply=True,
                    staging_path=staging_path,
                    previous_path=previous_path,
                    verify_staged=verify_staged,
                )
                checks = (*checks, *staged_checks)
                if restored.get("previous_data") != previous_path:
                    raise RuntimeError("RECOVERY_RESTORE_SWITCH_UNVERIFIED")
                switched = True

                active_checks = _prefixed_checks(
                    self._verify_data_tree(
                        self.data_dir,
                        target_manifest,
                        manifest_check_name="manifest",
                    ),
                    "active_",
                )
                checks = (*checks, *active_checks)
                if not all(check.passed for check in active_checks):
                    raise RuntimeError("RECOVERY_RESTORE_ACTIVE_VERIFICATION_FAILED")

                if self.verify_restored_data is None:
                    raise RuntimeError("RECOVERY_RESTORE_VERIFIER_UNAVAILABLE")
                product_checks = await self.verify_restored_data(safe_question)
                if (
                    not isinstance(product_checks, tuple)
                    or not product_checks
                    or len(product_checks) > 8
                    or any(
                        not isinstance(check, VerifiedOperationCheck)
                        for check in product_checks
                    )
                    or len({check.name for check in product_checks})
                    != len(product_checks)
                    or not {"snapshot_refresh", "recall_verification"}.issubset(
                        {check.name for check in product_checks}
                    )
                ):
                    raise RuntimeError("RECOVERY_POST_VERIFICATION_INVALID")
                checks = (*checks, *product_checks)
                if not all(check.passed for check in product_checks):
                    raise RuntimeError("RECOVERY_POST_VERIFICATION_FAILED")

            receipt = make_receipt(
                status=VerifiedOperationStatus.VERIFIED_COMPLETE,
                checks=checks,
                changed=True,
                recoverable=True,
                next_action="none",
                safety_archive=safety_archive,
                staging_name=staging_path.name,
                previous_data_name=previous_path.name,
                failed_restore_name=failed_restore_path.name,
            )
            self._write_history(receipt.to_dict())
            return VerifiedRecoveryResult(receipt.status, plan, receipt)
        except asyncio.CancelledError:
            if switched and original_manifest is not None:
                rolled_back, rollback_checks = await self._rollback_restored_data(
                    previous_path=previous_path,
                    failed_restore_path=failed_restore_path,
                    original_manifest=original_manifest,
                )
                receipt = make_receipt(
                    status=(
                        VerifiedOperationStatus.FAILED_ROLLED_BACK
                        if rolled_back
                        else VerifiedOperationStatus.UNSAFE
                    ),
                    checks=(*checks, *rollback_checks),
                    error_codes=("RECOVERY_RESTORE_INTERRUPTED",),
                    changed=not rolled_back,
                    rollback="verified" if rolled_back else "incomplete",
                    recoverable=bool(safety_archive and safety_archive.is_file()),
                    next_action=(
                        "retry_restore"
                        if rolled_back
                        else "stop_elefante_and_inspect_recovery"
                    ),
                    safety_archive=safety_archive,
                    staging_name=staging_path.name,
                    previous_data_name=previous_path.name,
                    failed_restore_name=failed_restore_path.name,
                )
                self._write_history(receipt.to_dict())
            raise
        except Exception as error:
            code = str(error)
            if not code.startswith("RECOVERY_"):
                code = "RECOVERY_RESTORE_FAILED"
            rolled_back = False
            rollback_checks: tuple[VerifiedOperationCheck, ...] = ()
            if switched and original_manifest is not None:
                rolled_back, rollback_checks = await self._rollback_restored_data(
                    previous_path=previous_path,
                    failed_restore_path=failed_restore_path,
                    original_manifest=original_manifest,
                )
            if switched:
                status = (
                    VerifiedOperationStatus.FAILED_ROLLED_BACK
                    if rolled_back
                    else VerifiedOperationStatus.UNSAFE
                )
                rollback = "verified" if rolled_back else "incomplete"
                next_action = (
                    "retry_restore"
                    if rolled_back
                    else "stop_elefante_and_inspect_recovery"
                )
            else:
                status = VerifiedOperationStatus.FAILED_NO_CHANGE
                rollback = "not_required"
                next_action = "inspect_restore_again"
            receipt = make_receipt(
                status=status,
                checks=(*checks, *rollback_checks),
                error_codes=(code,),
                changed=switched and not rolled_back,
                rollback=rollback,
                recoverable=bool(safety_archive and safety_archive.is_file()),
                next_action=next_action,
                safety_archive=safety_archive,
                staging_name=staging_path.name,
                previous_data_name=previous_path.name,
                failed_restore_name=failed_restore_path.name,
            )
            self._write_history(receipt.to_dict())
            return VerifiedRecoveryResult(receipt.status, plan, receipt)


__all__ = [
    "VerifiedBackupArchive",
    "VerifiedRecoveryHealth",
    "VerifiedRecoveryPlan",
    "VerifiedRecoveryReceipt",
    "VerifiedRecoveryResult",
    "VerifiedRecoveryService",
]
