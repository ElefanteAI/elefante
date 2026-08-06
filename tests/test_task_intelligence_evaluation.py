"""Safety tests for paired Task Intelligence evaluation."""

import json
from pathlib import Path

from scripts.ci import run_task_intelligence_evaluation as evaluation


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


def test_snapshot_memories_are_from_prefixed_base_context_only() -> None:
    task = _manifest()["tasks"][0]

    memories = evaluation.snapshot_memories(ROOT, task)

    assert memories
    assert {memory.metadata.file_path for memory in memories} <= set(
        task["context_paths"]
    )
    assert all(memory.metadata.project == "elefante" for memory in memories)
    assert all(memory.metadata.workspace == "historical-snapshot" for memory in memories)


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


def test_treatment_prompt_keeps_hidden_acceptance_out() -> None:
    task = _manifest()["tasks"][0]

    class Brief:
        rendered_context = "PLANNING EVIDENCE\n- [memory] stable customer rule"

    prompt = evaluation.build_treatment_prompt(task, Brief())

    assert task["acceptance_ref"] not in prompt
    assert task["acceptance_command"][3] not in prompt
    assert "stable customer rule" in prompt
