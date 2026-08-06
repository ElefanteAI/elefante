"""Safety and reproducibility tests for Task Intelligence baseline trials."""

import json
import subprocess
from pathlib import Path

from scripts.ci import run_task_intelligence_baseline as baseline


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _first_task() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["tasks"][0]


def test_baseline_prompt_hides_acceptance_and_treatment_context() -> None:
    task = _first_task()

    prompt = baseline.build_baseline_prompt(task)

    assert task["task_statement"] in prompt
    assert task["acceptance_ref"] not in prompt
    assert task["acceptance_command"][3] not in prompt
    assert not any(path in prompt for path in task["context_paths"])
    assert "Task Brief" not in prompt


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
            _first_task()["id"],
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
            _first_task()["id"],
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
