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

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.run_task_intelligence_baseline import configuration_id  # noqa: E402
from src.core.task_intelligence import TaskBriefProfile  # noqa: E402
from scripts.ci.verify_task_intelligence_benchmark import (  # noqa: E402
    manifest_promotion_readiness,
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
    differences: dict[str, list[int]],
    *,
    seed: int,
    samples: int = 10_000,
) -> tuple[float, float]:
    task_ids = sorted(differences)
    if not task_ids:
        return 0.0, 0.0
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
) -> list[dict[str, Any]]:
    profile = configuration_id(model, reasoning)
    brief_segment = "" if brief_profile == TaskBriefProfile.V1 else "__brief-v2"
    records: list[dict[str, Any]] = []
    for condition in ("baseline", "task-brief"):
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
) -> dict[str, Any]:
    tasks = {task["id"]: task for task in manifest["tasks"] if task["split"] == split}
    pairs: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for record in records:
        if record["task_id"] in tasks:
            pairs[(record["task_id"], record["repeat"])][record["condition"]] = record
    complete_pairs = {
        key: pair
        for key, pair in pairs.items()
        if set(pair) == {"baseline", "task-brief"}
    }
    repetitions = manifest["measurement"]["paired_repetitions"]
    expected_pairs = len(tasks) * repetitions
    protocol_complete = len(complete_pairs) == expected_pairs and all(
        (task_id, repeat) in complete_pairs
        for task_id in tasks
        for repeat in range(1, repetitions + 1)
    )

    differences: dict[str, list[int]] = defaultdict(list)
    by_class: dict[str, list[int]] = defaultdict(list)
    condition_records: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (task_id, _repeat), pair in complete_pairs.items():
        difference = int(pair["task-brief"]["acceptance_passed"]) - int(
            pair["baseline"]["acceptance_passed"]
        )
        differences[task_id].append(difference)
        by_class[tasks[task_id]["task_class"]].append(difference)
        for condition, record in pair.items():
            condition_records[condition].append(record)

    total_pairs = len(complete_pairs)
    baseline_passes = sum(
        int(record["acceptance_passed"]) for record in condition_records["baseline"]
    )
    treatment_passes = sum(
        int(record["acceptance_passed"]) for record in condition_records["task-brief"]
    )
    denominator = total_pairs or 1
    lift = (treatment_passes - baseline_passes) / denominator
    ci_low, ci_high = _clustered_interval(
        differences,
        seed=manifest["measurement"]["run_seed"],
    )

    def total(condition: str, field: str) -> int:
        return sum(record[field] for record in condition_records[condition])

    baseline_input = total("baseline", "input_tokens")
    treatment_input = total("task-brief", "input_tokens")
    baseline_duration = total("baseline", "duration_ms")
    treatment_duration = total("task-brief", "duration_ms")
    baseline_retries = total("baseline", "retries")
    baseline_corrections = total("baseline", "human_corrections")
    input_increase = (
        0.0
        if baseline_input == 0
        else 100 * (treatment_input - baseline_input) / baseline_input
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
    effectiveness_gate = (
        lift * 100 >= measurement["minimum_pass_rate_lift_points"] and ci_low > 0
    )
    cost_gate = (
        input_increase <= measurement["maximum_treatment_input_increase_percent"]
        and duration_increase
        <= measurement["maximum_treatment_duration_increase_percent"]
    )
    return {
        "benchmark_id": manifest["benchmark_id"],
        "split": split,
        "expected_pairs": expected_pairs,
        "complete_pairs": total_pairs,
        "protocol_complete": protocol_complete,
        "baseline_passes": baseline_passes,
        "task_brief_passes": treatment_passes,
        "baseline_pass_rate": round(baseline_passes / denominator, 6),
        "task_brief_pass_rate": round(treatment_passes / denominator, 6),
        "pass_rate_lift_points": round(lift * 100, 6),
        "paired_95_percent_ci_points": [
            round(ci_low * 100, 6),
            round(ci_high * 100, 6),
        ],
        "input_token_increase_percent": round(input_increase, 6),
        "duration_increase_percent": round(duration_increase, 6),
        "retry_correction_measurement_available": bool(
            baseline_retries or baseline_corrections
        ),
        "retry_correction_gate": False,
        "class_lift_points": {
            task_class: round(100 * sum(values) / len(values), 6)
            for task_class, values in sorted(by_class.items())
        },
        "effectiveness_gate": effectiveness_gate,
        "cost_gate": cost_gate,
        "benchmark_promotion_ready": readiness["promotion_ready"],
        "promotion_gate": (
            readiness["promotion_ready"]
            and protocol_complete
            and effectiveness_gate
            and cost_gate
        ),
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
    parser.add_argument("--require-complete", action="store_true")
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
    )
    report = summarize(manifest, records, split=args.split)
    report["brief_profile"] = args.brief_profile
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.require_complete and not report["protocol_complete"]:
        return 2
    if args.require_promotion and not report["promotion_gate"]:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
