"""Tests for the fail-closed six-scenario product-release evidence gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.ci import verify_product_release_gate as gate


ARTIFACT_SHA = "a" * 64
SOURCE_COMMIT = "b" * 40


def _expected(artifact_sha256: str = ARTIFACT_SHA) -> dict[str, str]:
    return {
        "expected_version": "2.13.0",
        "expected_source_commit": SOURCE_COMMIT,
        "expected_artifact_sha256": artifact_sha256,
        "expected_publication_status": "candidate",
        "expected_platform": "macOS",
        "expected_architecture": "arm64",
        "expected_agent_host": "codex",
    }


def test_project_scenario_requires_reachable_fail_closed_states() -> None:
    assert "missing_project_abstains" in gate.REQUIRED_SCENARIO_CHECKS["B"]
    assert "invalid_project_state_abstains" in gate.REQUIRED_SCENARIO_CHECKS["B"]
    assert "ambiguous_project_abstains" not in gate.REQUIRED_SCENARIO_CHECKS["B"]


def _valid_manifest(
    artifact_sha256: str = ARTIFACT_SHA,
) -> dict[str, object]:
    scenarios = {
        scenario_id: {
            "status": "PASS",
            "artifact_sha256": artifact_sha256,
            "executed_at": "2026-08-30T12:00:00+00:00",
            "receipt_sha256": scenario_id.lower() * 64,
            "machine_id": f"00000000-0000-4000-8000-00000000000{index}",
            "isolation_preflight_passed": True,
            "unattended": True,
            "customer_content_included": False,
            "checks": sorted(gate.REQUIRED_SCENARIO_CHECKS[scenario_id]),
        }
        for index, scenario_id in enumerate(gate.SCENARIO_IDS, start=1)
    }
    trials = [
        {
            "trial_id": f"10000000-0000-4000-8000-00000000000{index}",
            "receipt_sha256": str(index) * 64,
        }
        for index in range(1, 4)
    ]
    return {
        "schema_version": 1,
        "gate": "elefante_product_release",
        "generated_at": "2026-08-30T13:00:00+00:00",
        "artifact": {
            "package_name": "Elefante-Installer.dmg",
            "version": "2.13.0",
            "source_commit": SOURCE_COMMIT,
            "sha256": artifact_sha256,
            "publication_status": "candidate",
            "platform": "macOS",
            "architecture": "arm64",
            "agent_host": "codex",
        },
        "scenarios": scenarios,
        "native_acceptance": {
            "status": "PASS",
            "artifact_sha256": artifact_sha256,
            "receipt_sha256": "c" * 64,
            "checks": sorted(gate.NATIVE_ACCEPTANCE_CHECKS),
        },
        "human_trials": trials,
    }


def _write_private_json(path: Path, value: object) -> bytes:
    payload = (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()
    path.write_bytes(payload)
    path.chmod(0o600)
    return payload


def _write_scenario_receipts(
    root: Path,
    manifest: dict[str, object],
) -> None:
    root.mkdir(mode=0o700)
    scenarios = manifest["scenarios"]
    assert isinstance(scenarios, dict)
    for scenario_id in gate.SCENARIO_IDS:
        scenario = scenarios[scenario_id]
        assert isinstance(scenario, dict)
        receipt = {
            "schema_version": 1,
            "scenario": scenario_id,
            "status": "PASS",
            "artifact_sha256": scenario["artifact_sha256"],
            "executed_at": scenario["executed_at"],
            "machine_id": scenario["machine_id"],
            "isolation_preflight_passed": True,
            "unattended": True,
            "customer_content_included": False,
            "checks": [
                {
                    "name": name,
                    "passed": True,
                    "code": f"{scenario_id}_{name.upper()}_VERIFIED",
                }
                for name in sorted(gate.REQUIRED_SCENARIO_CHECKS[scenario_id])
            ],
        }
        payload = _write_private_json(root / f"scenario-{scenario_id}.json", receipt)
        scenario["receipt_sha256"] = hashlib.sha256(payload).hexdigest()


def _write_native_evidence(root: Path, manifest: dict[str, object]) -> None:
    checks = []
    for index, name in enumerate(sorted(gate.NATIVE_ACCEPTANCE_CHECKS), start=1):
        file_name = f"native-{index:02d}-{name}.bin"
        target = root / file_name
        target.write_bytes(f"disposable native evidence {name}\n".encode())
        target.chmod(0o600)
        checks.append(
            {
                "name": name,
                "passed": True,
                "code": f"NATIVE_{name.upper()}_VERIFIED",
                "evidence_file": file_name,
                "evidence_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    native = manifest["native_acceptance"]
    assert isinstance(native, dict)
    receipt = {
        "schema_version": 1,
        "status": "PASS",
        "artifact_sha256": native["artifact_sha256"],
        "executed_at": "2026-08-30T13:05:00+00:00",
        "machine_id": "20000000-0000-4000-8000-000000000001",
        "customer_content_included": False,
        "checks": checks,
    }
    payload = _write_private_json(root / "native-acceptance.json", receipt)
    native["receipt_sha256"] = hashlib.sha256(payload).hexdigest()


def _first_run_receipt(index: int) -> dict[str, object]:
    return {
        "schema_version": 1,
        "operation": "first_run_acceptance",
        "status": "VERIFIED_COMPLETE",
        "finished_at": "2026-08-30T13:10:00+00:00",
        "checks": [
            {
                "name": name,
                "passed": True,
                "code": f"{name.upper()}_VERIFIED",
            }
            for name in (
                "project_isolation",
                "disposable_recall",
                "acceptance_cleanup",
                "initial_backup",
            )
        ],
        "acceptance_operation_id": (
            f"30000000-0000-4000-8000-00000000000{index}"
        ),
        "backup_operation_id": f"40000000-0000-4000-8000-00000000000{index}",
        "initial_backup": {
            "archive_name": f"elefante_data_backup_trial_{index}.zip",
            "archive_sha256": str(index + 3) * 64,
        },
        "memory_content_included": False,
        "project_path_included": False,
        "next_action": "open_elefante_home",
    }


def _write_human_evidence(root: Path, manifest: dict[str, object]) -> None:
    trials = manifest["human_trials"]
    assert isinstance(trials, list)
    artifact = manifest["artifact"]
    assert isinstance(artifact, dict)
    for index, trial in enumerate(trials, start=1):
        assert isinstance(trial, dict)
        first_run_name = f"human-trial-{index}-first-run.json"
        first_run_payload = _write_private_json(
            root / first_run_name,
            _first_run_receipt(index),
        )
        receipt = {
            "schema_version": 1,
            "trial_id": trial["trial_id"],
            "scenario": "A",
            "status": "PASS",
            "artifact_sha256": artifact["sha256"],
            "executed_at": "2026-08-30T13:20:00+00:00",
            "machine_id": f"50000000-0000-4000-8000-00000000000{index}",
            "unfamiliar_user": True,
            "founder_interventions": 0,
            "terminal_used": False,
            "developer_checkout_used": False,
            "customer_content_included": False,
            "first_run_receipt_file": first_run_name,
            "first_run_receipt_sha256": hashlib.sha256(
                first_run_payload
            ).hexdigest(),
        }
        receipt_payload = _write_private_json(
            root / f"human-trial-{trial['trial_id']}.json",
            receipt,
        )
        trial["receipt_sha256"] = hashlib.sha256(receipt_payload).hexdigest()


def _complete_evidence(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, object], dict[str, str]]:
    artifact = tmp_path / "Elefante-Installer.dmg"
    artifact.write_bytes(b"exact signed and stapled package bytes")
    artifact_sha256 = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest = _valid_manifest(artifact_sha256)
    evidence = tmp_path / "evidence"
    _write_scenario_receipts(evidence, manifest)
    _write_native_evidence(evidence, manifest)
    _write_human_evidence(evidence, manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return artifact, manifest_path, evidence, manifest, _expected(artifact_sha256)


def test_manifest_claims_alone_never_become_release_evidence() -> None:
    report = gate.validate_product_release_manifest(_valid_manifest(), **_expected())

    assert report["release_ready"] is False
    assert report["error_codes"] == ["EVIDENCE_FILES_NOT_VERIFIED"]


def test_missing_scenario_and_check_fail_closed() -> None:
    manifest = _valid_manifest()
    scenarios = manifest["scenarios"]
    assert isinstance(scenarios, dict)
    scenarios.pop("F")
    report = gate.validate_product_release_manifest(manifest, **_expected())
    assert "SCENARIO_SET_INCOMPLETE" in report["error_codes"]

    manifest = _valid_manifest()
    scenarios = manifest["scenarios"]
    assert isinstance(scenarios, dict)
    scenario_c = scenarios["C"]
    assert isinstance(scenario_c, dict)
    checks = scenario_c["checks"]
    assert isinstance(checks, list)
    checks.remove("permanent_delete")
    report = gate.validate_product_release_manifest(manifest, **_expected())
    assert "SCENARIO_C_CHECKS_INCOMPLETE" in report["error_codes"]


def test_manifest_requires_three_distinct_human_receipt_claims() -> None:
    manifest = _valid_manifest()
    trials = manifest["human_trials"]
    assert isinstance(trials, list)
    trials.pop()
    report = gate.validate_product_release_manifest(manifest, **_expected())
    assert "HUMAN_TRIAL_COUNT_INSUFFICIENT" in report["error_codes"]


def test_identity_native_and_customer_content_fail_closed() -> None:
    manifest = _valid_manifest()
    artifact = manifest["artifact"]
    scenarios = manifest["scenarios"]
    native = manifest["native_acceptance"]
    assert isinstance(artifact, dict)
    assert isinstance(scenarios, dict)
    assert isinstance(native, dict)
    artifact["sha256"] = "c" * 64
    scenario_b = scenarios["B"]
    assert isinstance(scenario_b, dict)
    scenario_b["customer_content_included"] = True
    native["checks"] = ["keyboard"]
    report = gate.validate_product_release_manifest(manifest, **_expected())
    assert "ARTIFACT_SHA256_MISMATCH" in report["error_codes"]
    assert "SCENARIO_B_CUSTOMER_CONTENT_PRESENT" in report["error_codes"]
    assert "NATIVE_ACCEPTANCE_CHECKS_INCOMPLETE" in report["error_codes"]


def test_file_reader_rejects_duplicate_or_unknown_private_fields_without_echo(
    tmp_path: Path,
) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text('{"schema_version":1,"schema_version":1}', encoding="utf-8")
    report = gate.verify_product_release_manifest_file(duplicate, **_expected())
    assert report["error_codes"] == ["MANIFEST_DUPLICATE_JSON_KEY"]

    secret = "/Users/customer/Private Project"
    manifest = _valid_manifest()
    manifest["private_path"] = secret
    unknown = tmp_path / "unknown.json"
    unknown.write_text(json.dumps(manifest), encoding="utf-8")
    report = gate.verify_product_release_manifest_file(unknown, **_expected())
    assert report["error_codes"] == ["MANIFEST_SCHEMA_INVALID"]
    assert secret not in json.dumps(report)


def test_file_gate_reads_artifact_and_every_private_evidence_file(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact, manifest_path, evidence, _manifest, expected = _complete_evidence(tmp_path)
    monkeypatch.setattr(gate, "_artifact_trust_errors", lambda _artifact: [])

    report = gate.verify_product_release_manifest_file(
        manifest_path,
        artifact_path=artifact,
        evidence_dir=evidence,
        **expected,
    )

    assert report["release_ready"] is True
    assert report["scenario_count"] == 6


def test_file_gate_rejects_missing_tampered_or_nonprivate_scenario_receipts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact, manifest_path, evidence, _manifest, expected = _complete_evidence(tmp_path)
    monkeypatch.setattr(gate, "_artifact_trust_errors", lambda _artifact: [])

    missing = gate.verify_product_release_manifest_file(manifest_path, **expected)
    assert set(missing["error_codes"]) == {
        "ARTIFACT_FILE_REQUIRED",
        "PRODUCT_EVIDENCE_DIRECTORY_REQUIRED",
    }

    receipt_b = evidence / "scenario-B.json"
    receipt_b.write_bytes(receipt_b.read_bytes() + b" ")
    receipt_b.chmod(0o644)
    tampered = gate.verify_product_release_manifest_file(
        manifest_path,
        artifact_path=artifact,
        evidence_dir=evidence,
        **expected,
    )
    assert "SCENARIO_B_RECEIPT_HASH_MISMATCH" in tampered["error_codes"]
    assert "SCENARIO_B_RECEIPT_PRIVATE_MODE_INVALID" in tampered["error_codes"]


def test_file_gate_rejects_native_and_human_evidence_tampering(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact, manifest_path, evidence, manifest, expected = _complete_evidence(tmp_path)
    monkeypatch.setattr(gate, "_artifact_trust_errors", lambda _artifact: [])
    native_receipt = json.loads((evidence / "native-acceptance.json").read_text())
    native_file = evidence / native_receipt["checks"][0]["evidence_file"]
    native_file.write_bytes(b"tampered native evidence")
    trials = manifest["human_trials"]
    assert isinstance(trials, list)
    first_trial = trials[0]
    assert isinstance(first_trial, dict)
    human_receipt_path = evidence / f"human-trial-{first_trial['trial_id']}.json"
    human_receipt = json.loads(human_receipt_path.read_text())
    first_run_path = evidence / human_receipt["first_run_receipt_file"]
    first_run_path.write_bytes(first_run_path.read_bytes() + b" ")

    report = gate.verify_product_release_manifest_file(
        manifest_path,
        artifact_path=artifact,
        evidence_dir=evidence,
        **expected,
    )

    assert any(
        "NATIVE_" in code and "HASH_MISMATCH" in code
        for code in report["error_codes"]
    )
    assert any("FIRST_RUN_HASH_MISMATCH" in code for code in report["error_codes"])
    assert "HUMAN_TRIAL_COUNT_INSUFFICIENT" in report["error_codes"]


def test_file_gate_rejects_unverified_or_mismatched_artifact(
    monkeypatch,
    tmp_path: Path,
) -> None:
    artifact, manifest_path, evidence, _manifest, expected = _complete_evidence(tmp_path)
    monkeypatch.setattr(
        gate,
        "_artifact_trust_errors",
        lambda _artifact: ["ARTIFACT_NOTARIZATION_NOT_VERIFIED"],
    )
    report = gate.verify_product_release_manifest_file(
        manifest_path,
        artifact_path=artifact,
        evidence_dir=evidence,
        **expected,
    )
    assert "ARTIFACT_NOTARIZATION_NOT_VERIFIED" in report["error_codes"]

    artifact.write_bytes(b"different artifact bytes")
    mismatch = gate.verify_product_release_manifest_file(
        manifest_path,
        artifact_path=artifact,
        evidence_dir=evidence,
        **expected,
    )
    assert "ARTIFACT_FILE_SHA256_MISMATCH" in mismatch["error_codes"]
