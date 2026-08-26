#!/usr/bin/env python3
"""Summarize paired Task Intelligence outcomes and enforce the promotion gate."""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"
DEFAULT_OUTCOMES = ROOT / "benchmarks/task_intelligence/outcomes"
COMPARISON_CONDITIONS = {
    "standard": ("baseline", "task-brief"),
    "memory-component": ("source-brief", "memory-brief"),
}

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.run_task_intelligence_baseline import configuration_id  # noqa: E402
from src.core.task_intelligence import TaskBriefProfile  # noqa: E402
from scripts.ci.verify_task_intelligence_benchmark import (  # noqa: E402
    acceptance_test_sha256,
    manifest_promotion_readiness,
    task_promotion_validity,
    task_contract_sha256,
    validate_manifest,
    validate_outcome_record,
)


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _clustered_interval(
    differences: dict[str, list[float]],
    *,
    seed: int,
    samples: int = 10_000,
) -> tuple[float, float] | None:
    task_ids = sorted(differences)
    # One task can measure a local effect, but it cannot estimate whether that
    # effect generalizes across tasks. Resampling one cluster produces a
    # degenerate interval and false confidence.
    if len(task_ids) < 2:
        return None
    generator = random.Random(seed)
    estimates: list[float] = []
    for _ in range(samples):
        sampled = [generator.choice(task_ids) for _ in task_ids]
        values = [value for task_id in sampled for value in differences[task_id]]
        estimates.append(sum(values) / len(values))
    return _percentile(estimates, 0.025), _percentile(estimates, 0.975)


def load_records(
    outcome_dir: Path,
    *,
    model: str,
    reasoning: str,
    run_seed: int,
    brief_profile: TaskBriefProfile = TaskBriefProfile.V1,
    comparison: str = "standard",
) -> list[dict[str, Any]]:
    profile = configuration_id(model, reasoning)
    brief_segment = (
        "" if brief_profile == TaskBriefProfile.V1 else "__brief-v2__contract-*"
    )
    records: list[dict[str, Any]] = []
    for condition in COMPARISON_CONDITIONS[comparison]:
        pattern = f"{condition}__{profile}{brief_segment}__seed-{run_seed}__*.json"
        for path in sorted(outcome_dir.glob(pattern)):
            record = json.loads(path.read_text(encoding="utf-8"))
            errors = validate_outcome_record(record)
            if errors:
                raise ValueError(f"{path.name}: {'; '.join(errors)}")
            match = re.search(r"-seed-\d+-r(\d+)$", record["evaluation_id"])
            if not match:
                raise ValueError(f"{path.name}: evaluation_id has no repeat")
            record = {**record, "repeat": int(match.group(1))}
            records.append(record)
    return records


def summarize(
    manifest: dict[str, Any],
    records: list[dict[str, Any]],
    *,
    split: str,
    task_id: str | None = None,
    comparison: str = "standard",
) -> dict[str, Any]:
    control_condition, treatment_condition = COMPARISON_CONDITIONS[comparison]
    tasks = {task["id"]: task for task in manifest["tasks"] if task["split"] == split}
    if task_id is not None:
        if task_id not in tasks:
            raise ValueError(f"task {task_id!r} is not in split {split!r}")
        tasks = {task_id: tasks[task_id]}
    pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        if record["task_id"] in tasks:
            pairs[(record["task_id"], record["repeat"])][record["condition"]] = record
    complete_pairs = {
        key: pair
        for key, pair in pairs.items()
        if set(pair) == {control_condition, treatment_condition}
    }
    repetitions = manifest["measurement"]["paired_repetitions"]
    expected_pairs = len(tasks) * repetitions
    protocol_complete = len(complete_pairs) == expected_pairs and all(
        (task_id, repeat) in complete_pairs
        for task_id in tasks
        for repeat in range(1, repetitions + 1)
    )
    observed_records = [record for pair in pairs.values() for record in pair.values()]

    def stage_trace_is_bound(task_id: str, record: dict[str, Any]) -> bool:
        trace = record.get("stage_trace")
        if not isinstance(trace, dict):
            return False
        validity = task_promotion_validity(tasks[task_id], ROOT)
        expected_judge = (
            "eligible" if validity["promotion_eligible"] else "diagnostic-only"
        )
        return (
            record.get("outcome_schema_version") == 3
            and record.get("task_contract_sha256")
            == task_contract_sha256(tasks[task_id])
            and trace.get("judge_status") == expected_judge
            and trace.get("acceptance_fixture_sha256")
            == acceptance_test_sha256(tasks[task_id], ROOT)
        )

    stage_observability_failures = sorted(
        f"{task_id}:r{repeat}:{condition}"
        for (task_id, repeat), pair in complete_pairs.items()
        for condition, record in pair.items()
        if not stage_trace_is_bound(task_id, record)
    )
    stage_observability_complete = (
        protocol_complete and not stage_observability_failures
    )
    observed_stage_observability_failures = sorted(
        f"{observed_task_id}:r{repeat}:{condition}"
        for (observed_task_id, repeat), pair in pairs.items()
        for condition, record in pair.items()
        if not stage_trace_is_bound(observed_task_id, record)
    )

    differences: dict[str, list[int]] = defaultdict(list)
    by_class: dict[str, list[int]] = defaultdict(list)
    condition_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (task_id, _repeat), pair in complete_pairs.items():
        difference = int(pair[treatment_condition]["acceptance_passed"]) - int(
            pair[control_condition]["acceptance_passed"]
        )
        differences[task_id].append(difference)
        by_class[tasks[task_id]["task_class"]].append(difference)
        for condition, record in pair.items():
            condition_records[condition].append(record)
    observed_condition_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs.values():
        for condition, record in pair.items():
            observed_condition_records[condition].append(record)

    total_pairs = len(complete_pairs)
    baseline_passes = sum(
        int(record["acceptance_passed"])
        for record in condition_records[control_condition]
    )
    treatment_passes = sum(
        int(record["acceptance_passed"])
        for record in condition_records[treatment_condition]
    )
    observed_control_passes = sum(
        int(record["acceptance_passed"])
        for record in observed_condition_records[control_condition]
    )
    observed_treatment_passes = sum(
        int(record["acceptance_passed"])
        for record in observed_condition_records[treatment_condition]
    )
    denominator = total_pairs or 1
    lift = (treatment_passes - baseline_passes) / denominator
    pass_rate_interval = _clustered_interval(
        differences,
        seed=manifest["measurement"]["run_seed"],
    )

    def total(condition: str, field: str) -> int:
        return sum(record[field] for record in condition_records[condition])

    baseline_input = total(control_condition, "input_tokens")
    treatment_input = total(treatment_condition, "input_tokens")
    paired_control_total_tokens = baseline_input + total(
        control_condition, "output_tokens"
    )
    paired_treatment_total_tokens = treatment_input + total(
        treatment_condition, "output_tokens"
    )
    observed_control_total_tokens = sum(
        record["input_tokens"] + record["output_tokens"]
        for record in observed_condition_records[control_condition]
    )
    observed_treatment_total_tokens = sum(
        record["input_tokens"] + record["output_tokens"]
        for record in observed_condition_records[treatment_condition]
    )
    baseline_duration = total(control_condition, "duration_ms")
    treatment_duration = total(treatment_condition, "duration_ms")
    token_intelligence_measurement_available = bool(complete_pairs) and all(
        record["input_tokens"] + record["output_tokens"] > 0
        for pair in complete_pairs.values()
        for record in pair.values()
    )
    token_intelligence_differences: dict[str, list[float]] = defaultdict(list)
    if token_intelligence_measurement_available:
        for (paired_task_id, _repeat), pair in complete_pairs.items():
            control_record = pair[control_condition]
            treatment_record = pair[treatment_condition]
            control_tokens = (
                control_record["input_tokens"] + control_record["output_tokens"]
            )
            treatment_tokens = (
                treatment_record["input_tokens"]
                + treatment_record["output_tokens"]
            )
            control_value = (
                1_000_000 / control_tokens
                if control_record["acceptance_passed"]
                else 0.0
            )
            treatment_value = (
                1_000_000 / treatment_tokens
                if treatment_record["acceptance_passed"]
                else 0.0
            )
            token_intelligence_differences[paired_task_id].append(
                treatment_value - control_value
            )
    token_intelligence_values = [
        value
        for values in token_intelligence_differences.values()
        for value in values
    ]
    token_intelligence_lift = (
        sum(token_intelligence_values) / len(token_intelligence_values)
        if token_intelligence_values
        else None
    )
    token_intelligence_interval = (
        _clustered_interval(
            token_intelligence_differences,
            seed=manifest["measurement"]["run_seed"],
        )
        if token_intelligence_measurement_available
        else None
    )
    retry_measurement_available = bool(complete_pairs) and all(
        isinstance(record.get(field), int) and not isinstance(record.get(field), bool)
        for pair in complete_pairs.values()
        for record in pair.values()
        for field in ("retries", "human_corrections")
    )
    baseline_retry_total = 0
    treatment_retry_total = 0
    retry_differences: dict[str, list[int]] = defaultdict(list)
    if retry_measurement_available:
        for (task_id, _repeat), pair in complete_pairs.items():
            baseline_count = sum(
                pair[control_condition][field]
                for field in ("retries", "human_corrections")
            )
            treatment_count = sum(
                pair[treatment_condition][field]
                for field in ("retries", "human_corrections")
            )
            baseline_retry_total += baseline_count
            treatment_retry_total += treatment_count
            retry_differences[task_id].append(baseline_count - treatment_count)
    retry_reduction_percent = (
        100 * (baseline_retry_total - treatment_retry_total) / baseline_retry_total
        if retry_measurement_available and baseline_retry_total > 0
        else None
    )
    retry_interval = (
        _clustered_interval(
            retry_differences,
            seed=manifest["measurement"]["run_seed"],
        )
        if retry_reduction_percent is not None
        else None
    )
    input_increase = (
        0.0
        if baseline_input == 0
        else 100 * (treatment_input - baseline_input) / baseline_input
    )
    paired_total_token_increase = (
        None
        if paired_control_total_tokens == 0
        else 100
        * (paired_treatment_total_tokens - paired_control_total_tokens)
        / paired_control_total_tokens
    )
    duration_increase = (
        0.0
        if baseline_duration == 0
        else 100 * (treatment_duration - baseline_duration) / baseline_duration
    )
    measurement = manifest["measurement"]
    readiness = manifest_promotion_readiness(
        {**manifest, "tasks": list(tasks.values())}
    )
    pass_rate_gate = (
        pass_rate_interval is not None
        and lift * 100 >= measurement["minimum_pass_rate_lift_points"]
        and pass_rate_interval[0] > 0
    )
    retry_correction_gate = (
        retry_reduction_percent is not None
        and retry_interval is not None
        and retry_reduction_percent >= measurement["minimum_retry_reduction_percent"]
        and retry_interval[0] > 0
        and treatment_passes >= baseline_passes
    )
    token_intelligence_gate = (
        token_intelligence_lift is not None
        and token_intelligence_interval is not None
        and treatment_passes > 0
        and treatment_passes >= baseline_passes
        and token_intelligence_lift > 0
        and token_intelligence_interval[0] > 0
    )
    effectiveness_gate = (
        pass_rate_gate or retry_correction_gate or token_intelligence_gate
    )
    cost_gate = (
        paired_total_token_increase is not None
        and paired_total_token_increase
        <= measurement["maximum_treatment_total_token_increase_percent"]
        and duration_increase
        <= measurement["maximum_treatment_duration_increase_percent"]
    )
    intended_memory_id: str | None = None
    intended_memory_deliveries = 0
    if comparison == "memory-component" and task_id is not None:
        fixture = tasks[task_id].get("memory_fixture")
        if isinstance(fixture, dict):
            payload = json.loads(
                (ROOT / fixture["path"]).read_text(encoding="utf-8")
            )
            intended_memory_id = str(payload["source"]["memory_id"])
            intended_memory_deliveries = sum(
                intended_memory_id in record.get("memory_ids", [])
                and record.get("stage_trace", {}).get("delivery_status")
                == "delivered"
                for record in observed_condition_records[treatment_condition]
            )
    local_decision: str | None = None
    decisive_early_stop = False
    early_stop_reason: str | None = None
    if comparison == "memory-component" and task_id is not None:
        treatment_by_repeat = {
            repeat: pair[treatment_condition]
            for (observed_task_id, repeat), pair in pairs.items()
            if observed_task_id == task_id and treatment_condition in pair
        }
        treatment_repeats_complete = set(treatment_by_repeat) == set(
            range(1, repetitions + 1)
        )
        treatment_stages_bound = treatment_repeats_complete and all(
            stage_trace_is_bound(task_id, record)
            for record in treatment_by_repeat.values()
        )
        observed_treatment_stages_bound = bool(treatment_by_repeat) and all(
            stage_trace_is_bound(task_id, record)
            for record in treatment_by_repeat.values()
        )
        intended_delivery_failed = observed_treatment_stages_bound and any(
            intended_memory_id not in record.get("memory_ids", [])
            or record.get("stage_trace", {}).get("delivery_status") != "delivered"
            for record in treatment_by_repeat.values()
        )
        if intended_delivery_failed:
            decisive_early_stop = True
            early_stop_reason = "intended_memory_not_delivered"
        elif treatment_stages_bound and observed_treatment_passes == 0:
            decisive_early_stop = True
            early_stop_reason = f"treatment_passed_0_of_{repetitions}"
        if (
            protocol_complete
            and stage_observability_complete
            and treatment_passes == expected_pairs
            and baseline_passes == 0
            and intended_memory_deliveries == expected_pairs
            and cost_gate
        ):
            local_decision = "LOCAL GO"
        elif (
            (
                protocol_complete
                and (
                    treatment_passes == 0
                    or intended_memory_deliveries < expected_pairs
                )
            )
            or decisive_early_stop
        ):
            local_decision = "STOP"
        else:
            local_decision = "INCONCLUSIVE"
    decision_complete = (
        protocol_complete and stage_observability_complete
    ) or decisive_early_stop
    return {
        "benchmark_id": manifest["benchmark_id"],
        "split": split,
        "task_id": task_id,
        "comparison": comparison,
        "control_condition": control_condition,
        "treatment_condition": treatment_condition,
        "task_cluster_count": len(differences),
        "inferential_evidence_available": pass_rate_interval is not None,
        "expected_pairs": expected_pairs,
        "complete_pairs": total_pairs,
        "protocol_complete": protocol_complete,
        "stage_observability_complete": stage_observability_complete,
        "stage_observability_failures": stage_observability_failures,
        "observed_stage_observability_failures": observed_stage_observability_failures,
        "evaluation_complete": protocol_complete and stage_observability_complete,
        "decision_complete": decision_complete,
        "decisive_early_stop": decisive_early_stop,
        "early_stop_reason": early_stop_reason,
        "baseline_passes": baseline_passes,
        "task_brief_passes": treatment_passes,
        "control_passes": baseline_passes,
        "treatment_passes": treatment_passes,
        "observed_control_runs": len(observed_condition_records[control_condition]),
        "observed_treatment_runs": len(
            observed_condition_records[treatment_condition]
        ),
        "observed_control_passes": observed_control_passes,
        "observed_treatment_passes": observed_treatment_passes,
        "baseline_pass_rate": round(baseline_passes / denominator, 6),
        "task_brief_pass_rate": round(treatment_passes / denominator, 6),
        "pass_rate_lift_points": round(lift * 100, 6),
        "paired_95_percent_ci_points": (
            [
                round(pass_rate_interval[0] * 100, 6),
                round(pass_rate_interval[1] * 100, 6),
            ]
            if pass_rate_interval is not None
            else None
        ),
        "paired_control_total_tokens": paired_control_total_tokens,
        "paired_treatment_total_tokens": paired_treatment_total_tokens,
        "observed_control_total_tokens": observed_control_total_tokens,
        "observed_treatment_total_tokens": observed_treatment_total_tokens,
        "observed_total_tokens": (
            observed_control_total_tokens + observed_treatment_total_tokens
        ),
        "paired_total_token_increase_percent": (
            round(paired_total_token_increase, 6)
            if paired_total_token_increase is not None
            else None
        ),
        "paired_control_accepted_outcomes_per_million_total_tokens": (
            round(1_000_000 * baseline_passes / paired_control_total_tokens, 6)
            if paired_control_total_tokens > 0
            else None
        ),
        "paired_treatment_accepted_outcomes_per_million_total_tokens": (
            round(1_000_000 * treatment_passes / paired_treatment_total_tokens, 6)
            if paired_treatment_total_tokens > 0
            else None
        ),
        "token_intelligence_measurement_available": (
            token_intelligence_measurement_available
        ),
        "token_intelligence_lift_per_million_total_tokens": (
            round(token_intelligence_lift, 6)
            if token_intelligence_lift is not None
            else None
        ),
        "token_intelligence_95_percent_ci_per_million_total_tokens": (
            [
                round(token_intelligence_interval[0], 6),
                round(token_intelligence_interval[1], 6),
            ]
            if token_intelligence_interval is not None
            else None
        ),
        "token_intelligence_gate": token_intelligence_gate,
        "input_token_increase_percent": round(input_increase, 6),
        "duration_increase_percent": round(duration_increase, 6),
        "retry_correction_measurement_available": retry_measurement_available,
        "retry_correction_reduction_percent": (
            round(retry_reduction_percent, 6)
            if retry_reduction_percent is not None
            else None
        ),
        "retry_correction_95_percent_ci_counts": (
            [round(retry_interval[0], 6), round(retry_interval[1], 6)]
            if retry_interval is not None
            else None
        ),
        "retry_correction_gate": retry_correction_gate,
        "class_lift_points": {
            task_class: round(100 * sum(values) / len(values), 6)
            for task_class, values in sorted(by_class.items())
        },
        "causal_stage_observability": {
            "judge_eligible_records": sum(
                record.get("stage_trace", {}).get("judge_status") == "eligible"
                for record in observed_records
            ),
            "treatment_retrieval_completed": sum(
                record.get("stage_trace", {}).get("retrieval_status") == "completed"
                for record in observed_condition_records[treatment_condition]
            ),
            "treatment_selection_selected": sum(
                record.get("stage_trace", {}).get("selection_status") == "selected"
                for record in observed_condition_records[treatment_condition]
            ),
            "treatment_delivery_delivered": sum(
                record.get("stage_trace", {}).get("delivery_status") == "delivered"
                for record in observed_condition_records[treatment_condition]
            ),
            "baseline_execution_changed": sum(
                record.get("stage_trace", {}).get("execution_status") == "changed"
                for record in observed_condition_records[control_condition]
            ),
            "treatment_execution_changed": sum(
                record.get("stage_trace", {}).get("execution_status") == "changed"
                for record in observed_condition_records[treatment_condition]
            ),
            "agent_use_unknown": sum(
                record.get("stage_trace", {}).get("agent_use_status") == "unknown"
                for record in observed_records
            ),
        },
        "pass_rate_gate": pass_rate_gate,
        "effectiveness_gate": effectiveness_gate,
        "cost_gate": cost_gate,
        "benchmark_promotion_ready": readiness["promotion_ready"],
        "promotion_gate": (
            readiness["promotion_ready"]
            and protocol_complete
            and stage_observability_complete
            and effectiveness_gate
            and cost_gate
        ),
        "intended_memory_id": intended_memory_id,
        "intended_memory_deliveries": intended_memory_deliveries,
        "local_decision": local_decision,
        "raw_transcripts_stored": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--outcome-dir", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--run-seed", type=int, default=20260805)
    parser.add_argument(
        "--brief-profile",
        choices=tuple(profile.value for profile in TaskBriefProfile),
        default=TaskBriefProfile.V1.value,
    )
    parser.add_argument(
        "--split", choices=("calibration", "holdout"), default="holdout"
    )
    parser.add_argument("--task", help="Summarize one task in the selected split")
    parser.add_argument(
        "--comparison",
        choices=tuple(COMPARISON_CONDITIONS),
        default="standard",
    )
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--require-decision", action="store_true")
    parser.add_argument("--require-promotion", action="store_true")
    args = parser.parse_args(argv)

    verification = validate_manifest(args.manifest, ROOT)
    if verification["errors"]:
        print(json.dumps({"errors": verification["errors"]}, indent=2))
        return 2
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    records = load_records(
        args.outcome_dir,
        model=args.model,
        reasoning=args.reasoning,
        run_seed=args.run_seed,
        brief_profile=TaskBriefProfile(args.brief_profile),
        comparison=args.comparison,
    )
    try:
        report = summarize(
            manifest,
            records,
            split=args.split,
            task_id=args.task,
            comparison=args.comparison,
        )
    except ValueError as error:
        print(json.dumps({"errors": [str(error)]}, indent=2))
        return 2
    report["brief_profile"] = args.brief_profile
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_complete and not report["evaluation_complete"]:
        return 2
    if args.require_decision and not report["decision_complete"]:
        return 2
    if args.require_promotion and not report["promotion_gate"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
