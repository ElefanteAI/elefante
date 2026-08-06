"""Safety and reproducibility tests for Task Intelligence baseline trials."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from scripts.ci import run_task_intelligence_baseline as baseline


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _first_task() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"][0]


def _task(task_id: str) -> dict:
    tasks = json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"]
    return next(task for task in tasks if task["id"] == task_id)


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

    assert result == {"input_tokens": 100, "cached_input_tokens": 60, "output_tokens": 20}
    assert "private output" not in json.dumps(result)


def test_zero_token_agent_exit_is_infrastructure_failure() -> None:
    with pytest.raises(RuntimeError, match="failed before a measurable task attempt"):
        baseline.require_successful_agent_invocation(
            exit_code=1,
            usage={"input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0},
            diagnostic="authentication unavailable",
        )


def test_default_workspace_root_is_short_and_outside_the_repository() -> None:
    assert baseline.DEFAULT_WORKSPACES.parent == Path(tempfile.gettempdir())
    assert ROOT not in baseline.DEFAULT_WORKSPACES.parents
    assert len(baseline._workspace_name("condition", "task", "repeat")) < 32


def test_trial_records_end_to_end_causal_stage_trace(monkeypatch, tmp_path) -> None:
    task = _task("install-dry-run-005")
    fixed_path = "scripts/setup/bootstrap_release_bundle.py"

    def fake_agent(workspace, _task_value, **_kwargs):
        fixed_source = baseline._git_bytes(
            ROOT,
            "show",
            f"{task['acceptance_ref']}:{fixed_path}",
        )
        (workspace / fixed_path).write_bytes(fixed_source)
        return (
            0,
            {"input_tokens": 100, "cached_input_tokens": 40, "output_tokens": 20},
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


def test_run_plan_requires_an_exact_cost_cap() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    plan = baseline.build_run_plan(manifest, split="calibration", repetitions=3)

    assert len(plan) == 54
    assert plan[0]["repeat"] == 1
    assert plan[-1]["repeat"] == 3

    installation = baseline.build_run_plan(
        manifest,
        split="calibration",
        task_class="installation-and-distribution",
    )
    assert len(installation) == 6
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
