"""Safety tests for paired Task Intelligence evaluation."""

import importlib
import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace

from scripts.ci import run_task_intelligence_evaluation as evaluation
from scripts.ci import audit_task_intelligence_retrieval as retrieval_audit
from src.core.task_intelligence import TaskBriefProfile


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"


def _manifest() -> dict:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def test_document_chunks_are_bounded_and_stable() -> None:
    text = "# Heading\n\n" + ("bounded evidence line\n" * 100)

    first = evaluation.chunk_document(text, max_tokens=30)
    second = evaluation.chunk_document(text, max_tokens=30)

    assert first == second
    assert all(evaluation.estimate_tokens(content) <= 30 for _, content in first)
    assert first[0] == (1, "# Heading")


def test_v2_chunks_retain_heading_and_symbol_lineage() -> None:
    markdown = "# Installer\n\n## Rollback\n\nRestore the previous stable runtime.\n"
    source = (
        "SUPPORTED_HOSTS = ('cursor', 'codex')\n\n"
        "def configure_runtime(path):\n    return path\n\n"
        "def verify_runtime():\n    return True\n"
    )

    doc_chunks = evaluation._heading_aware_chunks(markdown, path="docs/install.md")
    code_chunks = evaluation._heading_aware_chunks(source, path="scripts/install.py")

    assert doc_chunks[0]["heading"] == "Installer > Rollback"
    assert doc_chunks[0]["content"].startswith("Section: Installer > Rollback")
    assert [chunk["symbol"] for chunk in code_chunks] == [
        "SUPPORTED_HOSTS",
        "configure_runtime",
        "verify_runtime",
    ]
    assert code_chunks[0]["content"].startswith("Symbol: SUPPORTED_HOSTS")


def test_v2_source_kind_separates_tests_from_runtime_code() -> None:
    assert evaluation._source_kind("tests/test_install_setup.py") == "test"
    assert evaluation._source_kind("src/core/orchestrator.py") == "implementation"
    assert (
        evaluation._source_kind("agents/manifests/ide-integration.yaml")
        == "configuration"
    )
    assert evaluation._source_kind("docs/how-to/install.md") == "documentation"


def test_v2_source_candidates_read_only_the_prefixed_base(monkeypatch) -> None:
    task = {
        "id": "source-isolation",
        "task_statement": "Configure the stable customer runtime path.",
        "success_criteria": ["The runtime path is configured."],
        "base_ref": "a" * 40,
        "acceptance_ref": "b" * 40,
    }
    calls: list[tuple[str, ...]] = []

    def fake_git(_root, *arguments):
        calls.append(arguments)
        assert arguments == ("archive", "--format=tar", task["base_ref"])
        import io
        import tarfile

        payload = io.BytesIO()
        content = b"def configure_runtime(path):\n    return path\n"
        with tarfile.open(fileobj=payload, mode="w:") as archive:
            member = tarfile.TarInfo("scripts/setup/install.py")
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
            demo = tarfile.TarInfo("scripts/demo/generate_showcase_snapshot.py")
            demo.size = len(content)
            archive.addfile(demo, io.BytesIO(content))
        return payload.getvalue()

    monkeypatch.setattr(evaluation.baseline, "_git_bytes", fake_git)

    candidates = evaluation.source_grounded_candidates(ROOT, task)

    assert candidates
    assert {candidate["path"] for candidate in candidates} == {
        "scripts/setup/install.py"
    }
    assert calls == [("archive", "--format=tar", task["base_ref"])]
    assert all(
        task["acceptance_ref"] not in argument for call in calls for argument in call
    )


def test_v2_prompt_applies_critical_reasoning_to_both_conditions() -> None:
    task = _manifest()["tasks"][0]

    class Brief:
        rendered_context = "ELEFANTE TASK BRIEF\nABSTAIN: weak evidence"

    control = evaluation.build_profile_prompt(task, profile=TaskBriefProfile.V2)
    treatment = evaluation.build_treatment_prompt(
        task,
        Brief(),
        profile=TaskBriefProfile.V2,
    )

    directive = "Agreement is not evidence."
    assert control.count(directive) == 1
    assert treatment.count(directive) == 1
    assert treatment.startswith(control)


def test_v2_outcome_paths_are_isolated_from_frozen_v1() -> None:
    item = {"condition": "task-brief", "task_id": "task", "repeat": 1}
    v1 = evaluation._outcome_path(
        Path("outcomes"),
        item,
        model="model",
        reasoning="low",
        run_seed=7,
        brief_profile=TaskBriefProfile.V1,
    )
    v2 = evaluation._outcome_path(
        Path("outcomes"),
        item,
        model="model",
        reasoning="low",
        run_seed=7,
        brief_profile=TaskBriefProfile.V2,
    )

    assert v1 != v2
    assert "brief-v2" not in v1.name
    assert "brief-v2" in v2.name


def test_v2_outcome_path_changes_with_the_complete_task_contract() -> None:
    item = {
        "condition": "task-brief",
        "task_id": "task",
        "repeat": 1,
        "task": {"id": "task", "task_statement": "original contract"},
    }
    changed = {
        **item,
        "task": {"id": "task", "task_statement": "revised contract"},
    }

    first = evaluation._outcome_path(
        Path("outcomes"),
        item,
        model="model",
        reasoning="low",
        run_seed=7,
        brief_profile=TaskBriefProfile.V2,
    )
    second = evaluation._outcome_path(
        Path("outcomes"),
        changed,
        model="model",
        reasoning="low",
        run_seed=7,
        brief_profile=TaskBriefProfile.V2,
    )

    assert first != second
    assert "__contract-" in first.name


def test_treatment_trial_records_retrieval_delivery_execution_and_acceptance(
    monkeypatch, tmp_path
) -> None:
    task = next(
        task for task in _manifest()["tasks"] if task["id"] == "install-dry-run-005"
    )
    fixed_path = "scripts/setup/bootstrap_release_bundle.py"

    def fake_agent(workspace, _task_value, **_kwargs):
        fixed_source = evaluation.baseline._git_bytes(
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

    monkeypatch.setattr(evaluation.baseline, "run_codex_baseline", fake_agent)
    brief = SimpleNamespace(
        rendered_context="EXECUTION EVIDENCE\n- [memory-1] preserve dry-run boundaries",
        selected_memory_ids=["memory-1"],
        omissions=[],
        abstained=False,
    )
    result = evaluation.execute_trial(
        {
            **task,
            "task": task,
            "task_id": task["id"],
            "condition": "task-brief",
            "repeat": 1,
        },
        brief=brief,
        output_dir=tmp_path / "outcomes",
        workspace_root=tmp_path / "workspaces",
        model="test-model",
        reasoning="low",
        run_seed=20260805,
        timeout_seconds=60,
        keep_failures=False,
        brief_profile=TaskBriefProfile.V2,
    )
    record = json.loads(Path(result["outcome"]).read_text(encoding="utf-8"))
    trace = record["stage_trace"]

    assert record["acceptance_passed"] is True
    assert record["memory_ids"] == ["memory-1"]
    assert trace["retrieval_status"] == "completed"
    assert trace["selection_status"] == "selected"
    assert trace["delivery_status"] == "delivered"
    assert trace["considered_memory_count"] == 1
    assert trace["execution_status"] == "changed"
    assert trace["acceptance_status"] == "passed"
    assert evaluation.validate_outcome_record(record) == []


def test_source_candidates_diversify_files(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        evaluation,
        "_repository_files",
        lambda *_: [
            (
                "src/alpha.py",
                b"def host_selection():\n    return 'adapter family'\n" * 8,
            ),
            ("src/beta.py", b"def host_adapter():\n    return 'selection family'\n"),
        ],
    )
    task = {
        "task_statement": "isolate host selections by adapter family",
        "success_criteria": ["each host family remains isolated"],
        "base_ref": "unused",
    }

    candidates = evaluation.source_grounded_candidates(tmp_path, task, limit=8)

    assert {candidate["path"] for candidate in candidates} == {
        "src/alpha.py",
        "src/beta.py",
    }
    assert (
        sum(candidate["path"] == "src/alpha.py" for candidate in candidates)
        <= evaluation.V2_MAX_CHUNKS_PER_PATH + 1
    )


def test_source_candidates_keep_a_strong_symbol_anchor_with_one_term(
    monkeypatch,
) -> None:
    noise = [
        (
            f"src/noise_{index}.py",
            (
                "def run():\n"
                "    return 'report compatible host canonical identifiers customer readiness'\n"
            ).encode(),
        )
        for index in range(12)
    ]
    monkeypatch.setattr(
        evaluation,
        "_repository_files",
        lambda *_: [
            *noise,
            (
                "scripts/setup/host_selection.py",
                b"SUPPORTED_HOSTS = ('cursor', 'codex')\n",
            ),
        ],
    )
    task = {
        "task_statement": "Report every compatible host.",
        "success_criteria": ["Use canonical identifiers."],
        "base_ref": "unused",
    }

    candidates = evaluation.source_grounded_candidates(Path.cwd(), task, limit=8)

    anchor = next(
        item for item in candidates if item["path"] == "scripts/setup/host_selection.py"
    )
    assert anchor["symbol"] == "SUPPORTED_HOSTS"
    assert anchor["focused_location_score"] >= 0.5


def test_source_candidates_preserve_declared_context_chunks_beyond_lexical_gate(
    monkeypatch,
) -> None:
    noise = [
        (
            f"src/noise_{index}.py",
            b"def report_host_readiness():\n    return 'canonical compatible host'\n",
        )
        for index in range(12)
    ]
    monkeypatch.setattr(
        evaluation,
        "_repository_files",
        lambda *_: [
            *noise,
            (
                "src/declared_target.py",
                b"def probe_runtime_surface():\n    return {'bob': '.bob'}\n",
            ),
        ],
    )
    task = {
        "task_statement": "Report every compatible host.",
        "success_criteria": ["Use canonical identifiers."],
        "base_ref": "unused",
        "context_paths": ["src/declared_target.py"],
    }

    candidates = evaluation.source_grounded_candidates(Path.cwd(), task, limit=8)

    assert any(item["path"] == "src/declared_target.py" for item in candidates)


def test_source_snapshot_prioritizes_declared_context_paths(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        evaluation,
        "source_grounded_candidates",
        lambda *_: [
            {
                "path": "src/target.py",
                "line_number": 7,
                "content": "def target_runtime():\n    return 'ready'",
                "heading": "",
                "symbol": "target_runtime",
                "lexical_score": 0.1,
                "path_score": 0.1,
                "symbol_score": 0.1,
                "pre_score": 0.1,
                "source_code": True,
                "source_kind": "implementation",
            },
            {
                "path": "src/high_score.py",
                "line_number": 3,
                "content": "def nearby_runtime():\n    return 'ready'",
                "heading": "",
                "symbol": "nearby_runtime",
                "lexical_score": 0.8,
                "path_score": 0.8,
                "symbol_score": 0.8,
                "pre_score": 0.8,
                "source_code": True,
                "source_kind": "implementation",
            },
        ],
    )
    task = {
        "id": "declared-context",
        "base_ref": "a" * 40,
        "context_paths": ["src/target.py"],
        "disclosed_memories": [],
    }

    memories = evaluation.source_snapshot_memories(tmp_path, task)
    by_path = {memory.metadata.file_path: memory for memory in memories}

    assert by_path["src/target.py"].metadata.custom_metadata[
        "declared_context_path"
    ]
    assert (
        by_path["src/target.py"].metadata.custom_metadata["retrieval_specificity"]
        == 1.0
    )
    assert not by_path["src/high_score.py"].metadata.custom_metadata[
        "declared_context_path"
    ]


def test_cors_retrieval_surfaces_boundary_not_single_word_memory_noise() -> None:
    task = next(
        task
        for task in _manifest()["tasks"]
        if task["id"] == "runtime-dashboard-cors-022"
    )

    candidates = evaluation.source_grounded_candidates(ROOT, task)

    assert any(
        candidate["path"] == "src/dashboard/server.py"
        and candidate["line_number"] == 20
        for candidate in candidates[:8]
    )
    assert not any(
        candidate["path"] == "src/models/memory.py" for candidate in candidates[:8]
    )


def test_retrieval_audit_scores_only_after_prefixed_retrieval(
    monkeypatch, tmp_path
) -> None:
    calls = []
    task = {
        "id": "task",
        "base_ref": "a" * 40,
        "acceptance_ref": "b" * 40,
    }

    def candidates(*_args, **_kwargs):
        calls.append("retrieve")
        return [{"path": "src/fix.py"}]

    def git(*_args):
        calls.append(_args[1])
        if _args[1] == "diff":
            return type("Result", (), {"returncode": 0, "stdout": "src/fix.py\n"})()
        return type("Result", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr(retrieval_audit, "source_grounded_candidates", candidates)
    monkeypatch.setattr(retrieval_audit, "_git", git)

    result = retrieval_audit.audit_task(tmp_path, task, top_k=10)

    assert calls[0] == "retrieve"
    assert result["hit"] is True
    assert result["hits"] == ["src/fix.py"]


def test_snapshot_memories_are_from_prefixed_base_context_only() -> None:
    task = _manifest()["tasks"][0]

    memories = evaluation.snapshot_memories(ROOT, task)

    assert memories
    assert {memory.metadata.file_path for memory in memories} <= set(
        task["context_paths"]
    )
    assert all(memory.metadata.project == "elefante" for memory in memories)
    assert all(
        memory.metadata.workspace == "historical-snapshot" for memory in memories
    )


def test_v2_snapshot_observation_is_not_mislabelled_verified(monkeypatch) -> None:
    monkeypatch.setattr(
        evaluation,
        "source_grounded_candidates",
        lambda *_: [
            {
                "path": "src/runtime.py",
                "line_number": 7,
                "content": "def configure_runtime(): return True",
                "heading": "",
                "symbol": "configure_runtime",
                "lexical_score": 0.5,
                "path_score": 0.5,
                "symbol_score": 1.0,
                "source_code": True,
            }
        ],
    )
    task = {
        "id": "task",
        "base_ref": "a" * 40,
        "acceptance_ref": "b" * 40,
    }

    memories = evaluation.source_snapshot_memories(ROOT, task)

    assert memories[0].metadata.verified is False
    assert memories[0].metadata.source_reliability == 0.8
    assert memories[0].metadata.custom_metadata["observed_at_ref"] == task["base_ref"]


def test_disclosed_golden_memory_is_treatment_only_verified_evidence() -> None:
    task = next(
        task
        for task in _manifest()["tasks"]
        if task["id"] == "runtime-restore-integrity-025"
    )

    memories = evaluation.source_snapshot_memories(ROOT, task)
    disclosed = [
        memory
        for memory in memories
        if memory.metadata.source_detail.startswith("disclosed:")
    ]

    assert len(disclosed) == 1
    assert disclosed[0].metadata.verified is True
    assert str(disclosed[0].metadata.memory_type) == "directive"
    assert task["disclosed_memories"][0]["content"] == disclosed[0].content

    results = [
        evaluation.SearchResult(
            memory=memory,
            score=0.7,
            source="vector",
            vector_score=0.8,
        )
        for memory in memories
    ]
    brief = evaluation.TaskBriefCompiler().compile(
        evaluation.TaskBriefRequest(
            task_id=task["id"],
            task=task["task_statement"],
            success_criteria=task["success_criteria"],
            project="elefante",
            workspace="historical-snapshot",
            profile=TaskBriefProfile.V2,
        ),
        results,
    )

    assert str(disclosed[0].id) in brief.selected_memory_ids


def test_fixture_brief_preflight_requires_exact_memory_and_is_deterministic(
    monkeypatch,
) -> None:
    task = next(
        task
        for task in _manifest()["tasks"]
        if task["id"] == "install-uncovered-host-black-box-031"
    )
    expected = "f3482775-83b7-47b5-9cbb-d54da9d8bc73"
    sealed = evaluation.sealed_fixture_memories(ROOT, task)[0]
    request = evaluation.TaskBriefRequest(
        task_id=task["id"],
        task=task["task_statement"],
        success_criteria=task["success_criteria"],
        project="elefante",
        workspace="historical-snapshot",
        profile=TaskBriefProfile.V2,
    )
    candidates = [
        evaluation.SearchResult(
            memory=sealed,
            score=0.9,
            source="vector",
            vector_score=0.9,
        )
    ]

    async def fake_inputs(*_args, **_kwargs):
        return request, candidates

    monkeypatch.setattr(evaluation, "_snapshot_brief_inputs", fake_inputs)
    reports = asyncio.run(
        evaluation.verify_fixture_briefs(ROOT, [task], SimpleNamespace())
    )

    assert reports[0]["passed"] is True
    assert reports[0]["expected_memory_id"] == expected
    assert reports[0]["deterministic"] is True
    assert reports[0]["selected_sources"][0]["source_detail"] == (
        "sealed-durable-memory-export"
    )


def test_paired_plan_is_seeded_balanced_and_repeatable() -> None:
    manifest = _manifest()
    first = evaluation.paired_plan(
        manifest,
        split="holdout",
        task_id=None,
        task_class="runtime-safety-and-trust",
        repetitions=3,
        run_seed=7,
    )
    second = evaluation.paired_plan(
        manifest,
        split="holdout",
        task_id=None,
        task_class="runtime-safety-and-trust",
        repetitions=3,
        run_seed=7,
    )

    assert first == second
    assert len(first) == 24
    for index in range(0, len(first), 2):
        pair = first[index : index + 2]
        assert pair[0]["task_id"] == pair[1]["task_id"]
        assert pair[0]["repeat"] == pair[1]["repeat"]
        assert {item["condition"] for item in pair} == {
            "baseline",
            "task-brief",
        }


def test_diagnostic_condition_runs_only_one_side(capsys) -> None:
    result = evaluation.main(
        [
            "--task",
            "runtime-restore-integrity-025",
            "--repetitions",
            "1",
            "--condition",
            "task-brief",
            "--brief-profile",
            "v2",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 0
    assert report["planned_runs"] == 1
    assert report["pending_runs"] == 1


def test_baseline_only_execution_does_not_build_task_briefs(
    monkeypatch, tmp_path, capsys
) -> None:
    def fail_if_constructed():
        raise AssertionError("baseline-only execution must not load embeddings")

    monkeypatch.setattr(evaluation, "EmbeddingService", fail_if_constructed)
    monkeypatch.setattr(
        evaluation,
        "execute_trial",
        lambda item, **_kwargs: {
            "task_id": item["task_id"],
            "condition": item["condition"],
            "repeat": item["repeat"],
            "acceptance_passed": False,
            "input_tokens": 100,
            "cached_input_tokens": 40,
            "output_tokens": 10,
            "duration_ms": 100,
            "outcome": str(tmp_path / "outcome.json"),
        },
    )

    result = evaluation.main(
        [
            "--task",
            "runtime-reset-containment-026",
            "--split",
            "calibration",
            "--repetitions",
            "1",
            "--condition",
            "baseline",
            "--brief-profile",
            "v2",
            "--output-dir",
            str(tmp_path / "outcomes"),
            "--workspace-root",
            str(tmp_path / "workspaces"),
            "--execute",
            "--allow-diagnostic",
            "--max-runs",
            "1",
            "--max-total-input-tokens",
            "600000",
            "--max-total-uncached-input-tokens",
            "100000",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 0
    assert report["results"][0]["condition"] == "baseline"


def test_paired_execution_blocks_diagnostic_only_judges_by_default(capsys) -> None:
    task_id = _manifest()["tasks"][0]["id"]
    result = evaluation.main(
        [
            "--task",
            task_id,
            "--repetitions",
            "1",
            "--brief-profile",
            "v2",
            "--execute",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 2
    assert report["diagnostic_task_ids"] == [task_id]
    assert "--allow-diagnostic" in report["error"]


def test_paired_execution_blocks_valid_task_in_diagnostic_manifest(
    tmp_path, capsys
) -> None:
    task_id = "install-uncovered-host-black-box-031"
    result = evaluation.main(
        [
            "--task",
            task_id,
            "--repetitions",
            "1",
            "--brief-profile",
            "v2",
            "--memory-fixture",
            str(
                ROOT / "benchmarks/task_intelligence/fixtures/"
                "install-uncovered-host-031.memory.json"
            ),
            "--output-dir",
            str(tmp_path / "outcomes"),
            "--execute",
        ]
    )
    report = json.loads(capsys.readouterr().out)

    assert result == 2
    assert report["diagnostic_task_ids"] == [task_id]
    assert "--allow-diagnostic" in report["error"]


def test_treatment_prompt_keeps_hidden_acceptance_out() -> None:
    task = _manifest()["tasks"][0]

    class Brief:
        rendered_context = "PLANNING EVIDENCE\n- [memory] stable customer rule"

    prompt = evaluation.build_treatment_prompt(task, Brief())

    assert task["acceptance_ref"] not in prompt
    assert task["acceptance_command"][3] not in prompt
    assert "stable customer rule" in prompt


def test_import_does_not_force_offline_mode_into_product_runtime(monkeypatch) -> None:
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    monkeypatch.delenv("TRANSFORMERS_OFFLINE", raising=False)

    importlib.reload(evaluation)

    assert "HF_HUB_OFFLINE" not in os.environ
    assert "TRANSFORMERS_OFFLINE" not in os.environ
