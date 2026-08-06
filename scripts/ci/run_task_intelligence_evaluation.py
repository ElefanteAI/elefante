#!/usr/bin/env python3
"""Run capped, paired baseline and Task Brief benchmark trials."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import math
import os
import re
import sys
import tarfile
import tempfile
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "benchmarks/task_intelligence/tasks.json"
DEFAULT_OUTCOMES = ROOT / "benchmarks/task_intelligence/outcomes"
DEFAULT_WORKSPACES = Path(tempfile.gettempdir()) / "elefante-ti"
DEFAULT_ESTIMATED_INPUT_TOKENS = 600_000
DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS = 100_000
CONDITIONS = ("baseline", "task-brief")

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
    TaskBriefProfile,
    TaskBriefRequest,
)
from src.models.memory import (  # noqa: E402
    DomainType,
    Memory,
    MemoryMetadata,
    MemoryType,
    SOURCE_RELIABILITY_SCORES,
    SourceType,
)
from src.models.query import SearchResult  # noqa: E402
from src.utils.curation import extract_concepts  # noqa: E402
from src.utils.token_counter import estimate_tokens  # noqa: E402


V2_SOURCE_SUFFIXES = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".sh",
        ".ps1",
        ".swift",
        ".toml",
        ".yaml",
        ".yml",
        ".json",
        ".md",
    }
)
V2_EXCLUDED_PREFIXES = (
    ".git/",
    "benchmarks/",
    "dist/",
    "node_modules/",
    "scripts/archive/",
    "scripts/demo/",
    "src/dashboard/ui/dist/",
    "workspace/proposals/_archive/",
    "workspace/postmortems/_archive/",
)
V2_EXCLUDED_NAMES = frozenset(
    {"CHANGELOG.md", "package-lock.json", "requirements.lock"}
)
V2_MAX_FILE_BYTES = 200_000
V2_MAX_CANDIDATE_CHUNKS = 32
V2_MAX_CHUNKS_PER_PATH = 5
_SYMBOL_PATTERN = re.compile(
    r"^\s*(?:async\s+def|def|class|function|export\s+(?:async\s+)?function|"
    r"export\s+class|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"
)


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


def _terms(value: str) -> set[str]:
    return TaskBriefCompiler._terms(value)


def _overlap(query_terms: set[str], evidence_terms: set[str]) -> float:
    return TaskBriefCompiler._overlap(query_terms, evidence_terms)


def _focused_overlap(query_terms: set[str], evidence_terms: set[str]) -> float:
    return TaskBriefCompiler._focused_overlap(query_terms, evidence_terms)


def _canonical_terms(value: str) -> set[str]:
    return TaskBriefCompiler._canonical_terms(value)


def _heading_aware_chunks(
    text: str,
    *,
    path: str,
    max_tokens: int = 220,
) -> list[dict[str, Any]]:
    """Return stable chunks that retain Markdown heading or code-symbol lineage."""
    suffix = PurePosixPath(path).suffix.casefold()
    heading_stack: list[str] = []
    symbol = ""
    chunks: list[dict[str, Any]] = []
    current: list[str] = []
    start_line = 1
    current_heading = ""
    current_symbol = ""

    def flush() -> None:
        nonlocal current
        content = "\n".join(current).strip()
        if content:
            prefix: list[str] = []
            if current_heading:
                prefix.append(f"Section: {current_heading}")
            if current_symbol:
                prefix.append(f"Symbol: {current_symbol}")
            rendered = "\n".join([*prefix, content])
            chunks.append(
                {
                    "line_number": start_line,
                    "content": rendered,
                    "heading": current_heading,
                    "symbol": current_symbol,
                }
            )
        current = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if suffix == ".md":
            heading_match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
            if heading_match:
                flush()
                level = len(heading_match.group(1))
                heading_stack = heading_stack[: level - 1]
                heading_stack.append(heading_match.group(2).strip())
                current_heading = " > ".join(heading_stack)
                current_symbol = ""
                continue
        else:
            symbol_match = _SYMBOL_PATTERN.match(line)
            if symbol_match:
                flush()
                symbol = symbol_match.group(1)
                current_symbol = symbol
                current_heading = ""
        stripped = line.rstrip()
        if not stripped:
            flush()
            continue
        if not current:
            start_line = line_number
        proposed = "\n".join([*current, stripped])
        context = "\n".join(
            item
            for item in (
                f"Section: {current_heading}" if current_heading else "",
                f"Symbol: {current_symbol}" if current_symbol else "",
                proposed,
            )
            if item
        )
        if current and estimate_tokens(context) > max_tokens:
            flush()
            start_line = line_number
        current.append(stripped)
    flush()
    return chunks


def _repository_files(repo_root: Path, ref: str) -> list[tuple[str, bytes]]:
    """Read an immutable repository snapshot with one Git process."""
    archive_bytes = baseline._git_bytes(repo_root, "archive", "--format=tar", ref)
    files: list[tuple[str, bytes]] = []
    with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:") as archive:
        for member in archive.getmembers():
            path = member.name
            if not member.isfile():
                continue
            if PurePosixPath(path).suffix.casefold() not in V2_SOURCE_SUFFIXES:
                continue
            if PurePosixPath(path).name in V2_EXCLUDED_NAMES:
                continue
            if path.startswith(V2_EXCLUDED_PREFIXES):
                continue
            source = archive.extractfile(member)
            if source is not None:
                files.append((path, source.read()))
    return sorted(files)


def source_grounded_candidates(
    repo_root: Path,
    task: dict[str, Any],
    *,
    limit: int = V2_MAX_CANDIDATE_CHUNKS,
) -> list[dict[str, Any]]:
    """Rank pre-fix repository chunks without reading any future ref."""
    query = "\n".join([task["task_statement"], *task["success_criteria"]])
    query_terms = _canonical_terms(query)
    candidates: list[dict[str, Any]] = []
    document_frequency: Counter[str] = Counter()
    chunk_count = 0
    chunk_sequences: dict[str, list[dict[str, Any]]] = {}
    for path, raw in _repository_files(repo_root, task["base_ref"]):
        if len(raw) > V2_MAX_FILE_BYTES or b"\x00" in raw:
            continue
        text = raw.decode("utf-8", errors="replace")
        path_terms = _canonical_terms(path)
        chunks = _heading_aware_chunks(text, path=path)
        chunk_sequences[path] = chunks
        for chunk_index, chunk in enumerate(chunks):
            chunk_count += 1
            content_terms = _canonical_terms(chunk["content"])
            symbol_terms = _canonical_terms(chunk["symbol"])
            evidence_terms = path_terms | content_terms | symbol_terms
            matched_terms = query_terms & evidence_terms
            document_frequency.update(matched_terms)
            minimum_matches = 1 if len(query_terms) <= 4 else 2
            if len(matched_terms) < minimum_matches:
                continue
            source_code = PurePosixPath(path).suffix.casefold() != ".md"
            candidates.append(
                {
                    **chunk,
                    "path": path,
                    "matched_terms": len(matched_terms),
                    "_chunk_index": chunk_index,
                    "_path_terms": path_terms,
                    "_content_terms": content_terms,
                    "_symbol_terms": symbol_terms,
                    "source_code": source_code,
                }
            )
    weights = {
        term: math.log((chunk_count + 1) / (document_frequency[term] + 1)) + 1.0
        for term in query_terms
    }
    weight_total = sum(weights.values()) or 1.0

    def weighted_overlap(evidence_terms: set[str]) -> float:
        return sum(weights[term] for term in query_terms & evidence_terms) / weight_total

    for candidate in candidates:
        path_score = weighted_overlap(candidate.pop("_path_terms"))
        lexical_score = weighted_overlap(candidate.pop("_content_terms"))
        symbol_score = weighted_overlap(candidate.pop("_symbol_terms"))
        candidate.update(
            {
                "path_score": path_score,
                "lexical_score": lexical_score,
                "symbol_score": symbol_score,
                "pre_score": (
                    0.62 * lexical_score
                    + 0.23 * path_score
                    + 0.10 * symbol_score
                    + 0.05 * float(candidate["source_code"])
                ),
            }
        )
    ranked = sorted(
        candidates,
        key=lambda item: (
            -item["pre_score"],
            -int(item["source_code"]),
            item["path"],
            item["line_number"],
        ),
    )
    diversified: list[dict[str, Any]] = []
    chunks_per_path: dict[str, int] = {}
    primary_limit = max(1, limit - min(4, limit // 4))
    for candidate in ranked:
        path = candidate["path"]
        if chunks_per_path.get(path, 0) >= V2_MAX_CHUNKS_PER_PATH:
            continue
        diversified.append(candidate)
        chunks_per_path[path] = chunks_per_path.get(path, 0) + 1
        if len(diversified) == primary_limit:
            break
    selected_keys = {
        (candidate["path"], candidate["line_number"]) for candidate in diversified
    }
    ordered_paths = list(dict.fromkeys(candidate["path"] for candidate in diversified))
    for path in ordered_paths:
        path_candidates = sorted(
            (
                candidate
                for candidate in diversified
                if candidate["path"] == path
                and candidate["source_code"]
                and candidate["symbol"]
            ),
            key=lambda candidate: int(candidate["_chunk_index"]),
            reverse=True,
        )
        candidate = None
        neighbor = None
        next_index = -1
        for possible in path_candidates:
            possible_index = int(possible["_chunk_index"]) + 1
            sequence = chunk_sequences[path]
            if possible_index >= len(sequence):
                continue
            possible_neighbor = sequence[possible_index]
            key = (path, possible_neighbor["line_number"])
            if (
                key not in selected_keys
                and possible_neighbor["symbol"] == possible["symbol"]
            ):
                candidate = possible
                neighbor = possible_neighbor
                next_index = possible_index
                break
        if candidate is None or neighbor is None:
            continue
        continuation = [neighbor["content"]]
        sequence = chunk_sequences[path]
        for following in sequence[next_index + 1 :]:
            if following["symbol"] != candidate["symbol"]:
                break
            proposed = "\n".join([*continuation, following["content"]])
            if estimate_tokens(proposed) > 220:
                break
            continuation.append(following["content"])
        neighbor = {**neighbor, "content": "\n".join(continuation)}
        key = (path, neighbor["line_number"])
        neighbor_content_terms = _canonical_terms(neighbor["content"])
        neighbor_symbol_terms = _canonical_terms(neighbor["symbol"])
        neighbor_matches = query_terms & (
            _canonical_terms(path) | neighbor_content_terms | neighbor_symbol_terms
        )
        diversified.append(
            {
                **neighbor,
                "path": path,
                "path_score": weighted_overlap(_canonical_terms(path)),
                "lexical_score": weighted_overlap(neighbor_content_terms),
                "symbol_score": weighted_overlap(neighbor_symbol_terms),
                "matched_terms": len(neighbor_matches),
                "pre_score": candidate["pre_score"] * 0.9,
                "source_code": True,
                "structural_dependency": True,
                "_chunk_index": next_index,
            }
        )
        selected_keys.add(key)
        if len(diversified) == limit:
            break
    return diversified


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


def source_snapshot_memories(repo_root: Path, task: dict[str, Any]) -> list[Memory]:
    """Build v2 memories only from task-relevant pre-fix source evidence."""
    memories: list[Memory] = []
    candidates = source_grounded_candidates(repo_root, task)
    maximum_pre_score = max(
        (float(candidate.get("pre_score", 0.0)) for candidate in candidates),
        default=1.0,
    )
    for candidate in candidates:
        path = candidate["path"]
        line_number = candidate["line_number"]
        content = candidate["content"]
        memory_id = uuid5(
            NAMESPACE_URL,
            f"v2:{task['base_ref']}:{path}:{line_number}:{content}",
        )
        source_code = candidate["source_code"]
        source_type = SourceType.CODE_ANALYSIS if source_code else SourceType.DOCUMENT
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
                    source=source_type,
                    source_detail=f"{path}:{line_number}",
                    source_reliability=SOURCE_RELIABILITY_SCORES[source_type],
                    verified=False,
                    project="elefante",
                    workspace="historical-snapshot",
                    file_path=path,
                    line_number=line_number,
                    custom_metadata={
                        "heading": candidate["heading"],
                        "symbol": candidate["symbol"],
                        "lexical_score": candidate["lexical_score"],
                        "path_score": candidate["path_score"],
                        "symbol_score": candidate["symbol_score"],
                        "retrieval_specificity": (
                            float(candidate.get("pre_score", 0.0)) / maximum_pre_score
                            if maximum_pre_score
                            else 0.0
                        ),
                        "structural_dependency": bool(
                            candidate.get("structural_dependency", False)
                        ),
                        "source_kind": (
                            "implementation" if source_code else "documentation"
                        ),
                        "observed_at_ref": task["base_ref"],
                    },
                    created_at=datetime.utcnow(),
                    last_accessed=datetime.utcnow(),
                ),
            )
        )
    for disclosed in task.get("disclosed_memories", []):
        content = disclosed["content"]
        memory_id = uuid5(
            NAMESPACE_URL,
            f"disclosed:{task['id']}:{disclosed['id']}:{content}",
        )
        memories.append(
            Memory(
                id=memory_id,
                content=content,
                metadata=MemoryMetadata(
                    domain=DomainType.PROJECT,
                    memory_type=MemoryType(disclosed["memory_type"]),
                    score=90,
                    confidence=0.95,
                    concepts=extract_concepts(content, max_concepts=8),
                    authority_score=0.9,
                    source=SourceType.USER_INPUT,
                    source_detail=f"disclosed:{disclosed['id']}",
                    source_reliability=SOURCE_RELIABILITY_SCORES[SourceType.USER_INPUT],
                    verified=True,
                    project="elefante",
                    workspace="historical-snapshot",
                    custom_metadata={
                        "evidence_role": "constraint",
                        "retrieval_specificity": 1.0,
                        "provenance": disclosed["provenance"],
                    },
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
    *,
    profile: TaskBriefProfile = TaskBriefProfile.V1,
) -> TaskBrief:
    memories = (
        source_snapshot_memories(repo_root, task)
        if profile == TaskBriefProfile.V2
        else snapshot_memories(repo_root, task)
    )
    if not memories:
        raise RuntimeError(f"no benchmark memories available for {task['id']}")
    query = "\n".join([task["task_statement"], *task["success_criteria"]])
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
        denominator = float(
            np.linalg.norm(query_vector) * np.linalg.norm(memory_vector)
        )
        similarity = (
            0.0
            if denominator == 0
            else float(np.dot(query_vector, memory_vector) / denominator)
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
        task_id=task["id"],
        task=task["task_statement"],
        success_criteria=task["success_criteria"],
        project="elefante",
        workspace="historical-snapshot",
        profile=profile,
    )
    candidate_results = results if profile == TaskBriefProfile.V2 else results[:24]
    return TaskBriefCompiler().compile(request, candidate_results)


def build_profile_prompt(
    task: dict[str, Any],
    *,
    profile: TaskBriefProfile,
) -> str:
    prompt = baseline.build_baseline_prompt(task)
    if profile == TaskBriefProfile.V1:
        return prompt
    return (
        prompt
        + "\n\nDecision protocol (identical in control and treatment):\n"
        + "- Agreement is not evidence. Inspect current source before accepting a premise.\n"
        + "- Identify the governing objective and root cause before changing code.\n"
        + "- Test the strongest plausible competing explanation.\n"
        + "- State material uncertainty as UNKNOWN; do not hide it with a local patch.\n"
        + "- Prefer the smallest change that improves the system and verify the measured result."
    )


def build_treatment_prompt(
    task: dict[str, Any],
    brief: TaskBrief,
    *,
    profile: TaskBriefProfile = TaskBriefProfile.V1,
) -> str:
    return (
        build_profile_prompt(task, profile=profile)
        + "\n\nElefante Task Brief (read-only evidence):\n"
        + brief.rendered_context
        + "\n\nUse an item only if it changes the next action. Treat conflicts as unresolved. "
        "If the Brief abstains or evidence is weak, inspect the repository. "
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
    brief_profile: TaskBriefProfile = TaskBriefProfile.V1,
) -> Path:
    profile = baseline.configuration_id(model, reasoning)
    brief_segment = "" if brief_profile == TaskBriefProfile.V1 else "__brief-v2"
    return output_dir / (
        f"{item['condition']}__{profile}{brief_segment}__seed-{run_seed}__"
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
    brief_profile: TaskBriefProfile = TaskBriefProfile.V1,
) -> dict[str, Any]:
    task = item["task"]
    condition = item["condition"]
    repeat = item["repeat"]
    profile = baseline.configuration_id(model, reasoning)
    workspace = workspace_root / baseline._workspace_name(
        condition,
        profile,
        brief_profile.value,
        str(run_seed),
        task["id"],
        str(repeat),
    )
    outcome_path = _outcome_path(
        output_dir,
        item,
        model=model,
        reasoning=reasoning,
        run_seed=run_seed,
        brief_profile=brief_profile,
    )
    baseline.prepare_workspace(ROOT, task, workspace)
    acceptance_passed = False
    try:
        prompt = (
            build_profile_prompt(task, profile=brief_profile)
            if condition == "baseline"
            else build_treatment_prompt(task, brief, profile=brief_profile)
        )
        (
            agent_exit,
            usage,
            duration_ms,
            cli_version,
            agent_diagnostic,
        ) = baseline.run_codex_baseline(
            workspace,
            task,
            model=model,
            reasoning=reasoning,
            timeout_seconds=timeout_seconds,
            prompt=prompt,
        )
        baseline.require_successful_agent_invocation(
            exit_code=agent_exit,
            usage=usage,
            diagnostic=agent_diagnostic,
        )
        acceptance_passed = baseline.evaluate_hidden_acceptance(
            ROOT,
            workspace,
            task,
            timeout_seconds=timeout_seconds,
        )
        record = {
            "evaluation_id": (f"{task['id']}-{condition}-seed-{run_seed}-r{repeat}"),
            "task_id": task["id"],
            "condition": condition,
            "model": model,
            "model_version": "not-exposed-by-codex-cli",
            "tool_configuration": (
                f"{cli_version}; reasoning={reasoning}; sandbox=workspace-write; "
                "ephemeral=true; ignore_user_config=true; ignore_rules=true; "
                f"prompt_profile=task-intelligence-{brief_profile.value}"
            ),
            "run_seed": run_seed,
            "memory_ids": brief.selected_memory_ids if brief else [],
            "acceptance_passed": acceptance_passed,
            # Not exposed by this single-turn runner. Preserve UNKNOWN instead
            # of manufacturing a zero that could influence promotion.
            "retries": None,
            "human_corrections": None,
            "input_tokens": usage["input_tokens"],
            "cached_input_tokens": usage["cached_input_tokens"],
            "output_tokens": usage["output_tokens"],
            "duration_ms": duration_ms,
            "failure_category": ""
            if acceptance_passed
            else ("agent-exit" if agent_exit else "acceptance-test"),
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
    *,
    profile: TaskBriefProfile = TaskBriefProfile.V1,
) -> dict[str, TaskBrief]:
    tasks = {item["task_id"]: item["task"] for item in plan}
    briefs: dict[str, TaskBrief] = {}
    for task_id in sorted(tasks):
        briefs[task_id] = await generate_snapshot_brief(
            ROOT,
            tasks[task_id],
            embedding_service,
            profile=profile,
        )
    return briefs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--task")
    selection.add_argument("--task-class")
    parser.add_argument(
        "--split", choices=("calibration", "holdout"), default="holdout"
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--run-seed", type=int, default=20260805)
    parser.add_argument("--model", default="gpt-5.6-terra")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument(
        "--condition",
        choices=CONDITIONS,
        help="Run one diagnostic condition; omit for a paired evaluation.",
    )
    parser.add_argument(
        "--brief-profile",
        choices=tuple(profile.value for profile in TaskBriefProfile),
        default=TaskBriefProfile.V1.value,
        help="v1 reproduces frozen evidence; v2 uses source-grounded actionable evidence",
    )
    parser.add_argument(
        "--estimated-input-tokens-per-run",
        type=int,
        default=DEFAULT_ESTIMATED_INPUT_TOKENS,
    )
    parser.add_argument(
        "--estimated-uncached-input-tokens-per-run",
        type=int,
        default=DEFAULT_ESTIMATED_UNCACHED_INPUT_TOKENS,
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTCOMES)
    parser.add_argument("--workspace-root", type=Path, default=DEFAULT_WORKSPACES)
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-runs", type=int)
    parser.add_argument("--max-total-input-tokens", type=int)
    parser.add_argument("--max-total-uncached-input-tokens", type=int)
    parser.add_argument("--keep-failures", action="store_true")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    brief_profile = TaskBriefProfile(args.brief_profile)

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
    if args.condition:
        plan = [item for item in plan if item["condition"] == args.condition]
    pending = [
        item
        for item in plan
        if not _outcome_path(
            args.output_dir,
            item,
            model=args.model,
            reasoning=args.reasoning,
            run_seed=args.run_seed,
            brief_profile=brief_profile,
        ).exists()
    ]
    estimate = len(pending) * args.estimated_input_tokens_per_run
    uncached_estimate = len(pending) * args.estimated_uncached_input_tokens_per_run
    summary = {
        "model": args.model,
        "reasoning": args.reasoning,
        "run_seed": args.run_seed,
        "brief_profile": brief_profile.value,
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
        print(
            json.dumps(
                {**summary, "error": "--max-runs must exactly match pending_runs"},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    limits = (
        args.max_total_input_tokens,
        args.max_total_uncached_input_tokens,
    )
    if any(not isinstance(value, int) or value <= 0 for value in limits):
        print(
            json.dumps(
                {**summary, "error": "positive cumulative token caps are required"},
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    if estimate > limits[0] or uncached_estimate > limits[1]:
        print(
            json.dumps(
                {
                    **summary,
                    "error": "estimated execution exceeds a cumulative token cap",
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 2

    # Apply offline mode only inside an explicitly executed evaluation. Setting
    # these at module import would leak into normal pytest collection/runtime.
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
    embedding_service = EmbeddingService()
    embedding_service._load_model()
    briefs = asyncio.run(
        _briefs_for_plan(pending, embedding_service, profile=brief_profile)
    )
    args.workspace_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    total_input = 0
    total_cached = 0
    total_output = 0
    for item in pending:
        result = execute_trial(
            item,
            brief=briefs[item["task_id"]]
            if item["condition"] == "task-brief"
            else None,
            output_dir=args.output_dir,
            workspace_root=args.workspace_root,
            model=args.model,
            reasoning=args.reasoning,
            run_seed=args.run_seed,
            timeout_seconds=args.timeout_seconds,
            keep_failures=args.keep_failures,
            brief_profile=brief_profile,
        )
        results.append(result)
        total_input += result["input_tokens"]
        total_cached += result["cached_input_tokens"]
        total_output += result["output_tokens"]
        if total_input > limits[0] or total_input - total_cached > limits[1]:
            print(
                json.dumps(
                    {
                        **summary,
                        "results": results,
                        "error": "cumulative token cap exceeded; remaining runs were not started",
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
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
