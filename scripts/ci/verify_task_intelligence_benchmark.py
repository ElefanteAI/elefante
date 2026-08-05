#!/usr/bin/env python3
"""Verify the frozen, answer-isolated Task Intelligence benchmark contract."""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"
MINIMUM_TASKS = 30
MINIMUM_CLASSES = 3
ALLOWED_SPLITS = {"calibration", "holdout"}
FORBIDDEN_CONTEXT_PREFIXES = (
    "benchmarks/",
    "workspace/postmortems/",
    "workspace/ISSUES.md",
    "CHANGELOG.md",
)
OUTCOME_FIELDS = {
    "evaluation_id",
    "task_id",
    "condition",
    "model",
    "model_version",
    "tool_configuration",
    "run_seed",
    "memory_ids",
    "acceptance_passed",
    "retries",
    "human_corrections",
    "input_tokens",
    "output_tokens",
    "duration_ms",
    "failure_category",
}


def _git(repo_root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


def _git_text(repo_root: Path, *arguments: str) -> str | None:
    result = _git(repo_root, *arguments)
    return result.stdout if result.returncode == 0 else None


def _walk_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_strings(key)
            yield from _walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_strings(item)


def _acceptance_target(task: dict[str, Any]) -> tuple[str, str] | None:
    command = task.get("acceptance_command")
    if not (
        isinstance(command, list)
        and len(command) == 5
        and command[:3] == ["python", "-m", "pytest"]
        and command[-1] == "-q"
        and isinstance(command[3], str)
        and "::" in command[3]
    ):
        return None
    test_path, node = command[3].split("::", 1)
    return test_path, node


def scan_memory_payload(payload: Any, tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Find exact benchmark-answer markers in a prospective memory export."""
    strings = list(_walk_strings(payload))
    findings: list[dict[str, str]] = []
    for task in tasks:
        target = _acceptance_target(task)
        markers = [task.get("acceptance_ref", "")]
        if target:
            markers.append(target[1])
        markers.extend(task.get("forbidden_leakage_terms", []))
        for marker in {item for item in markers if isinstance(item, str) and item}:
            if any(marker.casefold() in value.casefold() for value in strings):
                findings.append({"task_id": task["id"], "marker": marker})
                break
    return findings


def validate_outcome_record(record: dict[str, Any]) -> list[str]:
    """Enforce metadata-only local evaluation records."""
    errors = [
        f"{field} is not an allowed metadata field"
        for field in sorted(set(record) - OUTCOME_FIELDS)
    ]
    missing = OUTCOME_FIELDS - set(record)
    errors.extend(f"missing required field: {field}" for field in sorted(missing))
    if record.get("condition") not in {"baseline", "task-brief"}:
        errors.append("condition must be baseline or task-brief")
    if not isinstance(record.get("memory_ids"), list):
        errors.append("memory_ids must be a list")
    if not isinstance(record.get("acceptance_passed"), bool):
        errors.append("acceptance_passed must be boolean")
    for field in (
        "retries",
        "human_corrections",
        "input_tokens",
        "output_tokens",
        "duration_ms",
    ):
        value = record.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
    return errors


def validate_manifest(manifest_path: Path, repo_root: Path = ROOT) -> dict[str, Any]:
    """Validate task provenance, acceptance nodes, splits, budget, and leakage."""
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {"errors": [f"cannot read manifest: {error}"], "task_count": 0, "class_count": 0}

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list):
        return {"errors": ["tasks must be a list"], "task_count": 0, "class_count": 0}

    policy = manifest.get("task_brief_budget", {})
    stage_tokens = policy.get("stage_tokens", {}) if isinstance(policy, dict) else {}
    if policy.get("total_tokens") != 1500 or sum(stage_tokens.values()) != 1500:
        errors.append("Task Brief budget must freeze 1,500 tokens across all stages")
    if policy.get("max_evidence_items") != 8 or policy.get("max_graph_hops") != 1:
        errors.append("Task Brief evidence and graph bounds do not match the approved SDD")

    measurement = manifest.get("measurement", {})
    if measurement.get("minimum_pass_rate_lift_points") != 10:
        errors.append("pass-rate promotion threshold must remain 10 percentage points")
    if measurement.get("minimum_retry_reduction_percent") != 20:
        errors.append("retry-reduction promotion threshold must remain 20 percent")
    if measurement.get("paired_repetitions") != 3:
        errors.append("nondeterministic paired repetitions must remain 3")

    ids: set[str] = set()
    classes: Counter[str] = Counter()
    splits: Counter[str] = Counter()
    commit_splits: dict[str, set[str]] = defaultdict(set)
    for index, task in enumerate(tasks):
        prefix = f"task[{index}]"
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            errors.append(f"{prefix}: missing id")
            continue
        prefix = task_id
        if task_id in ids:
            errors.append(f"{prefix}: duplicate id")
        ids.add(task_id)

        task_class = task.get("task_class")
        split = task.get("split")
        if isinstance(task_class, str) and task_class:
            classes[task_class] += 1
        else:
            errors.append(f"{prefix}: missing task_class")
        if split in ALLOWED_SPLITS:
            splits[split] += 1
        else:
            errors.append(f"{prefix}: split must be calibration or holdout")

        if not isinstance(task.get("task_statement"), str) or len(task["task_statement"]) < 30:
            errors.append(f"{prefix}: task_statement is not specific enough")
        criteria = task.get("success_criteria")
        if not isinstance(criteria, list) or not criteria or not all(isinstance(item, str) for item in criteria):
            errors.append(f"{prefix}: success_criteria must be a non-empty string list")

        base_ref = task.get("base_ref")
        acceptance_ref = task.get("acceptance_ref")
        if not all(
            isinstance(value, str) and len(value) == 40
            for value in (base_ref, acceptance_ref)
        ):
            errors.append(f"{prefix}: base_ref and acceptance_ref must be full commit SHAs")
            continue
        commit_splits[acceptance_ref].add(split)
        parents = _git_text(repo_root, "show", "-s", "--format=%P", acceptance_ref)
        if parents is None or base_ref not in parents.split():
            errors.append(f"{prefix}: base_ref is not a parent of acceptance_ref")

        target = _acceptance_target(task)
        if target is None:
            errors.append(f"{prefix}: acceptance_command must be one exact pytest node")
            continue
        test_path, test_node = target
        test_source = _git_text(repo_root, "show", f"{acceptance_ref}:{test_path}")
        if test_source is None:
            errors.append(f"{prefix}: acceptance test file is absent at acceptance_ref")
        else:
            try:
                names = {node.name for node in ast.walk(ast.parse(test_source)) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
            except SyntaxError:
                names = set()
            if test_node not in names:
                errors.append(f"{prefix}: acceptance test node is absent at acceptance_ref")
        changed = _git_text(repo_root, "diff", "--name-only", base_ref, acceptance_ref)
        if changed is None or test_path not in changed.splitlines():
            errors.append(f"{prefix}: acceptance test was not changed by the source task")

        context_paths = task.get("context_paths")
        if not isinstance(context_paths, list) or not context_paths:
            errors.append(f"{prefix}: context_paths must be non-empty")
            continue
        for context_path in context_paths:
            if not isinstance(context_path, str):
                errors.append(f"{prefix}: context path must be a string")
                continue
            if context_path.startswith(FORBIDDEN_CONTEXT_PREFIXES):
                errors.append(f"{prefix}: forbidden answer-bearing context path {context_path}")
                continue
            content = _git_text(repo_root, "show", f"{base_ref}:{context_path}")
            if content is None:
                errors.append(f"{prefix}: context path absent at base_ref: {context_path}")
                continue
            leakage_markers = [acceptance_ref, test_node, *task.get("forbidden_leakage_terms", [])]
            for marker in leakage_markers:
                if isinstance(marker, str) and marker and marker.casefold() in content.casefold():
                    errors.append(f"{prefix}: context path leaks answer marker {marker}")

    if len(tasks) < MINIMUM_TASKS:
        errors.append(f"benchmark requires at least {MINIMUM_TASKS} tasks")
    if len(classes) < MINIMUM_CLASSES:
        errors.append(f"benchmark requires at least {MINIMUM_CLASSES} task classes")
    if not splits["calibration"] or not splits["holdout"]:
        errors.append("benchmark requires both calibration and holdout tasks")
    for commit, assigned in commit_splits.items():
        if len(assigned) > 1:
            errors.append(f"acceptance commit crosses calibration and holdout splits: {commit}")

    return {
        "benchmark_id": manifest.get("benchmark_id"),
        "task_count": len(tasks),
        "class_count": len(classes),
        "classes": dict(sorted(classes.items())),
        "calibration_count": splits["calibration"],
        "holdout_count": splits["holdout"],
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--memory-export", type=Path)
    args = parser.parse_args(argv)

    report = validate_manifest(args.manifest, ROOT)
    if args.memory_export and not report["errors"]:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        payload = json.loads(args.memory_export.read_text(encoding="utf-8"))
        report["memory_leakage"] = scan_memory_payload(payload, manifest["tasks"])
        if report["memory_leakage"]:
            report["errors"].append("memory export contains benchmark answer markers")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
