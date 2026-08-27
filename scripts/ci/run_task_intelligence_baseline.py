#!/usr/bin/env python3
"""Run isolated, metadata-only no-Brief Task Intelligence baseline trials."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable
from uuid import UUID


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"
DEFAULT_OUTCOMES = ROOT / "benchmarks/task_intelligence/outcomes"
DEFAULT_WORKSPACES = Path(tempfile.gettempdir()) / "elefante-ti"
BASELINE_CONDITION = "baseline"
DEFAULT_ESTIMATED_INPUT_TOKENS = 600_000
DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS = 100_000

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci.verify_task_intelligence_benchmark import (  # noqa: E402
    acceptance_test_sha256,
    acceptance_test_source,
    task_promotion_validity,
    validate_manifest,
    validate_outcome_record,
)
from src.core.session_intelligence import (  # noqa: E402
    SessionIntelligenceError,
    SessionIntelligenceStore,
)


def _run(command: list[str], *, cwd: Path, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, cwd=cwd, check=False, **kwargs)


def _git_bytes(repo_root: Path, *arguments: str) -> bytes:
    result = _run(["git", *arguments], cwd=repo_root, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed")
    return result.stdout


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_plan(
    manifest: dict[str, Any],
    *,
    split: str | None = None,
    task_id: str | None = None,
    task_class: str | None = None,
    repetitions: int = 1,
) -> list[dict[str, Any]]:
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    selected = [
        task
        for task in manifest["tasks"]
        if (task_id is None or task["id"] == task_id)
        and (split is None or task["split"] == split)
        and (task_class is None or task["task_class"] == task_class)
    ]
    if not selected:
        raise ValueError("no benchmark tasks match the requested selection")
    return [
        {"task_id": task["id"], "task": task, "repeat": repeat}
        for repeat in range(1, repetitions + 1)
        for task in selected
    ]


def configuration_id(model: str, reasoning: str) -> str:
    """Return a stable filesystem-safe identifier for one evaluator setup."""
    value = f"{model}__{reasoning}".casefold()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")


def build_baseline_prompt(task: dict[str, Any]) -> str:
    criteria = "\n".join(f"- {item}" for item in task["success_criteria"])
    return (
        "Solve the coding task in this isolated historical repository snapshot.\n\n"
        f"Task:\n{task['task_statement']}\n\n"
        f"Observable success criteria:\n{criteria}\n\n"
        "Rules:\n"
        "- Modify implementation files only; do not modify tests.\n"
        "- Do not use network access, remotes, external repositories, or git history.\n"
        "- Do not inspect files outside this workspace.\n"
        "- Use only evidence available inside this snapshot.\n"
        "- Use at most eight shell/tool calls. Inspect only files directly relevant to the task.\n"
        "- Do not run the full test suite; run only a narrow visible check when practical.\n"
        "- Finish with the smallest correct change."
    )


def _safe_extract_archive(archive: bytes, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    root = destination.resolve()
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as bundle:
        for member in bundle.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts or member.issym() or member.islnk():
                raise RuntimeError(f"unsafe benchmark archive member: {member.name}")
            target = (destination / Path(*path.parts)).resolve()
            if target != root and root not in target.parents:
                raise RuntimeError(f"benchmark archive escapes workspace: {member.name}")
            bundle.extract(member, destination)


def prepare_workspace(repo_root: Path, task: dict[str, Any], workspace: Path) -> None:
    """Create a one-commit repository snapshot with no future source history."""
    if workspace.exists():
        raise FileExistsError(f"benchmark workspace already exists: {workspace}")
    archive = _git_bytes(repo_root, "archive", "--format=tar", task["base_ref"])
    _safe_extract_archive(archive, workspace)
    commands = (
        ["git", "init", "-q"],
        ["git", "add", "-A"],
        [
            "git",
            "-c",
            "user.name=Elefante Benchmark",
            "-c",
            "user.email=benchmark@localhost",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            "Frozen benchmark base",
        ],
    )
    for command in commands:
        result = _run(command, cwd=workspace, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"workspace initialization failed: {' '.join(command)}")


def parse_codex_usage(stdout: str) -> dict[str, Any]:
    """Extract one complete provider usage event without retaining messages.

    A single ``turn.completed`` event is the only source contract currently
    proven by this runner. Multiple events are not summed or treated as
    cumulative because the stream does not declare those semantics. They fail
    closed as unknown instead of manufacturing provider-actual totals.
    """
    events: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "turn.completed" or not isinstance(event.get("usage"), dict):
            continue
        events.append(event["usage"])
    unknown = {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "usage_source": "unknown",
        "usage_scope": "unavailable",
        "usage_event_count": len(events),
    }
    if len(events) != 1:
        return unknown
    details = events[0]
    values: dict[str, int] = {}
    for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
        value = details.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return unknown
        values[field] = value
    if values["cached_input_tokens"] > values["input_tokens"]:
        return unknown
    if values["input_tokens"] + values["output_tokens"] <= 0:
        return unknown
    return {
        **values,
        "usage_source": "provider-actual",
        "usage_scope": "single-complete-turn",
        "usage_event_count": 1,
    }


def _codex_version(executable: str) -> str:
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def run_codex_baseline(
    workspace: Path,
    task: dict[str, Any],
    *,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    prompt: str | None = None,
    evidence_sink: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[int, dict[str, Any], int, str, str]:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("codex executable is unavailable")
    command = [
        executable,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--disable",
        "apps",
        "--disable",
        "memories",
        "--disable",
        "multi_agent",
        "--disable",
        "plugins",
        "--disable",
        "skill_search",
        "--json",
        "--sandbox",
        "workspace-write",
        "--model",
        model,
        "-c",
        f'model_reasoning_effort="{reasoning}"',
        "-c",
        "project_doc_max_bytes=0",
        "-C",
        str(workspace),
        prompt or build_baseline_prompt(task),
    ]
    environment = os.environ.copy()
    for name in list(environment):
        if name.startswith("ELEFANTE_") or name in {"PYTHONPATH", "ANONYMIZED_TELEMETRY"}:
            environment.pop(name, None)
    started_at_utc = datetime.now(timezone.utc)
    started_monotonic_ns = time.monotonic_ns()
    try:
        result = subprocess.run(
            command,
            cwd=workspace,
            input="",
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        finished_monotonic_ns = time.monotonic_ns()
        if evidence_sink is not None:
            evidence_sink(
                {
                    "event_schema_version": 1,
                    "started_at_utc": started_at_utc,
                    "finished_at_utc": datetime.now(timezone.utc),
                    "started_monotonic_ns": started_monotonic_ns,
                    "finished_monotonic_ns": finished_monotonic_ns,
                    "status": "error",
                    "result_count": 0,
                    "provider": "openai",
                    "model": model,
                    "usage": {
                        "input_tokens": None,
                        "cached_input_tokens": None,
                        "output_tokens": None,
                        "usage_source": "unknown",
                        "usage_scope": "unavailable",
                        "usage_event_count": 0,
                    },
                    "raw_content_included": False,
                }
            )
        raise
    finished_monotonic_ns = time.monotonic_ns()
    finished_at_utc = datetime.now(timezone.utc)
    duration_ms = max(1, (finished_monotonic_ns - started_monotonic_ns) // 1_000_000)
    usage = parse_codex_usage(result.stdout)
    if evidence_sink is not None:
        evidence_sink(
            {
                "event_schema_version": 1,
                "started_at_utc": started_at_utc,
                "finished_at_utc": finished_at_utc,
                "started_monotonic_ns": started_monotonic_ns,
                "finished_monotonic_ns": finished_monotonic_ns,
                "status": "success" if result.returncode == 0 else "error",
                "result_count": int(result.returncode == 0),
                "provider": "openai",
                "model": model,
                "usage": usage,
                "raw_content_included": False,
            }
        )
    stderr_tail = "\n".join(result.stderr.splitlines()[-5:])
    stdout_tail = "\n".join(result.stdout.splitlines()[-5:]) if result.returncode else ""
    diagnostic = "\n".join(part for part in (stderr_tail, stdout_tail) if part)[-2000:]
    return (
        result.returncode,
        usage,
        duration_ms,
        _codex_version(executable),
        diagnostic,
    )


def record_codex_attempt_evidence(
    store: SessionIntelligenceStore,
    *,
    session_id: str,
    workflow_id: str,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    """Append one evaluator attempt without retaining its prompt or response."""
    if evidence.get("event_schema_version") != 1:
        raise ValueError("unsupported Codex attempt evidence schema")
    if evidence.get("raw_content_included") is not False:
        raise ValueError("Codex attempt evidence must exclude raw content")
    usage = evidence.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Codex attempt evidence requires usage metadata")
    usage_source = usage.get("usage_source", "unknown")
    provider_actual = usage_source == "provider-actual"
    return store.append_invocation(
        session_id=session_id,
        workflow_id=workflow_id,
        invocation_kind="model-attempt",
        client_name="codex",
        tool_name="model-attempt",
        started_at_utc=evidence["started_at_utc"],
        finished_at_utc=evidence["finished_at_utc"],
        started_monotonic_ns=evidence["started_monotonic_ns"],
        finished_monotonic_ns=evidence["finished_monotonic_ns"],
        status=evidence["status"],
        result_count=evidence["result_count"],
        usage_source=usage_source if provider_actual else "unknown",
        usage_scope="provider-workflow",
        provider=evidence.get("provider") if provider_actual else None,
        model=evidence.get("model") if provider_actual else None,
        input_tokens=usage.get("input_tokens") if provider_actual else None,
        cached_input_tokens=(
            usage.get("cached_input_tokens") if provider_actual else None
        ),
        output_tokens=usage.get("output_tokens") if provider_actual else None,
        recall_context_tokens=0 if provider_actual else None,
    )


def session_intelligence_evidence_config(
    *,
    database: Path | None,
    session_id: str | None,
    workflow_id: str | None,
    pending_runs: int,
) -> dict[str, Any] | None:
    """Validate the explicit one-run binding without opening or creating a store."""
    values = (database, session_id, workflow_id)
    if not any(value is not None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError(
            "Session Intelligence evidence requires database, session ID, and "
            "workflow ID together"
        )
    if pending_runs != 1:
        raise ValueError(
            "Session Intelligence evidence requires exactly one pending run"
        )
    try:
        normalized_session = str(UUID(str(session_id)))
        normalized_workflow = str(UUID(str(workflow_id)))
    except ValueError as error:
        raise ValueError(
            "Session Intelligence session and workflow IDs must be UUIDs"
        ) from error
    return {
        "database": Path(database),
        "session_id": normalized_session,
        "workflow_id": normalized_workflow,
    }


def _validate_session_intelligence_binding(
    store: SessionIntelligenceStore,
    *,
    session_id: str,
    workflow_id: str,
    expected_condition: str,
) -> None:
    workflow = store.inspect_workflow(workflow_id)
    if workflow["session_id"] != session_id:
        raise SessionIntelligenceError(
            "Session Intelligence workflow belongs to a different session"
        )
    if workflow["condition"] != expected_condition:
        raise SessionIntelligenceError(
            "Session Intelligence workflow condition does not match this run"
        )
    if workflow["finished_at_utc"] is not None:
        raise SessionIntelligenceError(
            "Session Intelligence workflow is already finished"
        )
    session = next(
        (
            item
            for item in store.export_snapshot()["sessions"]
            if item["session_id"] == session_id
        ),
        None,
    )
    if session is None:
        raise SessionIntelligenceError("unknown Session Intelligence session")
    if session["ended_at_utc"] is not None:
        raise SessionIntelligenceError(
            "Session Intelligence session is already ended"
        )


def open_session_intelligence_evidence_sink(
    config: dict[str, Any],
    *,
    expected_condition: str,
) -> tuple[SessionIntelligenceStore, Callable[[dict[str, Any]], None]]:
    """Open one pre-registered local workflow after a read-only preflight."""
    database = Path(config["database"])
    if not database.is_file():
        raise SessionIntelligenceError(
            "Session Intelligence evidence database does not exist"
        )
    binding = {
        "session_id": str(config["session_id"]),
        "workflow_id": str(config["workflow_id"]),
        "expected_condition": expected_condition,
    }
    with SessionIntelligenceStore(database, read_only=True) as preflight:
        _validate_session_intelligence_binding(preflight, **binding)
    store = SessionIntelligenceStore(database, enabled=True)
    try:
        _validate_session_intelligence_binding(store, **binding)
    except Exception:
        store.close()
        raise

    def sink(evidence: dict[str, Any]) -> None:
        record_codex_attempt_evidence(
            store,
            session_id=binding["session_id"],
            workflow_id=binding["workflow_id"],
            evidence=evidence,
        )

    return store, sink


def require_successful_agent_invocation(
    *, exit_code: int, usage: dict[str, Any], diagnostic: str
) -> None:
    """Reject infrastructure failures before they can become task outcomes."""
    input_tokens = usage.get("input_tokens")
    if (
        exit_code == 0
        and usage.get("usage_source") == "provider-actual"
        and isinstance(input_tokens, int)
        and input_tokens > 0
    ):
        return
    detail = diagnostic.strip() or "no CLI diagnostic"
    raise RuntimeError(
        "Codex evaluator failed before a measurable task attempt: "
        f"exit={exit_code}, input_tokens={input_tokens}, "
        f"usage_source={usage.get('usage_source', 'unknown')}; {detail}"
    )


def evaluate_hidden_acceptance_result(
    repo_root: Path,
    workspace: Path,
    task: dict[str, Any],
    *,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run the bound black-box judge and retain metadata-only diagnostics."""
    test_target = task["acceptance_command"][3]
    test_path_text, _ = test_target.split("::", 1)
    test_path = workspace / test_path_text
    existed = test_path.exists()
    original = test_path.read_bytes() if existed else None
    original_mode = test_path.stat().st_mode if existed else None
    hidden_text = acceptance_test_source(task, repo_root)
    if hidden_text is None:
        raise RuntimeError(f"hidden acceptance artifact is unavailable: {test_path_text}")
    hidden_source = hidden_text.encode("utf-8")
    test_path.parent.mkdir(parents=True, exist_ok=True)
    test_path.write_bytes(hidden_source)
    try:
        with tempfile.TemporaryDirectory(prefix="elefante-baseline-home-") as home:
            environment = os.environ.copy()
            environment.update(
                {
                    "HOME": home,
                    "USERPROFILE": home,
                    "PYTHONPATH": str(workspace),
                    "ELEFANTE_ALLOW_TEST_MEMORIES": "true",
                    "ANONYMIZED_TELEMETRY": "False",
                }
            )
            command = [sys.executable, *task["acceptance_command"][1:]]
            result = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds,
                env=environment,
            )
            return {
                "passed": result.returncode == 0,
                "exit_code": result.returncode,
            }
    finally:
        if existed and original is not None:
            test_path.write_bytes(original)
            if original_mode is not None:
                test_path.chmod(original_mode)
        elif test_path.exists():
            test_path.unlink()


def evaluate_hidden_acceptance(
    repo_root: Path,
    workspace: Path,
    task: dict[str, Any],
    *,
    timeout_seconds: int,
) -> bool:
    """Compatibility wrapper for callers that need only the verdict."""
    return bool(
        evaluate_hidden_acceptance_result(
            repo_root,
            workspace,
            task,
            timeout_seconds=timeout_seconds,
        )["passed"]
    )


def workspace_change_evidence(workspace: Path) -> dict[str, Any]:
    """Return bounded metadata proving whether the agent changed the snapshot."""
    tracked = _run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD"],
        cwd=workspace,
        capture_output=True,
    )
    names = _run(
        ["git", "diff", "--name-only", "-z", "HEAD"],
        cwd=workspace,
        capture_output=True,
    )
    untracked = _run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=workspace,
        capture_output=True,
    )
    if any(result.returncode for result in (tracked, names, untracked)):
        raise RuntimeError("cannot inspect evaluator workspace changes")
    untracked_paths = {
        value.decode("utf-8", errors="surrogateescape")
        for value in untracked.stdout.split(b"\0")
        if value
    }
    paths = sorted(
        {
            value.decode("utf-8", errors="surrogateescape")
            for value in names.stdout.split(b"\0")
            if value
        }
        | untracked_paths
    )
    if len(paths) > 200:
        raise RuntimeError("evaluator changed-file evidence exceeds 200 paths")
    digest = hashlib.sha256()
    digest.update(tracked.stdout)
    for path in paths:
        digest.update(path.encode("utf-8", errors="surrogateescape"))
        candidate = workspace / path
        if path in untracked_paths:
            if candidate.is_file() and not candidate.is_symlink():
                digest.update(hashlib.sha256(candidate.read_bytes()).digest())
            else:
                digest.update(b"non-regular")
    return {
        "changed_files": paths,
        "change_digest": digest.hexdigest() if paths else None,
    }


def trial_stage_trace(
    repo_root: Path,
    task: dict[str, Any],
    *,
    condition: str,
    prompt: str,
    selected_memory_ids: list[str],
    considered_memory_count: int | None,
    brief_abstained: bool | None,
    brief_digest: str | None,
    change_evidence: dict[str, Any],
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    """Build the causal-stage trace without storing prompts or memory bodies."""
    treatment = condition != BASELINE_CONDITION
    validity = task_promotion_validity(task, repo_root)
    if not treatment:
        retrieval_status = "not-applicable"
        selection_status = "not-applicable"
        delivery_status = "not-applicable"
    else:
        retrieval_status = (
            "completed" if (considered_memory_count or 0) > 0 else "empty"
        )
        selection_status = (
            "abstained"
            if brief_abstained
            else ("selected" if selected_memory_ids else "empty")
        )
        delivery_status = "delivered" if selected_memory_ids else "empty"
    return {
        "judge_status": (
            "eligible" if validity["promotion_eligible"] else "diagnostic-only"
        ),
        "acceptance_fixture_sha256": acceptance_test_sha256(task, repo_root),
        "retrieval_status": retrieval_status,
        "considered_memory_count": considered_memory_count if treatment else None,
        "selection_status": selection_status,
        "selected_memory_count": len(selected_memory_ids),
        "delivery_status": delivery_status,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "brief_sha256": brief_digest if treatment else None,
        "agent_use_status": "unknown",
        "execution_status": (
            "changed" if change_evidence["changed_files"] else "no-change"
        ),
        "changed_files": change_evidence["changed_files"],
        "change_digest": change_evidence["change_digest"],
        "acceptance_status": "passed" if acceptance["passed"] else "failed",
        "acceptance_exit_code": acceptance["exit_code"],
    }


def _outcome_path(
    output_dir: Path,
    task_id: str,
    repeat: int,
    *,
    model: str,
    reasoning: str,
) -> Path:
    profile = configuration_id(model, reasoning)
    return output_dir / f"baseline__{profile}__{task_id}__r{repeat}.json"


def _workspace_name(*parts: str) -> str:
    """Keep temporary paths below tool and platform path-length limits."""
    digest = hashlib.sha256("\x00".join(parts).encode("utf-8")).hexdigest()[:16]
    return f"trial-{digest}"


def _safe_remove_workspace(workspace: Path, workspace_root: Path) -> None:
    resolved = workspace.resolve()
    root = workspace_root.resolve()
    if resolved == root or root not in resolved.parents:
        raise RuntimeError(f"refusing to remove workspace outside benchmark root: {workspace}")
    shutil.rmtree(resolved)


def execute_trial(
    repo_root: Path,
    plan_item: dict[str, Any],
    *,
    output_dir: Path,
    workspace_root: Path,
    model: str,
    reasoning: str,
    timeout_seconds: int,
    keep_failures: bool,
    evidence_sink: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    task = plan_item["task"]
    repeat = plan_item["repeat"]
    profile = configuration_id(model, reasoning)
    workspace = workspace_root / _workspace_name(
        "baseline", profile, task["id"], str(repeat)
    )
    outcome_path = _outcome_path(
        output_dir,
        task["id"],
        repeat,
        model=model,
        reasoning=reasoning,
    )
    if outcome_path.exists():
        return {"task_id": task["id"], "repeat": repeat, "skipped": True}

    prepare_workspace(repo_root, task, workspace)
    agent_exit = 1
    usage = {"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0}
    duration_ms = 0
    cli_version = "unknown"
    acceptance_passed = False
    failure_category = "harness"
    try:
        prompt = build_baseline_prompt(task)
        agent_exit, usage, duration_ms, cli_version, agent_diagnostic = run_codex_baseline(
            workspace,
            task,
            model=model,
            reasoning=reasoning,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
            evidence_sink=evidence_sink,
        )
        require_successful_agent_invocation(
            exit_code=agent_exit,
            usage=usage,
            diagnostic=agent_diagnostic,
        )
        change_evidence = workspace_change_evidence(workspace)
        acceptance = evaluate_hidden_acceptance_result(
            repo_root,
            workspace,
            task,
            timeout_seconds=timeout_seconds,
        )
        acceptance_passed = acceptance["passed"]
        failure_category = "" if acceptance_passed else (
            "agent-exit" if agent_exit else "acceptance-test"
        )
        record = {
            "outcome_schema_version": 2,
            "evaluation_id": f"{task['id']}-baseline-r{repeat}",
            "task_id": task["id"],
            "condition": BASELINE_CONDITION,
            "model": model,
            "model_version": "not-exposed-by-codex-cli",
            "tool_configuration": (
                f"{cli_version}; reasoning={reasoning}; sandbox=workspace-write; "
                "ephemeral=true; ignore_user_config=true; ignore_rules=true"
            ),
            "run_seed": None,
            "memory_ids": [],
            "acceptance_passed": acceptance_passed,
            # The single-turn Codex runner does not expose recovery-turn or
            # human-correction counts. Null is deliberate: zero would pretend
            # that an unmeasured secondary outcome was observed.
            "retries": None,
            "human_corrections": None,
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "output_tokens": usage["output_tokens"],
            "duration_ms": duration_ms,
            "failure_category": failure_category,
            "stage_trace": trial_stage_trace(
                repo_root,
                task,
                condition=BASELINE_CONDITION,
                prompt=prompt,
                selected_memory_ids=[],
                considered_memory_count=None,
                brief_abstained=None,
                brief_digest=None,
                change_evidence=change_evidence,
                acceptance=acceptance,
            ),
        }
        errors = validate_outcome_record(record)
        if errors:
            raise RuntimeError("invalid baseline outcome: " + "; ".join(errors))
        output_dir.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return {
            "task_id": task["id"],
            "repeat": repeat,
            "acceptance_passed": acceptance_passed,
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "output_tokens": usage["output_tokens"],
            "duration_ms": duration_ms,
            "outcome": str(outcome_path),
        }
    finally:
        if workspace.exists() and not (keep_failures and not acceptance_passed):
            _safe_remove_workspace(workspace, workspace_root)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task")
    selection.add_argument("--task-class")
    parser.add_argument("--split", choices=("calibration", "holdout"), default="calibration")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--model", default="gpt-5.6-sol")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--estimated-input-tokens-per-run", type=int, default=DEFAULT_ESTIMATED_INPUT_TOKENS)
    parser.add_argument(
        "--estimated-uncached-input-tokens-per-run",
        type=int,
        default=DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACES)
    parser.add_argument("--session-intelligence-db", type=Path)
    parser.add_argument("--session-intelligence-session-id")
    parser.add_argument("--session-intelligence-workflow-id")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--max-total-input-tokens", type=int)
    parser.add_argument("--max-total-uncached-input-tokens", type=int)
    parser.add_argument("--keep-failures", action="store_true")
    parser.add_argument(
        "--allow-diagnostic",
        action="store_true",
        help="Explicitly allow model runs against non-promotable historical judges.",
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    manifest_report = validate_manifest(args.manifest, ROOT)
    if manifest_report["errors"]:
        print(json.dumps({"errors": manifest_report["errors"]}, indent=2))
        return 1
    manifest = load_manifest(args.manifest)
    plan = build_run_plan(
        manifest,
        split=None if args.task else args.split,
        task_id=args.task,
        task_class=args.task_class,
        repetitions=args.repetitions,
    )
    pending = [
        item
        for item in plan
        if not _outcome_path(
            args.output_dir,
            item["task_id"],
            item["repeat"],
            model=args.model,
            reasoning=args.reasoning,
        ).exists()
    ]
    try:
        evidence_config = session_intelligence_evidence_config(
            database=args.session_intelligence_db,
            session_id=args.session_intelligence_session_id,
            workflow_id=args.session_intelligence_workflow_id,
            pending_runs=len(pending),
        )
    except ValueError as error:
        print(
            json.dumps(
                {
                    "pending_runs": len(pending),
                    "execute": args.execute,
                    "error": str(error),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    estimate = len(pending) * args.estimated_input_tokens_per_run
    uncached_estimate = len(pending) * args.estimated_uncached_input_tokens_per_run
    diagnostic_task_ids = sorted(
        {
            item["task_id"]
            for item in pending
            if not task_promotion_validity(item["task"], ROOT)["promotion_eligible"]
        }
    )
    summary = {
        "condition": BASELINE_CONDITION,
        "model": args.model,
        "reasoning": args.reasoning,
        "planned_runs": len(plan),
        "pending_runs": len(pending),
        "estimated_input_tokens": estimate,
        "estimated_uncached_input_tokens": uncached_estimate,
        "execute": args.execute,
        "diagnostic_task_ids": diagnostic_task_ids,
        "session_intelligence_evidence": evidence_config is not None,
    }
    if not args.execute:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if diagnostic_task_ids and not args.allow_diagnostic:
        print(
            json.dumps(
                {
                    **summary,
                    "error": (
                        "selected tasks are diagnostic-only; pass "
                        "--allow-diagnostic to spend model tokens intentionally"
                    ),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if args.max_runs != len(pending):
        print(
            json.dumps(
                {
                    **summary,
                    "error": "--max-runs must exactly match pending_runs before execution",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    limits = {
        "max_total_input_tokens": args.max_total_input_tokens,
        "max_total_uncached_input_tokens": args.max_total_uncached_input_tokens,
    }
    if any(not isinstance(value, int) or value <= 0 for value in limits.values()):
        print(json.dumps({**summary, **limits, "error": "positive cumulative token caps are required"}, indent=2, sort_keys=True))
        return 2
    if estimate > args.max_total_input_tokens or uncached_estimate > args.max_total_uncached_input_tokens:
        print(json.dumps({**summary, **limits, "error": "estimated execution exceeds a cumulative token cap"}, indent=2, sort_keys=True))
        return 2

    evidence_store: SessionIntelligenceStore | None = None
    evidence_sink: Callable[[dict[str, Any]], None] | None = None
    if evidence_config is not None:
        try:
            evidence_store, evidence_sink = open_session_intelligence_evidence_sink(
                evidence_config,
                expected_condition="control",
            )
        except (SessionIntelligenceError, ValueError) as error:
            print(
                json.dumps(
                    {**summary, "error": str(error)}, indent=2, sort_keys=True
                )
            )
            return 2

    args.workspace_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    total_input = 0
    total_cached = 0
    total_output = 0
    try:
        for item in pending:
            result = execute_trial(
                ROOT,
                item,
                output_dir=args.output_dir,
                workspace_root=args.workspace_root,
                model=args.model,
                reasoning=args.reasoning,
                timeout_seconds=args.timeout_seconds,
                keep_failures=args.keep_failures,
                evidence_sink=evidence_sink,
            )
            results.append(result)
            total_input += result["input_tokens"]
            total_cached += result["cached_input_tokens"]
            total_output += result["output_tokens"]
            total_uncached = total_input - total_cached
            if (
                total_input > args.max_total_input_tokens
                or total_uncached > args.max_total_uncached_input_tokens
            ):
                print(
                    json.dumps(
                        {
                            **summary,
                            **limits,
                            "results": results,
                            "actual_input_tokens": total_input,
                            "actual_cached_input_tokens": total_cached,
                            "actual_uncached_input_tokens": total_uncached,
                            "actual_output_tokens": total_output,
                            "error": (
                                "cumulative token cap exceeded; remaining runs "
                                "were not started"
                            ),
                        },
                        indent=2,
                        sort_keys=True,
                    )
                )
                return 3
    finally:
        if evidence_store is not None:
            evidence_store.close()
    print(
        json.dumps(
            {
                **summary,
                **limits,
                "results": results,
                "actual_input_tokens": total_input,
                "actual_cached_input_tokens": total_cached,
                "actual_uncached_input_tokens": total_input - total_cached,
                "actual_output_tokens": total_output,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
