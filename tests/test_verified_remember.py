# TEST    : tests/test_verified_remember.py
# PROVES  : explicit project Remember searches for overlap, writes once,
#           verifies stores/Home/Recall, and removes an unverified new record.
# RUN     : .venv/bin/python -m pytest tests/test_verified_remember.py -q

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from src.core.graph_store import GraphStore
from src.core.orchestrator import MemoryOrchestrator
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.core.verified_operation import (
    VerifiedOperationStatus,
    entity_record_sha256,
    memory_record_sha256,
)
from src.core.verified_remember import (
    RecallVerification,
    VerifiedRememberService,
    _expected_entity,
)
from src.models.entity import Entity, EntityType
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType
from src.models.query import SearchResult
from src.utils.atomic_json import write_json_atomically


PROJECT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PROJECT_NAME = "Customer project"
WORKSPACE = "/private/customer/project"
SCOPE = f"project:{PROJECT_ID}"
MEMORY_ID = UUID("11111111-1111-4111-8111-111111111111")
OPERATION_ID = UUID("22222222-2222-4222-8222-222222222222")
FIXED_NOW = datetime(2026, 8, 30, 18, 0, tzinfo=timezone.utc)


class DeterministicEmbedding:
    async def generate_embedding(self, _text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def get_embedding_dimension(self) -> int:
        return 3


@pytest.mark.asyncio
async def test_real_orchestrator_projects_identical_memory_timestamps(
    tmp_path: Path,
) -> None:
    embedding = DeterministicEmbedding()
    vector = SQLiteVectorStore(
        collection_name="memories",
        persist_directory=str(tmp_path / "vector"),
    )
    vector._embedding_service = embedding
    graph = GraphStore(database_path=str(tmp_path / "kuzu_db"))
    orchestrator = MemoryOrchestrator(
        vector_store=vector,
        graph_store=graph,
        embedding_service=embedding,
    )
    try:
        memory = await orchestrator.add_memory(
            "Decision: Elefante is organized around Remember, Recall, Correct, and Recover.",
            memory_type="decision",
            metadata={
                "project": PROJECT_ID,
                "workspace": WORKSPACE,
                "scope": SCOPE,
                "title": "Four customer actions",
                "summary": "The customer product has four stable actions.",
                "concepts": ["Remember", "Recall", "Correct", "Recover"],
            },
            force_new=True,
            memory_id=MEMORY_ID,
        )
        assert memory is not None
        entity = await graph.get_entity(memory.id)
        assert entity is not None
        assert entity.created_at == memory.metadata.created_at
        assert entity_record_sha256(entity) == entity_record_sha256(
            _expected_entity(memory)
        )
    finally:
        await orchestrator.close()


class FakeStore:
    def __init__(self, memories: list[Memory] | None = None) -> None:
        self.memories = {
            memory.id: memory.model_copy(deep=True) for memory in memories or []
        }
        self.fail_delete = False

    async def add_memory(self, memory: Memory) -> str:
        self.memories[memory.id] = memory.model_copy(deep=True)
        return str(memory.id)

    async def get_memory(self, memory_id: UUID) -> Memory | None:
        memory = self.memories.get(memory_id)
        return memory.model_copy(deep=True) if memory is not None else None

    async def delete_memory(self, memory_id: UUID) -> bool:
        if self.fail_delete:
            return False
        return self.memories.pop(memory_id, None) is not None

    async def replace_memory(self, memory: Memory) -> bool:
        self.memories[memory.id] = memory.model_copy(deep=True)
        return True


class FakeGraph:
    def __init__(self) -> None:
        self.entities: dict[UUID, Entity] = {}
        self.concepts: dict[UUID, list[str]] = {}
        self.sources: set[str] = set()
        self.source_links: dict[str, set[UUID]] = {}

    @staticmethod
    def source_id_for(source: dict) -> str:
        return GraphStore.source_id_for(source)

    async def source_exists(self, source_id: str) -> bool:
        return source_id in self.sources

    async def record_memory_source(self, memory_id: UUID, source: dict) -> str:
        source_id = self.source_id_for(source)
        self.sources.add(source_id)
        self.source_links.setdefault(source_id, set()).add(memory_id)
        return source_id

    async def delete_source_if_orphan(self, source_id: str) -> bool:
        if self.source_links.get(source_id):
            return False
        self.sources.discard(source_id)
        return True

    async def get_entity(self, memory_id: UUID) -> Entity | None:
        entity = self.entities.get(memory_id)
        return entity.model_copy(deep=True) if entity is not None else None

    async def get_memory_concepts(self, memory_id: UUID) -> list[str]:
        return list(self.concepts.get(memory_id, []))

    async def delete_entity(self, memory_id: UUID) -> bool:
        self.entities.pop(memory_id, None)
        self.concepts.pop(memory_id, None)
        for linked in self.source_links.values():
            linked.discard(memory_id)
        return True


def _memory(
    content: str,
    *,
    memory_id: UUID,
    memory_type: MemoryType = MemoryType.DECISION,
) -> Memory:
    return Memory(
        id=memory_id,
        content=content,
        metadata=MemoryMetadata(
            memory_type=memory_type,
            status=MemoryStatus.NEW,
            project=PROJECT_ID,
            workspace=WORKSPACE,
            scope=SCOPE,
            concepts=["sqlite", "project", "index"],
            custom_metadata={
                "title": "SQLite project index",
                "summary": "Use SQLite for the project index.",
                "processing_status": "raw",
            },
        ),
    )


class FakeOrchestrator:
    def __init__(self, overlaps: list[SearchResult] | None = None) -> None:
        self.vector_store = FakeStore(
            [result.memory for result in (overlaps or [])]
        )
        self.graph_store = FakeGraph()
        self.overlaps = list(overlaps or [])
        self.add_calls = 0

    async def search_memories(self, **_kwargs) -> list[SearchResult]:
        return list(self.overlaps)

    async def add_memory(
        self,
        *,
        content: str,
        memory_type: str,
        tags: list[str],
        entities: list[dict[str, str]],
        metadata: dict,
        force_new: bool,
        memory_id: UUID,
        conflict_ids: list[UUID] | None = None,
    ) -> Memory:
        assert force_new is True
        assert entities == []
        self.add_calls += 1
        memory = _memory(
            content,
            memory_id=memory_id,
            memory_type=MemoryType(memory_type),
        )
        memory.metadata.tags = list(tags)
        memory.metadata.project = metadata["project"]
        memory.metadata.workspace = metadata["workspace"]
        memory.metadata.scope = metadata["scope"]
        memory.metadata.recall_cues = list(metadata.get("recall_cues") or [])
        memory.metadata.conflict_ids = list(conflict_ids or [])
        if memory.metadata.conflict_ids:
            memory.metadata.status = MemoryStatus.CONTRADICTORY
        memory.metadata.custom_metadata["recall_cues"] = list(
            memory.metadata.recall_cues
        )
        await self.vector_store.add_memory(memory)
        entity = Entity(
            id=memory.id,
            name="SQLite project index",
            type=EntityType.MEMORY,
            description="Use SQLite for the project index.",
            created_at=memory.metadata.created_at,
            properties={
                "content": memory.content[:200],
                "memory_type": memory_type,
                "score": memory.metadata.score,
                "status": str(
                    getattr(
                        memory.metadata.status,
                        "value",
                        memory.metadata.status,
                    )
                ),
                "timestamp": memory.metadata.created_at.isoformat(),
                "processing_status": "raw",
            },
        )
        self.graph_store.entities[memory.id] = entity
        self.graph_store.concepts[memory.id] = list(memory.metadata.concepts)
        await self.graph_store.record_memory_source(
            memory.id,
            metadata["elefante_source"],
        )
        return memory


class Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        overlaps: list[SearchResult] | None = None,
        recall_fails: bool = False,
    ) -> None:
        self.orchestrator = FakeOrchestrator(overlaps)
        self.snapshot_path = tmp_path / "dashboard_snapshot.json"
        write_json_atomically(
            self.snapshot_path,
            {"generated_at": "before", "nodes": [], "edges": []},
        )
        self.before = self.snapshot_path.read_bytes()
        self.recall_fails = recall_fails
        self.received_question: str | None = None

    async def refresh_snapshot(self) -> dict:
        nodes = []
        for memory in self.orchestrator.vector_store.memories.values():
            nodes.append(
                {
                    "id": str(memory.id),
                    "type": "memory",
                    "properties": {
                        "content": memory.content,
                        "project": memory.metadata.project,
                        "workspace": memory.metadata.workspace,
                        "scope": memory.metadata.scope,
                        "memory_type": str(
                            getattr(
                                memory.metadata.memory_type,
                                "value",
                                memory.metadata.memory_type,
                            )
                        ),
                    },
                }
            )
        write_json_atomically(
            self.snapshot_path,
            {"generated_at": "after", "nodes": nodes, "edges": []},
        )
        return {"success": True, "generation_id": "snapshot-after"}

    async def recall(
        self,
        question: str,
        *,
        project: str | None,
        workspace: str | None,
    ) -> list[str] | RecallVerification:
        self.received_question = question
        assert project == PROJECT_ID
        assert workspace == WORKSPACE
        if self.recall_fails:
            return []
        if any(
            memory.metadata.conflict_ids
            for memory in self.orchestrator.vector_store.memories.values()
        ):
            return RecallVerification(selected_ids=(), conflict_count=1)
        return [str(memory_id) for memory_id in self.orchestrator.vector_store.memories]

    def service(self) -> VerifiedRememberService:
        return VerifiedRememberService(
            self.orchestrator,
            snapshot_path=self.snapshot_path,
            refresh_snapshot=self.refresh_snapshot,
            recall_selected_ids=self.recall,
            source_context={
                "tool": "codex",
                "instance_id": "instance",
                "session_id": "session",
                "cwd": WORKSPACE,
                "transport": "stdio",
            },
            now=lambda: FIXED_NOW,
            operation_id=lambda: OPERATION_ID,
            memory_id=lambda: MEMORY_ID,
        )


async def _execute(harness: Harness, **kwargs):
    content = kwargs.pop(
        "content",
        "Decision: use SQLite for the project index.",
    )
    verification_question = kwargs.pop(
        "verification_question",
        "What database should the project index use?",
    )
    return await harness.service().execute(
        content=content,
        knowledge_kind="decision",
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        workspace=WORKSPACE,
        scope=SCOPE,
        verification_question=verification_question,
        metadata={
            "project": PROJECT_ID,
            "workspace": WORKSPACE,
            "scope": SCOPE,
            "elefante_source": {
                "tool": "codex",
                "instance_id": "instance",
                "session_id": "session",
                "cwd": WORKSPACE,
                "transport": "stdio",
            },
        },
        **kwargs,
    )


@pytest.mark.asyncio
async def test_remember_writes_once_and_proves_store_graph_home_and_recall(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path)

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert harness.orchestrator.add_calls == 1
    assert list(harness.orchestrator.vector_store.memories) == [MEMORY_ID]
    assert harness.orchestrator.vector_store.memories[
        MEMORY_ID
    ].metadata.recall_cues == ["What database should the project index use?"]
    assert [check.name for check in result.receipt.checks] == [
        "authoritative_store_and_graph",
        "relationship_projection",
        "dashboard_snapshot",
        "scoped_recall",
    ]
    assert all(check.passed for check in result.receipt.checks)
    assert result.receipt.changed is True
    assert result.to_dict()["remembered"] == {
        "title": "SQLite project index",
        "kind": "decision",
        "project": {"project_id": PROJECT_ID, "name": PROJECT_NAME},
        "recall_verified": True,
    }
    receipt_text = json.dumps(result.receipt.to_dict(), sort_keys=True)
    assert WORKSPACE not in receipt_text
    assert "What database" not in receipt_text


@pytest.mark.asyncio
async def test_material_overlap_stops_without_write_and_offers_customer_choices(
    tmp_path: Path,
) -> None:
    existing = _memory(
        "Decision: use SQLite for the project index.",
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    overlap = SearchResult(memory=existing, score=0.99, source="vector")
    harness = Harness(tmp_path, overlaps=[overlap])

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.plan.reason_code == "REMEMBER_OVERLAP_REQUIRES_CHOICE"
    assert result.plan.choices == ("update", "supersede", "keep_both", "cancel")
    assert result.plan.overlaps[0].relation == "duplicate"
    assert harness.orchestrator.add_calls == 0
    assert result.receipt.changed is False


@pytest.mark.asyncio
async def test_same_project_boilerplate_does_not_create_unrelated_overlap(
    tmp_path: Path,
) -> None:
    existing = _memory(
        (
            "For Customer project onboarding, the dashboard accent must be "
            "copper, not violet."
        ),
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    harness = Harness(
        tmp_path,
        overlaps=[SearchResult(memory=existing, score=0.99, source="vector")],
    )

    result = await _execute(
        harness,
        content=(
            "For Customer project handoff, the required export format must be HTML."
        ),
        verification_question="Which export format is required for Customer project?",
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert result.plan.overlaps == ()
    assert harness.orchestrator.add_calls == 1


@pytest.mark.asyncio
async def test_high_score_related_overlap_requires_shared_substantive_terms(
    tmp_path: Path,
) -> None:
    existing = _memory(
        "For Customer project onboarding, the dashboard accent is copper.",
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    harness = Harness(
        tmp_path,
        overlaps=[SearchResult(memory=existing, score=0.99, source="vector")],
    )

    result = await _execute(
        harness,
        content=(
            "For Customer project onboarding, keep the dashboard accent burnished copper."
        ),
        verification_question="What dashboard accent should Customer project use?",
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.plan.overlaps[0].relation == "related"
    assert harness.orchestrator.add_calls == 0


@pytest.mark.asyncio
async def test_keep_both_requires_exact_fresh_overlap_hashes(tmp_path: Path) -> None:
    existing = _memory(
        "Decision: use SQLite for the project index.",
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    harness = Harness(
        tmp_path,
        overlaps=[SearchResult(memory=existing, score=0.99, source="vector")],
    )

    result = await _execute(
        harness,
        keep_both=True,
        expected_overlap_sha256={str(existing.id): "0" * 64},
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.receipt.error_codes == ("REMEMBER_OVERLAP_PLAN_STALE",)
    assert harness.orchestrator.add_calls == 0


@pytest.mark.asyncio
async def test_keep_both_persists_explicit_contradiction_for_resolve(
    tmp_path: Path,
) -> None:
    existing = _memory(
        "Disposable launch rule: The product launch banner must be blue.",
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    harness = Harness(
        tmp_path,
        overlaps=[SearchResult(memory=existing, score=0.99, source="vector")],
    )

    inspection = await _execute(
        harness,
        content=(
            "Disposable launch rule: The product launch banner must not be blue."
        ),
        verification_question=(
            "Which color is prohibited for the disposable product launch banner?"
        ),
    )
    assert inspection.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert inspection.plan.overlaps[0].relation == "conflict"

    result = await _execute(
        harness,
        content=(
            "Disposable launch rule: The product launch banner must not be blue."
        ),
        verification_question=(
            "Which color is prohibited for the disposable product launch banner?"
        ),
        keep_both=True,
        expected_overlap_sha256={
            str(existing.id): memory_record_sha256(existing),
        },
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    incoming = harness.orchestrator.vector_store.memories[MEMORY_ID]
    peer = harness.orchestrator.vector_store.memories[existing.id]
    assert incoming.metadata.status == MemoryStatus.CONTRADICTORY.value
    assert incoming.metadata.conflict_ids == [existing.id]
    assert peer.metadata.status == MemoryStatus.CONTRADICTORY.value
    assert peer.metadata.conflict_ids == [MEMORY_ID]
    assert any(
        check.name == "conflict_projection" and check.passed
        for check in result.receipt.checks
    )


@pytest.mark.asyncio
async def test_conflict_keep_both_rollback_restores_peer(
    tmp_path: Path,
) -> None:
    existing = _memory(
        "Disposable launch rule: The product launch banner must be blue.",
        memory_id=UUID("33333333-3333-4333-8333-333333333333"),
    )
    before_hash = memory_record_sha256(existing)
    harness = Harness(
        tmp_path,
        overlaps=[SearchResult(memory=existing, score=0.99, source="vector")],
        recall_fails=True,
    )

    result = await _execute(
        harness,
        content=(
            "Disposable launch rule: The product launch banner must not be blue."
        ),
        verification_question=(
            "Which color is prohibited for the disposable product launch banner?"
        ),
        keep_both=True,
        expected_overlap_sha256={str(existing.id): before_hash},
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert MEMORY_ID not in harness.orchestrator.vector_store.memories
    restored = harness.orchestrator.vector_store.memories[existing.id]
    assert memory_record_sha256(restored) == before_hash
    assert restored.metadata.conflict_ids == []


@pytest.mark.asyncio
async def test_failed_recall_removes_new_record_and_restores_home_snapshot(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path, recall_fails=True)

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.receipt.rollback == "verified"
    assert result.receipt.changed is False
    assert harness.orchestrator.vector_store.memories == {}
    assert harness.orchestrator.graph_store.entities == {}
    assert harness.snapshot_path.read_bytes() == harness.before
    assert "RECALL_POSTCONDITION_FAILED" in result.receipt.error_codes
    assert result.to_dict()["error"] == (
        "Elefante could not prove this memory would be recalled from that "
        "question. Nothing was saved."
    )


@pytest.mark.asyncio
async def test_incomplete_rollback_is_unsafe_and_never_reports_success(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path, recall_fails=True)
    harness.orchestrator.vector_store.fail_delete = True

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.UNSAFE
    assert result.success is False
    assert result.receipt.rollback == "incomplete"
    assert result.receipt.changed is True
    assert MEMORY_ID in harness.orchestrator.vector_store.memories
    assert "REMEMBER_ROLLBACK_INCOMPLETE" in result.receipt.error_codes
