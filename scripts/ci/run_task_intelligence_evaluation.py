#!/usr/bin/env python3
"""Run capped, paired baseline and Task Brief benchmark trials."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"
DEFAULT_OUTCOMES = ROOT / "benchmarks/task_intelligence/outcomes"
DEFAULT_WORKSPACES = ROOT / "benchmarks/task_intelligence/worktrees"
DEFAULT_ESTIMATED_INPUT_TOKENS = 600_000
DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS = 100_000
CONDITIONS = ("baseline", "task-brief")

# The evaluation must use the already installed local model and never reach a
# model hub while a benchmark is running.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ci import run_task_intelligence_baseline as baseline  # noqa: E402
from scripts.ci.verify_task_intelligence_benchmark import (  # noqa: E402
    scan_memory_payload,
    validate_manifest,
    validate_outcome_record,
)
from src.core.embeddings import EmbeddingService  # noqa: E402
from src.core.retrieval import CognitiveRetriever, MemoryCandidate  # noqa: E402
from src.core.task_intelligence import (  # noqa: E402
    TaskBrief,
    TaskBriefCompiler,
    TaskBriefRequest,
)
from src.models.memory import (  # noqa: E402
    DomainType,
    Memory,
    MemoryMetadata,
    MemoryType,
    SourceType,
)
from src.models.query import SearchResult  # noqa: E402
from src.utils.curation import extract_concepts  # noqa: E402
from src.utils.token_counter import estimate_tokens  # noqa: E402


def _git_text(repo_root: Path, ref: str, path: str) -> str:
    return baseline._git_bytes(repo_root, "show", f"{ref}:{path}").decode(
        "utf-8", errors="replace"
    )


def chunk_document(
    text: str,
    *,
    max_tokens: int = 220,
) -> list[tuple[int, str]]:
    """Split a document into stable, line-grounded evidence chunks."""
    chunks: list[tuple[int, str]] = []
    current: list[str] = []
    start_line = 1

    def flush() -> None:
        nonlocal current
        content = "\n".join(current).strip()
        if content:
            chunks.append((start_line, content))
        current = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.rstrip()
        if not stripped:
            flush()
            continue
        if not current:
            start_line = line_number
        proposed = "\n".join([*current, stripped])
        if current and estimate_tokens(proposed) > max_tokens:
            flush()
            start_line = line_number
        current.append(stripped)
        while estimate_tokens("\n".join(current)) > max_tokens:
            content = "\n".join(current)
            max_characters = max_tokens * 3
            chunks.append((start_line, content[:max_characters].rstrip()))
            remainder = content[max_characters:].lstrip()
            current = [remainder] if remainder else []
    flush()
    return chunks


def snapshot_memories(repo_root: Path, task: dict[str, Any]) -> list[Memory]:
    memories: list[Memory] = []
    for path in sorted(task["context_paths"]):
        text = _git_text(repo_root, task["base_ref"], path)
        for line_number, content in chunk_document(text):
            memory_id = uuid5(
                NAMESPACE_URL,
                f"{task['base_ref']}:{path}:{line_number}:{content}",
            )
            memories.append(
                Memory(
                    id=memory_id,
                    content=content,
                    metadata=MemoryMetadata(
                        domain=DomainType.PROJECT,
                        memory_type=MemoryType.FACT,
                        score=80,
                        confidence=0.8,
                        concepts=extract_concepts(content, max_concepts=5),
                        authority_score=0.8,
                        source=SourceType.DOCUMENT,
                        source_detail=f"{path}:{line_number}",
                        source_reliability=0.8,
                        verified=True,
                        project="elefante",
                        workspace="historical-snapshot",
                        file_path=path,
                        line_number=line_number,
                        created_at=datetime.utcnow(),
                        last_accessed=datetime.utcnow(),
                    ),
                )
            )
    findings = scan_memory_payload(
        {"memories": [{"content": memory.content} for memory in memories]},
        [task],
    )
    if findings:
        raise RuntimeError(f"benchmark memory leakage detected for {task['id']}")
    return memories


async def generate_snapshot_brief(
    repo_root: Path,
    task: dict[str, Any],
    embedding_service: EmbeddingService,
) -> TaskBrief:
    memories = snapshot_memories(repo_root, task)
    if not memories:
        raise RuntimeError(f"no benchmark memories available for {task['id']}")
    query = "\n".join(
        [task["task_statement"], *task["success_criteria"]]
    )
    vectors = await embedding_service.generate_embeddings_batch(
        [query, *[memory.content for memory in memories]]
    )
    query_vector = np.asarray(vectors[0], dtype=np.float32)
    retriever = CognitiveRetriever()
    analysis = retriever.analyze_query(query, query_embedding=vectors[0])
    results: list[SearchResult] = []
    for memory, vector in zip(memories, vectors[1:], strict=True):
        memory.embedding = vector
        memory_vector = np.asarray(vector, dtype=np.float32)
        denominator = float(np.linalg.norm(query_vector) * np.linalg.norm(memory_vector))
        similarity = 0.0 if denominator == 0 else float(
            np.dot(query_vector, memory_vector) / denominator
        )
        similarity = max(0.0, min(1.0, similarity))
        candidate = MemoryCandidate(
            id=str(memory.id),
            content=memory.content,
            title=str(memory.id)[:8],
            summary="",
            concepts=memory.metadata.concepts,
            domain=memory.metadata.domain,
            score=memory.metadata.score,
            access_count=memory.metadata.access_count,
            created_at=memory.metadata.created_at,
            last_accessed=memory.metadata.last_accessed,
            vector_score=similarity,
            memory_type=memory.metadata.memory_type,
        )
        scored, explanation = retriever.score_candidate(
            candidate,
            analysis,
            recent_memory_ids=[],
            include_explanation=True,
        )
        results.append(
            SearchResult(
                memory=memory,
                score=scored.composite_score,
                source="vector",
                vector_score=similarity,
                explanation=explanation.to_dict() if explanation else None,
            )
        )
    results.sort(key=lambda result: (-result.score, str(result.memory.id)))
    request = TaskBriefRequest(
        task=task["task_statement"],
        success_criteria=task["success_criteria"],
        project="elefante",
        workspace="historical-snapshot",
    )
    return TaskBriefCompiler().compile(request, results[:24])


def build_treatment_prompt(task: dict[str, Any], brief: TaskBrief) -> str:
    return (
        baseline.build_baseline_prompt(task)
        + "\n\nElefante Task Brief (read-only evidence):\n"
        + brief.rendered_context
        + "\n\nUse this evidence when relevant. Treat conflicts as unresolved. "
        "Current repository code remains authoritative."
    )


def paired_plan(
    manifest: dict[str, Any],
    *,
    split: str,
    task_id: str | None,
    task_class: str | None,
    repetitions: int,
    run_seed: int,
) -> list[dict[str, Any]]:
    task_plan = baseline.build_run_plan(
        manifest,
        split=None if task_id else split,
        task_id=task_id,
        task_class=task_class,
        repetitions=repetitions,
    )
    plan: list[dict[str, Any]] = []
    for item in task_plan:
        order = list(CONDITIONS)
        digest = hashlib.sha256(
            f"{run_seed}:{item['task_id']}:{item['repeat']}".encode()
        ).digest()
        if digest[0] % 2:
            order.reverse()
        plan.extend({**item, "condition": condition} for condition in order)
    return plan


def _outcome_path(
    output_dir: Path,
    item: dict[str, Any],
    *,
    model: str,
    reasoning: str,
    run_seed: int,
) -> Path:
    profile = baseline.configuration_id(model, reasoning)
    return output_dir / (
        f"{item['condition']}__{profile}__seed-{run_seed}__"
        f"{item['task_id']}__r{item['repeat']}.json"
    )


def execute_trial(
    item: dict[str, Any],
    *,
    brief: TaskBrief | None,
    output_dir: Path,
    workspace_root: Path,
    model: str,
    reasoning: str,
    run_seed: int,
    timeout_seconds: int,
    keep_failures: bool,
) -> dict[str, Any]:
    task = item["task"]
    condition = item["condition"]
    repeat = item["repeat"]
    profile = baseline.configuration_id(model, reasoning)
    workspace = workspace_root / (
        f"{condition}__{profile}__seed-{run_seed}__{task['id']}__r{repeat}"
    )
    outcome_path = _outcome_path(
        output_dir,
        item,
        model=model,
        reasoning=reasoning,
        run_seed=run_seed,
    )
    baseline.prepare_workspace(ROOT, task, workspace)
    acceptance_passed = False
    try:
        prompt = (
            baseline.build_baseline_prompt(task)
            if condition == "baseline"
            else build_treatment_prompt(task, brief)
        )
        agent_exit, usage, duration_ms, cli_version = baseline.run_codex_baseline(
            workspace,
            task,
            model=model,
            reasoning=reasoning,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
        )
        acceptance_passed = baseline.evaluate_hidden_acceptance(
            ROOT,
            workspace,
            task,
            timeout_seconds=timeout_seconds,
        )
        record = {
            "evaluation_id": (
                f"{task['id']}-{condition}-seed-{run_seed}-r{repeat}"
            ),
            "task_id": task["id"],
            "condition": condition,
            "model": model,
            "model_version": "not-exposed-by-codex-cli",
            "tool_configuration": (
                f"{cli_version}; reasoning={reasoning}; sandbox=workspace-write; "
                "ephemeral=true; ignore_user_config=true; ignore_rules=true; "
                "prompt_profile=task-intelligence-v1"
            ),
            "run_seed": run_seed,
            "memory_ids": brief.selected_memory_ids if brief else [],
            "acceptance_passed": acceptance_passed,
            "retries": 0,
            "human_corrections": 0,
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "output_tokens": usage["output_tokens"],
            "duration_ms": duration_ms,
            "failure_category": "" if acceptance_passed else (
                "agent-exit" if agent_exit else "acceptance-test"
            ),
        }
        errors = validate_outcome_record(record)
        if errors:
            raise RuntimeError("invalid evaluation outcome: " + "; ".join(errors))
        output_dir.mkdir(parents=True, exist_ok=True)
        outcome_path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "task_id": task["id"],
            "condition": condition,
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
            baseline._safe_remove_workspace(workspace, workspace_root)


async def _briefs_for_plan(
    plan: list[dict[str, Any]],
    embedding_service: EmbeddingService,
) -> dict[str, TaskBrief]:
    tasks = {item["task_id"]: item["task"] for item in plan}
    briefs: dict[str, TaskBrief] = {}
    for task_id in sorted(tasks):
        briefs[task_id] = await generate_snapshot_brief(
            ROOT,
            tasks[task_id],
            embedding_service,
        )
    return briefs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task")
    selection.add_argument("--task-class")
    parser.add_argument("--split", choices=("calibration", "holdout"), default="holdout")
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--run-seed", type=int, default=20260805)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--estimated-input-tokens-per-run", type=int, default=DEFAULT_ESTIMATED_INPUT_TOKENS)
    parser.add_argument("--estimated-uncached-input-tokens-per-run", type=int, default=DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACES)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--max-total-input-tokens", type=int)
    parser.add_argument("--max-total-uncached-input-tokens", type=int)
    parser.add_argument("--keep-failures", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)

    report = validate_manifest(args.manifest, ROOT)
    if report["errors"]:
        print(json.dumps({"errors": report["errors"]}, indent=2))
        return 1
    manifest = baseline.load_manifest(args.manifest)
    plan = paired_plan(
        manifest,
        split=args.split,
        task_id=args.task,
        task_class=args.task_class,
        repetitions=args.repetitions,
        run_seed=args.run_seed,
    )
    pending = [
        item
        for item in plan
        if not _outcome_path(
            args.output_dir,
            item,
            model=args.model,
            reasoning=args.reasoning,
            run_seed=args.run_seed,
        ).exists()
    ]
    estimate = len(pending) * args.estimated_input_tokens_per_run
    uncached_estimate = (
        len(pending) * args.estimated_uncached_input_tokens_per_run
    )
    summary = {
        "model": args.model,
        "reasoning": args.reasoning,
        "run_seed": args.run_seed,
        "planned_runs": len(plan),
        "pending_runs": len(pending),
        "estimated_input_tokens": estimate,
        "estimated_uncached_input_tokens": uncached_estimate,
        "execute": args.execute,
    }
    if not args.execute:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    if args.max_runs != len(pending):
        print(json.dumps({**summary, "error": "--max-runs must exactly match pending_runs"}, indent=2, sort_keys=True))
        return 2
    limits = (
        args.max_total_input_tokens,
        args.max_total_uncached_input_tokens,
    )
    if any(not isinstance(value, int) or value <= 0 for value in limits):
        print(json.dumps({**summary, "error": "positive cumulative token caps are required"}, indent=2, sort_keys=True))
        return 2
    if estimate > limits[0] or uncached_estimate > limits[1]:
        print(json.dumps({**summary, "error": "estimated execution exceeds a cumulative token cap"}, indent=2, sort_keys=True))
        return 2

    embedding_service = EmbeddingService()
    embedding_service._load_model()
    briefs = asyncio.run(_briefs_for_plan(pending, embedding_service))
    args.workspace_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    total_input = 0
    total_cached = 0
    total_output = 0
    for item in pending:
        result = execute_trial(
            item,
            brief=briefs[item["task_id"]] if item["condition"] == "task-brief" else None,
            output_dir=args.output_dir,
            workspace_root=args.workspace_root,
            model=args.model,
            reasoning=args.reasoning,
            run_seed=args.run_seed,
            timeout_seconds=args.timeout_seconds,
            keep_failures=args.keep_failures,
        )
        results.append(result)
        total_input += result["input_tokens"]
        total_cached += result["cached_input_tokens"]
        total_output += result["output_tokens"]
        if total_input > limits[0] or total_input - total_cached > limits[1]:
            print(json.dumps({**summary, "results": results, "error": "cumulative token cap exceeded; remaining runs were not started"}, indent=2, sort_keys=True))
            return 3
    print(
        json.dumps(
            {
                **summary,
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
