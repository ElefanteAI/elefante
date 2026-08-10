"""Contract tests for the Task Intelligence Phase 0 benchmark."""

import json
from pathlib import Path

from scripts.ci import verify_task_intelligence_benchmark as benchmark


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def test_task_intelligence_manifest_is_reproducible_and_leak_free() -> None:
    report = benchmark.validate_manifest(MANIFEST, ROOT)

    assert report["errors"] == []
    assert report["task_count"] >= 30
    assert report["class_count"] >= 3
    assert report["calibration_count"] > 0
    assert report["holdout_count"] > 0
    assert report["diagnostic_only"] is True
    assert report["promotion_ready"] is False
    assert report["promotion_eligible_tasks"] == 8
    assert len(report["invalid_tasks"]) == report["task_count"] - 8
    invalid_ids = {item["task_id"] for item in report["invalid_tasks"]}
    assert {
        "install-clean-bootstrap-002",
        "install-dry-run-005",
        "dashboard-null-graph-011",
        "runtime-dashboard-cors-022",
        "runtime-restore-paths-024",
        "runtime-restore-integrity-025",
        "runtime-reset-containment-026",
        "install-uncovered-host-black-box-031",
    }.isdisjoint(invalid_ids)


def test_promotion_ready_mode_fails_closed_for_historical_benchmark(capsys) -> None:
    result = benchmark.main(["--manifest", str(MANIFEST), "--require-promotion-ready"])
    report = json.loads(capsys.readouterr().out)

    assert result == 2
    assert report["promotion_ready"] is False
    assert report["invalid_tasks"][0]["reasons"] == ["missing-contract"]


def test_black_box_canary_verifier_proves_base_and_known_fix(capsys) -> None:
    result = benchmark.main(["--manifest", str(MANIFEST), "--verify-canaries"])
    report = json.loads(capsys.readouterr().out)

    assert result == 0
    assert len(report["canary_verification"]) == 8
    assert all(item["base_rejected"] for item in report["canary_verification"])
    assert all(item["known_fix_accepted"] for item in report["canary_verification"])
    assert all(item["passed"] for item in report["canary_verification"])


def test_behavioral_contract_requires_exact_known_good_restore_ref() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task = manifest["tasks"][0]
    task["acceptance_contract"] = {
        "kind": "behavioral",
        "promotion_eligible": True,
        "observable_surface": ["documented CLI"],
        "acceptance": {
            "command": task["acceptance_command"],
            "assertions": ["CLI result matches the documented contract"],
        },
        "rollback": {
            "base_ref": task["base_ref"],
            "restore_ref": "0" * 40,
        },
        "adversarial_review": {
            "status": "approved",
            "implementation_coupling_found": False,
            "reviewer": "independent-reviewer",
            "reviewed_at": "2026-08-06",
            "test_sha256": benchmark.acceptance_test_sha256(task),
        },
    }

    validity = benchmark.task_promotion_validity(task)

    assert validity["promotion_eligible"] is False
    assert "rollback-restore-mismatch" in validity["reasons"]


def test_behavioral_contract_is_bound_to_the_reviewed_hidden_test() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task = manifest["tasks"][0]
    task["acceptance_contract"] = {
        "kind": "behavioral",
        "promotion_eligible": True,
        "observable_surface": ["documented CLI"],
        "acceptance": {
            "command": task["acceptance_command"],
            "assertions": ["CLI result matches the documented contract"],
        },
        "rollback": {
            "base_ref": task["base_ref"],
            "restore_ref": task["acceptance_ref"],
        },
        "adversarial_review": {
            "status": "approved",
            "implementation_coupling_found": False,
            "reviewer": "independent-reviewer",
            "reviewed_at": "2026-08-06",
            "test_sha256": "0" * 64,
        },
    }

    validity = benchmark.task_promotion_validity(task)

    assert validity["promotion_eligible"] is False
    assert "reviewed-test-digest-mismatch" in validity["reasons"]


def test_failed_preliminary_holdout_cannot_be_relabelled_for_promotion(
    tmp_path,
) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["preliminary_holdout_evidence"]["promotion_gate"] = True
    changed = tmp_path / "tasks.json"
    changed.write_text(json.dumps(manifest), encoding="utf-8")

    report = benchmark.validate_manifest(changed, ROOT)

    assert "preliminary holdout must remain non-promotable" in report["errors"]


def test_memory_export_leakage_scan_rejects_expected_answer_markers() -> None:
    tasks = json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
    leaked = {"memories": [{"content": f"Apply fix {tasks[0]['acceptance_ref']}"}]}

    findings = benchmark.scan_memory_payload(leaked, tasks)

    assert findings
    assert findings[0]["task_id"] == tasks[0]["id"]


def test_outcome_records_are_metadata_only() -> None:
    valid = {
        "evaluation_id": "eval-001",
        "task_id": "install-001",
        "condition": "baseline",
        "model": "model-name",
        "model_version": "model-version",
        "tool_configuration": "codex-local",
        "run_seed": 7,
        "memory_ids": [],
        "acceptance_passed": False,
        "retries": 1,
        "human_corrections": 0,
        "input_tokens": 100,
        "cached_input_tokens": 60,
        "output_tokens": 50,
        "duration_ms": 1000,
        "failure_category": "acceptance-test",
    }
    assert benchmark.validate_outcome_record(valid) == []
    assert (
        benchmark.validate_outcome_record({**valid, "cached_input_tokens": None}) == []
    )
    assert (
        benchmark.validate_outcome_record(
            {**valid, "retries": None, "human_corrections": None}
        )
        == []
    )

    trace = {
        "judge_status": "diagnostic-only",
        "acceptance_fixture_sha256": "a" * 64,
        "retrieval_status": "not-applicable",
        "considered_memory_count": None,
        "selection_status": "not-applicable",
        "selected_memory_count": 0,
        "delivery_status": "not-applicable",
        "prompt_sha256": "b" * 64,
        "brief_sha256": None,
        "agent_use_status": "unknown",
        "execution_status": "no-change",
        "changed_files": [],
        "change_digest": None,
        "acceptance_status": "failed",
        "acceptance_exit_code": 1,
    }
    assert (
        benchmark.validate_outcome_record(
            {**valid, "outcome_schema_version": 2, "stage_trace": trace}
        )
        == []
    )
    assert (
        benchmark.validate_outcome_record(
            {
                **valid,
                "outcome_schema_version": 3,
                "task_contract_sha256": "c" * 64,
                "stage_trace": trace,
            }
        )
        == []
    )
    assert "outcome schema v3 requires task_contract_sha256" in (
        benchmark.validate_outcome_record(
            {**valid, "outcome_schema_version": 3, "stage_trace": trace}
        )
    )
    mismatch = {
        **valid,
        "outcome_schema_version": 2,
        "stage_trace": {**trace, "acceptance_status": "passed"},
    }
    assert (
        "stage_trace acceptance status mismatches outcome"
        in benchmark.validate_outcome_record(mismatch)
    )

    leaked = {**valid, "raw_response": "private model output"}
    assert (
        "raw_response is not an allowed metadata field"
        in benchmark.validate_outcome_record(leaked)
    )
