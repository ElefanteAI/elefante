"""Contract tests for the shadow-only Task Intelligence compiler."""

import hashlib
from datetime import datetime
from uuid import UUID, uuid4

import pytest

from src.core.task_intelligence import (
    CurrentSourceState,
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


def test_v2_governance_reserves_locked_always_memory_before_relevance_gates() -> None:
    locked = _result(
        "Release operator constraint: use the signed customer installer.",
        score=0.05,
        reliability=0.2,
    )
    locked.memory.metadata.injection_policy = "always"
    locked.memory.metadata.user_locked = True
    ordinary = _result(
        "Unrelated architecture note with no installer details.",
        score=0.95,
        vector_score=0.95,
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Review the customer release",
            project="elefante",
            workspace="/repo",
            profile=TaskBriefProfile.V2,
        ),
        [ordinary, locked],
    )

    assert str(locked.memory.id) in brief.selected_memory_ids
    assert any(
        "user-locked always-inject" in evidence.reason_selected
        for packet in brief.packets
        for evidence in packet.evidence
        if evidence.memory_id == str(locked.memory.id)
    )


def test_v2_mandatory_memory_wins_global_evidence_budget() -> None:
    ordinary = _result(
        "Architecture decision: use the release installer.",
        score=0.99,
        memory_type=MemoryType.DECISION,
    )
    mandatory = _result(
        "Safety rule: never expose private memory exports.",
        score=0.05,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Review the release installer",
            project="elefante",
            workspace="/repo",
            profile=TaskBriefProfile.V2,
            budget=TaskBriefBudget(
                total_tokens=1500,
                planning_tokens=450,
                execution_tokens=750,
                validation_tokens=300,
                max_evidence_items=1,
            ),
        ),
        [ordinary, mandatory],
    )

    assert brief.selected_memory_ids == [str(mandatory.memory.id)]


def test_v2_blocks_when_mandatory_memories_exceed_item_budget() -> None:
    mandatory = [
        _result(
            f"Required release constraint {index}: preserve customer rollback.",
            memory_type=MemoryType.DIRECTIVE,
            score=0.05,
        )
        for index in range(2)
    ]
    for item in mandatory:
        item.memory.metadata.injection_policy = "always"
        item.memory.metadata.user_locked = True

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Review the customer release rollback constraints.",
            profile=TaskBriefProfile.V2,
            budget=TaskBriefBudget(
                total_tokens=1500,
                planning_tokens=450,
                execution_tokens=750,
                validation_tokens=300,
                max_evidence_items=1,
            ),
        ),
        mandatory,
    )

    assert brief.delivery_blocked is True
    assert brief.selected_memory_ids == []
    assert brief.abstention_reason == "mandatory-context-exceeds-evidence-budget"


def test_v2_blocks_instead_of_truncating_mandatory_memory() -> None:
    mandatory = _result(
        "Required release rollback constraint " * 80,
        memory_type=MemoryType.DIRECTIVE,
        score=0.05,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Review the release rollback constraint.",
            profile=TaskBriefProfile.V2,
            budget=TaskBriefBudget(
                total_tokens=500,
                planning_tokens=250,
                execution_tokens=150,
                validation_tokens=100,
            ),
        ),
        [mandatory],
    )

    assert brief.delivery_blocked is True
    assert brief.selected_memory_ids == []
    assert brief.abstention_reason == "mandatory-context-exceeds-token-budget"
    assert any(
        item.reason == "mandatory-context-truncation" for item in brief.omissions
    )


def test_v2_governance_fails_closed_for_trigger_and_scope() -> None:
    triggered = _result("Installer signing policy for customer releases.")
    triggered.memory.metadata.injection_policy = "triggered"
    triggered.memory.metadata.trigger = ["signed installer"]
    scoped = _result("Private project-only decision.", score=0.95)
    scoped.memory.metadata.scope = "project:other"

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Review the customer release",
            project="elefante",
            workspace="/repo",
            profile=TaskBriefProfile.V2,
        ),
        [triggered, scoped],
    )

    reasons = {item.reason for item in brief.omissions}
    assert "trigger-not-matched" in reasons
    assert "governance-scope" in reasons


def test_v2_explicit_capture_is_deliverable_only_with_literal_scope_and_trigger() -> None:
    mission = _result(
        "Elefante canonical mission: improve intelligence per task.",
        score=0.93,
        vector_score=0.93,
        memory_type=MemoryType.DIRECTIVE,
        project=None,
        workspace=None,
    )
    mission.memory.metadata.scope = "elefante"
    mission.memory.metadata.injection_policy = "triggered"
    mission.memory.metadata.trigger = ["canonical mission"]
    prose_scoped = _result(
        "Elefante canonical mission: improve intelligence per task.",
        score=0.86,
        vector_score=0.86,
        memory_type=MemoryType.DIRECTIVE,
        project=None,
        workspace=None,
    )
    prose_scoped.memory.metadata.scope = "Elefante product and development decisions"
    prose_scoped.memory.metadata.injection_policy = "triggered"
    prose_scoped.memory.metadata.trigger = ["canonical mission"]

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="What is Elefante's canonical mission?",
            profile=TaskBriefProfile.V2,
        ),
        [mission, prose_scoped],
    )

    assert brief.selected_memory_ids == [str(mission.memory.id)]
    assert any(
        item.memory_id == str(prose_scoped.memory.id)
        and item.reason == "governance-scope"
        for item in brief.omissions
    )


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
        "def memory_to_dashboard_node(memory, vector_backend): return backend_label",
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


def test_v2_classifies_test_source_as_validation_safeguard() -> None:
    regression = _result(
        "def test_doctor_reports_uncovered_hosts(): assert customer_ready is False",
        vector_score=0.9,
        file_path="tests/test_install_setup.py",
        custom_metadata={"symbol": "test_doctor_reports_uncovered_hosts"},
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Make doctor report uncovered hosts.",
            success_criteria=["Customer readiness fails for an uncovered host."],
            profile=TaskBriefProfile.V2,
        ),
        [regression],
    )

    evidence = next(item for packet in brief.packets for item in packet.evidence)
    assert evidence.role == EvidenceRole.SAFEGUARD
    assert evidence.stage == TaskStage.VALIDATION


def test_v2_configuration_source_remains_context_without_explicit_role() -> None:
    configuration = _result(
        "status: compatible",
        vector_score=0.9,
        file_path="agents/manifests/ide-integration.yaml",
        custom_metadata={"source_kind": "configuration"},
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Report compatible integration status.",
            profile=TaskBriefProfile.V2,
        ),
        [configuration],
    )

    evidence = next(item for packet in brief.packets for item in packet.evidence)
    assert evidence.role == EvidenceRole.CONTEXT


def test_v2_token_fitting_does_not_starve_later_validation_stage() -> None:
    execution = [
        _result(
            "Configure customer runtime host coverage " * 100,
            vector_score=0.9 - index * 0.01,
            file_path=f"src/runtime_{index}.py",
            custom_metadata={"retrieval_specificity": 1.0 - index * 0.01},
        )
        for index in range(6)
    ]
    regression = _result(
        "def test_customer_host_coverage(): assert uncovered_hosts",
        vector_score=0.8,
        file_path="tests/test_runtime.py",
        custom_metadata={
            "symbol": "test_customer_host_coverage",
            "retrieval_specificity": 0.8,
        },
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Configure customer runtime host coverage.",
            success_criteria=["A regression verifies uncovered hosts."],
            profile=TaskBriefProfile.V2,
        ),
        [*execution, regression],
    )

    validation = next(
        packet for packet in brief.packets if packet.stage == TaskStage.VALIDATION
    )
    assert [item.memory_id for item in validation.evidence] == [
        str(regression.memory.id)
    ]
    assert any(item.reason == "stage-token-budget" for item in brief.omissions)
    assert len(brief.selected_memory_ids) <= 8


def test_v2_rejects_generic_anchor_noise_when_specific_evidence_exists() -> None:
    noise = _result(
        "Dashboard memory access remains private.",
        score=0.99,
        vector_score=0.99,
        file_path="src/utils/dashboard_serializer.py",
    )
    cors_boundary = _result(
        'CORSMiddleware allow_origins=["*"] exposes the dashboard origin boundary.',
        score=0.60,
        vector_score=0.60,
        file_path="src/dashboard/server.py",
    )
    request = TaskBriefRequest(
        task="Restrict dashboard CORS access to explicit local origins.",
        success_criteria=["Dashboard CORS accepts only configured origins."],
        profile=TaskBriefProfile.V2,
    )

    brief = TaskBriefCompiler().compile(request, [noise, cors_boundary])

    assert brief.selected_memory_ids == [str(cors_boundary.memory.id)]
    assert any(
        omission.memory_id == str(noise.memory.id)
        and omission.reason == "insufficient-independent-relevance"
        for omission in brief.omissions
    )


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


def test_v2_constraint_role_cannot_replace_a_question_specific_anchor() -> None:
    unrelated_process_constraint = _result(
        (
            "SDD Gate 2 leakage surface scan specification for contributors. "
            "Every change checks MCP response contracts, database round trips, "
            "stdout purity, state machines, snapshots, and documentation links."
        ),
        memory_type=MemoryType.SPECIFICATION,
        project=None,
        workspace=None,
        status=MemoryStatus.RELATED,
        score=0.60,
        vector_score=0.86,
    )
    request = TaskBriefRequest(
        task=(
            "GitHub issue 2 asks whether customer search results should explain "
            "vector similarity, concept overlap, domain match, authority, and "
            "temporal signals. Decide whether to implement it now and identify "
            "the governing customer-facing constraints."
        ),
        profile=TaskBriefProfile.V2,
    )
    compiler = TaskBriefCompiler()
    ranked = compiler._rank_candidates_v2(request, [unrelated_process_constraint])

    assert ranked[0].role == EvidenceRole.CONSTRAINT
    assert ranked[0].retrieval_signals["query_coverage"] < 0.20
    assert compiler._is_actionable(ranked[0]) is False
    brief = compiler.compile(request, [unrelated_process_constraint])
    assert brief.abstained is True
    assert brief.selected_memory_ids == []
    assert brief.omissions[0].reason == "insufficient-independent-relevance"


def test_v2_selects_a_constraint_with_a_question_specific_text_anchor() -> None:
    relevant_constraint = _result(
        (
            "Customer retrieval explanations must expose only verified signals "
            "and must not fabricate missing score components."
        ),
        memory_type=MemoryType.SPECIFICATION,
        project=None,
        workspace=None,
        score=0.72,
        vector_score=0.70,
    )
    request = TaskBriefRequest(
        task="What constraint governs customer retrieval explanations and score signals?",
        profile=TaskBriefProfile.V2,
    )

    compiler = TaskBriefCompiler()
    ranked = compiler._rank_candidates_v2(request, [relevant_constraint])
    brief = compiler.compile(request, [relevant_constraint])

    assert ranked[0].retrieval_signals["direct_answer"] == 0.0
    assert ranked[0].retrieval_signals["query_coverage"] >= 0.20
    assert compiler._is_actionable(ranked[0]) is True
    assert brief.abstained is False
    assert brief.selected_memory_ids == [str(relevant_constraint.memory.id)]


def test_v2_accepts_strong_direct_answer_without_implementation_signals() -> None:
    direct_answer = _result(
        "The Elefante validation passphrase is Copper-Orbit.",
        score=0.64,
        vector_score=0.91,
        project=None,
        workspace=None,
    )
    request = TaskBriefRequest(
        task=(
            "What is my Elefante validation passphrase? Return only the passphrase, "
            "or UNKNOWN if you cannot verify it."
        ),
        profile=TaskBriefProfile.V2,
    )
    compiler = TaskBriefCompiler()
    ranked = compiler._rank_candidates_v2(request, [direct_answer])

    assert ranked[0].retrieval_signals["direct_answer"] == 1.0
    assert ranked[0].actionability_score < 0.3
    brief = compiler.compile(request, [direct_answer])
    assert brief.selected_memory_ids == [str(direct_answer.memory.id)]
    assert brief.abstained is False


def test_v2_fails_closed_when_task_contract_exceeds_total_budget() -> None:
    mandatory = _result(
        "Release safety constraint " * 200,
        memory_type=MemoryType.DIRECTIVE,
        score=0.01,
        vector_score=0.01,
        file_path="docs/how-to/release.md",
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Prepare the customer release " * 120,
            success_criteria=["Safe and reversible criterion " * 16] * 20,
            profile=TaskBriefProfile.V2,
        ),
        [mandatory],
    )

    assert brief.delivery_blocked is True
    assert brief.selected_memory_ids == []
    assert brief.abstention_reason == "task-contract-exceeds-token-budget"
    assert brief.estimated_tokens <= brief.token_budget


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


def test_v2_user_locked_conflict_blocks_all_delivery() -> None:
    conflicting = _result(
        "Decision: use a global customer runtime for every host.",
        memory_type=MemoryType.DECISION,
        conflict_ids=[uuid4()],
        file_path="workspace/PLANNING.md",
        vector_score=0.9,
    )
    conflicting.memory.metadata.injection_policy = "always"
    conflicting.memory.metadata.user_locked = True
    optional = _result(
        "Use the customer runtime when installing compatible hosts.",
        vector_score=0.9,
        file_path="scripts/setup/host_selection.py",
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Choose the customer runtime installation scope.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [conflicting, optional],
    )

    assert brief.delivery_blocked is True
    assert brief.selected_memory_ids == []
    assert brief.abstention_reason == "mandatory-governance-conflict"
    assert any(item.reason == "unresolved-conflict" for item in brief.omissions)


def test_v2_rejects_secret_shaped_exposed_provenance() -> None:
    candidate = _result(
        "Decision: use a global customer runtime for every host.",
        memory_type=MemoryType.DECISION,
        vector_score=0.9,
    )
    candidate.memory.metadata.source_detail = "api_key=" + ("a" * 32)

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Choose the customer runtime installation scope.",
            profile=TaskBriefProfile.V2,
            project="elefante",
            workspace="/repo",
        ),
        [candidate],
    )

    assert brief.abstained is True
    assert brief.selected_memory_ids == []
    assert brief.omissions[0].reason == "privacy-redaction"


@pytest.mark.asyncio
async def test_service_marks_exact_current_source_as_supported(tmp_path) -> None:
    source = tmp_path / "runtime.py"
    source.write_text(
        "Decision: use one global runtime for every compatible IDE.\n",
        encoding="utf-8",
    )
    candidate = _result(
        "Decision: use one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        workspace=str(tmp_path),
        file_path="runtime.py",
        vector_score=0.9,
    )

    class GraphStore:
        async def get_relationships(self, *_args, **_kwargs):
            return []

    class Orchestrator:
        vector_store = object()
        graph_store = GraphStore()

        async def search_memories(self, *_args, **_kwargs):
            return [candidate]

    brief = await TaskBriefService(Orchestrator()).generate(
        TaskBriefRequest(
            task="What global runtime decision applies across compatible IDEs?",
            project="elefante",
            workspace=str(tmp_path),
            profile=TaskBriefProfile.V2,
        )
    )

    evidence = [item for packet in brief.packets for item in packet.evidence]
    assert evidence[0].current_source_state == CurrentSourceState.SUPPORTED
    assert "current_source_state" not in candidate.memory.metadata.custom_metadata


def test_digest_bound_source_mismatch_is_excluded_and_locked_policy_blocks(
    tmp_path,
) -> None:
    source = tmp_path / "runtime.py"
    source.write_text("CURRENT = 'per-workspace'\n", encoding="utf-8")
    expected_old_digest = hashlib.sha256(b"CURRENT = 'global'\n").hexdigest()
    candidate = _result(
        "Decision: use one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        workspace=str(tmp_path),
        file_path="runtime.py",
        custom_metadata={"source_file_sha256": expected_old_digest},
        vector_score=0.9,
    )
    TaskBriefService._annotate_current_source(candidate.memory, str(tmp_path))

    request = TaskBriefRequest(
        task="What global runtime decision applies across compatible IDEs?",
        project="elefante",
        workspace=str(tmp_path),
        profile=TaskBriefProfile.V2,
    )
    ordinary = TaskBriefCompiler().compile(request, [candidate])
    assert ordinary.abstained is True
    assert ordinary.omissions[0].reason == "current-source-contradicted"

    candidate.memory.metadata.injection_policy = "always"
    candidate.memory.metadata.user_locked = True
    locked = TaskBriefCompiler().compile(request, [candidate])
    assert locked.delivery_blocked is True
    assert locked.abstention_reason == "mandatory-governance-conflict"


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
    assert TaskBriefCompiler._location_overlap(query, {"host"}) == 0.0


def test_v2_accepts_one_strong_symbol_anchor_with_semantic_corroboration() -> None:
    supported_hosts = _result(
        "SUPPORTED_HOSTS = ('cursor', 'codex')",
        vector_score=0.8,
        file_path="scripts/setup/host_selection.py",
        custom_metadata={"symbol": "SUPPORTED_HOSTS"},
    )

    brief = TaskBriefCompiler().compile(
        TaskBriefRequest(
            task="Report every compatible host connected to the runtime.",
            success_criteria=["Use canonical host identifiers."],
            profile=TaskBriefProfile.V2,
        ),
        [supported_hosts],
    )

    assert brief.selected_memory_ids == [str(supported_hosts.memory.id)]
    evidence = next(item for packet in brief.packets for item in packet.evidence)
    assert evidence.retrieval_signals["symbol"] >= 0.5
