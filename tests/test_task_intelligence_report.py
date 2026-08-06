"""Promotion-report tests for Task Intelligence evaluation."""

import json
from pathlib import Path

from scripts.ci import summarize_task_intelligence_evaluation as report
from scripts.ci import verify_task_intelligence_benchmark as benchmark


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _record(task_id: str, condition: str, repeat: int, passed: bool) -> dict:
    return {
        "evaluation_id": f"{task_id}-{condition}-seed-20260805-r{repeat}",
        "task_id": task_id,
        "condition": condition,
        "model": "gpt-5.6-terra",
        "model_version": "not-exposed-by-codex-cli",
        "tool_configuration": "test",
        "run_seed": 20260805,
        "memory_ids": [] if condition == "baseline" else ["memory"],
        "acceptance_passed": passed,
        "retries": 0,
        "human_corrections": 0,
        "input_tokens": 1000 if condition == "baseline" else 1100,
        "cached_input_tokens": 800,
        "output_tokens": 100,
        "duration_ms": 1000 if condition == "baseline" else 1100,
        "failure_category": "" if passed else "acceptance-test",
        "repeat": repeat,
    }


def test_complete_strong_holdout_passes_promotion_gate() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    holdout = [task for task in manifest["tasks"] if task["split"] == "holdout"]
    manifest["evaluation_policy"]["promotion_allowed"] = True
    for task in holdout:
        task["acceptance_contract"] = {
            "kind": "behavioral",
            "promotion_eligible": True,
            "observable_surface": ["public test surface"],
            "acceptance": {
                "command": task["acceptance_command"],
                "assertions": ["observable behavior passes"],
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
                "test_sha256": benchmark.acceptance_test_sha256(task),
            },
        }
    records = []
    for task in holdout:
        for repeat in range(1, 4):
            records.append(_record(task["id"], "baseline", repeat, False))
            records.append(_record(task["id"], "task-brief", repeat, True))

    result = report.summarize(manifest, records, split="holdout")

    assert result["protocol_complete"] is True
    assert result["pass_rate_lift_points"] == 100
    assert result["paired_95_percent_ci_points"] == [100, 100]
    assert result["cost_gate"] is True
    assert result["benchmark_promotion_ready"] is True
    assert result["retry_correction_measurement_available"] is False
    assert result["retry_correction_gate"] is False
    assert result["promotion_gate"] is True


def test_historical_manifest_blocks_promotion_even_with_perfect_results() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task = next(task for task in manifest["tasks"] if task["split"] == "holdout")
    records = [
        _record(task["id"], "baseline", 1, False),
        _record(task["id"], "task-brief", 1, True),
    ]

    result = report.summarize(manifest, records, split="holdout")

    assert result["benchmark_promotion_ready"] is False
    assert result["promotion_gate"] is False


def test_incomplete_or_non_improving_results_do_not_promote() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task = next(task for task in manifest["tasks"] if task["split"] == "holdout")
    records = [
        _record(task["id"], "baseline", 1, True),
        _record(task["id"], "task-brief", 1, True),
    ]

    result = report.summarize(manifest, records, split="holdout")

    assert result["protocol_complete"] is False
    assert result["effectiveness_gate"] is False
    assert result["promotion_gate"] is False


def test_v2_report_loader_does_not_mix_frozen_v1_outcomes(tmp_path) -> None:
    task_id = "task"
    for suffix in ("", "__brief-v2"):
        for condition in ("baseline", "task-brief"):
            record = _record(task_id, condition, 1, True)
            record.pop("repeat")
            path = tmp_path / (
                f"{condition}__gpt-5-6-terra-low{suffix}__seed-20260805__"
                f"{task_id}__r1.json"
            )
            path.write_text(json.dumps(record), encoding="utf-8")

    records = report.load_records(
        tmp_path,
        model="gpt-5.6-terra",
        reasoning="low",
        run_seed=20260805,
        brief_profile=report.TaskBriefProfile.V2,
    )

    assert len(records) == 2
