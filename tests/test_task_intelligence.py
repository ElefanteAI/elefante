"""Contract tests for the shadow-only Task Intelligence compiler."""

from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.core.task_intelligence import (
    EvidenceRole,
    TaskBriefBudget,
    TaskBriefCompiler,
    TaskBriefProfile,
    TaskBriefRequest,
    TaskBriefService,
    TaskStage,
)
from src.models.entity import Relationship, RelationshipType
from src.models.memory import (
    Memory,
    MemoryMetadata,
    MemoryStatus,
    MemoryType,
    SourceType,
)
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
    file_path: str | None = None,
    custom_metadata: dict | None = None,
    vector_score: float | None = None,
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
            file_path=file_path,
            custom_metadata=custom_metadata or {},
            created_at=datetime(2026, 1, 1),
            last_accessed=datetime(2026, 1, 1),
        ),
    )
    return SearchResult(
        memory=memory,
        score=score,
        source=source,
        vector_score=vector_score,
    )


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
    assert all(
        packet.estimated_tokens <= packet.token_budget for packet in first.packets
    )
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


def test_v2_prefers_actionable_source_and_exposes_selection_contract() -> None:
    generic = _result(
        "The dashboard architecture provides a stable backend abstraction.",
        score=0.95,
        vector_score=0.95,
        file_path="docs/reference/architecture.md",
    )
    implementation = _result(
        "def memory_to_dashboard_node(memory, vector_source): return vector_source",
        score=0.62,
        vector_score=0.62,
        file_path="src/utils/dashboard_serializer.py",
        custom_metadata={"symbol": "memory_to_dashboard_node"},
    )
    request = TaskBriefRequest(
        task_id="dashboard-backend-label",
        task="Report the configured dashboard vector backend label.",
        success_criteria=["Serialized memory nodes expose the backend label."],
        project="elefante",
        workspace="/repo",
        profile=TaskBriefProfile.V2,
    )

    brief = TaskBriefCompiler().compile(request, [generic, implementation])

    assert brief.profile == TaskBriefProfile.V2
    assert brief.task_id == "dashboard-backend-label"
    assert brief.success_criteria == request.success_criteria
    assert brief.selected_memory_ids == [str(implementation.memory.id)]
    evidence = next(item for packet in brief.packets for item in packet.evidence)
    assert evidence.role == EvidenceRole.IMPLEMENTATION
    assert evidence.stage == TaskStage.EXECUTION
    assert "source_code" in evidence.reason_selected
    assert evidence.retrieval_signals["actionability"] >= 0.3


def test_v2_abstains_when_evidence_is_only_generic_semantic_context() -> None:
    generic = _result(
        "Persistent systems should remain reliable and easy to understand.",
        score=0.92,
        vector_score=0.92,
        file_path="docs/reference/architecture.md",
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Repair an unrelated installer permission failure.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [generic],
    )

    assert brief.abstained is True
    assert brief.selected_memory_ids == []
    assert "ABSTAIN" in brief.rendered_context
    assert {item.reason for item in brief.omissions} == {
        "insufficient-independent-relevance"
    }


def test_v2_source_type_alone_does_not_prove_task_relevance() -> None:
    unrelated_source = _result(
        "def render_widget(theme): return theme",
        score=0.93,
        vector_score=0.93,
        file_path="src/dashboard/theme.py",
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Repair installer permissions for the extracted launcher.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [unrelated_source],
    )

    assert brief.abstained is True
    assert brief.omissions[0].reason == "insufficient-independent-relevance"


def test_v2_never_selects_one_side_of_an_unresolved_conflict() -> None:
    conflicting = _result(
        "Decision: use a global customer runtime for every host.",
        memory_type=MemoryType.DECISION,
        conflict_ids=[uuid4()],
        file_path="workspace/PLANNING.md",
        vector_score=0.9,
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Choose the customer runtime installation scope.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [conflicting],
    )

    assert brief.abstained is True
    assert brief.conflicts[0].memory_id == str(conflicting.memory.id)
    assert brief.omissions[0].reason == "unresolved-conflict"


def test_v2_decision_with_test_word_remains_planning_evidence() -> None:
    decision = _result(
        "Architecture decision: tests must use the stable customer runtime.",
        memory_type=MemoryType.DECISION,
        file_path="workspace/PLANNING.md",
        vector_score=0.8,
    )
    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Plan stable customer runtime tests.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [decision],
    )

    evidence = next(item for packet in brief.packets for item in packet.evidence)
    assert evidence.role == EvidenceRole.DECISION
    assert evidence.stage == TaskStage.PLANNING


def test_v2_term_matching_normalizes_plurals_and_rewards_focused_paths() -> None:
    query = TaskBriefCompiler._terms("host selections across adapter families")
    path = TaskBriefCompiler._terms("scripts/setup/host_selection.py")

    assert {"selection", "family"}.issubset(query)
    assert TaskBriefCompiler._focused_overlap(query, path) > TaskBriefCompiler._overlap(
        query, path
    )
