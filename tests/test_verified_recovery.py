# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_verified_recovery.py
# PROVES  : Recover backup planning, exclusive quiescence, archive/restage proof,
#           bounded receipts, interruption visibility, and safe rollback.
# RUN     : .venv/bin/python -m pytest tests/test_verified_recovery.py -v
# WHEN    : After any verified Recover or managed-backup contract change.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sqlite3
import zipfile

import pytest

from scripts.lifecycle.backup_elefante_data import build_backup_manifest
from scripts.setup.bootstrap_release_bundle import write_package_receipt
from src.core.verified_operation import VerifiedOperationStatus
from src.core.verified_operation import VerifiedOperationCheck
from src.core.verified_recovery import VerifiedRecoveryService
from src.core.graph_store import GraphStore
from src.utils.atomic_json import read_json_strict


class _Guard:
    def __init__(self, acquired: bool = True) -> None:
        self.acquired = acquired

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def _write_managed_data(data_dir: Path, content: str = "private customer memory") -> None:
    database = data_dir / "vector" / "memories.sqlite3"
    database.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE memories (content TEXT NOT NULL)")
        connection.execute("INSERT INTO memories (content) VALUES (?)", (content,))
    (data_dir / "dashboard_snapshot.json").write_text(
        json.dumps({"schema_version": 2, "private": content}),
        encoding="utf-8",
    )


def _service(
    tmp_path: Path,
    *,
    acquired: bool = True,
    quiesce=None,
    backup_creator=None,
    verify_restored_data=None,
    health_inspector=None,
    environment_inspector=None,
    report_dir=None,
    app_root=None,
) -> VerifiedRecoveryService:
    data_dir = tmp_path / "home" / "data"
    if quiesce is None:
        async def quiesce():
            return None

    kwargs = {}
    if backup_creator is not None:
        kwargs["backup_creator"] = backup_creator
    if environment_inspector is not None:
        kwargs["environment_inspector"] = environment_inspector
    return VerifiedRecoveryService(
        data_dir=data_dir,
        vector_path=data_dir / "vector",
        graph_path=data_dir / "kuzu_db",
        backup_dir=tmp_path / "home" / "backups",
        history_path=tmp_path / "home" / "recovery" / "operations.json",
        write_guard=lambda: _Guard(acquired),
        quiesce_databases=quiesce,
        verify_restored_data=verify_restored_data,
        health_inspector=health_inspector,
        report_dir=report_dir or tmp_path / "home" / "support",
        app_root=app_root or tmp_path / "app",
        **kwargs,
    )


def _product_checks(*, recall_passed: bool = True):
    return (
        VerifiedOperationCheck(
            "snapshot_refresh",
            True,
            1,
            "SNAPSHOT_REFRESH_OK",
        ),
        VerifiedOperationCheck(
            "recall_verification",
            recall_passed,
            1,
            "RECALL_OK" if recall_passed else "RECALL_FAILED",
        ),
    )


def _doctor_report(
    *,
    ready: bool = True,
    customer_ready: bool = True,
    daemon_ready: bool = True,
    verified_hosts: list[str] | None = None,
    recall_required: bool = True,
    recall_ready: bool = True,
    diagnostics: list[str] | None = None,
    customer_diagnostics: list[str] | None = None,
):
    return {
        "ready": ready,
        "customer_ready": customer_ready,
        "daemon": {"daemon_health": daemon_ready},
        "host_coverage": {
            "verified": ["codex"] if verified_hosts is None else verified_hosts,
        },
        "recall": {"required": recall_required, "ready": recall_ready},
        "diagnostics": diagnostics or [],
        "customer_diagnostics": customer_diagnostics or [],
    }


@pytest.mark.asyncio
async def test_support_report_preview_and_export_are_strictly_allowlisted(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    secret_memory = "PRIVATE-MEMORY-CONTENT-DO-NOT-EXPORT"
    secret_project = "/Users/customer/Secret Elephant Project"
    secret_token = "sk-private-support-secret"
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, secret_memory)
    create_backup(data_dir, tmp_path / "home" / "backups")

    history_path = tmp_path / "home" / "recovery" / "operations.json"
    history_path.parent.mkdir(parents=True)
    history_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operations": [
                    {
                        "schema_version": 1,
                        "operation_id": "11111111-1111-4111-8111-111111111111",
                        "operation": "restore",
                        "status": "VERIFIED_COMPLETE",
                        "authority": "user_directed",
                        "started_at": "2026-08-30T12:00:00+00:00",
                        "finished_at": "2026-08-30T12:01:00+00:00",
                        "checks": [
                            {
                                "name": "recall_verification",
                                "passed": True,
                                "attempts": 1,
                                "code": "RECALL_OK",
                            }
                        ],
                        "error_codes": [],
                        "changed": True,
                        "rollback": "not_required",
                        "recoverable": True,
                        "next_action": "none",
                        "archive_name": f"backup-{secret_project}.zip",
                        "verification_question": secret_memory,
                        "answer": secret_token,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    app_root = tmp_path / "app"
    app_root.mkdir()
    (app_root / ".elefante-package-receipt.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation_id": "22222222-2222-4222-8222-222222222222",
                "operation": "update",
                "status": "VERIFIED_COMPLETE",
                "authority": "verified_official_package",
                "started_at": "2026-08-30T11:00:00+00:00",
                "finished_at": "2026-08-30T11:02:00+00:00",
                "previous_version": "2.12.3",
                "target_version": "2.13.0",
                "checks": [
                    {
                        "name": "safety_backup",
                        "passed": True,
                        "attempts": 1,
                        "code": "SAFETY_BACKUP_VERIFIED",
                    },
                    {
                        "name": "product_readiness",
                        "passed": True,
                        "attempts": 1,
                        "code": "RUNTIME_AGENT_RECALL_VERIFIED",
                    },
                    {
                        "name": "first_run_acceptance",
                        "passed": True,
                        "attempts": 1,
                        "code": "FIRST_RUN_ACCEPTANCE_NOT_REQUIRED",
                    },
                ],
                "error_codes": [],
                "changed": True,
                "rollback": "not_required",
                "recoverable": True,
                "next_action": "none",
                "failed_candidate_name": secret_project,
                "prompt": secret_memory,
            }
        ),
        encoding="utf-8",
    )

    async def health_report():
        return {
            "ready": False,
            "customer_ready": False,
            "runtime": {"venv_python_exists": True, "config_exists": True},
            "daemon": {
                "platform": "Darwin",
                "service_file_exists": True,
                "service_file_ownership": "owned",
                "service_runtime": "active",
                "daemon_health": True,
                "service_path": secret_project,
            },
            "installation": {
                "scope": "customer",
                "version": "2.13.0",
                "source_commit": "a" * 40,
                "release_channel": "candidate",
                "source_clean": True,
                "app_root": secret_project,
            },
            "host_coverage": {
                "detected": ["codex", secret_project],
                "verified": ["codex"],
                "uncovered": [],
                "certified_required": ["codex"],
                "certified_verified": ["codex"],
                "certified_uncovered": [],
                "compatibility_uncovered": [],
            },
            "installer_ownership": {
                "files": 8,
                "host_registrations": 1,
                "configured_surfaces": ["codex", "codex-recall-routing"],
                "commands": {"codex": secret_token},
            },
            "recall": {
                "required": True,
                "handshake_ready": True,
                "tool_count": 17,
                "tool_present": True,
                "annotations_read_only": True,
                "probe_status": "no_match",
                "probe_read_only": True,
                "ready": True,
                "question": secret_memory,
            },
            "diagnostics": ["runtime_version_mismatch"],
            "customer_diagnostics": [],
            "memory_content": secret_memory,
            "project_path": secret_project,
            "environment": {"API_TOKEN": secret_token},
        }

    service = _service(
        tmp_path,
        health_inspector=health_report,
        app_root=app_root,
        environment_inspector=lambda: {
            "operating_system": "Darwin",
            "os_release": "25.6.0",
            "architecture": "arm64",
            "python_version": "3.12.8",
            "hostname": secret_project,
            "environment": secret_token,
        },
    )

    plan = await service.plan_support_report()
    plan_text = json.dumps(plan.to_dict(), sort_keys=True)

    assert plan.applicable is True
    assert plan.action == "support_report"
    assert plan.preview["product"]["version"] == "2.13.0"
    assert plan.preview["agent_connection"]["verified"] == ["codex"]
    assert plan.preview["agent_connection"]["certified_verified"] == ["codex"]
    assert plan.preview["backups"]["valid"] == 1
    assert plan.preview["operation_receipts"]["package"]["status"] == "available"
    assert len(plan.preview["operation_receipts"]["recovery"]) == 1
    assert not (tmp_path / "home" / "support").exists()
    for forbidden in (secret_memory, secret_project, secret_token):
        assert forbidden not in plan_text

    result = await service.execute_support_report(
        expected_report_sha256=plan.report_sha256,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.receipt.operation == "support_report"
    assert result.receipt.next_action == "download_support_report"
    assert all(check.passed for check in result.receipt.checks)
    archive_path = tmp_path / "home" / "support" / str(result.receipt.archive_name)
    assert archive_path.is_file()
    assert archive_path.stat().st_mode & 0o777 == 0o600
    assert service.support_report_bytes(archive_path.name) == archive_path.read_bytes()
    with zipfile.ZipFile(archive_path) as archive:
        assert archive.namelist() == ["support-report.json"]
        report_bytes = archive.read("support-report.json")
    report = json.loads(report_bytes)
    assert report["report_sha256"] == plan.report_sha256
    assert report["privacy"]["transmission"] == "none"
    assert report["evidence"] == plan.preview
    for forbidden in (secret_memory, secret_project, secret_token):
        assert forbidden.encode() not in archive_path.read_bytes()
        assert forbidden.encode() not in report_bytes

    with zipfile.ZipFile(archive_path, mode="w") as archive:
        archive.writestr(
            "support-report.json",
            '{"schema_version":1,"privacy":{},"privacy":{},"evidence":{},'
            '"report_sha256":"' + "f" * 64 + '"}',
        )
    with pytest.raises(ValueError, match="ARCHIVE_INVALID"):
        service.support_report_bytes(archive_path.name)


@pytest.mark.asyncio
async def test_support_report_rejects_stale_preview_and_unsafe_output(tmp_path):
    diagnostics: list[str] = []

    async def changing_health():
        return {
            **_doctor_report(diagnostics=list(diagnostics)),
            "installation": {"scope": "customer", "version": "2.13.0"},
        }

    service = _service(tmp_path, health_inspector=changing_health)
    plan = await service.plan_support_report()
    diagnostics.append("runtime_version_mismatch")

    stale = await service.execute_support_report(
        expected_report_sha256=plan.report_sha256,
    )

    assert stale.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert stale.receipt.changed is False
    assert stale.receipt.error_codes == ("RECOVERY_SUPPORT_REPORT_PLAN_STALE",)
    assert not (tmp_path / "home" / "support").exists()

    outside = tmp_path / "outside"
    outside.mkdir()
    support = tmp_path / "home" / "support"
    support.parent.mkdir(parents=True, exist_ok=True)
    support.symlink_to(outside, target_is_directory=True)
    unsafe_plan = await service.plan_support_report()

    assert unsafe_plan.applicable is False
    assert unsafe_plan.reason_code == "RECOVERY_SUPPORT_REPORT_TARGET_UNSAFE"
    assert list(outside.iterdir()) == []


@pytest.mark.asyncio
async def test_failed_support_report_verification_removes_archive(tmp_path, monkeypatch):
    async def health_report():
        return _doctor_report()

    service = _service(tmp_path, health_inspector=health_report)
    plan = await service.plan_support_report()
    monkeypatch.setattr(
        "src.core.verified_recovery._build_support_report_zip",
        lambda _payload: b"not-a-zip",
    )

    result = await service.execute_support_report(
        expected_report_sha256=plan.report_sha256,
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.receipt.rollback == "verified"
    assert list((tmp_path / "home" / "support").glob("*.zip")) == []


@pytest.mark.asyncio
async def test_health_requires_runtime_agent_recall_and_verified_backup(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)

    async def healthy_report():
        return _doctor_report()

    service = _service(tmp_path, health_inspector=healthy_report)
    missing_backup = await service.check_health()

    assert missing_backup.state == "NEEDS_ATTENTION"
    assert missing_backup.next_action == "back_up_now"
    assert missing_backup.valid_backups == 0
    assert missing_backup.diagnostic_codes == ("verified_backup_missing",)

    create_backup(data_dir, tmp_path / "home" / "backups")
    ready = await service.check_health()

    assert ready.state == "READY"
    assert ready.next_action == "none"
    assert ready.valid_backups == 1
    assert ready.backup_directory == str(tmp_path / "home" / "backups")
    assert ready.connected_agents == ("Codex",)
    assert ready.recall_verified_at == ready.checked_at
    assert all(check.passed for check in ready.checks)
    assert {check.name for check in ready.checks} == {
        "runtime_readiness",
        "daemon_connection",
        "agent_connection",
        "recall_path",
        "verified_backup",
    }


@pytest.mark.asyncio
async def test_health_rejects_unknown_agent_labels_and_requires_recall(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    create_backup(data_dir, tmp_path / "home" / "backups")

    async def untrusted_report():
        return _doctor_report(
            verified_hosts=["Private Customer Name"],
            recall_required=False,
            recall_ready=True,
        )

    health = await _service(tmp_path, health_inspector=untrusted_report).check_health()
    payload = json.dumps(health.to_dict())

    assert health.state == "NEEDS_ATTENTION"
    assert health.next_action == "repair"
    assert health.connected_agents == ()
    assert health.recall_verified_at is None
    assert "certified_agent_missing" in health.diagnostic_codes
    assert "recall_not_ready" in health.diagnostic_codes
    assert "Private Customer Name" not in payload


@pytest.mark.asyncio
async def test_health_does_not_treat_a_compatibility_preview_as_certified(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    create_backup(data_dir, tmp_path / "home" / "backups")

    async def preview_only_report():
        return _doctor_report(verified_hosts=["cursor"])

    health = await _service(
        tmp_path,
        health_inspector=preview_only_report,
    ).check_health()

    assert health.state == "NEEDS_ATTENTION"
    assert health.next_action == "repair"
    assert health.connected_agents == ("Cursor",)
    assert "certified_agent_missing" in health.diagnostic_codes
    assert next(
        check for check in health.checks if check.name == "agent_connection"
    ).passed is False


@pytest.mark.asyncio
async def test_health_exposes_only_allowlisted_package_handoff_receipt(tmp_path):
    app_root = tmp_path / "app"
    secret = "/Users/customer/Private Project do not expose"
    write_package_receipt(
        app_root,
        operation_id="44444444-4444-4444-8444-444444444444",
        operation="update",
        status="VERIFIED_COMPLETE",
        started_at="2026-08-30T12:00:00+00:00",
        previous_version="2.12.3",
        target_version="2.13.0",
        safety_backup="VERIFIED",
        product_verification=True,
        rollback="verified_previous_product_available",
        recoverable=True,
        next_action=secret,
        failed_candidate_name=secret,
    )

    async def healthy_report():
        return _doctor_report()

    health = await _service(
        tmp_path,
        app_root=app_root,
        health_inspector=healthy_report,
    ).check_health()
    payload = json.dumps(health.to_dict())
    package_receipt = health.package_maintenance["receipt"]

    assert health.package_maintenance == {
        "authority": "official_package",
        "handoff_required": True,
        "status": "available",
        "receipt": {
            "operation": "update",
            "status": "VERIFIED_COMPLETE",
            "checks": [
                {
                    "name": "safety_backup",
                    "passed": True,
                    "attempts": 1,
                    "code": "SAFETY_BACKUP_VERIFIED",
                },
                {
                    "name": "product_readiness",
                    "passed": True,
                    "attempts": 1,
                    "code": "RUNTIME_AGENT_RECALL_VERIFIED",
                },
                {
                    "name": "first_run_acceptance",
                    "passed": True,
                    "attempts": 1,
                    "code": "FIRST_RUN_ACCEPTANCE_NOT_REQUIRED",
                },
            ],
            "error_codes": [],
            "operation_id": "44444444-4444-4444-8444-444444444444",
            "started_at": "2026-08-30T12:00:00+00:00",
            "finished_at": package_receipt["finished_at"],
            "authority": "verified_official_package",
            "rollback": "verified_previous_product_available",
            "changed": True,
            "recoverable": True,
            "previous_version": "2.12.3",
            "target_version": "2.13.0",
        },
    }
    assert secret not in payload
    assert "failed_candidate_name" not in payload
    assert "next_action" not in health.package_maintenance["receipt"]


@pytest.mark.asyncio
async def test_failed_package_rollback_becomes_home_one_safe_next_action(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    app_root = tmp_path / "app"
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    create_backup(data_dir, tmp_path / "home" / "backups")
    write_package_receipt(
        app_root,
        operation_id="55555555-5555-4555-8555-555555555555",
        operation="update",
        status="FAILED_ROLLED_BACK",
        started_at="2026-08-30T12:00:00+00:00",
        previous_version="2.13.0",
        target_version="2.14.0",
        safety_backup="VERIFIED",
        product_verification=True,
        rollback="previous_product_restored",
        recoverable=True,
        next_action="create_support_report",
        failed_stage="4",
    )

    async def healthy_report():
        return _doctor_report()

    health = await _service(
        tmp_path,
        app_root=app_root,
        health_inspector=healthy_report,
    ).check_health()

    assert health.state == "NEEDS_ATTENTION"
    assert health.next_action == "create_support_report"
    assert health.diagnostic_codes == ("package_followup_required",)
    assert "next_action" not in health.package_maintenance["receipt"]
    assert health.package_maintenance["receipt"]["failed_stage"] == "4"

    plan = await _service(
        tmp_path,
        app_root=app_root,
        health_inspector=healthy_report,
    ).plan_support_report()
    package_receipt = plan.preview["operation_receipts"]["package"]["receipt"]
    assert package_receipt["operation"] == "update"
    assert package_receipt["status"] == "FAILED_ROLLED_BACK"
    assert package_receipt["failed_stage"] == "4"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("diagnostics", "customer_diagnostics", "expected_state", "next_action"),
    [
        (
            [],
            ["integration_surface_not_customer_ready"],
            "UNSUPPORTED",
            "use_supported_setup",
        ),
        (
            ["runtime_build_identity_mismatch"],
            [],
            "RECOVERY_REQUIRED",
            "create_support_report",
        ),
        (
            ["vector_integrity_failed"],
            [],
            "RECOVERY_REQUIRED",
            "restore",
        ),
    ],
)
async def test_health_maps_diagnostics_to_one_safe_next_action(
    tmp_path,
    diagnostics,
    customer_diagnostics,
    expected_state,
    next_action,
):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    create_backup(data_dir, tmp_path / "home" / "backups")

    async def inspected():
        return _doctor_report(
            ready=False,
            customer_ready=False,
            diagnostics=diagnostics,
            customer_diagnostics=customer_diagnostics,
        )

    health = await _service(tmp_path, health_inspector=inspected).check_health()

    assert health.state == expected_state
    assert health.next_action == next_action
    assert len(health.diagnostic_codes) == 1


@pytest.mark.asyncio
async def test_health_failure_is_content_free_and_requests_support_report(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "private customer memory")

    async def unavailable():
        raise RuntimeError("/private/customer/path private customer memory")

    health = await _service(tmp_path, health_inspector=unavailable).check_health()
    payload = json.dumps(health.to_dict())

    assert health.state == "NEEDS_ATTENTION"
    assert health.next_action == "create_support_report"
    assert health.diagnostic_codes == (
        "certified_agent_missing",
        "health_inspector_unavailable",
        "health_report_invalid",
        "recall_not_ready",
        "verified_backup_missing",
    )
    assert "private customer memory" not in payload
    assert "/private/customer/path" not in payload


def test_backup_plan_is_read_only_and_rejects_external_database_layout(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    service = _service(tmp_path)

    plan = service.plan_backup()

    assert plan.applicable is True
    assert plan.storage_layout == "managed"
    assert plan.estimated_files == 2
    assert plan.estimated_bytes > 0
    assert plan.irreversible is False
    assert not (tmp_path / "home" / "recovery" / "operations.json").exists()

    unsupported = VerifiedRecoveryService(
        data_dir=data_dir,
        vector_path=tmp_path / "external" / "vector",
        graph_path=data_dir / "kuzu_db",
        backup_dir=tmp_path / "home" / "backups",
        history_path=tmp_path / "home" / "recovery" / "operations.json",
        write_guard=lambda: _Guard(),
        quiesce_databases=lambda: asyncio.sleep(0),
    ).plan_backup()

    assert unsupported.applicable is False
    assert unsupported.reason_code == "RECOVERY_STORAGE_LAYOUT_UNSUPPORTED"


@pytest.mark.asyncio
async def test_verified_backup_quiesces_then_proves_archive_and_staged_restore(tmp_path):
    data_dir = tmp_path / "home" / "data"
    secret = "customer-secret-memory-body"
    _write_managed_data(data_dir, secret)
    events: list[str] = []

    async def quiesce():
        events.append("quiesced")

    from scripts.lifecycle.backup_elefante_data import create_backup

    def observed_backup(*args, **kwargs):
        assert events == ["quiesced"]
        events.append("backup")
        return create_backup(*args, **kwargs)

    service = _service(
        tmp_path,
        quiesce=quiesce,
        backup_creator=observed_backup,
    )
    plan = service.plan_backup()

    result = await service.execute_backup(
        expected_layout_sha256=plan.layout_sha256,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert events == ["quiesced", "backup"]
    assert result.receipt.recoverable is True
    assert result.receipt.changed is True
    assert result.receipt.archive_sha256
    assert result.receipt.source_sha256
    assert result.receipt.archive_name
    assert all(check.passed for check in result.receipt.checks)
    assert {check.name for check in result.receipt.checks} == {
        "archive_readback",
        "staged_restore",
        "sqlite_integrity",
        "kuzu_integrity",
    }
    assert (tmp_path / "home" / "backups" / result.receipt.archive_name).is_file()

    history_path = tmp_path / "home" / "recovery" / "operations.json"
    history_text = history_path.read_text(encoding="utf-8")
    assert secret not in history_text
    assert str(data_dir) not in history_text
    history = read_json_strict(history_path)
    assert history["operations"][-1]["status"] == "VERIFIED_COMPLETE"
    assert history_path.stat().st_mode & 0o777 == 0o600


@pytest.mark.asyncio
async def test_permanent_delete_consumes_only_its_exact_workflow_backup(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    service = _service(tmp_path)
    plan = service.plan_backup()
    result = await service.execute_backup(
        expected_layout_sha256=plan.layout_sha256,
        authority="workflow_managed",
    )
    archive = tmp_path / "home" / "backups" / str(result.receipt.archive_name)

    verified = await service.verify_workflow_backup(
        str(result.receipt.archive_name),
        expected_archive_sha256=str(result.receipt.archive_sha256),
        backup_operation_id=result.receipt.operation_id,
    )
    assert verified is True

    wrong = await service.discard_workflow_backup(
        str(result.receipt.archive_name),
        expected_archive_sha256="0" * 64,
        backup_operation_id=result.receipt.operation_id,
        consumed_by="permanent_delete",
    )
    assert wrong is False
    assert archive.is_file()

    removed = await service.discard_workflow_backup(
        str(result.receipt.archive_name),
        expected_archive_sha256=str(result.receipt.archive_sha256),
        backup_operation_id=result.receipt.operation_id,
        consumed_by="permanent_delete",
    )

    assert removed is True
    assert not archive.exists()
    history = read_json_strict(
        tmp_path / "home" / "recovery" / "operations.json"
    )
    consumed = history["operations"][-1]
    assert consumed["archive_consumed"] is True
    assert consumed["archive_consumed_by"] == "permanent_delete"
    assert consumed["recoverable"] is False
    assert await service.verify_workflow_backup(
        str(result.receipt.archive_name),
        expected_archive_sha256=str(result.receipt.archive_sha256),
        backup_operation_id=result.receipt.operation_id,
    ) is False


@pytest.mark.asyncio
async def test_stale_backup_plan_and_busy_lock_change_nothing(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    service = _service(tmp_path)
    plan = service.plan_backup()

    stale = await service.execute_backup(expected_layout_sha256="0" * 64)

    assert stale.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert stale.receipt.changed is False
    assert stale.receipt.error_codes == ("RECOVERY_PLAN_STALE",)
    assert not (tmp_path / "home" / "backups").exists()

    busy_service = _service(tmp_path, acquired=False)
    busy = await busy_service.execute_backup(
        expected_layout_sha256=plan.layout_sha256,
    )

    assert busy.status is VerifiedOperationStatus.FAILED_NO_CHANGE
    assert busy.receipt.changed is False
    assert busy.receipt.error_codes == ("RECOVERY_WRITE_LOCK_BUSY",)
    history = read_json_strict(tmp_path / "home" / "recovery" / "operations.json")
    assert history["operations"][-1]["status"] == "FAILED_NO_CHANGE"


@pytest.mark.asyncio
async def test_interruption_leaves_one_inspectable_running_receipt(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)

    async def interrupted():
        raise asyncio.CancelledError

    service = _service(tmp_path, quiesce=interrupted)
    plan = service.plan_backup()

    with pytest.raises(asyncio.CancelledError):
        await service.execute_backup(expected_layout_sha256=plan.layout_sha256)

    history = read_json_strict(tmp_path / "home" / "recovery" / "operations.json")
    assert len(history["operations"]) == 1
    assert history["operations"][0]["status"] == "RUNNING"
    assert history["operations"][0]["next_action"] == "wait_or_reopen_recover"


@pytest.mark.asyncio
async def test_failed_database_verification_removes_untrusted_archive(tmp_path):
    data_dir = tmp_path / "home" / "data"
    invalid_sqlite = data_dir / "vector" / "memories.sqlite3"
    invalid_sqlite.parent.mkdir(parents=True)
    invalid_sqlite.write_bytes(b"SQLite format 3\x00not-a-real-database")
    service = _service(tmp_path)
    plan = service.plan_backup()

    result = await service.execute_backup(
        expected_layout_sha256=plan.layout_sha256,
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.receipt.changed is False
    assert result.receipt.rollback == "verified"
    assert result.receipt.recoverable is False
    assert result.receipt.error_codes == ("RECOVERY_BACKUP_VERIFICATION_FAILED",)
    assert list((tmp_path / "home" / "backups").glob("*.zip")) == []


@pytest.mark.asyncio
async def test_verified_backup_opens_a_real_restaged_kuzu_database(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    graph_path = data_dir / "kuzu_db"
    graph = GraphStore(database_path=str(graph_path))
    try:
        graph._initialize_connection()
    finally:
        graph.close()
    service = _service(tmp_path)
    plan = service.plan_backup()

    result = await service.execute_backup(
        expected_layout_sha256=plan.layout_sha256,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    kuzu_check = next(
        check for check in result.receipt.checks if check.name == "kuzu_integrity"
    )
    assert kuzu_check.passed is True
    assert kuzu_check.code == "KUZU_OK"


def test_invalid_recovery_history_blocks_backup_before_any_mutation(tmp_path):
    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir)
    history_path = tmp_path / "home" / "recovery" / "operations.json"
    history_path.parent.mkdir(parents=True)
    history_path.write_text('{"schema_version":1,"operations":[],"operations":[]}', encoding="utf-8")

    plan = _service(tmp_path).plan_backup()

    assert plan.applicable is False
    assert plan.reason_code == "RECOVERY_HISTORY_INVALID"
    assert list((tmp_path / "home" / "backups").glob("*.zip")) == []


def test_restore_plan_lists_only_configured_basenames_and_is_read_only(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "backup state")
    archive = create_backup(data_dir, tmp_path / "home" / "backups")

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    plan = service.plan_restore(archive.name)

    assert plan.applicable is True
    assert plan.action == "restore"
    assert plan.archive_name == archive.name
    assert plan.archive_sha256
    assert plan.source_sha256
    assert plan.estimated_files == 2
    assert not (tmp_path / "home" / "recovery" / "operations.json").exists()
    assert [item.archive_name for item in service.available_backups()] == [archive.name]

    outside = service.plan_restore(f"../{archive.name}")
    assert outside.applicable is False
    assert outside.reason_code == "RECOVERY_ARCHIVE_INVALID"


def test_restore_inventory_marks_symlinked_archive_invalid(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "backup state")
    outside_archive = create_backup(data_dir, tmp_path / "outside")
    backup_dir = tmp_path / "home" / "backups"
    backup_dir.mkdir(parents=True)
    linked_archive = backup_dir / "linked_backup.zip"
    linked_archive.symlink_to(outside_archive)

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    inventory = service.available_backups()
    plan = service.plan_restore(linked_archive.name)

    assert len(inventory) == 1
    assert inventory[0].archive_name == linked_archive.name
    assert inventory[0].valid is False
    assert inventory[0].reason_code == "RECOVERY_ARCHIVE_INVALID"
    assert inventory[0].archive_sha256 is None
    assert plan.applicable is False
    assert plan.reason_code == "RECOVERY_ARCHIVE_INVALID"
    assert not (tmp_path / "home" / "recovery" / "operations.json").exists()


@pytest.mark.asyncio
async def test_restore_rejects_archive_changed_after_plan_without_mutation(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))
    quiesce_calls = 0

    async def quiesce():
        nonlocal quiesce_calls
        quiesce_calls += 1

    async def verify_restored(_question):
        return _product_checks()

    service = _service(
        tmp_path,
        quiesce=quiesce,
        verify_restored_data=verify_restored,
    )
    plan = service.plan_restore(target_archive.name)
    target_archive.write_bytes(target_archive.read_bytes() + b"changed-after-plan")

    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify restore",
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.receipt.changed is False
    assert result.receipt.error_codes == ("RECOVERY_PLAN_STALE",)
    assert quiesce_calls == 0
    assert not (tmp_path / "home" / "recovery" / "operations.json").exists()
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )


@pytest.mark.asyncio
async def test_restore_interruption_before_switch_keeps_predeclared_inspection_paths(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))

    async def interrupted():
        raise asyncio.CancelledError

    async def verify_restored(_question):
        return _product_checks()

    service = _service(
        tmp_path,
        quiesce=interrupted,
        verify_restored_data=verify_restored,
    )
    plan = service.plan_restore(target_archive.name)

    with pytest.raises(asyncio.CancelledError):
        await service.execute_restore(
            target_archive.name,
            expected_layout_sha256=plan.layout_sha256,
            expected_archive_sha256=str(plan.archive_sha256),
            verification_question="Verify restore",
        )

    history = read_json_strict(tmp_path / "home" / "recovery" / "operations.json")
    assert len(history["operations"]) == 1
    running = history["operations"][0]
    assert running["status"] == "RUNNING"
    assert running["next_action"] == "wait_or_reopen_recover"
    assert running["staging_name"].startswith(".data.restore.")
    assert running["previous_data_name"].startswith("data.pre_restore.")
    assert running["failed_restore_name"].startswith("data.failed_restore.")
    assert not (data_dir.parent / running["staging_name"]).exists()
    assert not (data_dir.parent / running["previous_data_name"]).exists()
    assert not (data_dir.parent / running["failed_restore_name"]).exists()
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )


@pytest.mark.asyncio
async def test_verified_restore_creates_safety_backup_then_switches_and_verifies(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "restored state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))
    (data_dir / "dashboard_snapshot.json").write_text(
        json.dumps({"schema_version": 2, "private": "current state"}),
        encoding="utf-8",
    )
    questions: list[str] = []

    async def verify_restored(question):
        questions.append(question)
        with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
            assert connection.execute("SELECT content FROM memories").fetchone() == (
                "restored state",
            )
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    plan = service.plan_restore(target_archive.name)
    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="What state should be restored?",
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.receipt.operation == "restore"
    assert result.receipt.changed is True
    assert result.receipt.recoverable is True
    assert result.receipt.safety_archive_name
    assert result.receipt.safety_archive_name != target_archive.name
    assert questions == ["What state should be restored?"]
    assert {"snapshot_refresh", "recall_verification"}.issubset(
        {check.name for check in result.receipt.checks}
    )
    previous = data_dir.parent / str(result.receipt.previous_data_name)
    with sqlite3.connect(previous / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )
    history_text = (tmp_path / "home" / "recovery" / "operations.json").read_text(
        encoding="utf-8"
    )
    assert "What state should be restored?" not in history_text
    assert "restored state" not in history_text
    assert "current state" not in history_text
    assert str(data_dir) not in history_text


@pytest.mark.asyncio
async def test_verified_restore_does_not_mutate_wal_archive_during_integrity_check(
    tmp_path,
):
    """A read-only staged check must not create SQLite WAL sidecars."""
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "restored WAL state")
    database = data_dir / "vector" / "memories.sqlite3"
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")

    with sqlite3.connect(database) as connection:
        connection.execute(
            "UPDATE memories SET content = ?",
            ("current WAL state",),
        )

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    plan = service.plan_restore(target_archive.name)
    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify the restored WAL state",
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert all(check.passed for check in result.receipt.checks)
    assert not database.with_name(f"{database.name}-wal").exists()
    assert not database.with_name(f"{database.name}-shm").exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "restored WAL state",
        )


@pytest.mark.asyncio
async def test_restore_staging_rejects_an_integrity_check_that_mutates_the_tree(
    tmp_path,
    monkeypatch,
):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    original_verify_sqlite = service._verify_sqlite

    def mutating_verify_sqlite(staged_data):
        check = original_verify_sqlite(staged_data)
        if staged_data.name.startswith(".data.restore."):
            (staged_data / "integrity-check-side-effect").write_text(
                "must be rejected",
                encoding="utf-8",
            )
        return check

    monkeypatch.setattr(service, "_verify_sqlite", mutating_verify_sqlite)
    plan = service.plan_restore(target_archive.name)
    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify target state",
    )

    assert result.status is VerifiedOperationStatus.FAILED_NO_CHANGE
    assert result.receipt.error_codes == (
        "RECOVERY_RESTORE_STAGING_VERIFICATION_FAILED",
    )
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )


@pytest.mark.asyncio
async def test_verified_restore_opens_real_kuzu_in_staging_and_active_data(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    graph_path = data_dir / "kuzu_db"
    graph = GraphStore(database_path=str(graph_path))
    try:
        graph._initialize_connection()
    finally:
        graph.close()
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")

    graph_path.unlink()
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    plan = service.plan_restore(target_archive.name)
    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify the restored graph",
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    checks = {check.name: check for check in result.receipt.checks}
    assert checks["staged_kuzu_integrity"].code == "KUZU_OK"
    assert checks["active_kuzu_integrity"].code == "KUZU_OK"
    reopened = GraphStore(database_path=str(graph_path))
    try:
        reopened._initialize_connection()
    finally:
        reopened.close()


@pytest.mark.asyncio
async def test_failed_recall_after_restore_rolls_back_exact_previous_data(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("exact current state",))
    (data_dir / "dashboard_snapshot.json").write_text(
        json.dumps({"schema_version": 2, "private": "exact current state"}),
        encoding="utf-8",
    )

    async def reject_recall(_question):
        return _product_checks(recall_passed=False)

    service = _service(tmp_path, verify_restored_data=reject_recall)
    original_manifest = build_backup_manifest(data_dir)
    plan = service.plan_restore(target_archive.name)
    result = await service.execute_restore(
        target_archive.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify the restored decision",
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.receipt.changed is False
    assert result.receipt.rollback == "verified"
    assert result.receipt.error_codes == ("RECOVERY_POST_VERIFICATION_FAILED",)
    assert build_backup_manifest(data_dir)["files"] == original_manifest["files"]
    assert not (data_dir.parent / str(result.receipt.previous_data_name)).exists()
    assert not (data_dir.parent / str(result.receipt.failed_restore_name)).exists()
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "exact current state",
        )


@pytest.mark.asyncio
async def test_restore_staging_failure_never_switches_current_data(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))
    invalid_sqlite = data_dir / "vector" / "memories.sqlite3"
    invalid_sqlite.unlink()
    invalid_sqlite.write_bytes(b"SQLite format 3\x00not-a-real-database")
    invalid_target = create_backup(data_dir, tmp_path / "home" / "backups")
    target_archive.unlink()
    invalid_sqlite.unlink()
    _write_managed_data(data_dir, "current state")

    async def verify_restored(_question):
        return _product_checks()

    service = _service(tmp_path, verify_restored_data=verify_restored)
    plan = service.plan_restore(invalid_target.name)
    result = await service.execute_restore(
        invalid_target.name,
        expected_layout_sha256=plan.layout_sha256,
        expected_archive_sha256=str(plan.archive_sha256),
        verification_question="Verify restore",
    )

    assert result.status is VerifiedOperationStatus.FAILED_NO_CHANGE
    assert result.receipt.changed is False
    assert result.receipt.error_codes == (
        "RECOVERY_RESTORE_STAGING_VERIFICATION_FAILED",
    )
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )
    assert not (data_dir.parent / str(result.receipt.previous_data_name)).exists()


@pytest.mark.asyncio
async def test_restore_interruption_after_switch_rolls_back_and_records_terminal_state(tmp_path):
    from scripts.lifecycle.backup_elefante_data import create_backup

    data_dir = tmp_path / "home" / "data"
    _write_managed_data(data_dir, "target backup state")
    target_archive = create_backup(data_dir, tmp_path / "home" / "backups")
    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        connection.execute("UPDATE memories SET content = ?", ("current state",))

    async def interrupted(_question):
        raise asyncio.CancelledError

    service = _service(tmp_path, verify_restored_data=interrupted)
    plan = service.plan_restore(target_archive.name)
    with pytest.raises(asyncio.CancelledError):
        await service.execute_restore(
            target_archive.name,
            expected_layout_sha256=plan.layout_sha256,
            expected_archive_sha256=str(plan.archive_sha256),
            verification_question="Verify restore",
        )

    with sqlite3.connect(data_dir / "vector" / "memories.sqlite3") as connection:
        assert connection.execute("SELECT content FROM memories").fetchone() == (
            "current state",
        )
    history = read_json_strict(tmp_path / "home" / "recovery" / "operations.json")
    receipt = history["operations"][-1]
    assert receipt["status"] == "FAILED_ROLLED_BACK"
    assert receipt["error_codes"] == ["RECOVERY_RESTORE_INTERRUPTED"]
    assert receipt["staging_name"].startswith(".data.restore.")
    assert receipt["previous_data_name"].startswith("data.pre_restore.")
    assert receipt["failed_restore_name"].startswith("data.failed_restore.")
