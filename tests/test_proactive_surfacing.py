"""Regression tests for the bounded literal-trigger surfacing path."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
from uuid import uuid4

import pytest

from src.core.governance import matching_triggers
from src.core.orchestrator import MemoryOrchestrator
from src.core.task_intelligence import TaskBriefCompiler, TaskBriefProfile, TaskBriefRequest
from src.mcp.server import ElefanteMCPServer
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType, SourceType
from src.models.query import QueryMode, SearchFilters, SearchResult


def _memory(
    content: str,
    *,
    trigger: list[str] | None = None,
    policy: str = "ranked",
    project: str | None = None,
    workspace: str | None = None,
    recall_cues: list[str] | None = None,
    source_reliability: float = 0.9,
    status: MemoryStatus = MemoryStatus.VERIFIED,
    archived: bool = False,
    conflict_ids: list | None = None,
) -> Memory:
    return Memory(
        id=uuid4(),
        content=content,
        metadata=MemoryMetadata(
            created_at=datetime(2026, 1, 1),
            last_accessed=datetime(2026, 1, 1),
            memory_type=MemoryType.DIRECTIVE,
            source=SourceType.USER_INPUT,
            source_reliability=source_reliability,
            status=status,
            archived=archived,
            conflict_ids=conflict_ids or [],
            project=project,
            workspace=workspace,
            injection_policy=policy,
            trigger=trigger or [],
            surfaces_when=[],
            recall_cues=recall_cues or [],
        ),
    )


class _VectorStore:
    def __init__(self, memories: list[Memory]) -> None:
        self.memories = memories
        self.calls: list[tuple[int, int, object]] = []

    async def get_all(self, *, limit: int, offset: int, filters=None):
        self.calls.append((limit, offset, filters))
        return self.memories[offset : offset + limit]


def test_matching_triggers_is_literal_case_insensitive_and_deduplicated():
    memory = _memory(
        "A governed deployment note.",
        trigger=["Deploy Now", "deploy now"],
        policy="triggered",
    )
    memory.metadata.surfaces_when = ["release train"]

    assert matching_triggers(
        memory.metadata,
        "The RELEASE TRAIN is blocked; deploy now after review.",
    ) == ["Deploy Now", "release train"]


@pytest.mark.asyncio
async def test_surface_path_requires_explicit_trigger_policy_and_literal_match():
    triggered = _memory(
        "The deployment runbook is stored in the release handbook.",
        trigger=["open the deployment runbook"],
        policy="triggered",
    )
    ranked = _memory(
        "The ranked note also mentions the deployment runbook.",
        trigger=["open the deployment runbook"],
        policy="ranked",
    )
    unrelated = _memory(
        "A different operational note.",
        trigger=["rotate the staging key"],
        policy="triggered",
    )
    vector_store = _VectorStore([ranked, unrelated, triggered])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    before = [deepcopy(item.model_dump()) for item in vector_store.memories]
    results = await orchestrator._surface_triggered_memories(
        "Please open the deployment runbook before continuing.",
        filters=SearchFilters(project=None),
    )

    assert [result.memory.id for result in results] == [triggered.id]
    assert results[0].source == "triggered"
    assert results[0].score == 1.0
    assert results[0].surface_matches == ["open the deployment runbook"]
    assert [item.model_dump() for item in vector_store.memories] == before


@pytest.mark.asyncio
async def test_surface_path_preserves_scope_trust_lifecycle_and_conflict_gates():
    accepted = _memory(
        "Use the customer rollback runbook.",
        trigger=["customer rollback"],
        policy="triggered",
        project="elefante",
    )
    other_project = _memory(
        "Use the other project's rollback runbook.",
        trigger=["customer rollback"],
        policy="triggered",
        project="other",
    )
    low_trust = _memory(
        "Unverified rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        source_reliability=0.49,
    )
    archived = _memory(
        "Archived rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        archived=True,
    )
    conflicted = _memory(
        "Conflicted rollback advice.",
        trigger=["customer rollback"],
        policy="triggered",
        conflict_ids=[uuid4()],
    )
    vector_store = _VectorStore([other_project, low_trust, archived, conflicted, accepted])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    results = await orchestrator._surface_triggered_memories(
        "The customer rollback is required.",
        filters=SearchFilters(project="elefante"),
    )

    assert [result.memory.id for result in results] == [accepted.id]


@pytest.mark.asyncio
async def test_surface_path_is_bounded_to_three_matches():
    memories = [
        _memory(
            f"Operational note {index}.",
            trigger=["shared release trigger"],
            policy="triggered",
        )
        for index in range(4)
    ]
    vector_store = _VectorStore(memories)
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_triggered_memories(
        "The shared release trigger is active."
    )

    assert len(results) == 3
    assert len({result.memory.id for result in results}) == 3


@pytest.mark.asyncio
async def test_surface_path_blocks_digest_stale_source_without_mutating_store(tmp_path):
    source = tmp_path / "runtime.py"
    source.write_text("CURRENT = 'new'\n", encoding="utf-8")
    stale = _memory(
        "Use the old migration rollback contract.",
        trigger=["migration locked"],
        policy="triggered",
    )
    stale.metadata.file_path = "runtime.py"
    stale.metadata.custom_metadata = {
        "source_file_sha256": hashlib.sha256(b"CURRENT = 'old'\n").hexdigest()
    }
    vector_store = _VectorStore([stale])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_triggered_memories(
        "terminal error: migration locked",
        filters=SearchFilters(workspace=str(tmp_path)),
    )

    assert results == []
    assert "current_source_state" not in stale.metadata.custom_metadata


@pytest.mark.asyncio
async def test_surface_path_accepts_context_separate_from_semantic_query(monkeypatch):
    triggered = _memory(
        "Keep the rollback note available.",
        trigger=["terminal error: migration locked"],
        policy="triggered",
    )
    vector_store = _VectorStore([triggered])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    results = await orchestrator.search_memories(
        query="What should I investigate next?",
        surface_context="terminal error: migration locked while applying the backup",
        mode=QueryMode.HYBRID,
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert [result.memory.id for result in results] == [triggered.id]
    assert results[0].surface_matches == ["terminal error: migration locked"]


@pytest.mark.asyncio
async def test_search_integrates_triggered_surface_without_access_or_graph_mutation(monkeypatch):
    triggered = _memory(
        "The exact deployment runbook is in the customer handbook.",
        trigger=["deployment emergency"],
        policy="triggered",
    )
    vector_store = _VectorStore([triggered])
    orchestrator = MemoryOrchestrator(vector_store=vector_store, graph_store=object(), embedding_service=object())

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    before = deepcopy(triggered.model_dump())

    results = await orchestrator.search_memories(
        query="deployment emergency",
        mode=QueryMode.HYBRID,
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert len(results) == 1
    assert results[0].source == "triggered"
    assert results[0].surface_matches == ["deployment emergency"]
    assert results[0].explanation["signals"][0]["name"] == "explicit_trigger"
    assert triggered.model_dump() == before


def test_triggered_surface_is_deliverable_without_semantic_overlap():
    memory = _memory(
        "The deployment runbook is stored in the customer handbook.",
        trigger=["deployment emergency"],
        policy="triggered",
    )
    result = SearchResult(
        memory=memory,
        score=1.0,
        source="triggered",
        surface_matches=["deployment emergency"],
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="deployment emergency",
            profile=TaskBriefProfile.V2,
        ),
        [result],
    )

    assert brief.selected_memory_ids == [str(memory.id)]
    assert brief.packets[0].evidence[0].retrieval_signals["surface_match"] == 1.0


@pytest.mark.asyncio
async def test_recall_cue_is_exact_project_scoped_and_not_a_generic_trigger():
    question = "What is the conclusion after all this work? Explain it to me in STAC."
    accepted = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=[question],
    )
    other_project = _memory(
        "A different project preference.",
        project="other",
        workspace="/work/other",
        recall_cues=[question],
    )
    vector_store = _VectorStore([accepted, other_project])
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=object(),
        embedding_service=object(),
    )

    results = await orchestrator._surface_recall_cue_memories(
        "what is the conclusion after all this work explain it to me in stac",
        filters=SearchFilters(project="elefante", workspace="/work/elefante"),
    )

    assert [result.memory.id for result in results] == [accepted.id]
    assert results[0].source == "recall-cue"
    assert results[0].recall_cue_match is True
    assert await orchestrator._surface_recall_cue_memories(
        "Explain STAC differently",
        filters=SearchFilters(project="elefante", workspace="/work/elefante"),
    ) == []
    assert await orchestrator._surface_recall_cue_memories(
        question,
        filters=None,
    ) == []


@pytest.mark.asyncio
async def test_search_preserves_recall_cue_as_explicit_non_vector_evidence(monkeypatch):
    question = "What is the conclusion after all this work? Explain it to me in STAC."
    memory = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=[question],
    )
    orchestrator = MemoryOrchestrator(
        vector_store=_VectorStore([memory]),
        graph_store=object(),
        embedding_service=object(),
    )

    async def no_semantic_results(*_args, **_kwargs):
        return []

    monkeypatch.setattr(orchestrator, "_search_hybrid", no_semantic_results)
    results = await orchestrator.search_memories(
        query=question,
        mode=QueryMode.HYBRID,
        filters=SearchFilters(
            project="elefante",
            workspace="/work/elefante",
            include_conversation=False,
            include_stored=True,
        ),
        include_conversation=False,
        include_stored=True,
        apply_temporal_decay=False,
        reinforce_access=False,
    )

    assert [result.memory.id for result in results] == [memory.id]
    assert results[0].score == 1.0
    assert results[0].vector_score is None
    assert results[0].recall_cue_match is True
    assert results[0].explanation["signals"][0]["name"] == "customer_recall_cue"


def test_recall_cue_is_deliverable_without_semantic_or_lexical_overlap():
    memory = _memory(
        'User likes answers in simple terms and concisely (STAC).',
        project="elefante",
        workspace="/work/elefante",
        recall_cues=["What is the conclusion after all this work?"],
    )
    result = SearchResult(
        memory=memory,
        score=1.0,
        source="recall-cue",
        recall_cue_match=True,
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="What is the conclusion after all this work?",
            project="elefante",
            workspace="/work/elefante",
            profile=TaskBriefProfile.V2,
        ),
        [result],
    )

    assert brief.selected_memory_ids == [str(memory.id)]
    assert brief.packets[0].evidence[0].retrieval_signals[
        "recall_cue_match"
    ] == 1.0


@pytest.mark.asyncio
async def test_memory_search_handler_forwards_surface_context_and_exposes_match(monkeypatch):
    memory = _memory(
        "The migration rollback note is in the customer handbook.",
        trigger=["terminal error: migration locked"],
        policy="triggered",
    )
    captured = {}

    class _Orchestrator:
        async def search_memories(self, **kwargs):
            captured.update(kwargs)
            return [
                SearchResult(
                    memory=memory,
                    score=1.0,
                    source="triggered",
                    surface_matches=["terminal error: migration locked"],
                )
            ]

    server = ElefanteMCPServer()

    async def get_orchestrator():
        return _Orchestrator()

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    response = await server._handle_search_memories(
        {
            "query": "What should I investigate next?",
            "surface_context": "terminal error: migration locked while applying the backup",
            "include_conversation": False,
            "include_stored": True,
        }
    )

    assert captured["surface_context"].startswith("terminal error")
    assert response["results"][0]["source"] == "triggered"
    assert response["results"][0]["surface_matches"] == [
        "terminal error: migration locked"
    ]
