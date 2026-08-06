"""Contract tests for the shadow-only Task Intelligence compiler."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.core.task_intelligence import (
    TaskBriefBudget,
    TaskBriefCompiler,
    TaskBriefRequest,
    TaskBriefService,
)
from src.models.entity import Relationship, RelationshipType
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType, SourceType
from src.models.query import SearchResult


def _result(
    content: str,
    *,
    score: float = 0.8,
    memory_id: UUID | None = None,
    memory_type: MemoryType = MemoryType.FACT,
    project: str | None = "elefante",
    workspace: str | None = "/repo",
    reliability: float = 0.9,
    status: MemoryStatus = MemoryStatus.VERIFIED,
    deprecated: bool = False,
    archived: bool = False,
    superseded_by_id: UUID | None = None,
    conflict_ids: list[UUID] | None = None,
    source: str = "vector",
) -> SearchResult:
    memory = Memory(
        id=memory_id or uuid4(),
        content=content,
        metadata=MemoryMetadata(
            memory_type=memory_type,
            project=project,
            workspace=workspace,
            source=SourceType.DOCUMENT,
            source_detail="docs/reference.md",
            source_reliability=reliability,
            status=status,
            verified=True,
            deprecated=deprecated,
            archived=archived,
            superseded_by_id=superseded_by_id,
            conflict_ids=conflict_ids or [],
            created_at=datetime(2026, 1, 1),
            last_accessed=datetime(2026, 1, 1),
        ),
    )
    return SearchResult(memory=memory, score=score, source=source)


def test_compiler_filters_lifecycle_scope_and_trust_without_mutation() -> None:
    compiler = TaskBriefCompiler()
    request = TaskBriefRequest(
        task="Repair the Elefante installer",
        project="elefante",
        workspace="/repo",
    )
    accepted = _result("Use the stable global customer runtime path.")
    rejected = [
        _result("old", deprecated=True),
        _result("old", archived=True),
        _result("old", superseded_by_id=uuid4()),
        _result("other project", project="other"),
        _result("other workspace", workspace="/other"),
        _result("untrusted", reliability=0.4),
        _result("weak", score=0.2),
    ]
    original = accepted.memory.model_dump()

    brief = compiler.compile(request, [accepted, *rejected])

    assert brief.selected_memory_ids == [str(accepted.memory.id)]
    assert brief.mutated_memory_count == 0
    assert accepted.memory.model_dump() == original
    assert {item.reason for item in brief.omissions} == {
        "archived",
        "cross-project",
        "cross-workspace",
        "deprecated",
        "low-retrieval-score",
        "low-source-reliability",
        "superseded",
    }


def test_compiler_is_deterministic_bounded_and_surfaces_conflicts() -> None:
    conflict_id = uuid4()
    candidates = [
        _result(
            "Architecture decision: keep memory local and inspectable. " * 80,
            score=0.9,
            memory_type=MemoryType.DECISION,
            conflict_ids=[conflict_id],
        ),
        _result(
            "Run the exact installer regression before publishing.",
            score=0.8,
            memory_type=MemoryType.DIRECTIVE,
        ),
        _result("Use a per-user daemon shared by all compatible clients.", score=0.7),
    ]
    request = TaskBriefRequest(
        task="Ship a reliable global installer",
        success_criteria=["The installer regression passes"],
        project="elefante",
        workspace="/repo",
    )
    compiler = TaskBriefCompiler()

    first = compiler.compile(request, candidates)
    second = compiler.compile(request, list(reversed(candidates)))

    assert first == second
    assert first.estimated_tokens <= request.budget.total_tokens
    assert all(packet.estimated_tokens <= packet.token_budget for packet in first.packets)
    assert len(first.selected_memory_ids) <= request.budget.max_evidence_items
    assert first.conflicts[0].related_memory_ids == [str(conflict_id)]
    assert any(item.truncated for packet in first.packets for item in packet.evidence)


def test_budget_rejects_more_than_the_shadow_limit() -> None:
    with pytest.raises(ValueError):
        TaskBriefBudget(
            total_tokens=1501,
            planning_tokens=451,
            execution_tokens=750,
            validation_tokens=300,
        )


@pytest.mark.asyncio
async def test_service_uses_non_mutating_search_and_exactly_one_graph_hop() -> None:
    seed = _result("Use the shared daemon.", score=0.9)
    neighbor = _result("The daemon must remain local.", score=0.1)
    relationship = Relationship(
        from_entity_id=seed.memory.id,
        to_entity_id=neighbor.memory.id,
        relationship_type=RelationshipType.DEPENDS_ON,
        strength=0.8,
    )

    class VectorStore:
        async def get_memory(self, memory_id):
            return neighbor.memory if memory_id == neighbor.memory.id else None

    class GraphStore:
        async def get_relationships(self, memory_id, direction):
            assert memory_id == seed.memory.id
            assert direction == "both"
            return [relationship]

    class Orchestrator:
        vector_store = VectorStore()
        graph_store = GraphStore()

        def __init__(self):
            self.arguments = None

        async def search_memories(self, *args, **kwargs):
            self.arguments = (args, kwargs)
            return [seed]

    orchestrator = Orchestrator()
    brief = await TaskBriefService(orchestrator).generate(
        TaskBriefRequest(
            task="Configure the local daemon",
            project="elefante",
            workspace="/repo",
        )
    )

    kwargs = orchestrator.arguments[1]
    assert kwargs["apply_temporal_decay"] is False
    assert kwargs["reinforce_access"] is False
    assert kwargs["include_conversation"] is False
    graph_evidence = [
        evidence
        for packet in brief.packets
        for evidence in packet.evidence
        if evidence.graph_hop == 1
    ]
    assert len(graph_evidence) == 1
    assert graph_evidence[0].relationship_path == ["DEPENDS_ON"]
