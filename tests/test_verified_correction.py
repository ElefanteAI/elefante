# TEST    : tests/test_verified_correction.py
# PROVES  : reversible customer corrections bind exact state, verify vector,
#           graph, Home, and scoped Recall, and compensate failed postconditions.
# RUN     : .venv/bin/python -m pytest tests/test_verified_correction.py -q

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import pytest

from src.core.verified_correction import (
    ARCHIVE_RESTORE_POINT_KEY,
    CorrectionAction,
    VerifiedCorrectionService,
)
from src.core.verified_permanent_delete import VerifiedPermanentDeleteService
from src.core.graph_store import GraphStore
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.core.verified_operation import (
    VerifiedOperationStatus,
    entity_record_sha256,
    memory_record_sha256,
)
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType
from src.utils.atomic_json import write_json_atomically


FIXED_NOW = datetime(2026, 8, 29, 16, 0, tzinfo=timezone.utc)


class FakeEmbeddingService:
    async def generate_embedding(self, _text: str) -> list[float]:
        return [1.0, 0.0, 0.0]

    def get_embedding_dimension(self) -> int:
        return 3


def _memory(
    content: str = "Decision: use SQLite for the project index.",
    *,
    memory_id: str = "11111111-1111-4111-8111-111111111111",
    scoped: bool = True,
    protected: bool = False,
) -> Memory:
    return Memory(
        id=UUID(memory_id),
        content=content,
        metadata=MemoryMetadata(
            memory_type=MemoryType.DECISION,
            status=MemoryStatus.VERIFIED,
            verified=True,
            project="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" if scoped else None,
            workspace="/tmp/verified-correction/project" if scoped else None,
            scope="project:aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa" if scoped else None,
            user_locked=protected,
            concepts=["decision", "sqlite", "project", "index"],
            custom_metadata={
                "title": "SQLite project index",
                "summary": "Use SQLite for the project index.",
                "processing_status": "processed",
            },
        ),
    )


def _entity(memory: Memory) -> Entity:
    return Entity(
        id=memory.id,
        name=str(memory.metadata.custom_metadata.get("title") or "Memory"),
        type=EntityType.MEMORY,
        description=str(memory.metadata.summary or ""),
        created_at=memory.metadata.created_at,
        properties={
            "content": memory.content[:200],
            "memory_type": str(memory.metadata.memory_type),
            "score": memory.metadata.score,
            "status": str(memory.metadata.status),
            "timestamp": memory.metadata.created_at.isoformat(),
            "processing_status": "processed",
            "archived": memory.metadata.archived,
            "deprecated": memory.metadata.deprecated,
            "version": memory.metadata.version,
        },
    )


class FakeVectorStore:
    def __init__(self, memories: list[Memory]) -> None:
        self.memories = {memory.id: memory.model_copy(deep=True) for memory in memories}
        self.replace_calls = 0
        self.fail_replace_calls: set[int] = set()

    async def get_memory(self, memory_id: UUID) -> Memory | None:
        value = self.memories.get(memory_id)
        return value.model_copy(deep=True) if value is not None else None

    async def replace_memory(self, memory: Memory) -> bool:
        self.replace_calls += 1
        if self.replace_calls in self.fail_replace_calls:
            return False
        self.memories[memory.id] = memory.model_copy(deep=True)
        return True

    async def add_memory(self, memory: Memory) -> str:
        if memory.id in self.memories:
            raise ValueError("duplicate")
        self.memories[memory.id] = memory.model_copy(deep=True)
        return str(memory.id)

    async def delete_memory(self, memory_id: UUID) -> bool:
        return self.memories.pop(memory_id, None) is not None

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        values = [
            memory.model_copy(deep=True)
            for memory in self.memories.values()
        ]
        return values[offset:offset + limit]


class FakeGraphStore:
    def __init__(
        self,
        entities: list[Entity],
        memory_concepts: dict[UUID, list[str]] | None = None,
    ) -> None:
        self.entities = {entity.id: entity.model_copy(deep=True) for entity in entities}
        self.memory_concepts = {
            memory_id: tuple(sorted(concepts))
            for memory_id, concepts in (memory_concepts or {}).items()
        }
        self.sources: set[str] = set()
        self.source_links: dict[str, set[UUID]] = {}
        self.replace_calls = 0
        self.fail_replace_calls: set[int] = set()
        self.concept_replace_calls = 0
        self.fail_concept_replace_calls: set[int] = set()

    async def get_entity(self, entity_id: UUID) -> Entity | None:
        value = self.entities.get(entity_id)
        return value.model_copy(deep=True) if value is not None else None

    async def replace_entity(self, entity: Entity) -> bool:
        self.replace_calls += 1
        if self.replace_calls in self.fail_replace_calls:
            return False
        self.entities[entity.id] = entity.model_copy(deep=True)
        return True

    async def get_memory_concepts(self, memory_id: UUID) -> list[str]:
        return list(self.memory_concepts.get(memory_id, ()))

    async def replace_memory_concepts(
        self,
        memory_id: UUID,
        concepts: list[str],
    ) -> list[str]:
        self.concept_replace_calls += 1
        if self.concept_replace_calls in self.fail_concept_replace_calls:
            raise RuntimeError("forced concept projection failure")
        if memory_id not in self.entities:
            raise RuntimeError("memory entity unavailable")
        projected = tuple(sorted(dict.fromkeys(concepts)))
        self.memory_concepts[memory_id] = projected
        return list(projected)

    async def create_entity(self, entity: Entity) -> UUID:
        if entity.id in self.entities:
            raise ValueError("duplicate")
        self.entities[entity.id] = entity.model_copy(deep=True)
        return entity.id

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
        self.source_links.pop(source_id, None)
        return True

    async def delete_entity(self, entity_id: UUID) -> bool:
        self.entities.pop(entity_id, None)
        self.memory_concepts.pop(entity_id, None)
        for linked_ids in self.source_links.values():
            linked_ids.discard(entity_id)
        return True


class Harness:
    def __init__(
        self,
        tmp_path: Path,
        memory: Memory,
        *,
        recall_fails: bool = False,
        replacement_id: str = "22222222-2222-4222-8222-222222222222",
    ) -> None:
        self.store = FakeVectorStore([memory])
        self.graph = FakeGraphStore(
            [_entity(memory)],
            {memory.id: list(memory.metadata.concepts)},
        )
        self.snapshot_path = tmp_path / "dashboard_snapshot.json"
        self.refresh_count = 0
        self.recall_fails = recall_fails
        self.replacement_id = UUID(replacement_id)
        self.refresh_snapshot_sync()
        self.service = VerifiedCorrectionService(
            self.store,
            self.graph,
            snapshot_path=self.snapshot_path,
            refresh_snapshot=self.refresh_snapshot,
            recall_selected_ids=self.recall_selected_ids,
            source_context={"tool": "pytest", "instance_id": "test"},
            verification_attempts=2,
            now=lambda: FIXED_NOW,
            operation_id=lambda: UUID("33333333-3333-4333-8333-333333333333"),
            replacement_id=lambda: self.replacement_id,
        )

    def refresh_snapshot_sync(self) -> None:
        self.refresh_count += 1
        nodes = []
        for memory in self.store.memories.values():
            nodes.append(
                {
                    "id": str(memory.id),
                    "type": "memory",
                    "name": str(memory.metadata.custom_metadata.get("title") or "Memory"),
                    "properties": {
                        "content": memory.content,
                        "status": str(memory.metadata.status),
                        "archived": bool(memory.metadata.archived),
                        "deprecated": bool(memory.metadata.deprecated),
                        "supersedes_id": (
                            str(memory.metadata.supersedes_id)
                            if memory.metadata.supersedes_id
                            else ""
                        ),
                        "superseded_by_id": (
                            str(memory.metadata.superseded_by_id)
                            if memory.metadata.superseded_by_id
                            else ""
                        ),
                        "version": max(1, int(memory.metadata.version)),
                    },
                }
            )
        write_json_atomically(
            self.snapshot_path,
            {
                "generated_at": f"2026-08-29T16:00:{self.refresh_count:02d}Z",
                "nodes": nodes,
                "edges": [],
                "stats": {
                    "total_nodes": len(nodes),
                    "memories": len(nodes),
                    "entities": 0,
                    "edges": 0,
                },
            },
        )

    async def refresh_snapshot(self) -> dict[str, bool]:
        self.refresh_snapshot_sync()
        return {"success": True}

    async def recall_selected_ids(
        self,
        _question: str,
        *,
        project: str | None,
        workspace: str | None,
    ) -> list[str]:
        assert project == "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
        assert workspace == "/tmp/verified-correction/project"
        if self.recall_fails:
            return []
        return [
            str(memory.id)
            for memory in self.store.memories.values()
            if not memory.metadata.archived
            and not memory.metadata.deprecated
            and not memory.metadata.superseded_by_id
        ]


async def _plan_and_execute(
    harness: Harness,
    memory: Memory,
    *,
    action: CorrectionAction,
    content: str | None = None,
    confirm_protected: bool = False,
):
    plan = await harness.service.plan(
        memory.id,
        action=action,
        content=content,
        confirm_protected=confirm_protected,
    )
    assert plan.applicable, plan
    result = await harness.service.execute(
        memory.id,
        action=action,
        content=content,
        reason=f"User requested {action.value}",
        verification_question="What project index decision applies?",
        confirm_protected=confirm_protected,
        expected_record_sha256=plan.record_sha256,
        expected_graph_sha256=plan.graph_sha256,
        expected_content_sha256=plan.content_sha256,
    )
    return plan, result


@pytest.mark.asyncio
async def test_edit_verifies_memory_graph_snapshot_and_scoped_recall(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)
    new_content = "Decision: use SQLite WAL mode for the project index."

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.EDIT,
        content=new_content,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    current = await harness.store.get_memory(memory.id)
    assert current is not None
    assert current.id == memory.id
    assert current.content == new_content
    assert current.metadata.version == 2
    graph = await harness.graph.get_entity(memory.id)
    assert graph is not None
    assert graph.properties["content"] == new_content[:200]
    assert graph.properties["processing_status"] == "processed"
    assert graph.properties["relationship_projection_status"] == "deterministic_concepts"
    assert await harness.graph.get_memory_concepts(memory.id) == [
        "decision",
        "mode",
        "project",
        "sqlite",
        "wal",
    ]
    assert [check.name for check in result.receipt.checks] == [
        "authoritative_store_and_graph",
        "relationship_projection",
        "dashboard_snapshot",
        "scoped_recall",
    ]


@pytest.mark.asyncio
async def test_failed_edit_recall_restores_exact_memory_graph_and_snapshot(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory, recall_fails=True)
    memory_before = memory_record_sha256(memory)
    graph_before = entity_record_sha256(_entity(memory))
    snapshot_before = harness.snapshot_path.read_bytes()

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.EDIT,
        content="Decision: use PostgreSQL for the project index.",
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    current = await harness.store.get_memory(memory.id)
    graph = await harness.graph.get_entity(memory.id)
    assert current is not None and memory_record_sha256(current) == memory_before
    assert graph is not None and entity_record_sha256(graph) == graph_before
    assert await harness.graph.get_memory_concepts(memory.id) == [
        "decision",
        "index",
        "project",
        "sqlite",
    ]
    assert harness.snapshot_path.read_bytes() == snapshot_before
    assert result.receipt.rollback == "verified"


@pytest.mark.asyncio
async def test_archive_and_restore_are_verified_and_preserve_restore_point(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)

    _, archived_result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.ARCHIVE,
    )
    assert archived_result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    archived = await harness.store.get_memory(memory.id)
    assert archived is not None
    assert archived.metadata.archived is True
    assert archived.metadata.deprecated is True
    assert ARCHIVE_RESTORE_POINT_KEY in archived.metadata.custom_metadata

    _, restored_result = await _plan_and_execute(
        harness,
        archived,
        action=CorrectionAction.RESTORE,
    )
    assert restored_result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    restored = await harness.store.get_memory(memory.id)
    assert restored is not None
    assert restored.metadata.archived is False
    assert restored.metadata.deprecated is False
    assert restored.metadata.status == MemoryStatus.VERIFIED
    assert ARCHIVE_RESTORE_POINT_KEY not in restored.metadata.custom_metadata


@pytest.mark.asyncio
async def test_replace_preserves_old_assertion_and_verifies_new_memory(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.REPLACE,
        content="Decision: use PostgreSQL for the project index.",
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    old = await harness.store.get_memory(memory.id)
    replacement = await harness.store.get_memory(harness.replacement_id)
    assert old is not None and replacement is not None
    assert old.content == memory.content
    assert old.metadata.archived is True
    assert old.metadata.superseded_by_id == replacement.id
    assert replacement.metadata.supersedes_id == old.id
    assert replacement.content.startswith("Decision: use PostgreSQL")
    assert replacement.metadata.access_count == 0
    assert replacement.metadata.custom_metadata["elefante_source"]["tool"] == "pytest"
    assert await harness.graph.get_entity(replacement.id) is not None
    assert await harness.graph.get_memory_concepts(replacement.id) == [
        "decision",
        "index",
        "postgresql",
        "project",
    ]
    assert result.receipt.memory_ids["replacement"] == str(replacement.id)


@pytest.mark.asyncio
async def test_replace_failure_removes_new_record_and_restores_old_pair(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory, recall_fails=True)
    memory_before = memory_record_sha256(memory)
    graph_before = entity_record_sha256(_entity(memory))
    snapshot_before = harness.snapshot_path.read_bytes()

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.REPLACE,
        content="Decision: use PostgreSQL for the project index.",
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    old = await harness.store.get_memory(memory.id)
    old_graph = await harness.graph.get_entity(memory.id)
    assert old is not None and memory_record_sha256(old) == memory_before
    assert old_graph is not None and entity_record_sha256(old_graph) == graph_before
    assert await harness.store.get_memory(harness.replacement_id) is None
    assert await harness.graph.get_entity(harness.replacement_id) is None
    assert await harness.graph.get_memory_concepts(harness.replacement_id) == []
    assert harness.graph.sources == set()
    assert harness.snapshot_path.read_bytes() == snapshot_before


@pytest.mark.asyncio
async def test_incomplete_graph_rollback_is_unsafe(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory, recall_fails=True)
    harness.graph.fail_replace_calls = {2}

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.EDIT,
        content="Decision: use PostgreSQL for the project index.",
    )

    assert result.status is VerifiedOperationStatus.UNSAFE
    assert result.receipt.changed is True
    assert "ROLLBACK_INCOMPLETE" in result.receipt.error_codes


@pytest.mark.asyncio
async def test_relationship_mining_failure_restores_content_graph_and_connections(
    tmp_path: Path,
) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)
    harness.graph.fail_concept_replace_calls = {1}
    memory_before = memory_record_sha256(memory)
    graph_before = entity_record_sha256(_entity(memory))

    _, result = await _plan_and_execute(
        harness,
        memory,
        action=CorrectionAction.EDIT,
        content="Decision: use PostgreSQL for the project index.",
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    current = await harness.store.get_memory(memory.id)
    graph = await harness.graph.get_entity(memory.id)
    assert current is not None and memory_record_sha256(current) == memory_before
    assert graph is not None and entity_record_sha256(graph) == graph_before
    assert await harness.graph.get_memory_concepts(memory.id) == [
        "decision",
        "index",
        "project",
        "sqlite",
    ]
    assert result.receipt.error_codes == ("RELATIONSHIP_MINING_FAILED",)


@pytest.mark.asyncio
async def test_plan_blocks_unscoped_and_protected_but_previews_backup_bound_delete(
    tmp_path: Path,
) -> None:
    unscoped = _memory(scoped=False)
    unscoped_harness = Harness(tmp_path / "unscoped", unscoped)
    unscoped_plan = await unscoped_harness.service.plan(
        unscoped.id,
        action=CorrectionAction.EDIT,
        content="Decision: change this.",
    )
    assert unscoped_plan.applicable is False
    assert unscoped_plan.reason_code == "DECLARED_SCOPE_REQUIRED"

    protected = _memory(protected=True)
    protected_harness = Harness(tmp_path / "protected", protected)
    protected_plan = await protected_harness.service.plan(
        protected.id,
        action=CorrectionAction.ARCHIVE,
    )
    assert protected_plan.applicable is False
    assert protected_plan.reason_code == "PROTECTED_CONFIRMATION_REQUIRED"
    confirmed = await protected_harness.service.plan(
        protected.id,
        action=CorrectionAction.ARCHIVE,
        confirm_protected=True,
    )
    assert confirmed.applicable is True

    delete_plan = await protected_harness.service.plan(
        protected.id,
        action=CorrectionAction.PERMANENT_DELETE,
        confirm_protected=True,
    )
    assert delete_plan.applicable is True
    assert delete_plan.irreversible is True
    assert "fresh local backup" in delete_plan.reason
    assert unscoped_harness.store.replace_calls == 0
    assert protected_harness.store.replace_calls == 0


@pytest.mark.asyncio
async def test_stale_plan_and_receipt_privacy(tmp_path: Path) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)
    secret_content = "Decision: use SQLite WAL mode and private marker cactus-lantern."
    plan = await harness.service.plan(
        memory.id,
        action=CorrectionAction.EDIT,
        content=secret_content,
    )
    result = await harness.service.execute(
        memory.id,
        action=CorrectionAction.EDIT,
        content=secret_content,
        reason="private reason river-otter",
        verification_question="private question moon-glass",
        expected_record_sha256={"target": "0" * 64},
        expected_graph_sha256=plan.graph_sha256,
        expected_content_sha256=plan.content_sha256,
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert harness.store.replace_calls == 0
    rendered = str(result.receipt.to_dict())
    assert "cactus-lantern" not in rendered
    assert "river-otter" not in rendered
    assert "moon-glass" not in rendered


def test_graph_store_projection_contract_uses_persisted_props_field() -> None:
    from src.core.graph_store import GraphStore

    source = Path(GraphStore.__module__.replace(".", "/"))
    assert source.parts[-1] == "graph_store"
    graph_source = Path("src/core/graph_store.py").read_text(encoding="utf-8")
    assert "e.props" in graph_source
    assert "async def replace_entity" in graph_source


@pytest.mark.asyncio
async def test_edit_round_trips_real_sqlite_kuzu_and_preserves_relationships(
    tmp_path: Path,
) -> None:
    memory = _memory()
    vector_store = SQLiteVectorStore(
        collection_name="verified_correction",
        persist_directory=str(tmp_path / "vectors"),
    )
    vector_store._embedding_service = FakeEmbeddingService()
    graph_store = GraphStore(database_path=str(tmp_path / "graph.kuzu"))
    snapshot_path = tmp_path / "dashboard_snapshot.json"
    recall_fails = False
    related = Entity(
        id=UUID("44444444-4444-4444-8444-444444444444"),
        name="Project index",
        type=EntityType.PROJECT,
    )

    async def refresh_snapshot() -> dict[str, bool]:
        memories = await vector_store.get_all(limit=100)
        nodes = [
            {
                "id": str(item.id),
                "type": "memory",
                "name": str(item.metadata.custom_metadata.get("title") or "Memory"),
                "properties": {
                    "content": item.content,
                    "status": str(item.metadata.status),
                    "archived": bool(item.metadata.archived),
                    "deprecated": bool(item.metadata.deprecated),
                    "supersedes_id": (
                        str(item.metadata.supersedes_id)
                        if item.metadata.supersedes_id
                        else ""
                    ),
                    "superseded_by_id": (
                        str(item.metadata.superseded_by_id)
                        if item.metadata.superseded_by_id
                        else ""
                    ),
                    "version": max(1, int(item.metadata.version)),
                },
            }
            for item in memories
        ]
        write_json_atomically(
            snapshot_path,
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "nodes": nodes,
                "edges": [],
                "stats": {"total_nodes": len(nodes)},
            },
        )
        return {"success": True}

    async def recall_selected_ids(
        _question: str,
        *,
        project: str | None,
        workspace: str | None,
    ) -> list[str]:
        if recall_fails:
            return []
        return [
            str(item.id)
            for item in await vector_store.get_all(limit=100)
            if item.metadata.project == project
            and item.metadata.workspace == workspace
            and not item.metadata.archived
            and not item.metadata.deprecated
            and not item.metadata.superseded_by_id
        ]

    try:
        await vector_store.add_memory(memory)
        await graph_store.create_entity(_entity(memory))
        await graph_store.replace_memory_concepts(
            memory.id,
            list(memory.metadata.concepts),
        )
        await graph_store.create_entity(related)
        await graph_store.create_relationship(
            Relationship(
                from_entity_id=memory.id,
                to_entity_id=related.id,
                relationship_type=RelationshipType.RELATES_TO,
            )
        )
        await refresh_snapshot()
        service = VerifiedCorrectionService(
            vector_store,
            graph_store,
            snapshot_path=snapshot_path,
            refresh_snapshot=refresh_snapshot,
            recall_selected_ids=recall_selected_ids,
            source_context={"tool": "pytest", "instance_id": "integration"},
            now=lambda: FIXED_NOW,
            operation_id=lambda: UUID("33333333-3333-4333-8333-333333333333"),
        )
        content = "Decision: use SQLite WAL mode for the project index."
        plan = await service.plan(memory.id, action=CorrectionAction.EDIT, content=content)
        result = await service.execute(
            memory.id,
            action=CorrectionAction.EDIT,
            content=content,
            reason="User corrected the project index decision.",
            verification_question="What project index decision applies?",
            expected_record_sha256=plan.record_sha256,
            expected_graph_sha256=plan.graph_sha256,
            expected_content_sha256=plan.content_sha256,
        )

        persisted = await vector_store.get_memory(memory.id)
        projected = await graph_store.get_entity(memory.id)
        relationships = await graph_store.get_relationships(memory.id, "outgoing")
        concepts = await graph_store.get_memory_concepts(memory.id)
        assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
        assert persisted is not None and persisted.content == content
        assert projected is not None and projected.properties["content"] == content[:200]
        assert any(item.to_entity_id == related.id for item in relationships)
        assert concepts == ["decision", "mode", "project", "sqlite", "wal"]

        recall_fails = True
        replace_content = "Decision: use PostgreSQL for the project index."
        replace_plan = await service.plan(
            memory.id,
            action=CorrectionAction.REPLACE,
            content=replace_content,
        )
        failed_replace = await service.execute(
            memory.id,
            action=CorrectionAction.REPLACE,
            content=replace_content,
            reason="User replaced the project index decision.",
            verification_question="What project index decision applies?",
            expected_record_sha256=replace_plan.record_sha256,
            expected_graph_sha256=replace_plan.graph_sha256,
            expected_content_sha256=replace_plan.content_sha256,
        )
        sources = await graph_store.execute_query("MATCH (s:Source) RETURN s.id")
        rolled_back = await vector_store.get_memory(memory.id)
        concepts_after_rollback = await graph_store.get_memory_concepts(memory.id)
        all_concepts = await graph_store.get_all_concepts()
        assert failed_replace.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
        assert rolled_back is not None and rolled_back.content == content
        assert sources == []
        assert concepts_after_rollback == concepts
        assert all(item["canonical_name"] != "postgresql" for item in all_concepts)
    finally:
        vector_store.close()
        graph_store.close()


def _backup_receipt() -> dict:
    return {
        "operation_id": "55555555-5555-4555-8555-555555555555",
        "operation": "backup",
        "status": "VERIFIED_COMPLETE",
        "authority": "workflow_managed",
        "recoverable": True,
        "archive_name": "elefante_backup_verified.zip",
        "archive_sha256": "a" * 64,
        "source_sha256": "b" * 64,
        "checks": [
            {"name": "archive_readback", "passed": True},
            {"name": "staged_restore", "passed": True},
            {"name": "sqlite_integrity", "passed": True},
            {"name": "kuzu_integrity", "passed": True},
        ],
    }


@pytest.mark.asyncio
async def test_permanent_delete_requires_backup_then_removes_exact_memory_and_attachment(
    tmp_path: Path,
) -> None:
    memory = _memory()
    attachment_payload = b"private attachment"
    attachment_sha256 = __import__("hashlib").sha256(attachment_payload).hexdigest()
    attachment_path = (
        tmp_path
        / "attachments"
        / attachment_sha256[:2]
        / f"{attachment_sha256}.png"
    )
    attachment_path.parent.mkdir(parents=True)
    attachment_path.write_bytes(attachment_payload)
    memory.metadata.custom_metadata["attachments"] = [
        {
            "sha256": attachment_sha256,
            "storage_path": (
                Path("attachments")
                / attachment_sha256[:2]
                / f"{attachment_sha256}.png"
            ).as_posix(),
        }
    ]
    harness = Harness(tmp_path, memory)
    restore_calls: list[tuple[str, str, str]] = []
    discarded: list[tuple[str, str, str]] = []

    async def restore_backup(name: str, digest: str, question: str) -> bool:
        restore_calls.append((name, digest, question))
        return True

    async def discard_backup(name: str, digest: str, operation_id: str) -> bool:
        discarded.append((name, digest, operation_id))
        return True

    async def verify_backup(name: str, digest: str, operation_id: str) -> bool:
        return (name, digest, operation_id) == (
            "elefante_backup_verified.zip",
            "a" * 64,
            "55555555-5555-4555-8555-555555555555",
        )

    service = VerifiedPermanentDeleteService(
        harness.store,
        harness.graph,
        snapshot_path=harness.snapshot_path,
        refresh_snapshot=harness.refresh_snapshot,
        recall_selected_ids=harness.recall_selected_ids,
        attachment_root=tmp_path / "attachments",
        restore_backup=restore_backup,
        verify_backup=verify_backup,
        discard_backup=discard_backup,
        now=lambda: FIXED_NOW,
        operation_id=lambda: UUID("66666666-6666-4666-8666-666666666666"),
    )
    plan = await harness.service.plan(
        memory.id,
        action=CorrectionAction.PERMANENT_DELETE,
    )

    result = await service.execute(
        memory.id,
        plan=plan,
        backup_receipt=_backup_receipt(),
        reason="The user requested permanent removal.",
        verification_question="What project index decision applies?",
        expected_record_sha256=plan.record_sha256,
        expected_graph_sha256=plan.graph_sha256,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert await harness.store.get_memory(memory.id) is None
    assert await harness.graph.get_entity(memory.id) is None
    assert not attachment_path.exists()
    assert restore_calls == []
    assert discarded == [
        (
            "elefante_backup_verified.zip",
            "a" * 64,
            "55555555-5555-4555-8555-555555555555",
        )
    ]
    assert result.receipt.recoverable is False
    assert result.receipt.recovery_archive_name == "elefante_backup_verified.zip"


@pytest.mark.asyncio
async def test_permanent_delete_refuses_missing_backup_before_any_mutation(
    tmp_path: Path,
) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)

    async def restore_backup(_name: str, _digest: str, _question: str) -> bool:
        raise AssertionError("no mutation means restore must not run")

    async def verify_backup(_name: str, _digest: str, _operation_id: str) -> bool:
        return False

    async def discard_backup(_name: str, _digest: str, _operation_id: str) -> bool:
        raise AssertionError("an unverified archive must not be touched")

    service = VerifiedPermanentDeleteService(
        harness.store,
        harness.graph,
        snapshot_path=harness.snapshot_path,
        refresh_snapshot=harness.refresh_snapshot,
        recall_selected_ids=harness.recall_selected_ids,
        attachment_root=tmp_path / "attachments",
        restore_backup=restore_backup,
        verify_backup=verify_backup,
        discard_backup=discard_backup,
        now=lambda: FIXED_NOW,
    )
    plan = await harness.service.plan(
        memory.id,
        action=CorrectionAction.PERMANENT_DELETE,
    )

    result = await service.execute(
        memory.id,
        plan=plan,
        backup_receipt=_backup_receipt(),
        reason="The user requested permanent removal.",
        verification_question="What project index decision applies?",
        expected_record_sha256=plan.record_sha256,
        expected_graph_sha256=plan.graph_sha256,
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.receipt.error_codes == ("RECOVERY_BASELINE_STALE",)
    assert await harness.store.get_memory(memory.id) is not None
    assert await harness.graph.get_entity(memory.id) is not None


@pytest.mark.asyncio
async def test_permanent_delete_failed_recall_restores_verified_backup(
    tmp_path: Path,
) -> None:
    memory = _memory()
    harness = Harness(tmp_path, memory)
    memory_before = memory.model_copy(deep=True)
    entity_before = _entity(memory)
    concepts_before = list(memory.metadata.concepts)
    restored: list[str] = []

    async def stale_recall(
        _question: str,
        *,
        project: str | None,
        workspace: str | None,
    ) -> list[str]:
        assert project == memory.metadata.project
        assert workspace == memory.metadata.workspace
        return [str(memory.id)]

    async def restore_backup(name: str, _digest: str, _question: str) -> bool:
        restored.append(name)
        harness.store.memories[memory.id] = memory_before.model_copy(deep=True)
        harness.graph.entities[memory.id] = entity_before.model_copy(deep=True)
        harness.graph.memory_concepts[memory.id] = tuple(sorted(concepts_before))
        harness.refresh_snapshot_sync()
        return True

    async def discard_backup(_name: str, _digest: str, _operation_id: str) -> bool:
        raise AssertionError("failed deletion must preserve its rollback backup")

    async def verify_backup(_name: str, _digest: str, _operation_id: str) -> bool:
        return True

    service = VerifiedPermanentDeleteService(
        harness.store,
        harness.graph,
        snapshot_path=harness.snapshot_path,
        refresh_snapshot=harness.refresh_snapshot,
        recall_selected_ids=stale_recall,
        attachment_root=tmp_path / "attachments",
        restore_backup=restore_backup,
        verify_backup=verify_backup,
        discard_backup=discard_backup,
        now=lambda: FIXED_NOW,
    )
    plan = await harness.service.plan(
        memory.id,
        action=CorrectionAction.PERMANENT_DELETE,
    )
    result = await service.execute(
        memory.id,
        plan=plan,
        backup_receipt=_backup_receipt(),
        reason="The user requested permanent removal.",
        verification_question="What project index decision applies?",
        expected_record_sha256=plan.record_sha256,
        expected_graph_sha256=plan.graph_sha256,
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert restored == ["elefante_backup_verified.zip"]
    assert await harness.store.get_memory(memory.id) is not None
    assert result.receipt.rollback == "verified"
