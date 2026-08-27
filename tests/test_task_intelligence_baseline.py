"""Safety and reproducibility tests for Task Intelligence baseline trials."""

import json
import hashlib
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.ci import run_task_intelligence_baseline as baseline
from src.core.session_intelligence import (
    CORE_QUALITY_FLOORS,
    SessionIntelligenceStore,
)


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _first_task() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"][0]


def _task(task_id: str) -> dict:
    tasks = json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
    return next(task for task in tasks if task["id"] == task_id)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _session_intelligence_binding(
    path: Path, *, condition: str = "control"
) -> tuple[str, str]:
    current = datetime.now(timezone.utc)
    task_observed = current - timedelta(minutes=2)
    preregistered = current - timedelta(minutes=1)
    store = SessionIntelligenceStore(
        path,
        enabled=True,
        now=lambda: current,
        monotonic_ns=lambda: 1_000_000,
        clock_instance_id="baseline-test-clock",
    )
    session = store.create_session(
        client_name="codex",
        purpose="developer-value-evaluation",
        consent_source="user-directed",
    )
    contract = store.register_task_value_contract(
        goal_sha256=_digest("accepted implementation"),
        question_sha256=_digest("frozen question"),
        acceptance_rubric_sha256=_digest("binary rubric"),
        task_class="developer-implementation",
        quality_floors=sorted(CORE_QUALITY_FLOORS),
        value_units=[
            {
                "id": "accepted-change",
                "weight": 1,
                "criterion_sha256": _digest("maintained checks pass"),
                "evidence_source": "test",
            }
        ],
        time_boundary_sha256=_digest("complete workflow"),
        resource_boundary_sha256=_digest("all provider attempts"),
        preregistered_at_utc=preregistered.isoformat(),
    )
    workflow = store.start_workflow(
        session_id=session["session_id"],
        comparison_id=str(uuid4()),
        condition=condition,
        task_value_contract_sha256=contract,
        matched_context_sha256=_digest("same model tools source and policy"),
        task_observed_at_utc=task_observed.isoformat(),
        independently_arising=True,
        evidence_previously_consumed=False,
    )
    store.close()
    return session["session_id"], workflow["workflow_id"]


def test_baseline_prompt_hides_acceptance_and_treatment_context() -> None:
    task = _first_task()

    prompt = baseline.build_baseline_prompt(task)

    assert task["task_statement"] in prompt
    assert task["acceptance_ref"] not in prompt
    assert task["acceptance_command"][3] not in prompt
    assert not any(path in prompt for path in task["context_paths"])
    assert not any(
        memory["content"] in prompt for memory in task.get("disclosed_memories", [])
    )
    assert "Task Brief" not in prompt


def test_baseline_prompt_hides_disclosed_golden_memory() -> None:
    task = _task("runtime-restore-integrity-025")

    prompt = baseline.build_baseline_prompt(task)

    assert task["disclosed_memories"][0]["content"] not in prompt


def test_workspace_is_a_single_commit_snapshot_without_future_history(tmp_path) -> None:
    task = _first_task()
    workspace = tmp_path / task["id"]

    baseline.prepare_workspace(ROOT, task, workspace)

    count = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    assert count == "1"
    assert not (workspace / "benchmarks/task_intelligence/tasks.json").exists()


def test_installer_black_box_canary_fails_on_base_and_passes_on_known_fix(
    tmp_path,
) -> None:
    task = _task("install-dry-run-005")
    broken_workspace = tmp_path / "broken"
    fixed_workspace = tmp_path / "fixed"

    baseline.prepare_workspace(ROOT, task, broken_workspace)
    fixed_task = {**task, "base_ref": task["acceptance_ref"]}
    baseline.prepare_workspace(ROOT, fixed_task, fixed_workspace)

    assert baseline.evaluate_hidden_acceptance(
        ROOT, broken_workspace, task, timeout_seconds=60
    ) is False
    assert baseline.evaluate_hidden_acceptance(
        ROOT, fixed_workspace, task, timeout_seconds=60
    ) is True


def test_dashboard_cors_black_box_canary_fails_on_base_and_passes_on_known_fix(
    tmp_path,
) -> None:
    task = _task("runtime-dashboard-cors-022")
    broken_workspace = tmp_path / "broken-cors"
    fixed_workspace = tmp_path / "fixed-cors"

    baseline.prepare_workspace(ROOT, task, broken_workspace)
    fixed_task = {**task, "base_ref": task["acceptance_ref"]}
    baseline.prepare_workspace(ROOT, fixed_task, fixed_workspace)

    assert baseline.evaluate_hidden_acceptance(
        ROOT, broken_workspace, task, timeout_seconds=60
    ) is False
    assert baseline.evaluate_hidden_acceptance(
        ROOT, fixed_workspace, task, timeout_seconds=60
    ) is True


def test_restore_integrity_black_box_canary_fails_on_base_and_passes_on_known_fix(
    tmp_path,
) -> None:
    task = _task("runtime-restore-integrity-025")
    broken_workspace = tmp_path / "broken-restore"
    fixed_workspace = tmp_path / "fixed-restore"

    baseline.prepare_workspace(ROOT, task, broken_workspace)
    fixed_task = {**task, "base_ref": task["acceptance_ref"]}
    baseline.prepare_workspace(ROOT, fixed_task, fixed_workspace)

    assert baseline.evaluate_hidden_acceptance(
        ROOT, broken_workspace, task, timeout_seconds=60
    ) is False
    assert baseline.evaluate_hidden_acceptance(
        ROOT, fixed_workspace, task, timeout_seconds=60
    ) is True


def test_codex_event_parser_keeps_usage_not_raw_messages() -> None:
    events = "\n".join(
        [
            '{"type":"item.completed","item":{"type":"agent_message","text":"private output"}}',
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":20}}',
        ]
    )

    result = baseline.parse_codex_usage(events)

    assert result == {
        "input_tokens": 100,
        "cached_input_tokens": 60,
        "output_tokens": 20,
        "usage_source": "provider-actual",
        "usage_scope": "single-complete-turn",
        "usage_event_count": 1,
    }
    assert "private output" not in json.dumps(result)


def test_codex_event_parser_fails_closed_when_usage_semantics_are_ambiguous() -> None:
    multiple = "\n".join(
        [
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":20}}',
            '{"type":"turn.completed","usage":{"input_tokens":120,"cached_input_tokens":70,"output_tokens":25}}',
        ]
    )
    absent = '{"type":"item.completed","item":{"type":"agent_message"}}'

    assert baseline.parse_codex_usage(multiple) == {
        "input_tokens": None,
        "cached_input_tokens": None,
        "output_tokens": None,
        "usage_source": "unknown",
        "usage_scope": "unavailable",
        "usage_event_count": 2,
    }
    assert baseline.parse_codex_usage(absent)["usage_source"] == "unknown"


def test_codex_runner_emits_metadata_only_attempt_evidence(monkeypatch, tmp_path) -> None:
    stdout = "\n".join(
        [
            '{"type":"item.completed","item":{"type":"agent_message","text":"private output"}}',
            '{"type":"turn.completed","usage":{"input_tokens":100,"cached_input_tokens":60,"output_tokens":20}}',
        ]
    )

    def fake_run(command, **_kwargs):
        if command[1:] == ["--version"]:
            return subprocess.CompletedProcess(command, 0, "codex-test\n", "")
        return subprocess.CompletedProcess(command, 0, stdout, "")

    ticks = iter((1_000_000_000, 1_250_000_000))
    monkeypatch.setattr(baseline.shutil, "which", lambda _name: "/tmp/codex")
    monkeypatch.setattr(baseline.subprocess, "run", fake_run)
    monkeypatch.setattr(baseline.time, "monotonic_ns", lambda: next(ticks))
    evidence: list[dict] = []

    result = baseline.run_codex_baseline(
        tmp_path,
        _first_task(),
        model="gpt-5.6-sol",
        reasoning="max",
        timeout_seconds=60,
        evidence_sink=evidence.append,
    )

    assert result[0] == 0
    assert result[2] == 250
    assert evidence[0]["raw_content_included"] is False
    assert evidence[0]["usage"]["usage_source"] == "provider-actual"
    assert "private output" not in json.dumps(evidence[0], default=str)


def test_codex_timeout_keeps_unknown_attempt_evidence(monkeypatch, tmp_path) -> None:
    def fake_run(command, **_kwargs):
        raise subprocess.TimeoutExpired(command, 60)

    ticks = iter((1_000_000_000, 61_000_000_000))
    monkeypatch.setattr(baseline.shutil, "which", lambda _name: "/tmp/codex")
    monkeypatch.setattr(baseline.subprocess, "run", fake_run)
    monkeypatch.setattr(baseline.time, "monotonic_ns", lambda: next(ticks))
    evidence: list[dict] = []

    with pytest.raises(subprocess.TimeoutExpired):
        baseline.run_codex_baseline(
            tmp_path,
            _first_task(),
            model="gpt-5.6-sol",
            reasoning="max",
            timeout_seconds=60,
            evidence_sink=evidence.append,
        )

    assert evidence[0]["status"] == "error"
    assert evidence[0]["usage"]["usage_source"] == "unknown"
    assert evidence[0]["raw_content_included"] is False


def test_pre_registered_session_intelligence_binding_records_attempt(tmp_path) -> None:
    path = tmp_path / "session_intelligence.db"
    session_id, workflow_id = _session_intelligence_binding(path)
    config = baseline.session_intelligence_evidence_config(
        database=path,
        session_id=session_id,
        workflow_id=workflow_id,
        pending_runs=1,
    )
    assert config is not None
    store, sink = baseline.open_session_intelligence_evidence_sink(
        config, expected_condition="control"
    )
    started = datetime.now(timezone.utc)
    sink(
        {
            "event_schema_version": 1,
            "started_at_utc": started,
            "finished_at_utc": started + timedelta(milliseconds=250),
            "started_monotonic_ns": 2_000_000_000,
            "finished_monotonic_ns": 2_250_000_000,
            "status": "success",
            "result_count": 1,
            "provider": "openai",
            "model": "gpt-5.6-sol",
            "usage": {
                "input_tokens": 100,
                "cached_input_tokens": 40,
                "output_tokens": 20,
                "usage_source": "provider-actual",
            },
            "raw_content_included": False,
        }
    )
    store.close()

    with SessionIntelligenceStore(path, read_only=True) as inspected:
        workflow = inspected.inspect_workflow(workflow_id)
    assert len(workflow["invocations"]) == 1
    assert workflow["invocations"][0]["usage_scope"] == "provider-workflow"


def test_session_intelligence_cli_binding_is_all_or_nothing(tmp_path, capsys) -> None:
    result = baseline.main(
        [
            "--task",
            "install-dry-run-005",
            "--session-intelligence-db",
            str(tmp_path / "missing.db"),
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 2
    assert "requires database, session ID, and workflow ID together" in report[
        "error"
    ]


def test_zero_token_agent_exit_is_infrastructure_failure() -> None:
    with pytest.raises(RuntimeError, match="failed before a measurable task attempt"):
        baseline.require_successful_agent_invocation(
            exit_code=1,
            usage={
                "input_tokens": None,
                "cached_input_tokens": None,
                "output_tokens": None,
                "usage_source": "unknown",
            },
            diagnostic="authentication unavailable",
        )


def test_default_workspace_root_is_short_and_outside_the_repository() -> None:
    assert baseline.DEFAULT_WORKSPACES.parent == Path(tempfile.gettempdir())
    assert ROOT not in baseline.DEFAULT_WORKSPACES.parents
    assert len(baseline._workspace_name("condition", "task", "repeat")) < 32


def test_trial_records_end_to_end_causal_stage_trace(monkeypatch, tmp_path) -> None:
    task = _task("install-dry-run-005")
    fixed_path = "scripts/setup/bootstrap_release_bundle.py"

    evidence: list[dict] = []

    def fake_agent(workspace, _task_value, **kwargs):
        kwargs["evidence_sink"]({"attempt": "recorded"})
        fixed_source = baseline._git_bytes(
            ROOT,
            "show",
            f"{task['acceptance_ref']}:{fixed_path}",
        )
        (workspace / fixed_path).write_bytes(fixed_source)
        return (
            0,
            {
                "input_tokens": 100,
                "cached_input_tokens": 40,
                "output_tokens": 20,
                "usage_source": "provider-actual",
                "usage_scope": "single-complete-turn",
                "usage_event_count": 1,
            },
            250,
            "codex-test",
            "",
        )

    monkeypatch.setattr(baseline, "run_codex_baseline", fake_agent)
    output_dir = tmp_path / "outcomes"
    workspace_root = tmp_path / "workspaces"
    result = baseline.execute_trial(
        ROOT,
        {"task": task, "task_id": task["id"], "repeat": 1},
        output_dir=output_dir,
        workspace_root=workspace_root,
        model="test-model",
        reasoning="low",
        timeout_seconds=60,
        keep_failures=False,
        evidence_sink=evidence.append,
    )
    record = json.loads(Path(result["outcome"]).read_text(encoding="utf-8"))
    trace = record["stage_trace"]

    assert record["acceptance_passed"] is True
    assert trace["judge_status"] == "eligible"
    assert trace["retrieval_status"] == "not-applicable"
    assert trace["execution_status"] == "changed"
    assert trace["changed_files"] == [fixed_path]
    assert trace["acceptance_status"] == "passed"
    assert trace["agent_use_status"] == "unknown"
    assert baseline.validate_outcome_record(record) == []
    assert not any(workspace_root.glob("trial-*"))
    assert evidence == [{"attempt": "recorded"}]


def test_run_plan_requires_an_exact_cost_cap() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    plan = baseline.build_run_plan(manifest, split="calibration", repetitions=3)
    calibration_count = sum(
        task["split"] == "calibration" for task in manifest["tasks"]
    )

    assert len(plan) == calibration_count * 3
    assert plan[0]["repeat"] == 1
    assert plan[-1]["repeat"] == 3

    installation = baseline.build_run_plan(
        manifest,
        split="calibration",
        task_class="installation-and-distribution",
    )
    installation_count = sum(
        task["split"] == "calibration"
        and task["task_class"] == "installation-and-distribution"
        for task in manifest["tasks"]
    )
    assert len(installation) == installation_count
    assert {item["task"]["task_class"] for item in installation} == {
        "installation-and-distribution"
    }


def test_outcomes_are_isolated_by_model_configuration(tmp_path) -> None:
    terra = baseline._outcome_path(
        tmp_path,
        "task-001",
        1,
        model="gpt-5.6-terra",
        reasoning="low",
    )
    sol = baseline._outcome_path(
        tmp_path,
        "task-001",
        1,
        model="gpt-5.6-sol",
        reasoning="low",
    )

    assert terra != sol
    assert "gpt-5-6-terra-low" in terra.name
    assert "gpt-5-6-sol-low" in sol.name


def test_execute_requires_explicit_token_caps(capsys) -> None:
    result = baseline.main(
        [
            "--task",
            "install-dry-run-005",
            "--model",
            "test-model",
            "--execute",
            "--max-runs",
            "1",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 2
    assert report["error"] == "positive cumulative token caps are required"


def test_execute_rejects_estimate_above_cap(capsys) -> None:
    result = baseline.main(
        [
            "--task",
            "install-dry-run-005",
            "--model",
            "test-model",
            "--execute",
            "--max-runs",
            "1",
            "--max-total-input-tokens",
            "599999",
            "--max-total-uncached-input-tokens",
            "100000",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 2
    assert report["error"] == "estimated execution exceeds a cumulative token cap"


def test_execute_blocks_diagnostic_only_judges_by_default(capsys) -> None:
    result = baseline.main(
        [
            "--task",
            _first_task()["id"],
            "--execute",
        ]
    )

    report = json.loads(capsys.readouterr().out)
    assert result == 2
    assert report["diagnostic_task_ids"] == [_first_task()["id"]]
    assert "--allow-diagnostic" in report["error"]
