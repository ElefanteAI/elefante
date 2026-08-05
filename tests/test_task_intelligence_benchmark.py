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
        "output_tokens": 50,
        "duration_ms": 1000,
        "failure_category": "acceptance-test",
    }
    assert benchmark.validate_outcome_record(valid) == []

    leaked = {**valid, "raw_response": "private model output"}
    assert "raw_response is not an allowed metadata field" in benchmark.validate_outcome_record(leaked)
