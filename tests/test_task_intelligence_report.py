"""Promotion-report tests for Task Intelligence evaluation."""

import hashlib
import json
from pathlib import Path

from scripts.ci import summarize_task_intelligence_evaluation as report
from scripts.ci import verify_task_intelligence_benchmark as benchmark


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _record(task_id: str, condition: str, repeat: int, passed: bool) -> dict:
    memory_ids = [] if condition == "baseline" else ["memory"]
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task = next((item for item in manifest["tasks"] if item["id"] == task_id), None)
    fixture_digest = benchmark.acceptance_test_sha256(task) if task else "a" * 64
    task_digest = benchmark.task_contract_sha256(task) if task else "a" * 64
    return {
        "outcome_schema_version": 3,
        "evaluation_id": f"{task_id}-{condition}-seed-20260805-r{repeat}",
        "task_id": task_id,
        "task_contract_sha256": task_digest,
        "condition": condition,
        "model": "gpt-5.6-terra",
        "model_version": "not-exposed-by-codex-cli",
        "tool_configuration": "test",
        "run_seed": 20260805,
        "memory_ids": memory_ids,
        "acceptance_passed": passed,
        "retries": None,
        "human_corrections": None,
        "input_tokens": 1000 if condition == "baseline" else 1100,
        "cached_input_tokens": 800,
        "output_tokens": 100,
        "duration_ms": 1000 if condition == "baseline" else 1100,
        "failure_category": "" if passed else "acceptance-test",
        "stage_trace": {
            "judge_status": "eligible",
            "acceptance_fixture_sha256": fixture_digest,
            "retrieval_status": (
                "not-applicable" if condition == "baseline" else "completed"
            ),
            "considered_memory_count": None if condition == "baseline" else 1,
            "selection_status": (
                "not-applicable" if condition == "baseline" else "selected"
            ),
            "selected_memory_count": len(memory_ids),
            "delivery_status": (
                "not-applicable" if condition == "baseline" else "delivered"
            ),
            "prompt_sha256": "b" * 64,
            "brief_sha256": None if condition == "baseline" else "c" * 64,
            "agent_use_status": "unknown",
            "execution_status": "changed",
            "changed_files": ["src/fix.py"],
            "change_digest": "d" * 64,
            "acceptance_status": "passed" if passed else "failed",
            "acceptance_exit_code": 0 if passed else 1,
        },
        "repeat": repeat,
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _live_trial_record(
    task_id: str,
    task_class: str,
    condition: str,
    *,
    passed: bool,
    repeat: int = 1,
) -> dict:
    treatment = condition == "treatment"
    return {
        "trial_schema_version": 1,
        "experiment_id": f"natural-{task_id}",
        "task_id": task_id,
        "task_class": task_class,
        "repeat": repeat,
        "condition": condition,
        "question_sha256": _digest(f"question:{task_id}"),
        "acceptance_rubric_sha256": _digest(f"binary-rubric:{task_id}"),
        "acceptance_scale": "binary",
        "prompt_sha256": _digest(f"identical-prompt:{task_id}"),
        "system_instructions_sha256": _digest("fixed-system-instructions"),
        "held_constant_environment_sha256": _digest("fixed-environment"),
        "tools_without_elefante_sha256": _digest("fixed-non-elefante-tools"),
        "source_state_sha256": _digest("fixed-source-state"),
        "model": "gpt-5.6-sol",
        "model_version": "exact-version",
        "reasoning": "max",
        "run_seed": 20260827,
        "elefante_available": treatment,
        "recall_calls": 1 if treatment else 0,
        "recall_status": "supplied" if treatment else "not-available",
        "recall_context_tokens": 120 if treatment else 0,
        "recall_context_token_source": (
            "model-tokenizer" if treatment else "not-applicable"
        ),
        "input_tokens": 600 if treatment else 900,
        "cached_input_tokens": 250 if treatment else 400,
        "output_tokens": 80 if treatment else 100,
        "retries": 0 if treatment else 1,
        "duration_ms": 900 if treatment else 1200,
        "token_count_source": "provider-actual",
        "latency_source": "monotonic-clock",
        "usage_scope": "all-observed-attempts",
        "acceptance_passed": passed,
        "quality": {
            "correctness": passed,
            "relevance": passed,
            "decision_usefulness": passed,
            "hallucination_control": passed,
        },
        "task_origin": "user-request",
        "independently_arising": True,
        "evidence_previously_consumed": False,
        "memory_evidence_sha256": _digest(f"pre-existing-memory:{task_id}"),
        "memory_created_at_utc": "2026-08-01T12:00:00Z",
        "task_observed_at_utc": "2026-08-27T13:00:00Z",
        "preregistered_at_utc": "2026-08-27T13:01:00Z",
        "run_started_at_utc": (
            "2026-08-27T13:03:00Z" if treatment else "2026-08-27T13:02:00Z"
        ),
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
            for condition, passed in (("baseline", False), ("task-brief", True)):
                record = _record(task["id"], condition, repeat, passed)
                record["task_contract_sha256"] = benchmark.task_contract_sha256(task)
                records.append(record)

    result = report.summarize(manifest, records, split="holdout")

    assert result["protocol_complete"] is True
    assert result["stage_observability_complete"] is True
    assert result["stage_observability_failures"] == []
    assert result["evaluation_complete"] is True
    assert result["pass_rate_lift_points"] == 100
    assert result["paired_95_percent_ci_points"] == [100, 100]
    assert result["cost_gate"] is True
    assert result["benchmark_promotion_ready"] is True
    assert result["retry_correction_measurement_available"] is False
    assert result["retry_correction_gate"] is False
    assert result["promotion_gate"] is True
    assert (
        result["causal_stage_observability"]["treatment_delivery_delivered"]
        == len(holdout) * 3
    )

    legacy_records = [
        {
            key: value
            for key, value in record.items()
            if key
            not in {"outcome_schema_version", "stage_trace", "task_contract_sha256"}
        }
        for record in records
    ]
    legacy_result = report.summarize(manifest, legacy_records, split="holdout")
    assert legacy_result["protocol_complete"] is True
    assert legacy_result["stage_observability_complete"] is False
    assert len(legacy_result["stage_observability_failures"]) == len(legacy_records)
    assert legacy_result["evaluation_complete"] is False
    assert legacy_result["promotion_gate"] is False

    tampered_records = json.loads(json.dumps(records))
    tampered_records[0]["stage_trace"]["acceptance_fixture_sha256"] = "0" * 64
    tampered_result = report.summarize(manifest, tampered_records, split="holdout")
    assert tampered_result["stage_observability_complete"] is False
    assert tampered_result["promotion_gate"] is False

    stale_contract_records = json.loads(json.dumps(records))
    stale_contract_records[0]["task_contract_sha256"] = "0" * 64
    stale_contract_result = report.summarize(
        manifest, stale_contract_records, split="holdout"
    )
    assert stale_contract_result["stage_observability_complete"] is False
    assert stale_contract_result["promotion_gate"] is False


def test_measured_retry_reduction_is_an_effectiveness_path() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [task for task in manifest["tasks"] if task["split"] == "holdout"]
    records = []
    for task in tasks:
        for repeat in range(1, 4):
            control = _record(task["id"], "baseline", repeat, True)
            treatment = _record(task["id"], "task-brief", repeat, True)
            control.update({"retries": 2, "human_corrections": 0})
            treatment.update({"retries": 0, "human_corrections": 0})
            records.extend((control, treatment))

    result = report.summarize(manifest, records, split="holdout")

    assert result["pass_rate_gate"] is False
    assert result["retry_correction_measurement_available"] is True
    assert result["retry_correction_reduction_percent"] == 100
    assert result["retry_correction_95_percent_ci_counts"] == [2, 2]
    assert result["retry_correction_gate"] is True
    assert result["effectiveness_gate"] is True
    assert result["promotion_gate"] is False


def test_accepted_results_can_improve_total_token_intelligence() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [task for task in manifest["tasks"] if task["split"] == "holdout"]
    records = []
    for task in tasks:
        for repeat in range(1, 4):
            control = _record(task["id"], "baseline", repeat, True)
            treatment = _record(task["id"], "task-brief", repeat, True)
            treatment.update({"input_tokens": 500, "cached_input_tokens": 400})
            treatment["output_tokens"] = 50
            records.extend((control, treatment))

    result = report.summarize(manifest, records, split="holdout")

    assert result["pass_rate_gate"] is False
    assert result["paired_control_total_tokens"] == len(tasks) * 3 * 1100
    assert result["paired_treatment_total_tokens"] == len(tasks) * 3 * 550
    assert result["observed_total_tokens"] == len(tasks) * 3 * 1650
    assert result["paired_total_token_increase_percent"] == -50
    assert (
        result["paired_control_accepted_outcomes_per_million_total_tokens"]
        == 909.090909
    )
    assert (
        result["paired_treatment_accepted_outcomes_per_million_total_tokens"]
        == 1818.181818
    )
    assert result["token_intelligence_lift_per_million_total_tokens"] == 909.090909
    assert result["token_intelligence_95_percent_ci_per_million_total_tokens"] == [
        909.090909,
        909.090909,
    ]
    assert result["token_intelligence_gate"] is True
    assert result["effectiveness_gate"] is True


def test_cheap_failures_have_zero_token_intelligence_value() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [task for task in manifest["tasks"] if task["split"] == "holdout"]
    records = []
    for task in tasks:
        for repeat in range(1, 4):
            control = _record(task["id"], "baseline", repeat, False)
            treatment = _record(task["id"], "task-brief", repeat, False)
            treatment.update(
                {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}
            )
            records.extend((control, treatment))

    result = report.summarize(manifest, records, split="holdout")

    assert result["paired_control_accepted_outcomes_per_million_total_tokens"] == 0
    assert result["paired_treatment_accepted_outcomes_per_million_total_tokens"] == 0
    assert result["token_intelligence_lift_per_million_total_tokens"] == 0
    assert result["token_intelligence_95_percent_ci_per_million_total_tokens"] == [
        0,
        0,
    ]
    assert result["token_intelligence_gate"] is False
    assert result["effectiveness_gate"] is False


def test_token_efficiency_cannot_hide_an_acceptance_regression() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [task for task in manifest["tasks"] if task["split"] == "holdout"]
    records = []
    for task in tasks:
        for repeat in range(1, 4):
            control = _record(task["id"], "baseline", repeat, True)
            treatment = _record(
                task["id"], "task-brief", repeat, passed=repeat < 3
            )
            treatment.update(
                {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 1}
            )
            records.extend((control, treatment))

    result = report.summarize(manifest, records, split="holdout")

    assert result["treatment_passes"] < result["control_passes"]
    assert result["token_intelligence_lift_per_million_total_tokens"] > 0
    assert result["token_intelligence_gate"] is False
    assert result["effectiveness_gate"] is False


def test_output_tokens_are_part_of_the_cost_gate() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "runtime-restore-integrity-025"
    records = []
    for repeat in range(1, 4):
        control = _record(task_id, "baseline", repeat, True)
        treatment = _record(task_id, "task-brief", repeat, True)
        treatment.update(
            {"input_tokens": 1000, "cached_input_tokens": 800, "output_tokens": 1000}
        )
        records.extend((control, treatment))

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
    )

    assert result["input_token_increase_percent"] == 0
    assert result["paired_total_token_increase_percent"] == 81.818182
    assert result["cost_gate"] is False


def test_single_task_report_is_complete_but_not_inferential() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "runtime-restore-integrity-025"
    records = []
    for repeat, treatment_passed in enumerate((True, True, False), start=1):
        records.append(_record(task_id, "baseline", repeat, False))
        records.append(_record(task_id, "task-brief", repeat, treatment_passed))

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
    )

    assert result["expected_pairs"] == 3
    assert result["evaluation_complete"] is True
    assert result["pass_rate_lift_points"] == 66.666667
    assert result["task_cluster_count"] == 1
    assert result["inferential_evidence_available"] is False
    assert result["paired_95_percent_ci_points"] is None
    assert result["pass_rate_gate"] is False
    assert result["promotion_gate"] is False


def test_memory_component_report_requires_intended_memory_for_local_go() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "install-codex-recall-routing-black-box-032"
    task = next(task for task in manifest["tasks"] if task["id"] == task_id)
    fixture = json.loads((ROOT / task["memory_fixture"]["path"]).read_text())
    intended = fixture["source"]["memory_id"]
    records = []
    for repeat in range(1, 4):
        control = _record(task_id, "source-brief", repeat, False)
        treatment = _record(task_id, "memory-brief", repeat, True)
        control["memory_ids"] = ["source-evidence"]
        control["stage_trace"]["selected_memory_count"] = 1
        treatment["memory_ids"] = ["source-evidence", intended]
        treatment["stage_trace"]["selected_memory_count"] = 2
        records.extend((control, treatment))

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
        comparison="memory-component",
    )

    assert result["control_condition"] == "source-brief"
    assert result["treatment_condition"] == "memory-brief"
    assert result["control_passes"] == 0
    assert result["treatment_passes"] == 3
    assert result["intended_memory_deliveries"] == 3
    assert result["local_decision"] == "LOCAL GO"


def test_memory_component_zero_of_three_is_a_decisive_early_stop() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "install-codex-recall-routing-black-box-032"
    task = next(task for task in manifest["tasks"] if task["id"] == task_id)
    fixture = json.loads((ROOT / task["memory_fixture"]["path"]).read_text())
    intended = fixture["source"]["memory_id"]
    records = []
    for repeat in range(1, 4):
        treatment = _record(task_id, "memory-brief", repeat, False)
        treatment["memory_ids"] = ["source-evidence", intended]
        treatment["stage_trace"]["selected_memory_count"] = 2
        records.append(treatment)
        if repeat < 3:
            records.append(_record(task_id, "source-brief", repeat, False))

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
        comparison="memory-component",
    )

    assert result["protocol_complete"] is False
    assert result["evaluation_complete"] is False
    assert result["decision_complete"] is True
    assert result["decisive_early_stop"] is True
    assert result["early_stop_reason"] == "treatment_passed_0_of_3"
    assert result["observed_control_runs"] == 2
    assert result["observed_treatment_runs"] == 3
    assert result["paired_control_total_tokens"] == 2400
    assert result["paired_treatment_total_tokens"] == 2400
    assert result["observed_control_total_tokens"] == 2400
    assert result["observed_treatment_total_tokens"] == 3600
    assert result["observed_total_tokens"] == 6000
    assert result["intended_memory_deliveries"] == 3
    assert result["local_decision"] == "STOP"


def test_memory_component_zero_of_two_remains_inconclusive() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "install-codex-recall-routing-black-box-032"
    task = next(task for task in manifest["tasks"] if task["id"] == task_id)
    fixture = json.loads((ROOT / task["memory_fixture"]["path"]).read_text())
    intended = fixture["source"]["memory_id"]
    records = [
        _record(task_id, condition, repeat, False)
        for repeat in range(1, 3)
        for condition in ("source-brief", "memory-brief")
    ]
    for record in records:
        if record["condition"] == "memory-brief":
            record["memory_ids"] = [intended]

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
        comparison="memory-component",
    )

    assert result["decision_complete"] is False
    assert result["decisive_early_stop"] is False
    assert result["local_decision"] == "INCONCLUSIVE"


def test_memory_component_requires_recorded_delivery_not_only_memory_id() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "install-codex-recall-routing-black-box-032"
    task = next(task for task in manifest["tasks"] if task["id"] == task_id)
    fixture = json.loads((ROOT / task["memory_fixture"]["path"]).read_text())
    intended = fixture["source"]["memory_id"]
    records = []
    for repeat in range(1, 4):
        control = _record(task_id, "source-brief", repeat, False)
        treatment = _record(task_id, "memory-brief", repeat, True)
        treatment["memory_ids"] = [intended]
        treatment["stage_trace"]["delivery_status"] = "blocked"
        records.extend((control, treatment))

    result = report.summarize(
        manifest,
        records,
        split="calibration",
        task_id=task_id,
        comparison="memory-component",
    )

    assert result["intended_memory_deliveries"] == 0
    assert result["local_decision"] == "STOP"


def test_memory_component_failed_delivery_stops_after_one_bound_treatment() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    task_id = "install-codex-recall-routing-black-box-032"
    record = _record(task_id, "memory-brief", 1, False)
    record["stage_trace"]["delivery_status"] = "blocked"

    result = report.summarize(
        manifest,
        [record],
        split="calibration",
        task_id=task_id,
        comparison="memory-component",
    )

    assert result["protocol_complete"] is False
    assert result["decision_complete"] is True
    assert result["early_stop_reason"] == "intended_memory_not_delivered"
    assert result["local_decision"] == "STOP"


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
    for suffix in ("", "__brief-v2__contract-aaaaaaaaaaaa"):
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


def test_live_trial_1_requires_preregistered_exact_question_and_binary_rubric() -> None:
    record = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=True
    )

    assert benchmark.validate_live_outcome_trial_record(record) == []

    invalid_question = {**record, "question_sha256": "mutable-question"}
    assert "question_sha256 must be SHA-256" in (
        benchmark.validate_live_outcome_trial_record(invalid_question)
    )

    invalid_rubric = {**record, "acceptance_rubric_sha256": "mutable-rubric"}
    assert "acceptance_rubric_sha256 must be SHA-256" in (
        benchmark.validate_live_outcome_trial_record(invalid_rubric)
    )

    non_binary = {**record, "acceptance_scale": "five-point"}
    assert "acceptance_scale must be binary" in (
        benchmark.validate_live_outcome_trial_record(non_binary)
    )

    premature_registration = {
        **record,
        "preregistered_at_utc": "2026-08-27T12:59:00Z",
    }
    assert "preregistration cannot precede natural task observation" in (
        benchmark.validate_live_outcome_trial_record(premature_registration)
    )

    late_registration = {
        **record,
        "preregistered_at_utc": "2026-08-27T13:04:00Z",
    }
    assert "preregistration must precede the run" in (
        benchmark.validate_live_outcome_trial_record(late_registration)
    )


def test_live_trial_2_matches_chats_with_only_elefante_availability_changed() -> None:
    control = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=True
    )
    treatment = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=True
    )

    assert benchmark.validate_live_outcome_trial_pair(control, treatment) == []

    drift_cases = {
        "prompt_sha256": _digest("different prompt"),
        "system_instructions_sha256": _digest("different instructions"),
        "held_constant_environment_sha256": _digest("different environment"),
        "tools_without_elefante_sha256": _digest("different tools"),
        "source_state_sha256": _digest("different source state"),
        "model": "different-model",
        "model_version": "different-version",
        "reasoning": "different-reasoning",
        "run_seed": 7,
    }
    for field, value in drift_cases.items():
        drifted = {**treatment, field: value}
        assert f"matched pair differs in {field}" in (
            benchmark.validate_live_outcome_trial_pair(control, drifted)
        )

    no_match = {
        **treatment,
        "recall_status": "no_match",
        "recall_context_tokens": 0,
        "recall_context_token_source": "not-applicable",
    }
    no_delivery = report.summarize_live_outcome_trials([control, no_match])
    assert no_delivery["recall_delivery_complete"] is False
    assert no_delivery["decision"] == "REJECT"
    assert "treatment-memory-not-supplied" in no_delivery["rejection_reasons"]


def test_live_trial_3_records_complete_nonduplicative_cost_accounting() -> None:
    control = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=True
    )
    treatment = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=True
    )

    result = report.summarize_live_outcome_trials([control, treatment])

    assert result["costs"]["control"] == {
        "input_tokens": 900,
        "cached_input_tokens": 400,
        "output_tokens": 100,
        "recall_context_tokens": 0,
        "retries": 1,
        "duration_ms": 1200,
        "total_tokens": 1000,
    }
    assert result["costs"]["treatment"] == {
        "input_tokens": 600,
        "cached_input_tokens": 250,
        "output_tokens": 80,
        "recall_context_tokens": 120,
        "retries": 0,
        "duration_ms": 900,
        "total_tokens": 680,
    }
    assert result["observed_total_tokens"] == 1680
    assert result["cached_and_recall_tokens_are_subsets"] is True

    unpaired = _live_trial_record(
        "natural-unpaired-002", "operations", "treatment", passed=False
    )
    incomplete = report.summarize_live_outcome_trials(
        [control, treatment, unpaired]
    )
    assert incomplete["protocol_complete"] is False
    assert incomplete["decision"] == "INCONCLUSIVE"
    assert incomplete["costs"]["treatment"]["total_tokens"] == 1360
    assert incomplete["paired_costs"]["treatment"]["total_tokens"] == 680
    assert incomplete["observed_total_tokens"] == 2360

    double_counted_recall = {**treatment, "recall_context_tokens": 601}
    assert "recall_context_tokens cannot exceed input_tokens" in (
        benchmark.validate_live_outcome_trial_record(double_counted_recall)
    )

    estimated_recall = {
        **treatment,
        "recall_context_token_source": "estimated",
    }
    assert "supplied Recall requires an exact token source" in (
        benchmark.validate_live_outcome_trial_record(estimated_recall)
    )


def test_live_trial_4_scores_quality_and_blocks_unsafe_acceptance() -> None:
    control = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=False
    )
    control["quality"] = {
        "correctness": True,
        "relevance": True,
        "decision_usefulness": False,
        "hallucination_control": True,
    }
    treatment = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=True
    )

    result = report.summarize_live_outcome_trials([control, treatment])

    assert result["quality_passes"]["control"] == {
        "correctness": 1,
        "relevance": 1,
        "decision_usefulness": 0,
        "hallucination_control": 1,
    }
    assert result["quality_passes"]["treatment"] == {
        "correctness": 1,
        "relevance": 1,
        "decision_usefulness": 1,
        "hallucination_control": 1,
    }

    unsafe_acceptance = {
        **treatment,
        "quality": {**treatment["quality"], "hallucination_control": False},
    }
    assert "accepted outcome requires all quality dimensions to pass" in (
        benchmark.validate_live_outcome_trial_record(unsafe_acceptance)
    )


def test_live_trial_5_calculates_accepted_task_value_per_total_token() -> None:
    control = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=True
    )
    treatment = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=True
    )
    treatment.update(
        {
            "input_tokens": 400,
            "cached_input_tokens": 200,
            "output_tokens": 100,
            "recall_context_tokens": 100,
        }
    )

    result = report.summarize_live_outcome_trials([control, treatment])

    assert result["accepted_task_value"] == {"control": 1, "treatment": 1}
    assert result["accepted_task_value_per_total_token"] == {
        "control": 0.001,
        "treatment": 0.002,
    }
    assert result["accepted_outcomes_per_million_total_tokens"] == {
        "control": 1000.0,
        "treatment": 2000.0,
    }
    assert result["token_intelligence_lift_per_million_total_tokens"] == 1000.0


def test_live_trial_6_rejects_cost_without_value_and_any_acceptance_regression() -> None:
    control = _live_trial_record(
        "natural-finance-001", "financial-advisory", "control", passed=True
    )
    treatment = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=True
    )
    treatment.update(
        {
            "input_tokens": 1200,
            "cached_input_tokens": 500,
            "output_tokens": 200,
        }
    )

    costly = report.summarize_live_outcome_trials([control, treatment])

    assert costly["higher_cost_without_accepted_value_gain"] is True
    assert costly["decision"] == "REJECT"
    assert "higher-cost-without-accepted-value-gain" in costly["rejection_reasons"]

    regressed = _live_trial_record(
        "natural-finance-001", "financial-advisory", "treatment", passed=False
    )
    regressed.update(
        {
            "input_tokens": 100,
            "cached_input_tokens": 50,
            "output_tokens": 20,
            "recall_context_tokens": 50,
        }
    )
    regression = report.summarize_live_outcome_trials([control, regressed])

    assert regression["acceptance_regression"] is True
    assert regression["decision"] == "REJECT"
    assert "acceptance-regression" in regression["rejection_reasons"]

    offsetting_records = [
        _live_trial_record(
            "natural-improvement-002", "operations", "control", passed=False
        ),
        _live_trial_record(
            "natural-improvement-002", "operations", "treatment", passed=True
        ),
        _live_trial_record(
            "natural-regression-003", "product-decision", "control", passed=True
        ),
        _live_trial_record(
            "natural-regression-003", "product-decision", "treatment", passed=False
        ),
    ]
    offsetting = report.summarize_live_outcome_trials(offsetting_records)

    assert offsetting["acceptance_regression"] is False
    assert offsetting["token_intelligence_lift_per_million_total_tokens"] > 0
    assert offsetting["decision"] == "REJECT"
    assert offsetting["local_signal_gate"] is False
    assert "blocking-pair-rejection" in offsetting["rejection_reasons"]
    assert any(
        pair["rejection_reason"] == "acceptance-regression"
        for pair in offsetting["pair_decisions"]
    )


def test_live_trial_7_requires_multiple_natural_tasks_before_a_product_claim() -> None:
    first_pair = [
        _live_trial_record(
            "natural-finance-001", "financial-advisory", condition, passed=True
        )
        for condition in ("control", "treatment")
    ]

    one_task = report.summarize_live_outcome_trials(first_pair)

    assert one_task["local_signal_gate"] is True
    assert one_task["product_claim_evidence_gate"] is False
    assert "insufficient-natural-task-clusters" in one_task["product_claim_blockers"]

    records = list(first_pair)
    for task_id, task_class in (
        ("natural-operator-002", "operations"),
        ("natural-product-003", "product-decision"),
    ):
        records.extend(
            _live_trial_record(task_id, task_class, condition, passed=True)
            for condition in ("control", "treatment")
        )

    multi_task = report.summarize_live_outcome_trials(records)

    assert multi_task["task_cluster_count"] == 3
    assert multi_task["task_class_count"] == 3
    assert multi_task["product_claim_evidence_gate"] is True
    assert multi_task["public_claim_authorized"] is False

    manufactured = {**first_pair[0], "task_origin": "benchmark-authored"}
    assert "task_origin must be naturally occurring" in (
        benchmark.validate_live_outcome_trial_record(manufactured)
    )

    reused = {**first_pair[0], "evidence_previously_consumed": True}
    assert "previously consumed evidence is ineligible" in (
        benchmark.validate_live_outcome_trial_record(reused)
    )

    late_memory = {
        **first_pair[0],
        "memory_created_at_utc": "2026-08-27T13:00:01Z",
    }
    assert "eligible memory must predate the task" in (
        benchmark.validate_live_outcome_trial_record(late_memory)
    )
