"""Safety tests for paired Task Intelligence evaluation."""

import importlib
import json
import os
from pathlib import Path

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
    source = "def configure_runtime(path):\n    return path\n\ndef verify_runtime():\n    return True\n"

    doc_chunks = evaluation._heading_aware_chunks(markdown, path="docs/install.md")
    code_chunks = evaluation._heading_aware_chunks(source, path="scripts/install.py")

    assert doc_chunks[0]["heading"] == "Installer > Rollback"
    assert doc_chunks[0]["content"].startswith("Section: Installer > Rollback")
    assert [chunk["symbol"] for chunk in code_chunks] == [
        "configure_runtime",
        "verify_runtime",
    ]
    assert code_chunks[0]["content"].startswith("Symbol: configure_runtime")


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


def test_paired_plan_is_seeded_balanced_and_repeatable() -> None:
    manifest = _manifest()
    first = evaluation.paired_plan(
        manifest,
        split="holdout",
        task_id=None,
        task_class="installation-and-distribution",
        repetitions=3,
        run_seed=7,
    )
    second = evaluation.paired_plan(
        manifest,
        split="holdout",
        task_id=None,
        task_class="installation-and-distribution",
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
