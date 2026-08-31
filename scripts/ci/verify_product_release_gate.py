#!/usr/bin/env python3
"""Validate complete, content-free evidence for the six-scenario product gate.

This verifier does not execute or attest a customer journey. It rejects an
evidence manifest unless every required exact-artifact, scenario, native UI,
and unfamiliar-user result is present and bound to the same artifact digest.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess
from typing import Any
from uuid import UUID


MAX_MANIFEST_BYTES = 256 * 1024
MAX_EVIDENCE_BYTES = 32 * 1024 * 1024
SCENARIO_IDS = ("A", "B", "C", "D", "E", "F")
PASS = "PASS"
CERTIFIED_PLATFORM = "macOS"
CERTIFIED_ARCHITECTURE = "arm64"
CERTIFIED_AGENT_HOST = "codex"
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")
SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,79}$")
PACKAGE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")
PLATFORM_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9._ -]{0,39}$")
EVIDENCE_FILE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$")

TOP_LEVEL_FIELDS = {
    "schema_version",
    "gate",
    "generated_at",
    "artifact",
    "scenarios",
    "native_acceptance",
    "human_trials",
}
ARTIFACT_FIELDS = {
    "package_name",
    "version",
    "source_commit",
    "sha256",
    "publication_status",
    "platform",
    "architecture",
    "agent_host",
}
SCENARIO_FIELDS = {
    "status",
    "artifact_sha256",
    "executed_at",
    "receipt_sha256",
    "machine_id",
    "isolation_preflight_passed",
    "unattended",
    "customer_content_included",
    "checks",
}
SCENARIO_RECEIPT_FIELDS = {
    "schema_version",
    "scenario",
    "status",
    "artifact_sha256",
    "executed_at",
    "machine_id",
    "isolation_preflight_passed",
    "unattended",
    "customer_content_included",
    "checks",
}
SCENARIO_RECEIPT_CHECK_FIELDS = {"name", "passed", "code"}
NATIVE_ACCEPTANCE_FIELDS = {
    "status",
    "artifact_sha256",
    "receipt_sha256",
    "checks",
}
NATIVE_ACCEPTANCE_CHECKS = {
    "installer_native_rendered",
    "home_desktop",
    "home_narrow_screen",
    "keyboard",
    "light",
    "dark",
    "reduced_motion",
}
NATIVE_RECEIPT_FIELDS = {
    "schema_version",
    "status",
    "artifact_sha256",
    "executed_at",
    "machine_id",
    "customer_content_included",
    "checks",
}
NATIVE_RECEIPT_CHECK_FIELDS = {
    "name",
    "passed",
    "code",
    "evidence_file",
    "evidence_sha256",
}
HUMAN_TRIAL_FIELDS = {"trial_id", "receipt_sha256"}
HUMAN_TRIAL_RECEIPT_FIELDS = {
    "schema_version",
    "trial_id",
    "scenario",
    "status",
    "artifact_sha256",
    "executed_at",
    "machine_id",
    "unfamiliar_user",
    "founder_interventions",
    "terminal_used",
    "developer_checkout_used",
    "customer_content_included",
    "first_run_receipt_file",
    "first_run_receipt_sha256",
}
REQUIRED_SCENARIO_CHECKS = {
    "A": {
        "fresh_install",
        "agent_connection",
        "two_projects",
        "disposable_recall",
        "acceptance_cleanup",
        "real_decision_remembered",
        "agent_restart",
        "real_decision_recalled",
    },
    "B": {
        "alpha_isolated",
        "beta_isolated",
        "missing_project_abstains",
        "invalid_project_state_abstains",
        "zero_cross_project_exposure",
    },
    "C": {
        "edit",
        "replace",
        "resolve",
        "archive",
        "restore",
        "permanent_delete",
        "scoped_recall_verified",
        "promised_history_preserved",
    },
    "D": {
        "install_interruption",
        "daemon_restart",
        "stale_agent_session",
        "failed_update_rollback",
        "one_safe_next_action",
    },
    "E": {
        "backup_verified",
        "restore_verified",
        "checksums_verified",
        "graph_integrity",
        "project_isolation",
        "recall_verified",
        "uninstall_preserves_data",
        "reinstall_recovers_data",
        "customer_files_untouched",
    },
    "F": {
        "failed_stage_identified",
        "previewed_before_export",
        "no_memory_content",
        "no_project_names_or_paths",
        "no_prompts_questions_answers_or_transcripts",
        "no_credentials_or_environment_values",
        "no_host_configuration_contents",
        "no_application_logs",
    },
}


class DuplicateJSONKey(ValueError):
    """Raised when strict JSON decoding sees a repeated object key."""


def _strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKey(key)
        result[key] = value
    return result


def _safe_timestamp(value: object) -> bool:
    if not isinstance(value, str) or len(value) > 40:
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _safe_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value.lower()
    except ValueError:
        return False


def _exact_fields(value: object, expected: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == expected


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_errors(
    artifact: object,
    *,
    expected_version: str,
    expected_source_commit: str,
    expected_artifact_sha256: str,
    expected_publication_status: str,
    expected_platform: str,
    expected_architecture: str,
    expected_agent_host: str,
) -> list[str]:
    if not _exact_fields(artifact, ARTIFACT_FIELDS):
        return ["ARTIFACT_SCHEMA_INVALID"]
    assert isinstance(artifact, dict)
    errors: list[str] = []
    if not (
        isinstance(artifact["package_name"], str)
        and PACKAGE_PATTERN.fullmatch(artifact["package_name"])
    ):
        errors.append("ARTIFACT_PACKAGE_NAME_INVALID")
    if not (
        isinstance(artifact["version"], str)
        and VERSION_PATTERN.fullmatch(artifact["version"])
        and artifact["version"] == expected_version
    ):
        errors.append("ARTIFACT_VERSION_MISMATCH")
    if not (
        isinstance(artifact["source_commit"], str)
        and COMMIT_PATTERN.fullmatch(artifact["source_commit"])
        and artifact["source_commit"] == expected_source_commit
    ):
        errors.append("ARTIFACT_SOURCE_COMMIT_MISMATCH")
    if not (
        isinstance(artifact["sha256"], str)
        and SHA256_PATTERN.fullmatch(artifact["sha256"])
        and artifact["sha256"] == expected_artifact_sha256
    ):
        errors.append("ARTIFACT_SHA256_MISMATCH")
    for key, expected in (
        ("publication_status", expected_publication_status),
        ("platform", expected_platform),
        ("architecture", expected_architecture),
        ("agent_host", expected_agent_host),
    ):
        if artifact[key] != expected:
            errors.append(f"ARTIFACT_{key.upper()}_MISMATCH")
    if artifact["publication_status"] not in {"candidate", "release"}:
        errors.append("ARTIFACT_PUBLICATION_STATUS_INVALID")
    if not (
        isinstance(artifact["platform"], str)
        and PLATFORM_PATTERN.fullmatch(artifact["platform"])
    ):
        errors.append("ARTIFACT_PLATFORM_INVALID")
    for key in ("architecture", "agent_host"):
        if not (
            isinstance(artifact[key], str)
            and SLUG_PATTERN.fullmatch(artifact[key])
        ):
            errors.append(f"ARTIFACT_{key.upper()}_INVALID")
    if expected_platform != CERTIFIED_PLATFORM:
        errors.append("CERTIFIED_PLATFORM_REQUIRED")
    if expected_architecture != CERTIFIED_ARCHITECTURE:
        errors.append("CERTIFIED_ARCHITECTURE_REQUIRED")
    if expected_agent_host != CERTIFIED_AGENT_HOST:
        errors.append("CERTIFIED_AGENT_HOST_REQUIRED")
    return errors


def _scenario_errors(scenarios: object, artifact_sha256: str) -> list[str]:
    if not isinstance(scenarios, dict) or set(scenarios) != set(SCENARIO_IDS):
        return ["SCENARIO_SET_INCOMPLETE"]
    errors: list[str] = []
    for scenario_id in SCENARIO_IDS:
        scenario = scenarios[scenario_id]
        prefix = f"SCENARIO_{scenario_id}"
        if not _exact_fields(scenario, SCENARIO_FIELDS):
            errors.append(f"{prefix}_SCHEMA_INVALID")
            continue
        assert isinstance(scenario, dict)
        if scenario["status"] != PASS:
            errors.append(f"{prefix}_NOT_PASSED")
        if scenario["artifact_sha256"] != artifact_sha256:
            errors.append(f"{prefix}_ARTIFACT_MISMATCH")
        if not _safe_timestamp(scenario["executed_at"]):
            errors.append(f"{prefix}_TIMESTAMP_INVALID")
        if not (
            isinstance(scenario["receipt_sha256"], str)
            and SHA256_PATTERN.fullmatch(scenario["receipt_sha256"])
        ):
            errors.append(f"{prefix}_RECEIPT_INVALID")
        if not _safe_uuid(scenario["machine_id"]):
            errors.append(f"{prefix}_MACHINE_ID_INVALID")
        if scenario["isolation_preflight_passed"] is not True:
            errors.append(f"{prefix}_ISOLATION_PREFLIGHT_NOT_PROVEN")
        if scenario["unattended"] is not True:
            errors.append(f"{prefix}_UNATTENDED_EXECUTION_NOT_PROVEN")
        if scenario["customer_content_included"] is not False:
            errors.append(f"{prefix}_CUSTOMER_CONTENT_PRESENT")
        checks = scenario["checks"]
        if not (
            isinstance(checks, list)
            and all(
                isinstance(check, str) and SLUG_PATTERN.fullmatch(check)
                for check in checks
            )
            and len(checks) == len(set(checks))
            and set(checks) == REQUIRED_SCENARIO_CHECKS[scenario_id]
        ):
            errors.append(f"{prefix}_CHECKS_INCOMPLETE")
    return errors


def _scenario_receipt_errors(
    evidence_dir: Path,
    scenarios: object,
    artifact_sha256: str,
) -> list[str]:
    """Read back every content-free receipt instead of trusting claimed hashes."""
    root = Path(evidence_dir)
    if root.is_symlink() or not root.is_dir():
        return ["SCENARIO_EVIDENCE_DIRECTORY_INVALID"]
    if not isinstance(scenarios, dict) or set(scenarios) != set(SCENARIO_IDS):
        return ["SCENARIO_EVIDENCE_MANIFEST_INVALID"]
    errors: list[str] = []
    for scenario_id in SCENARIO_IDS:
        prefix = f"SCENARIO_{scenario_id}_RECEIPT"
        target = root / f"scenario-{scenario_id}.json"
        try:
            if (
                target.is_symlink()
                or not target.is_file()
                or target.stat().st_size > MAX_MANIFEST_BYTES
            ):
                raise ValueError("unsafe receipt")
            if stat.S_IMODE(target.stat().st_mode) != 0o600:
                errors.append(f"{prefix}_PRIVATE_MODE_INVALID")
            receipt_bytes = target.read_bytes()
            receipt = json.loads(
                receipt_bytes.decode("utf-8"),
                object_pairs_hook=_strict_object,
            )
        except DuplicateJSONKey:
            errors.append(f"{prefix}_DUPLICATE_JSON_KEY")
            continue
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            errors.append(f"{prefix}_UNREADABLE")
            continue
        scenario = scenarios[scenario_id]
        if not isinstance(scenario, dict):
            errors.append(f"{prefix}_MANIFEST_INVALID")
            continue
        if hashlib.sha256(receipt_bytes).hexdigest() != scenario.get("receipt_sha256"):
            errors.append(f"{prefix}_HASH_MISMATCH")
        if not _exact_fields(receipt, SCENARIO_RECEIPT_FIELDS):
            errors.append(f"{prefix}_SCHEMA_INVALID")
            continue
        assert isinstance(receipt, dict)
        checks = receipt["checks"]
        expected_checks = REQUIRED_SCENARIO_CHECKS[scenario_id]
        valid_checks = bool(
            isinstance(checks, list)
            and len(checks) == len(expected_checks)
            and all(_exact_fields(check, SCENARIO_RECEIPT_CHECK_FIELDS) for check in checks)
            and {
                check["name"]
                for check in checks
                if isinstance(check, dict) and isinstance(check.get("name"), str)
            }
            == expected_checks
            and all(
                isinstance(check, dict)
                and check.get("passed") is True
                and check.get("code")
                == f"{scenario_id}_{str(check.get('name')).upper()}_VERIFIED"
                for check in checks
            )
        )
        if not valid_checks:
            errors.append(f"{prefix}_CHECKS_INVALID")
        if not (
            receipt["schema_version"] == 1
            and receipt["scenario"] == scenario_id
            and receipt["status"] == PASS
            and receipt["artifact_sha256"] == artifact_sha256
            and receipt["executed_at"] == scenario.get("executed_at")
            and receipt["machine_id"] == scenario.get("machine_id")
            and receipt["isolation_preflight_passed"] is True
            and receipt["unattended"] is True
            and receipt["customer_content_included"] is False
            and sorted(expected_checks) == scenario.get("checks")
        ):
            errors.append(f"{prefix}_CONTENT_INVALID")
    return errors


def _native_errors(value: object, artifact_sha256: str) -> list[str]:
    if not _exact_fields(value, NATIVE_ACCEPTANCE_FIELDS):
        return ["NATIVE_ACCEPTANCE_SCHEMA_INVALID"]
    assert isinstance(value, dict)
    errors: list[str] = []
    if value["status"] != PASS:
        errors.append("NATIVE_ACCEPTANCE_NOT_PASSED")
    if value["artifact_sha256"] != artifact_sha256:
        errors.append("NATIVE_ACCEPTANCE_ARTIFACT_MISMATCH")
    if not (
        isinstance(value["receipt_sha256"], str)
        and SHA256_PATTERN.fullmatch(value["receipt_sha256"]) is not None
    ):
        errors.append("NATIVE_ACCEPTANCE_RECEIPT_INVALID")
    checks = value["checks"]
    if not (
        isinstance(checks, list)
        and len(checks) == len(set(checks))
        and all(isinstance(check, str) for check in checks)
        and set(checks) == NATIVE_ACCEPTANCE_CHECKS
    ):
        errors.append("NATIVE_ACCEPTANCE_CHECKS_INCOMPLETE")
    return errors


def _human_trial_errors(value: object) -> list[str]:
    if not isinstance(value, list):
        return ["HUMAN_TRIALS_INVALID"]
    errors: list[str] = []
    trial_ids: set[str] = set()
    valid_trials = 0
    for trial in value:
        if not _exact_fields(trial, HUMAN_TRIAL_FIELDS):
            errors.append("HUMAN_TRIAL_SCHEMA_INVALID")
            continue
        assert isinstance(trial, dict)
        trial_id = trial["trial_id"]
        if not _safe_uuid(trial_id) or trial_id in trial_ids:
            errors.append("HUMAN_TRIAL_ID_INVALID")
            continue
        trial_ids.add(trial_id)
        if not (
            isinstance(trial["receipt_sha256"], str)
            and SHA256_PATTERN.fullmatch(trial["receipt_sha256"]) is not None
        ):
            errors.append("HUMAN_TRIAL_RECEIPT_INVALID")
        else:
            valid_trials += 1
    if valid_trials < 3:
        errors.append("HUMAN_TRIAL_COUNT_INSUFFICIENT")
    return errors


def _read_private_json_evidence(
    target: Path,
    *,
    prefix: str,
) -> tuple[bytes | None, dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        if (
            target.is_symlink()
            or not target.is_file()
            or target.stat().st_size > MAX_MANIFEST_BYTES
        ):
            raise ValueError("unsafe evidence")
        if stat.S_IMODE(target.stat().st_mode) != 0o600:
            errors.append(f"{prefix}_PRIVATE_MODE_INVALID")
        payload = target.read_bytes()
        decoded = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_strict_object,
        )
        if not isinstance(decoded, dict):
            raise ValueError("evidence is not an object")
    except DuplicateJSONKey:
        return None, None, [*errors, f"{prefix}_DUPLICATE_JSON_KEY"]
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return None, None, [*errors, f"{prefix}_UNREADABLE"]
    return payload, decoded, errors


def _evidence_payload_errors(
    evidence_dir: Path,
    *,
    file_name: object,
    expected_sha256: object,
    prefix: str,
) -> list[str]:
    if not (
        isinstance(file_name, str)
        and EVIDENCE_FILE_PATTERN.fullmatch(file_name) is not None
        and Path(file_name).name == file_name
    ):
        return [f"{prefix}_FILE_NAME_INVALID"]
    if not (
        isinstance(expected_sha256, str)
        and SHA256_PATTERN.fullmatch(expected_sha256) is not None
    ):
        return [f"{prefix}_HASH_INVALID"]
    target = evidence_dir / file_name
    errors: list[str] = []
    try:
        if (
            target.is_symlink()
            or not target.is_file()
            or not 0 < target.stat().st_size <= MAX_EVIDENCE_BYTES
        ):
            raise ValueError("unsafe evidence payload")
        if stat.S_IMODE(target.stat().st_mode) != 0o600:
            errors.append(f"{prefix}_PRIVATE_MODE_INVALID")
        payload_sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
    except (OSError, ValueError):
        return [f"{prefix}_UNREADABLE"]
    if payload_sha256 != expected_sha256:
        errors.append(f"{prefix}_HASH_MISMATCH")
    return errors


def _native_receipt_errors(
    evidence_dir: Path,
    manifest_value: object,
    artifact_sha256: str,
) -> list[str]:
    if not isinstance(manifest_value, dict):
        return ["NATIVE_ACCEPTANCE_MANIFEST_INVALID"]
    receipt_bytes, receipt, errors = _read_private_json_evidence(
        evidence_dir / "native-acceptance.json",
        prefix="NATIVE_ACCEPTANCE_RECEIPT",
    )
    if receipt_bytes is None or receipt is None:
        return errors
    if hashlib.sha256(receipt_bytes).hexdigest() != manifest_value.get(
        "receipt_sha256"
    ):
        errors.append("NATIVE_ACCEPTANCE_RECEIPT_HASH_MISMATCH")
    if not _exact_fields(receipt, NATIVE_RECEIPT_FIELDS):
        errors.append("NATIVE_ACCEPTANCE_RECEIPT_SCHEMA_INVALID")
        return errors
    checks = receipt["checks"]
    valid_checks = bool(
        isinstance(checks, list)
        and len(checks) == len(NATIVE_ACCEPTANCE_CHECKS)
        and all(_exact_fields(check, NATIVE_RECEIPT_CHECK_FIELDS) for check in checks)
        and {
            check["name"]
            for check in checks
            if isinstance(check, dict) and isinstance(check.get("name"), str)
        }
        == NATIVE_ACCEPTANCE_CHECKS
    )
    if not valid_checks:
        errors.append("NATIVE_ACCEPTANCE_RECEIPT_CHECKS_INVALID")
        return errors
    assert isinstance(checks, list)
    evidence_names: set[str] = set()
    for check in checks:
        assert isinstance(check, dict)
        name = str(check["name"])
        if not (
            check["passed"] is True
            and check["code"] == f"NATIVE_{name.upper()}_VERIFIED"
        ):
            errors.append("NATIVE_ACCEPTANCE_RECEIPT_CHECKS_INVALID")
        evidence_file = check["evidence_file"]
        if isinstance(evidence_file, str) and evidence_file in evidence_names:
            errors.append("NATIVE_ACCEPTANCE_EVIDENCE_REUSED")
        elif isinstance(evidence_file, str):
            evidence_names.add(evidence_file)
        errors.extend(
            _evidence_payload_errors(
                evidence_dir,
                file_name=evidence_file,
                expected_sha256=check["evidence_sha256"],
                prefix=f"NATIVE_{name.upper()}_EVIDENCE",
            )
        )
    if not (
        receipt["schema_version"] == 1
        and receipt["status"] == PASS
        and receipt["artifact_sha256"] == artifact_sha256
        and _safe_timestamp(receipt["executed_at"])
        and _safe_uuid(receipt["machine_id"])
        and receipt["customer_content_included"] is False
        and sorted(NATIVE_ACCEPTANCE_CHECKS) == manifest_value.get("checks")
    ):
        errors.append("NATIVE_ACCEPTANCE_RECEIPT_CONTENT_INVALID")
    return errors


FIRST_RUN_RECEIPT_FIELDS = {
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


def _first_run_receipt_errors(
    evidence_dir: Path,
    *,
    file_name: object,
    expected_sha256: object,
    prefix: str,
) -> list[str]:
    errors = _evidence_payload_errors(
        evidence_dir,
        file_name=file_name,
        expected_sha256=expected_sha256,
        prefix=prefix,
    )
    if errors or not isinstance(file_name, str):
        return errors
    target = evidence_dir / file_name
    try:
        receipt = json.loads(
            target.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return [*errors, f"{prefix}_INVALID"]
    if not _exact_fields(receipt, FIRST_RUN_RECEIPT_FIELDS):
        return [*errors, f"{prefix}_INVALID"]
    assert isinstance(receipt, dict)
    checks = receipt["checks"]
    expected_checks = {
        "project_isolation",
        "disposable_recall",
        "acceptance_cleanup",
        "initial_backup",
    }
    check_names = {
        check.get("name")
        for check in checks or []
        if isinstance(check, dict)
        and set(check) == {"name", "passed", "code"}
        and check.get("passed") is True
        and isinstance(check.get("code"), str)
    }
    initial_backup = receipt["initial_backup"]
    if not (
        receipt["schema_version"] == 1
        and receipt["operation"] == "first_run_acceptance"
        and receipt["status"] == "VERIFIED_COMPLETE"
        and _safe_timestamp(receipt["finished_at"])
        and _safe_uuid(receipt["acceptance_operation_id"])
        and _safe_uuid(receipt["backup_operation_id"])
        and receipt["memory_content_included"] is False
        and receipt["project_path_included"] is False
        and receipt["next_action"] == "open_elefante_home"
        and isinstance(checks, list)
        and len(checks) == len(expected_checks)
        and check_names == expected_checks
        and isinstance(initial_backup, dict)
        and set(initial_backup) == {"archive_name", "archive_sha256"}
        and isinstance(initial_backup.get("archive_name"), str)
        and Path(str(initial_backup["archive_name"])).name
        == initial_backup["archive_name"]
        and isinstance(initial_backup.get("archive_sha256"), str)
        and SHA256_PATTERN.fullmatch(initial_backup["archive_sha256"]) is not None
    ):
        errors.append(f"{prefix}_INVALID")
    return errors


def _human_trial_receipt_errors(
    evidence_dir: Path,
    manifest_value: object,
    artifact_sha256: str,
) -> list[str]:
    if not isinstance(manifest_value, list):
        return ["HUMAN_TRIAL_EVIDENCE_MANIFEST_INVALID"]
    errors: list[str] = []
    valid_trials = 0
    machine_ids: set[str] = set()
    first_run_files: set[str] = set()
    for trial_claim in manifest_value:
        if not isinstance(trial_claim, dict):
            errors.append("HUMAN_TRIAL_EVIDENCE_MANIFEST_INVALID")
            continue
        trial_id = trial_claim.get("trial_id")
        if not _safe_uuid(trial_id):
            errors.append("HUMAN_TRIAL_ID_INVALID")
            continue
        prefix = f"HUMAN_TRIAL_{str(trial_id).replace('-', '').upper()}"
        target = evidence_dir / f"human-trial-{trial_id}.json"
        receipt_bytes, receipt, trial_errors = _read_private_json_evidence(
            target,
            prefix=f"{prefix}_RECEIPT",
        )
        errors.extend(trial_errors)
        if receipt_bytes is None or receipt is None:
            continue
        if hashlib.sha256(receipt_bytes).hexdigest() != trial_claim.get(
            "receipt_sha256"
        ):
            errors.append(f"{prefix}_RECEIPT_HASH_MISMATCH")
        if not _exact_fields(receipt, HUMAN_TRIAL_RECEIPT_FIELDS):
            errors.append(f"{prefix}_RECEIPT_SCHEMA_INVALID")
            continue
        machine_id = receipt["machine_id"]
        first_run_file = receipt["first_run_receipt_file"]
        valid = True
        for condition, code in (
            (receipt["schema_version"] == 1, f"{prefix}_SCHEMA_VERSION_INVALID"),
            (receipt["trial_id"] == trial_id, f"{prefix}_ID_MISMATCH"),
            (receipt["scenario"] == "A", f"{prefix}_SCENARIO_INVALID"),
            (receipt["status"] == PASS, f"{prefix}_NOT_PASSED"),
            (
                receipt["artifact_sha256"] == artifact_sha256,
                f"{prefix}_ARTIFACT_MISMATCH",
            ),
            (_safe_timestamp(receipt["executed_at"]), f"{prefix}_TIMESTAMP_INVALID"),
            (_safe_uuid(machine_id), f"{prefix}_MACHINE_ID_INVALID"),
            (receipt["unfamiliar_user"] is True, f"{prefix}_NOT_UNFAMILIAR"),
            (
                _is_integer(receipt["founder_interventions"])
                and receipt["founder_interventions"] == 0,
                f"{prefix}_FOUNDER_INTERVENTION",
            ),
            (receipt["terminal_used"] is False, f"{prefix}_TERMINAL_USED"),
            (
                receipt["developer_checkout_used"] is False,
                f"{prefix}_DEVELOPER_CHECKOUT_USED",
            ),
            (
                receipt["customer_content_included"] is False,
                f"{prefix}_CUSTOMER_CONTENT_PRESENT",
            ),
        ):
            if not condition:
                errors.append(code)
                valid = False
        if isinstance(machine_id, str) and machine_id in machine_ids:
            errors.append("HUMAN_TRIAL_MACHINE_REUSED")
            valid = False
        elif isinstance(machine_id, str):
            machine_ids.add(machine_id)
        if isinstance(first_run_file, str) and first_run_file in first_run_files:
            errors.append("HUMAN_TRIAL_FIRST_RUN_EVIDENCE_REUSED")
            valid = False
        elif isinstance(first_run_file, str):
            first_run_files.add(first_run_file)
        first_run_errors = _first_run_receipt_errors(
            evidence_dir,
            file_name=first_run_file,
            expected_sha256=receipt["first_run_receipt_sha256"],
            prefix=f"{prefix}_FIRST_RUN",
        )
        if first_run_errors:
            errors.extend(first_run_errors)
            valid = False
        if valid:
            valid_trials += 1
    if valid_trials < 3:
        errors.append("HUMAN_TRIAL_COUNT_INSUFFICIENT")
    return errors


def _artifact_trust_errors(artifact_path: Path) -> list[str]:
    checks = (
        (
            ["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(artifact_path)],
            "ARTIFACT_SIGNATURE_NOT_VERIFIED",
        ),
        (
            [
                "spctl",
                "--assess",
                "--type",
                "open",
                "--context",
                "context:primary-signature",
                "--verbose=2",
                str(artifact_path),
            ],
            "ARTIFACT_GATEKEEPER_NOT_VERIFIED",
        ),
        (
            ["xcrun", "stapler", "validate", str(artifact_path)],
            "ARTIFACT_NOTARIZATION_NOT_VERIFIED",
        ),
    )
    errors: list[str] = []
    for command, code in checks:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            errors.append(f"{code}_CHECK_UNAVAILABLE")
            continue
        if result.returncode != 0:
            errors.append(code)
    return errors


def _artifact_file_errors(
    artifact_path: Path,
    artifact_claim: object,
    expected_artifact_sha256: str,
) -> list[str]:
    target = Path(artifact_path).expanduser()
    try:
        if target.is_symlink() or not target.is_file() or target.stat().st_size <= 0:
            raise ValueError("unsafe artifact")
        target = target.resolve(strict=True)
        actual_sha256 = _sha256_file(target)
    except (OSError, ValueError):
        return ["ARTIFACT_FILE_UNREADABLE"]
    errors: list[str] = []
    if target.suffix.casefold() != ".dmg":
        errors.append("ARTIFACT_CERTIFIED_FORMAT_REQUIRED")
    if not isinstance(artifact_claim, dict):
        errors.append("ARTIFACT_CLAIM_INVALID")
        return errors
    if artifact_claim.get("package_name") != target.name:
        errors.append("ARTIFACT_PACKAGE_NAME_MISMATCH")
    if actual_sha256 != expected_artifact_sha256:
        errors.append("ARTIFACT_FILE_SHA256_MISMATCH")
    if actual_sha256 != artifact_claim.get("sha256"):
        errors.append("ARTIFACT_CLAIM_SHA256_MISMATCH")
    if not errors:
        errors.extend(_artifact_trust_errors(target))
    return errors


def _manifest_claim_errors(
    manifest: object,
    *,
    expected_version: str,
    expected_source_commit: str,
    expected_artifact_sha256: str,
    expected_publication_status: str,
    expected_platform: str,
    expected_architecture: str,
    expected_agent_host: str,
) -> list[str]:
    """Validate bounded claims without treating claims as release evidence."""
    errors: list[str] = []
    if not _exact_fields(manifest, TOP_LEVEL_FIELDS):
        errors.append("MANIFEST_SCHEMA_INVALID")
    else:
        assert isinstance(manifest, dict)
        if not _is_integer(manifest["schema_version"]) or manifest[
            "schema_version"
        ] != 1:
            errors.append("MANIFEST_VERSION_UNSUPPORTED")
        if manifest["gate"] != "elefante_product_release":
            errors.append("MANIFEST_GATE_INVALID")
        if not _safe_timestamp(manifest["generated_at"]):
            errors.append("MANIFEST_TIMESTAMP_INVALID")
        errors.extend(
            _identity_errors(
                manifest["artifact"],
                expected_version=expected_version,
                expected_source_commit=expected_source_commit,
                expected_artifact_sha256=expected_artifact_sha256,
                expected_publication_status=expected_publication_status,
                expected_platform=expected_platform,
                expected_architecture=expected_architecture,
                expected_agent_host=expected_agent_host,
            )
        )
        errors.extend(
            _scenario_errors(manifest["scenarios"], expected_artifact_sha256)
        )
        errors.extend(
            _native_errors(
                manifest["native_acceptance"],
                expected_artifact_sha256,
            )
        )
        errors.extend(_human_trial_errors(manifest["human_trials"]))
    return sorted(set(errors))


def _release_report(errors: list[str]) -> dict[str, Any]:
    unique_errors = sorted(set(errors))
    return {
        "release_ready": not unique_errors,
        "gate": "elefante_product_release",
        "scenario_count": len(SCENARIO_IDS) if not unique_errors else 0,
        "required_human_trials": 3,
        "error_codes": unique_errors,
    }


def validate_product_release_manifest(
    manifest: object,
    **expected: str,
) -> dict[str, Any]:
    """Validate manifest claims but fail closed until external evidence is read."""
    errors = _manifest_claim_errors(manifest, **expected)
    if not errors:
        errors.append("EVIDENCE_FILES_NOT_VERIFIED")
    return _release_report(errors)


def verify_product_release_manifest_file(
    manifest_path: Path,
    *,
    artifact_path: Path | None = None,
    evidence_dir: Path | None = None,
    **expected: str,
) -> dict[str, Any]:
    path = Path(manifest_path)
    try:
        if path.is_symlink() or not path.is_file():
            raise ValueError("unsafe target")
        if path.stat().st_size > MAX_MANIFEST_BYTES:
            raise ValueError("oversized")
        manifest = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_strict_object,
        )
    except DuplicateJSONKey:
        return _release_report(["MANIFEST_DUPLICATE_JSON_KEY"])
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
        return _release_report(["MANIFEST_UNREADABLE"])
    errors = _manifest_claim_errors(manifest, **expected)
    if errors:
        return _release_report(errors)
    assert isinstance(manifest, dict)
    if artifact_path is None:
        errors.append("ARTIFACT_FILE_REQUIRED")
    else:
        errors.extend(
            _artifact_file_errors(
                artifact_path,
                manifest["artifact"],
                expected["expected_artifact_sha256"],
            )
        )
    if evidence_dir is None:
        errors.append("PRODUCT_EVIDENCE_DIRECTORY_REQUIRED")
    else:
        root = Path(evidence_dir)
        if root.is_symlink() or not root.is_dir():
            errors.append("PRODUCT_EVIDENCE_DIRECTORY_INVALID")
        else:
            errors.extend(
                _scenario_receipt_errors(
                    root,
                    manifest["scenarios"],
                    expected["expected_artifact_sha256"],
                )
            )
            errors.extend(
                _native_receipt_errors(
                    root,
                    manifest["native_acceptance"],
                    expected["expected_artifact_sha256"],
                )
            )
            errors.extend(
                _human_trial_receipt_errors(
                    root,
                    manifest["human_trials"],
                    expected["expected_artifact_sha256"],
                )
            )
    return _release_report(errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail closed unless complete product-release evidence is present."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument(
        "--artifact",
        type=Path,
        required=True,
        help="Exact signed and stapled macOS DMG whose bytes the gate verifies.",
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        required=True,
        help="Directory containing private scenario-A.json through scenario-F.json receipts.",
    )
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--expected-source-commit", required=True)
    parser.add_argument("--expected-artifact-sha256", required=True)
    parser.add_argument(
        "--expected-publication-status",
        choices=("candidate", "release"),
        required=True,
    )
    parser.add_argument("--expected-platform", required=True)
    parser.add_argument("--expected-architecture", required=True)
    parser.add_argument("--expected-agent-host", required=True)
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = verify_product_release_manifest_file(
        args.manifest,
        artifact_path=args.artifact,
        evidence_dir=args.evidence_dir,
        expected_version=args.expected_version,
        expected_source_commit=args.expected_source_commit,
        expected_artifact_sha256=args.expected_artifact_sha256,
        expected_publication_status=args.expected_publication_status,
        expected_platform=args.expected_platform,
        expected_architecture=args.expected_architecture,
        expected_agent_host=args.expected_agent_host,
    )
    if args.json:
        print(json.dumps(report, sort_keys=True))
    elif report["release_ready"]:
        print("PASS: all six exact-artifact product scenarios are evidenced")
    else:
        print("BLOCKED: product release evidence is incomplete")
        for code in report["error_codes"]:
            print(f"- {code}")
    return 0 if report["release_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
