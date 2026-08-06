#!/usr/bin/env python3
"""Verify the frozen, answer-isolated Task Intelligence benchmark contract."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
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
    "cached_input_tokens",
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


def _benchmark_fixture_path(task: dict[str, Any], repo_root: Path) -> Path | None:
    artifact = task.get("acceptance_artifact")
    target = _acceptance_target(task)
    if not isinstance(artifact, dict) or artifact.get("source") != "benchmark-fixture":
        return None
    path = artifact.get("path")
    if (
        target is None
        or not isinstance(path, str)
        or path != target[0]
        or not path.startswith("benchmarks/task_intelligence/acceptance/")
    ):
        return None
    candidate = (repo_root / path).resolve()
    root = repo_root.resolve()
    if root not in candidate.parents:
        return None
    return candidate


def acceptance_test_source(task: dict[str, Any], repo_root: Path = ROOT) -> str | None:
    fixture = _benchmark_fixture_path(task, repo_root)
    if fixture is not None:
        try:
            return fixture.read_text(encoding="utf-8")
        except OSError:
            return None
    target = _acceptance_target(task)
    acceptance_ref = task.get("acceptance_ref")
    if target is None or not isinstance(acceptance_ref, str):
        return None
    return _git_text(repo_root, "show", f"{acceptance_ref}:{target[0]}")


def scan_memory_payload(
    payload: Any, tasks: list[dict[str, Any]]
) -> list[dict[str, str]]:
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
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "duration_ms",
    ):
        value = record.get(field)
        if field == "cached_input_tokens" and value is None:
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            errors.append(f"{field} must be a non-negative integer")
    for field in ("retries", "human_corrections"):
        value = record.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            errors.append(f"{field} must be null or a non-negative integer")
    return errors


def acceptance_test_sha256(task: dict[str, Any], repo_root: Path = ROOT) -> str | None:
    """Digest the exact hidden test artifact that received adversarial review."""
    source = acceptance_test_source(task, repo_root)
    if source is None:
        return None
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def task_promotion_validity(
    task: dict[str, Any], repo_root: Path = ROOT
) -> dict[str, Any]:
    """Validate the explicit behavioral and rollback contract for one task."""
    reasons: list[str] = []
    contract = task.get("acceptance_contract")
    if not isinstance(contract, dict):
        reasons.append("missing-contract")
        return {
            "task_id": task.get("id"),
            "promotion_eligible": False,
            "reasons": reasons,
        }
    if contract.get("kind") != "behavioral":
        reasons.append("implementation-coupled-acceptance")
    if contract.get("promotion_eligible") is not True:
        reasons.append("task-promotion-disabled")
    surfaces = contract.get("observable_surface")
    if not (
        isinstance(surfaces, list)
        and surfaces
        and all(isinstance(item, str) and item for item in surfaces)
    ):
        reasons.append("missing-observable-surface")
    acceptance = contract.get("acceptance")
    if not isinstance(acceptance, dict):
        reasons.append("missing-behavioral-acceptance")
    else:
        if acceptance.get("command") != task.get("acceptance_command"):
            reasons.append("acceptance-command-mismatch")
        assertions = acceptance.get("assertions")
        if not (
            isinstance(assertions, list)
            and assertions
            and all(isinstance(item, str) and item for item in assertions)
        ):
            reasons.append("missing-behavioral-assertions")
    rollback = contract.get("rollback")
    if not isinstance(rollback, dict):
        reasons.append("missing-rollback")
    else:
        if rollback.get("base_ref") != task.get("base_ref"):
            reasons.append("rollback-base-mismatch")
        restore_ref = rollback.get("restore_ref")
        if not isinstance(restore_ref, str) or len(restore_ref) != 40:
            reasons.append("missing-restore-ref")
        elif restore_ref != task.get("acceptance_ref"):
            reasons.append("rollback-restore-mismatch")
    review = contract.get("adversarial_review")
    if not isinstance(review, dict):
        reasons.append("missing-adversarial-review")
    else:
        if review.get("status") != "approved":
            reasons.append("adversarial-review-not-approved")
        if review.get("implementation_coupling_found") is not False:
            reasons.append("implementation-coupling-not-rejected")
        if (
            not isinstance(review.get("reviewer"), str)
            or not review["reviewer"].strip()
        ):
            reasons.append("missing-reviewer")
        reviewed_at = review.get("reviewed_at")
        if (
            not isinstance(reviewed_at, str)
            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", reviewed_at) is None
        ):
            reasons.append("missing-review-date")
        expected_digest = acceptance_test_sha256(task, repo_root)
        if expected_digest is None or review.get("test_sha256") != expected_digest:
            reasons.append("reviewed-test-digest-mismatch")
    return {
        "task_id": task.get("id"),
        "promotion_eligible": not reasons,
        "reasons": reasons,
    }


def manifest_promotion_readiness(
    manifest: dict[str, Any], repo_root: Path = ROOT
) -> dict[str, Any]:
    tasks = manifest.get("tasks") if isinstance(manifest.get("tasks"), list) else []
    validity = [task_promotion_validity(task, repo_root) for task in tasks]
    eligible = sum(int(item["promotion_eligible"]) for item in validity)
    policy = manifest.get("evaluation_policy")
    policy_allows = isinstance(policy, dict) and policy.get("promotion_allowed") is True
    return {
        "diagnostic_only": not policy_allows,
        "promotion_ready": policy_allows
        and bool(validity)
        and eligible == len(validity),
        "promotion_eligible_tasks": eligible,
        "invalid_tasks": [item for item in validity if not item["promotion_eligible"]],
    }


def validate_manifest(manifest_path: Path, repo_root: Path = ROOT) -> dict[str, Any]:
    """Validate task provenance, acceptance nodes, splits, budget, and leakage."""
    errors: list[str] = []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return {
            "errors": [f"cannot read manifest: {error}"],
            "task_count": 0,
            "class_count": 0,
        }

    tasks = manifest.get("tasks")
    if not isinstance(tasks, list):
        return {"errors": ["tasks must be a list"], "task_count": 0, "class_count": 0}

    policy = manifest.get("task_brief_budget", {})
    stage_tokens = policy.get("stage_tokens", {}) if isinstance(policy, dict) else {}
    if policy.get("total_tokens") != 1500 or sum(stage_tokens.values()) != 1500:
        errors.append("Task Brief budget must freeze 1,500 tokens across all stages")
    if policy.get("max_evidence_items") != 8 or policy.get("max_graph_hops") != 1:
        errors.append(
            "Task Brief evidence and graph bounds do not match the approved SDD"
        )

    measurement = manifest.get("measurement", {})
    if measurement.get("minimum_pass_rate_lift_points") != 10:
        errors.append("pass-rate promotion threshold must remain 10 percentage points")
    if measurement.get("minimum_retry_reduction_percent") != 20:
        errors.append("retry-reduction promotion threshold must remain 20 percent")
    if measurement.get("paired_repetitions") != 3:
        errors.append("nondeterministic paired repetitions must remain 3")
    if measurement.get("run_seed") != 20260805:
        errors.append("paired evaluation seed must remain frozen")
    if measurement.get("maximum_treatment_input_increase_percent") != 20:
        errors.append("treatment input-cost limit must remain 20 percent")
    if measurement.get("maximum_treatment_duration_increase_percent") != 25:
        errors.append("treatment duration limit must remain 25 percent")

    baseline = manifest.get("baseline_configuration", {})
    if baseline.get("model") != "gpt-5.6-terra" or baseline.get("reasoning") != "low":
        errors.append("baseline model and reasoning configuration are not frozen")
    if baseline.get("calibration_tasks") != 18 or baseline.get("repetitions") != 1:
        errors.append(
            "calibration baseline scope must remain 18 tasks by one repetition"
        )
    evidence = manifest.get("baseline_evidence", {})
    if evidence.get("passed") != 6 or evidence.get("failed") != 12:
        errors.append("calibration baseline result must remain 6 passed and 12 failed")
    if evidence.get("promotion_evidence") is not False:
        errors.append("calibration baseline must not be labelled promotion evidence")

    preliminary = manifest.get("preliminary_holdout_evidence", {})
    if preliminary:
        if preliminary.get("completed_pairs") != 12 or preliminary.get("runs") != 24:
            errors.append(
                "preliminary holdout evidence must remain 12 pairs and 24 runs"
            )
        if (
            preliminary.get("baseline_passes") != 1
            or preliminary.get("task_brief_passes") != 1
        ):
            errors.append(
                "preliminary holdout result must remain tied at 1 pass per condition"
            )
        if preliminary.get("pass_rate_lift_points") != 0.0:
            errors.append("preliminary holdout lift must remain zero")
        if preliminary.get("paired_95_percent_ci_points") != [0.0, 0.0]:
            errors.append("preliminary holdout confidence interval must remain [0, 0]")
        if (
            preliminary.get("effectiveness_gate") is not False
            or preliminary.get("promotion_gate") is not False
        ):
            errors.append("preliminary holdout must remain non-promotable")
        if preliminary.get("protocol_complete") is not False:
            errors.append("preliminary holdout protocol must remain incomplete")
        if preliminary.get("holdout_reusable_for_promotion") is not False:
            errors.append(
                "inspected holdout must not be reused as fresh promotion evidence"
            )
        if preliminary.get("raw_transcripts_stored") is not False:
            errors.append("preliminary holdout must remain metadata-only")
        if preliminary.get("decision") != "return-to-phase-1":
            errors.append("preliminary holdout decision must return to Phase 1")

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

        if (
            not isinstance(task.get("task_statement"), str)
            or len(task["task_statement"]) < 30
        ):
            errors.append(f"{prefix}: task_statement is not specific enough")
        criteria = task.get("success_criteria")
        if (
            not isinstance(criteria, list)
            or not criteria
            or not all(isinstance(item, str) for item in criteria)
        ):
            errors.append(f"{prefix}: success_criteria must be a non-empty string list")

        disclosed_memories = task.get("disclosed_memories", [])
        if not isinstance(disclosed_memories, list):
            errors.append(f"{prefix}: disclosed_memories must be a list")
        else:
            for memory_index, memory in enumerate(disclosed_memories):
                memory_prefix = f"{prefix}: disclosed_memories[{memory_index}]"
                if not isinstance(memory, dict):
                    errors.append(f"{memory_prefix} must be an object")
                    continue
                if memory.get("provenance") != "disclosed-golden-path":
                    errors.append(f"{memory_prefix} has invalid provenance")
                if memory.get("memory_type") not in {
                    "decision",
                    "directive",
                    "fact",
                    "specification",
                }:
                    errors.append(f"{memory_prefix} has invalid memory_type")
                if not isinstance(memory.get("id"), str) or not memory["id"]:
                    errors.append(f"{memory_prefix} has no id")
                content = memory.get("content")
                if not isinstance(content, str) or not 40 <= len(content) <= 1200:
                    errors.append(f"{memory_prefix} content must be 40-1200 characters")

        base_ref = task.get("base_ref")
        acceptance_ref = task.get("acceptance_ref")
        if not all(
            isinstance(value, str) and len(value) == 40
            for value in (base_ref, acceptance_ref)
        ):
            errors.append(
                f"{prefix}: base_ref and acceptance_ref must be full commit SHAs"
            )
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
        fixture = _benchmark_fixture_path(task, repo_root)
        artifact = task.get("acceptance_artifact")
        if isinstance(artifact, dict) and artifact.get("source") == "benchmark-fixture":
            if fixture is None:
                errors.append(f"{prefix}: invalid benchmark acceptance fixture")
            expected_digest = acceptance_test_sha256(task, repo_root)
            if artifact.get("sha256") != expected_digest:
                errors.append(f"{prefix}: acceptance fixture digest mismatch")
        test_source = acceptance_test_source(task, repo_root)
        if test_source is None:
            errors.append(f"{prefix}: acceptance test artifact is absent")
        else:
            try:
                names = {
                    node.name
                    for node in ast.walk(ast.parse(test_source))
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                }
            except SyntaxError:
                names = set()
            if test_node not in names:
                errors.append(
                    f"{prefix}: acceptance test node is absent at acceptance_ref"
                )
        changed = _git_text(repo_root, "diff", "--name-only", base_ref, acceptance_ref)
        if fixture is None and (changed is None or test_path not in changed.splitlines()):
            errors.append(
                f"{prefix}: acceptance test was not changed by the source task"
            )
        if fixture is not None and (
            changed is None
            or not any(
                path and not path.startswith(("tests/", "benchmarks/"))
                for path in changed.splitlines()
            )
        ):
            errors.append(f"{prefix}: source task has no production change")

        context_paths = task.get("context_paths")
        if not isinstance(context_paths, list) or not context_paths:
            errors.append(f"{prefix}: context_paths must be non-empty")
            continue
        for context_path in context_paths:
            if not isinstance(context_path, str):
                errors.append(f"{prefix}: context path must be a string")
                continue
            if context_path.startswith(FORBIDDEN_CONTEXT_PREFIXES):
                errors.append(
                    f"{prefix}: forbidden answer-bearing context path {context_path}"
                )
                continue
            content = _git_text(repo_root, "show", f"{base_ref}:{context_path}")
            if content is None:
                errors.append(
                    f"{prefix}: context path absent at base_ref: {context_path}"
                )
                continue
            leakage_markers = [
                acceptance_ref,
                test_node,
                *task.get("forbidden_leakage_terms", []),
            ]
            for marker in leakage_markers:
                if (
                    isinstance(marker, str)
                    and marker
                    and marker.casefold() in content.casefold()
                ):
                    errors.append(
                        f"{prefix}: context path leaks answer marker {marker}"
                    )

    if len(tasks) < MINIMUM_TASKS:
        errors.append(f"benchmark requires at least {MINIMUM_TASKS} tasks")
    if len(classes) < MINIMUM_CLASSES:
        errors.append(f"benchmark requires at least {MINIMUM_CLASSES} task classes")
    if not splits["calibration"] or not splits["holdout"]:
        errors.append("benchmark requires both calibration and holdout tasks")
    for commit, assigned in commit_splits.items():
        if len(assigned) > 1:
            errors.append(
                f"acceptance commit crosses calibration and holdout splits: {commit}"
            )

    readiness = manifest_promotion_readiness(manifest, repo_root)
    return {
        "benchmark_id": manifest.get("benchmark_id"),
        "task_count": len(tasks),
        "class_count": len(classes),
        "classes": dict(sorted(classes.items())),
        "calibration_count": splits["calibration"],
        "holdout_count": splits["holdout"],
        **readiness,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--memory-export", type=Path)
    parser.add_argument("--require-promotion-ready", action="store_true")
    args = parser.parse_args(argv)

    report = validate_manifest(args.manifest, ROOT)
    if args.memory_export and not report["errors"]:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        payload = json.loads(args.memory_export.read_text(encoding="utf-8"))
        report["memory_leakage"] = scan_memory_payload(payload, manifest["tasks"])
        if report["memory_leakage"]:
            report["errors"].append("memory export contains benchmark answer markers")
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["errors"]:
        return 1
    if args.require_promotion_ready and not report["promotion_ready"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
