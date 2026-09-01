"""Tests for exact-package product scenario execution and evidence receipts."""

from __future__ import annotations

import asyncio
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import plistlib
import stat
from types import SimpleNamespace
import zipfile

import pytest

from scripts.ci import run_product_release_scenarios as scenarios
from scripts.ci.verify_product_release_gate import REQUIRED_SCENARIO_CHECKS


def _context(tmp_path: Path) -> scenarios.ScenarioContext:
    artifact = tmp_path / "elefante-exact.zip"
    artifact.write_bytes(b"exact artifact")
    install_root = tmp_path / "home" / ".elefante" / "app" / "current"
    data_root = tmp_path / "home" / ".elefante" / "data"
    alpha = tmp_path / "home" / "projects" / "Alpha"
    beta = tmp_path / "home" / "projects" / "Beta"
    for path in (install_root, data_root, alpha, beta):
        path.mkdir(parents=True, exist_ok=True)
    return scenarios.ScenarioContext(
        artifact_path=artifact,
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        install_root=install_root,
        data_root=data_root,
        customer_home=tmp_path / "home",
        project_alpha=alpha,
        project_beta=beta,
        machine_id="11111111-1111-4111-8111-111111111111",
        output_dir=tmp_path / "evidence",
    )


def test_scenario_receipt_is_private_content_free_and_digest_bound(tmp_path):
    context = _context(tmp_path)
    private_canary = str(context.project_alpha)

    gate = scenarios.write_scenario_receipt(
        context,
        "B",
        sorted(REQUIRED_SCENARIO_CHECKS["B"]),
    )

    receipt_path = context.output_dir / "scenario-B.json"
    gate_path = context.output_dir / "scenario-B.gate.json"
    receipt_bytes = receipt_path.read_bytes()
    assert stat.S_IMODE(receipt_path.stat().st_mode) == 0o600
    assert stat.S_IMODE(gate_path.stat().st_mode) == 0o600
    assert gate["receipt_sha256"] == hashlib.sha256(receipt_bytes).hexdigest()
    assert gate["checks"] == sorted(REQUIRED_SCENARIO_CHECKS["B"])
    assert gate["isolation_preflight_passed"] is True
    assert gate["unattended"] is True
    assert private_canary.encode() not in receipt_bytes
    assert b"customer_content_included\": false" in receipt_bytes


def test_scenario_receipt_rejects_an_incomplete_check_set(tmp_path):
    context = _context(tmp_path)

    with pytest.raises(scenarios.ScenarioFailure, match="SCENARIO_CHECK_SET_INCOMPLETE"):
        scenarios.write_scenario_receipt(
            context,
            "F",
            ["failed_stage_identified"],
        )


def test_scenario_receipt_never_overwrites_prior_evidence(tmp_path):
    context = _context(tmp_path)
    checks = sorted(REQUIRED_SCENARIO_CHECKS["A"])
    scenarios.write_scenario_receipt(context, "A", checks)

    with pytest.raises(scenarios.ScenarioFailure, match="SCENARIO_RECEIPT_ALREADY_EXISTS"):
        scenarios.write_scenario_receipt(context, "A", checks)


def test_build_context_binds_artifact_and_certified_lane(monkeypatch, tmp_path):
    context = _context(tmp_path)
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o700)
    scenario_root = tmp_path / "scenario-runtime"
    evidence = tmp_path / "evidence-runtime"
    monkeypatch.setattr(scenarios.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(scenarios.platform, "machine", lambda: "arm64")
    args = scenarios.parse_args(
        [
            "--artifact",
            str(context.artifact_path),
            "--expected-artifact-sha256",
            context.artifact_sha256,
            "--scenario-root",
            str(scenario_root),
            "--codex-executable",
            str(codex),
            "--machine-id",
            context.machine_id,
            "--output-dir",
            str(evidence),
            "--confirm-isolated-machine",
            scenarios.CONFIRMATION,
        ]
    )

    built = scenarios.build_context(args)

    assert built.artifact_sha256 == context.artifact_sha256
    assert built.machine_id == context.machine_id
    assert built.scenario_root == scenario_root.resolve()
    assert built.output_dir == evidence.resolve()

    args.expected_artifact_sha256 = "f" * 64
    with pytest.raises(scenarios.ScenarioFailure, match="ARTIFACT_SHA256_MISMATCH"):
        scenarios.build_context(args)


def test_build_lifecycle_context_derives_every_mutable_path_under_disposable_root(
    monkeypatch,
    tmp_path,
):
    candidate = tmp_path / "candidate.dmg"
    baseline = tmp_path / "baseline.zip"
    candidate.write_bytes(b"candidate exact artifact")
    baseline.write_bytes(b"baseline exact artifact")
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o700)
    scenario_root = tmp_path / "scenario-d"
    monkeypatch.setattr(scenarios.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(scenarios.platform, "machine", lambda: "arm64")
    args = scenarios.parse_args(
        [
            "--artifact",
            str(candidate),
            "--baseline-artifact",
            str(baseline),
            "--scenario-root",
            str(scenario_root),
            "--codex-executable",
            str(codex),
            "--machine-id",
            "11111111-1111-4111-8111-111111111111",
            "--output-dir",
            str(tmp_path / "evidence-d"),
            "--scenario",
            "D",
            "--confirm-isolated-machine",
            scenarios.CONFIRMATION,
        ]
    )

    context = scenarios.build_lifecycle_context(args)

    assert context.scenario_root == scenario_root.resolve()
    assert context.output_dir == (tmp_path / "evidence-d").resolve()
    assert context.lane_install_root("failed-update").is_relative_to(context.scenario_root)
    assert context.lane_data_root("failed-update").is_relative_to(context.scenario_root)
    assert stat.S_IMODE(context.scenario_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(context.output_dir.stat().st_mode) == 0o700


def test_build_data_lifecycle_context_needs_only_one_exact_package(
    monkeypatch,
    tmp_path,
):
    candidate = tmp_path / "candidate.zip"
    candidate.write_bytes(b"candidate exact artifact")
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o700)
    scenario_root = tmp_path / "scenario-e"
    monkeypatch.setattr(scenarios.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(scenarios.platform, "machine", lambda: "arm64")
    args = scenarios.parse_args(
        [
            "--artifact",
            str(candidate),
            "--scenario-root",
            str(scenario_root),
            "--codex-executable",
            str(codex),
            "--machine-id",
            "11111111-1111-4111-8111-111111111111",
            "--output-dir",
            str(tmp_path / "evidence-e"),
            "--scenario",
            "E",
            "--confirm-isolated-machine",
            scenarios.CONFIRMATION,
        ]
    )

    context = scenarios.build_data_lifecycle_context(args)

    assert context.artifact_sha256 == hashlib.sha256(candidate.read_bytes()).hexdigest()
    assert context.baseline_artifact_path is None
    assert context.lane_data_root("data-lifecycle").is_relative_to(scenario_root)
    assert stat.S_IMODE(context.scenario_root.stat().st_mode) == 0o700
    assert stat.S_IMODE(context.output_dir.stat().st_mode) == 0o700


def test_scenario_d_receipt_uses_the_same_private_artifact_binding(tmp_path):
    context = _context(tmp_path)
    lifecycle = scenarios.LifecycleScenarioContext(
        artifact_path=context.artifact_path,
        artifact_sha256=context.artifact_sha256,
        baseline_artifact_path=tmp_path / "baseline.zip",
        baseline_artifact_sha256="f" * 64,
        scenario_root=tmp_path / "scenario-d",
        codex_executable=tmp_path / "codex",
        machine_id=context.machine_id,
        output_dir=context.output_dir,
    )

    gate = scenarios.write_scenario_receipt(
        lifecycle,
        "D",
        sorted(REQUIRED_SCENARIO_CHECKS["D"]),
    )

    assert gate["artifact_sha256"] == context.artifact_sha256
    assert gate["checks"] == sorted(REQUIRED_SCENARIO_CHECKS["D"])
    assert stat.S_IMODE((context.output_dir / "scenario-D.json").stat().st_mode) == 0o600


def test_dmg_mount_parser_requires_one_mount_point():
    valid = plistlib.dumps(
        {"system-entities": [{"dev-entry": "/dev/disk1"}, {"mount-point": "/Volumes/Elefante"}]}
    )
    assert scenarios._dmg_mount_point(valid) == Path("/Volumes/Elefante").resolve()

    ambiguous = plistlib.dumps(
        {
            "system-entities": [
                {"mount-point": "/Volumes/Elefante"},
                {"mount-point": "/Volumes/Elefante 1"},
            ]
        }
    )
    with pytest.raises(scenarios.ScenarioFailure, match="PACKAGE_DMG_MOUNT_AMBIGUOUS"):
        scenarios._dmg_mount_point(ambiguous)


def test_package_zip_validation_rejects_traversal_and_symlinks(tmp_path):
    safe = tmp_path / "safe.zip"
    with zipfile.ZipFile(safe, "w") as archive:
        archive.writestr("elefante/install.sh", "#!/bin/sh\n")
    scenarios._validate_zip_members(safe)

    traversal = tmp_path / "traversal.zip"
    with zipfile.ZipFile(traversal, "w") as archive:
        archive.writestr("../outside", "unsafe")
    with pytest.raises(scenarios.ScenarioFailure, match="PACKAGE_ARCHIVE_UNSAFE"):
        scenarios._validate_zip_members(traversal)

    symlink = tmp_path / "symlink.zip"
    member = zipfile.ZipInfo("elefante/install.sh")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(symlink, "w") as archive:
        archive.writestr(member, "../../outside")
    with pytest.raises(scenarios.ScenarioFailure, match="PACKAGE_ARCHIVE_UNSAFE"):
        scenarios._validate_zip_members(symlink)


def test_installed_payload_must_match_every_shipped_package_byte(tmp_path):
    bundle_root = tmp_path / "bundle"
    payload = bundle_root / "payload" / "elefante"
    installed = tmp_path / "installed"
    for root in (payload, installed):
        (root / "src").mkdir(parents=True)
        (root / "src" / "runtime.py").write_text("trusted = True\n", encoding="utf-8")

    digest = scenarios._verify_installed_payload_matches_package(bundle_root, installed)
    assert len(digest) == 64

    (installed / "src" / "runtime.py").write_text("trusted = False\n", encoding="utf-8")
    with pytest.raises(scenarios.ScenarioFailure, match="RUNTIME_PAYLOAD_FILE_MISMATCH"):
        scenarios._verify_installed_payload_matches_package(bundle_root, installed)


def test_failed_update_receipt_requires_verified_restore_and_one_action():
    receipt = {
        "operation": "update",
        "status": "FAILED_ROLLED_BACK",
        "failed_stage": "4",
        "rollback": "previous_product_restored",
        "recoverable": True,
        "changed": False,
        "next_action": "create_support_report",
        "failed_candidate_name": None,
        "checks": [
            {"name": "safety_backup", "passed": True},
            {"name": "product_readiness", "passed": True},
        ],
    }
    scenarios._validate_failed_update_receipt(receipt)

    receipt["next_action"] = "retry_forever"
    with pytest.raises(scenarios.ScenarioFailure, match="D_FAILED_UPDATE_RECEIPT_INVALID"):
        scenarios._validate_failed_update_receipt(receipt)


def test_zero_cross_project_delivery_requires_exact_no_match_contract():
    valid = {
        "status": "no_match",
        "supplied_count": 0,
        "abstained": True,
        "delivery_blocked": False,
        "read_only": True,
        "context": "",
    }
    assert scenarios._no_memory_delivery(valid, "private-anchor")

    for key, value in (
        ("status", "blocked"),
        ("supplied_count", 1),
        ("abstained", False),
        ("delivery_blocked", True),
        ("read_only", False),
        ("context", "private-anchor"),
    ):
        invalid = {**valid, key: value}
        assert not scenarios._no_memory_delivery(invalid, "private-anchor")


def test_run_scenario_d_requires_every_lifecycle_postcondition(monkeypatch, tmp_path):
    context = _context(tmp_path)
    lifecycle = scenarios.LifecycleScenarioContext(
        artifact_path=context.artifact_path,
        artifact_sha256=context.artifact_sha256,
        baseline_artifact_path=tmp_path / "baseline.zip",
        baseline_artifact_sha256="f" * 64,
        scenario_root=tmp_path / "scenario-d",
        codex_executable=tmp_path / "codex",
        machine_id=context.machine_id,
        output_dir=context.output_dir,
    )
    candidate_root = tmp_path / "candidate-root"
    baseline_root = tmp_path / "baseline-root"
    fresh_install = tmp_path / "fresh-install"
    update_install = tmp_path / "update-install"
    project = tmp_path / "project"
    for path in (candidate_root, baseline_root, fresh_install, update_install, project):
        path.mkdir()
    calls: list[str] = []

    @contextmanager
    def materialized(artifact, _destination):
        yield candidate_root if Path(artifact) == lifecycle.artifact_path else baseline_root

    async def interrupted(*_args):
        calls.append("interruption")
        return fresh_install, project, {"HOME": str(tmp_path / "fresh-home")}

    async def restarted(*_args):
        calls.append("restart")

    async def failed_update(*_args):
        calls.append("rollback")
        return update_install, {"HOME": str(tmp_path / "update-home")}

    async def stopped(*_args):
        calls.append("stop")

    monkeypatch.setattr(scenarios, "_require_clean_scenario_machine", lambda _context: None)
    monkeypatch.setattr(scenarios, "_materialize_package", materialized)
    monkeypatch.setattr(
        scenarios,
        "_package_identity",
        lambda root: {
            "schema_version": 1,
            "version": "2.14.0",
            "source_commit": ("a" if root == candidate_root else "b") * 40,
            "source_clean": True,
            "release_channel": "candidate",
        },
    )
    monkeypatch.setattr(scenarios, "_exercise_interrupted_install", interrupted)
    monkeypatch.setattr(scenarios, "_exercise_daemon_restart_and_stale_session", restarted)
    monkeypatch.setattr(scenarios, "_exercise_failed_update_rollback", failed_update)
    monkeypatch.setattr(scenarios, "_stop_lane_service", stopped)

    checks = asyncio.run(scenarios.run_scenario_d(lifecycle))

    assert checks == REQUIRED_SCENARIO_CHECKS["D"]
    assert calls[:3] == ["interruption", "restart", "stop"]
    assert "rollback" in calls


def test_recovery_receipt_requires_all_integrity_postconditions():
    required = {"archive_readback", "sqlite_integrity", "kuzu_integrity"}
    payload = {
        "success": True,
        "status": "VERIFIED_COMPLETE",
        "recovery_status": "VERIFIED_COMPLETE",
        "receipt": {
            "operation": "backup",
            "status": "VERIFIED_COMPLETE",
            "authority": "user_directed",
            "changed": True,
            "recoverable": True,
            "error_codes": [],
            "next_action": "none",
            "checks": [
                {"name": name, "passed": True, "code": f"{name.upper()}_OK"}
                for name in sorted(required)
            ],
        },
    }

    receipt, checks = scenarios._recovery_receipt(
        payload,
        operation="backup",
        required_checks=required,
        code="E_BACKUP_VERIFICATION_FAILED",
    )

    assert receipt["operation"] == "backup"
    assert set(checks) == required
    payload["receipt"]["checks"] = payload["receipt"]["checks"][:-1]
    with pytest.raises(scenarios.ScenarioFailure, match="E_BACKUP_VERIFICATION_FAILED"):
        scenarios._recovery_receipt(
            payload,
            operation="backup",
            required_checks=required,
            code="E_BACKUP_VERIFICATION_FAILED",
        )


def test_run_scenario_e_requires_the_complete_data_lifecycle(monkeypatch, tmp_path):
    runtime = _context(tmp_path)
    context = scenarios.LifecycleScenarioContext(
        artifact_path=runtime.artifact_path,
        artifact_sha256=runtime.artifact_sha256,
        scenario_root=tmp_path / "scenario-e",
        codex_executable=tmp_path / "codex",
        machine_id=runtime.machine_id,
        output_dir=runtime.output_dir,
    )
    candidate_root = tmp_path / "candidate-root"
    candidate_root.mkdir()
    calls: list[str] = []

    @contextmanager
    def materialized(_artifact, _destination):
        calls.append("materialized")
        yield candidate_root

    async def exercised(received_context, received_root, identity):
        assert received_context is context
        assert received_root == candidate_root
        assert identity["version"] == "2.14.0"
        calls.append("data-lifecycle")

    monkeypatch.setattr(scenarios, "_require_clean_scenario_machine", lambda _context: None)
    monkeypatch.setattr(scenarios, "_materialize_package", materialized)
    monkeypatch.setattr(
        scenarios,
        "_package_identity",
        lambda _root: {
            "schema_version": 1,
            "version": "2.14.0",
            "source_commit": "a" * 40,
            "source_clean": True,
            "release_channel": "candidate",
        },
    )
    monkeypatch.setattr(scenarios, "_exercise_data_lifecycle", exercised)

    checks = asyncio.run(scenarios.run_scenario_e(context))

    assert checks == REQUIRED_SCENARIO_CHECKS["E"]
    assert calls == ["materialized", "data-lifecycle"]


def test_runtime_scenarios_install_exact_package_before_any_product_check(
    monkeypatch,
    tmp_path,
):
    artifact = tmp_path / "candidate.dmg"
    artifact.write_bytes(b"candidate")
    codex = tmp_path / "codex"
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o700)
    scenario_root = tmp_path / "scenario-runtime"
    scenario_root.mkdir()
    context = scenarios.LifecycleScenarioContext(
        artifact_path=artifact,
        artifact_sha256=hashlib.sha256(artifact.read_bytes()).hexdigest(),
        scenario_root=scenario_root,
        codex_executable=codex,
        machine_id="11111111-1111-4111-8111-111111111111",
        output_dir=tmp_path / "evidence",
    )
    bundle_root = tmp_path / "bundle-root"
    bundle_root.mkdir()
    calls: list[str] = []

    @contextmanager
    def materialized(_artifact, _destination):
        calls.append("materialize")
        yield bundle_root

    async def install(**kwargs):
        calls.append("install")
        assert kwargs["bundle_root"] == bundle_root
        assert [name for name, _root in kwargs["projects"]] == ["Alpha", "Beta"]
        kwargs["install_root"].mkdir(parents=True)

    async def selected(runtime, selected_scenarios):
        calls.append("scenarios")
        assert runtime.bundle_root == bundle_root
        assert runtime.base_environment is not None
        assert selected_scenarios == ["A", "F"]
        return {"A": {"status": "PASS"}, "F": {"status": "PASS"}}

    async def stop(*_args):
        calls.append("stop")

    monkeypatch.setattr(scenarios, "_require_clean_scenario_machine", lambda _context: None)
    monkeypatch.setattr(scenarios, "_materialize_package", materialized)
    monkeypatch.setattr(scenarios, "_package_identity", lambda _root: {"version": "2.13.0"})
    monkeypatch.setattr(scenarios, "_install_exact_candidate", install)
    monkeypatch.setattr(scenarios, "run_selected_runtime_scenarios", selected)
    monkeypatch.setattr(
        scenarios,
        "_verify_installed_payload_matches_package",
        lambda *_args: "d" * 64,
    )
    monkeypatch.setattr(scenarios, "_stop_lane_service", stop)

    result = asyncio.run(
        scenarios.run_runtime_package_scenarios(context, ["A", "F"])
    )

    assert result == {"A": {"status": "PASS"}, "F": {"status": "PASS"}}
    assert calls == ["materialize", "install", "scenarios", "stop"]


def test_runtime_scenarios_bind_installed_identity_to_exact_artifact(
    monkeypatch,
    tmp_path,
):
    context = _context(tmp_path)
    context.output_dir.mkdir()
    bundle_root = tmp_path / "bundle-root"
    bundle_root.mkdir()
    identity = {
        "schema_version": 1,
        "version": "2.14.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "candidate",
    }
    (context.install_root / scenarios.BUILD_IDENTITY_FILE_NAME).write_text(
        json.dumps(identity),
        encoding="utf-8",
    )

    @contextmanager
    def materialized(artifact, destination):
        assert artifact == context.artifact_path
        assert destination.parent.parent == context.output_dir
        yield bundle_root

    monkeypatch.setattr(scenarios, "_materialize_package", materialized)
    monkeypatch.setattr(scenarios, "_package_identity", lambda _root: identity)

    scenarios.verify_runtime_artifact_identity(context)

    mismatched = {**identity, "source_commit": "b" * 40}
    monkeypatch.setattr(scenarios, "_package_identity", lambda _root: mismatched)
    with pytest.raises(
        scenarios.ScenarioFailure,
        match="RUNTIME_ARTIFACT_IDENTITY_MISMATCH",
    ):
        scenarios.verify_runtime_artifact_identity(context)


class _FirstUseClient:
    def __init__(self, state: dict[str, object]) -> None:
        self.state = state

    async def start(self) -> None:
        self.state["starts"] = int(self.state.get("starts", 0)) + 1

    async def close(self) -> None:
        self.state["closes"] = int(self.state.get("closes", 0)) + 1

    async def call_tool(self, name, arguments):
        if name == "elefante-Recover":
            return {
                "success": True,
                "health": {"state": "READY", "connected_agents": ["Codex"]},
            }
        if name == "elefante-Recall":
            return {
                "status": "supplied",
                "read_only": True,
                "context": self.state["content"],
            }
        assert name == "elefante-Memory"
        if arguments.get("list_all") is True:
            return {"success": True, "memories": []}
        if arguments["action"] == "search":
            return {"success": True, "memories": []}
        assert arguments["action"] == "add"
        self.state["content"] = arguments["content"]
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "remember_status": "VERIFIED_COMPLETE",
            "memory_written": True,
            "classification": "VERIFIED",
            "memory_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            "receipt": {
                "checks": [
                    {"name": "scoped_recall", "passed": True, "code": "RECALL_OK"}
                ]
            },
        }


def test_first_use_scenario_requires_receipt_cleanup_and_agent_restart(tmp_path):
    context = _context(tmp_path)
    backup = context.data_root.parent / "backups" / "elefante_data_backup.zip"
    backup.parent.mkdir(parents=True)
    backup.write_bytes(b"verified initial backup")
    receipt = {
        "schema_version": 1,
        "operation": "first_run_acceptance",
        "status": "VERIFIED_COMPLETE",
        "finished_at": "2026-08-30T14:00:00+00:00",
        "checks": [
            {"name": name, "passed": True, "code": f"{name.upper()}_VERIFIED"}
            for name in (
                "project_isolation",
                "disposable_recall",
                "acceptance_cleanup",
                "initial_backup",
            )
        ],
        "acceptance_operation_id": "11111111-1111-4111-8111-111111111111",
        "backup_operation_id": "22222222-2222-4222-8222-222222222222",
        "initial_backup": {
            "archive_name": backup.name,
            "archive_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
        },
        "memory_content_included": False,
        "project_path_included": False,
        "next_action": "open_elefante_home",
    }
    receipt_path = context.install_root / scenarios.FIRST_RUN_RECEIPT_FILE_NAME
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    receipt_path.chmod(0o600)
    projects = []
    for index, (name, root) in enumerate(
        (("Alpha", context.project_alpha), ("Beta", context.project_beta)),
        start=1,
    ):
        projects.append(
            {
                "project_id": f"{index:08d}-1111-4111-8111-111111111111",
                "name": name,
                "root": str(root.resolve()),
                "active": True,
                "created_at": "2026-08-30T14:00:00+00:00",
                "updated_at": "2026-08-30T14:00:00+00:00",
            }
        )
    (context.data_root / "projects.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generation_id": "33333333-3333-4333-8333-333333333333",
                "revision": 1,
                "updated_at": "2026-08-30T14:00:00+00:00",
                "mode": "strict",
                "projects": projects,
            }
        ),
        encoding="utf-8",
    )
    state: dict[str, object] = {"starts": 0, "closes": 0}

    checks = asyncio.run(
        scenarios.run_scenario_a(
            context,
            client_factory=lambda _workspace: _FirstUseClient(state),
        )
    )

    assert checks == REQUIRED_SCENARIO_CHECKS["A"]
    assert state["starts"] == 2
    assert state["closes"] == 2
    assert "release-first-use-" in str(state["content"])


class _ProjectClient:
    def __init__(self, context: scenarios.ScenarioContext, workspace: Path) -> None:
        self.context = context
        self.workspace = workspace
        self.ids: dict[Path, set[str]] = {
            context.project_alpha: set(),
            context.project_beta: set(),
        }

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def call_tool(self, name, arguments):
        if name == "elefante-Recall":
            try:
                json.loads((self.context.data_root / "projects.json").read_text())
            except json.JSONDecodeError:
                return {
                    "status": "blocked",
                    "supplied_count": 0,
                    "delivery_blocked": True,
                    "read_only": True,
                }
            if self.workspace == self.context.project_alpha:
                return {
                    "status": "supplied",
                    "context": "amber",
                    "read_only": True,
                }
            if self.workspace == self.context.project_beta:
                return {
                    "status": "supplied",
                    "context": "violet",
                    "read_only": True,
                }
            return {
                "status": "blocked",
                "supplied_count": 0,
                "delivery_blocked": True,
                "read_only": True,
            }
        assert name == "elefante-Memory"
        if arguments["action"] == "search" and arguments.get("list_all") is True:
            values = _PROJECT_MEMORY_IDS.setdefault(self.workspace, set())
            return {
                "success": True,
                "memories": [{"id": value} for value in sorted(values)],
            }
        if arguments["action"] == "search":
            return {"success": True, "memories": []}
        assert arguments["action"] == "add"
        memory_id = (
            "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
            if "amber" in arguments["content"]
            else "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
        )
        _PROJECT_MEMORY_IDS.setdefault(self.workspace, set()).add(memory_id)
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "remember_status": "VERIFIED_COMPLETE",
            "memory_written": True,
            "classification": "VERIFIED",
            "memory_id": memory_id,
            "receipt": {
                "checks": [
                    {"name": "scoped_recall", "passed": True, "code": "RECALL_OK"}
                ]
            },
        }


_PROJECT_MEMORY_IDS: dict[Path, set[str]] = {}


def test_project_scenario_proves_isolation_and_invalid_state_abstention(tmp_path):
    context = _context(tmp_path)
    _PROJECT_MEMORY_IDS.clear()
    (context.data_root / "projects.json").write_text(
        json.dumps({"schema_version": 1, "mode": "strict", "projects": []}),
        encoding="utf-8",
    )
    (context.data_root / "dashboard_snapshot.json").write_text(
        json.dumps(
            {
                "project_registry": {
                    "mode": "strict",
                    "scope_policy": "isolated",
                    "shared_across_projects": False,
                }
            }
        ),
        encoding="utf-8",
    )

    checks = asyncio.run(
        scenarios.run_scenario_b(
            context,
            client_factory=lambda workspace: _ProjectClient(context, workspace),
        )
    )

    assert checks == REQUIRED_SCENARIO_CHECKS["B"]
    restored = json.loads((context.data_root / "projects.json").read_text())
    assert restored["mode"] == "strict"


class _CorrectionClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def call_tool(self, name, arguments):
        self.calls.append((name, dict(arguments)))
        if arguments.get("action") == "search":
            return {"success": True}
        if arguments.get("apply") is not True:
            return {
                "success": True,
                "plan": {
                    "applicable": True,
                    "record_sha256": {"target": "a" * 64},
                    "graph_sha256": {"target": "b" * 64},
                    "content_sha256": "c" * 64,
                },
            }
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "receipt": {
                "checks": [
                    {"name": "scoped_recall", "passed": True, "code": "RECALL_OK"}
                ]
            },
        }


def test_correction_apply_binds_exact_plan_and_permanent_confirmation():
    client = _CorrectionClient()

    result = asyncio.run(
        scenarios._apply_correction(
            client,
            memory_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            correction="permanent_delete",
            question="What synthetic record remains?",
            reason="Scenario C exact delete.",
        )
    )

    assert result["status"] == "VERIFIED_COMPLETE"
    applied = client.calls[-1][1]
    assert applied["expected_record_sha256"] == {"target": "a" * 64}
    assert applied["expected_graph_sha256"] == {"target": "b" * 64}
    assert applied["confirm_permanent"] is True
    assert applied["invocation_mode"] == "user_directed"


def test_permanent_delete_scenario_rejects_a_remaining_safety_archive(tmp_path):
    archive_name = "elefante_data_backup_delete.zip"
    result = {
        "receipt": {
            "recoverable": False,
            "recovery_archive_name": archive_name,
        }
    }
    memory_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    data_root = tmp_path / "home" / "data"
    data_root.mkdir(parents=True)

    assert scenarios._permanent_delete_is_final(
        result,
        data_root=data_root,
        memory_id=memory_id,
        remaining_ids=set(),
    )

    archive = data_root.parent / "backups" / archive_name
    archive.parent.mkdir()
    archive.write_bytes(b"still recoverable")
    assert not scenarios._permanent_delete_is_final(
        result,
        data_root=data_root,
        memory_id=memory_id,
        remaining_ids=set(),
    )


def test_support_report_reader_rejects_extra_members_and_duplicate_json(tmp_path):
    valid = tmp_path / "valid.zip"
    with zipfile.ZipFile(valid, "w") as archive:
        archive.writestr(
            "support-report.json",
            json.dumps({"schema_version": 1, "evidence": {}}),
        )

    payload, report = scenarios._read_support_report(valid)

    assert json.loads(payload)["schema_version"] == 1
    assert report["evidence"] == {}

    extra = tmp_path / "extra.zip"
    with zipfile.ZipFile(extra, "w") as archive:
        archive.writestr("support-report.json", "{}")
        archive.writestr("private.log", "customer content")
    with pytest.raises(scenarios.ScenarioFailure, match="F_SUPPORT_ARCHIVE_LAYOUT_INVALID"):
        scenarios._read_support_report(extra)

    duplicate = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(duplicate, "w") as archive:
        archive.writestr(
            "support-report.json",
            '{"schema_version":1,"schema_version":1}',
        )
    with pytest.raises(scenarios.ScenarioFailure, match="F_SUPPORT_REPORT_INVALID"):
        scenarios._read_support_report(duplicate)


class _ScenarioFClient:
    def __init__(
        self,
        context: scenarios.ScenarioContext,
        state: dict[str, object],
    ) -> None:
        self.context = context
        self.state = state

    async def start(self) -> None:
        self.state["starts"] = int(self.state.get("starts", 0)) + 1

    async def close(self) -> None:
        self.state["closes"] = int(self.state.get("closes", 0)) + 1

    async def call_tool(self, name, arguments):
        if name == "elefante-Memory":
            if arguments["action"] == "search":
                return {"success": True, "memories": []}
            self.state["memory"] = arguments["content"]
            return {
                "status": "stored",
                "memory_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            }
        if name == "elefante-Recall":
            return {
                "status": "supplied",
                "read_only": True,
                "context": self.state.get("memory", ""),
            }
        assert name == "elefante-Recover"
        if arguments["action"] == "health":
            return {
                "success": True,
                "health": {
                    "state": "NEEDS_ATTENTION",
                    "next_action": "create_support_report",
                    "diagnostic_codes": ["package_followup_required"],
                    "package_maintenance": {
                        "receipt": {
                            "operation": "repair",
                            "status": "FAILED_ROLLED_BACK",
                            "failed_stage": "4",
                        }
                    },
                },
            }
        if arguments.get("apply") is not True:
            return {
                "success": True,
                "plan": {
                    "applicable": True,
                    "report_sha256": "f" * 64,
                    "preview": {"diagnostic_codes": ["package_followup_required"]},
                },
            }
        archive_name = "elefante_support_scenario_f.zip"
        report = {
            "schema_version": 1,
            "evidence": {
                "diagnostic_codes": ["daemon_service_user_managed"],
                "operation_receipts": {
                    "package": {
                        "status": "available",
                        "receipt": {
                            "operation": "repair",
                            "status": "FAILED_ROLLED_BACK",
                            "failed_stage": "4",
                        },
                    }
                },
            },
        }
        target = self.context.data_root.parent / "support" / archive_name
        target.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(target, "w") as archive:
            archive.writestr("support-report.json", json.dumps(report))
        return {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "receipt": {
                "archive_name": archive_name,
                "checks": [
                    {"name": "private_file", "passed": True, "code": "PRIVATE_FILE_OK"}
                ],
            },
        }


def test_scenario_f_forces_real_repair_failure_and_exports_failed_stage(
    monkeypatch,
    tmp_path,
):
    base = _context(tmp_path)
    scenario_root = tmp_path / "scenario-root"
    bundle_root = tmp_path / "bundle"
    codex = tmp_path / "codex"
    for path in (scenario_root, bundle_root):
        path.mkdir()
    codex.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    codex.chmod(0o700)
    service = (
        base.customer_home
        / "Library"
        / "LaunchAgents"
        / "ai.elefante.daemon.plist"
    )
    service.parent.mkdir(parents=True)
    service.write_bytes(b"<plist/>\n")
    context = scenarios.ScenarioContext(
        artifact_path=base.artifact_path,
        artifact_sha256=base.artifact_sha256,
        install_root=base.install_root,
        data_root=base.data_root,
        customer_home=base.customer_home,
        project_alpha=base.project_alpha,
        project_beta=base.project_beta,
        machine_id=base.machine_id,
        output_dir=base.output_dir,
        scenario_root=scenario_root,
        bundle_root=bundle_root,
        codex_executable=codex,
        base_environment={"HOME": str(base.customer_home), "PATH": str(tmp_path)},
    )
    identity = {
        "schema_version": 1,
        "version": "2.13.0",
        "source_commit": "a" * 40,
        "source_clean": True,
        "release_channel": "candidate",
    }
    state: dict[str, object] = {}

    async def describe(*_args):
        return {"operation": "repair", "requires_confirmation": False}

    async def run_failed_repair(*_args, environment, on_marker, **_kwargs):
        assert on_marker is not None
        on_marker(SimpleNamespace())
        failure_flag = Path(environment["ELEFANTE_SCENARIO_CODEX_FAIL_FLAG"])
        assert failure_flag.is_file()
        failure_flag.unlink()
        receipt = {
            "operation": "repair",
            "status": "FAILED_ROLLED_BACK",
            "failed_stage": "4",
            "rollback": "previous_product_restored",
            "recoverable": True,
            "changed": False,
            "next_action": "create_support_report",
        }
        target = context.install_root / scenarios.PACKAGE_RECEIPT_FILE_NAME
        target.write_text(json.dumps(receipt), encoding="utf-8")
        target.chmod(0o600)
        return scenarios.CommandResult(returncode=93, output=b"failed", marker_seen=True)

    async def ready(*_args):
        return None

    monkeypatch.setattr(scenarios.sys, "platform", "darwin")
    monkeypatch.setattr(scenarios, "_describe_package_operation", describe)
    monkeypatch.setattr(scenarios, "_run_bounded_command", run_failed_repair)
    monkeypatch.setattr(scenarios, "_package_identity", lambda _root: identity)
    monkeypatch.setattr(scenarios, "_require_ready_product", ready)
    monkeypatch.setattr(
        scenarios,
        "_verify_installed_payload_matches_package",
        lambda *_args: "d" * 64,
    )

    checks = asyncio.run(
        scenarios.run_scenario_f(
            context,
            client_factory=lambda _workspace: _ScenarioFClient(context, state),
        )
    )

    assert checks == REQUIRED_SCENARIO_CHECKS["F"]
    assert state["starts"] == 2
    assert state["closes"] == 2
    assert service.read_bytes() == b"<plist/>\n"
