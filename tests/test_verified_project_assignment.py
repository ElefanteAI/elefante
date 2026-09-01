# TEST    : tests/test_verified_project_assignment.py
# PROVES  : legacy project review never guesses, binds an exact unscoped
#           preimage, verifies every projection, and restores failed writes.
# RUN     : .venv/bin/python -m pytest tests/test_verified_project_assignment.py -q

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID

import pytest

from src.core.verified_operation import VerifiedOperationStatus
from src.core.verified_project_assignment import VerifiedProjectAssignmentService
from src.models.entity import Entity, EntityType
from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.utils.atomic_json import write_json_atomically


MEMORY_ID = UUID("11111111-1111-4111-8111-111111111111")
PROJECT_ID = "22222222-2222-4222-8222-222222222222"
PROJECT_NAME = "Customer project"
WORKSPACE = "/private/customer/project"
SCOPE = f"project:{PROJECT_ID}"
OPERATION_ID = UUID("33333333-3333-4333-8333-333333333333")
FIXED_NOW = datetime(2026, 8, 30, 20, 0, tzinfo=timezone.utc)


def _memory(*, project: str | None = None, locked: bool = False) -> Memory:
    return Memory(
        id=MEMORY_ID,
        content="Use SQLite for the project index because recovery is local.",
        metadata=MemoryMetadata(
            memory_type=MemoryType.DECISION,
            project=project,
            workspace=None,
            scope=None,
            concepts=["sqlite", "project", "recovery"],
            user_locked=locked,
            custom_metadata={
                "title": "Use SQLite for the project index",
                "summary": "The local project index uses SQLite.",
            },
        ),
    )


def _entity(memory: Memory) -> Entity:
    return Entity(
        id=memory.id,
        name="Use SQLite for the project index",
        type=EntityType.MEMORY,
        description="The local project index uses SQLite.",
        created_at=memory.metadata.created_at,
        properties={"status": "new", "version": 1},
    )


class FakeStore:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory.model_copy(deep=True)
        self.fail_unscoped_replace = False
        self.replace_calls = 0

    async def get_memory(self, memory_id: UUID) -> Memory | None:
        if memory_id != self.memory.id:
            return None
        return self.memory.model_copy(deep=True)

    async def replace_memory(self, memory: Memory) -> bool:
        self.replace_calls += 1
        if self.fail_unscoped_replace and memory.metadata.project is None:
            return False
        self.memory = memory.model_copy(deep=True)
        return True


class FakeGraph:
    def __init__(self, memory: Memory, *, include_entity: bool = True) -> None:
        self.entity = _entity(memory) if include_entity else None
        self.concepts = list(memory.metadata.concepts)

    async def get_entity(self, memory_id: UUID) -> Entity | None:
        if memory_id != MEMORY_ID or self.entity is None:
            return None
        return self.entity.model_copy(deep=True)

    async def get_memory_concepts(self, memory_id: UUID) -> list[str]:
        return list(self.concepts) if memory_id == MEMORY_ID else []

    async def replace_entity(self, entity: Entity) -> bool:
        self.entity = entity.model_copy(deep=True)
        return True

    async def create_entity(self, entity: Entity) -> bool:
        self.entity = entity.model_copy(deep=True)
        return True

    async def delete_entity(self, memory_id: UUID) -> bool:
        if memory_id == MEMORY_ID:
            self.entity = None
        return True


class Harness:
    def __init__(
        self,
        tmp_path: Path,
        *,
        memory: Memory | None = None,
        include_entity: bool = True,
        fail_snapshot: bool = False,
    ) -> None:
        self.store = FakeStore(memory or _memory())
        self.graph = FakeGraph(self.store.memory, include_entity=include_entity)
        if not include_entity:
            self.graph.concepts = []
        self.snapshot_path = tmp_path / "dashboard_snapshot.json"
        write_json_atomically(
            self.snapshot_path,
            {"generated_at": "before", "nodes": [], "edges": []},
        )
        self.snapshot_before = self.snapshot_path.read_bytes()
        self.fail_snapshot = fail_snapshot

    async def refresh_snapshot(self) -> dict:
        memory = self.store.memory
        write_json_atomically(
            self.snapshot_path,
            {
                "generated_at": "after",
                "nodes": [
                    {
                        "id": str(memory.id),
                        "type": "memory",
                        "properties": {
                            "project": (
                                "wrong-project"
                                if self.fail_snapshot
                                else memory.metadata.project
                            ),
                            "workspace": memory.metadata.workspace,
                            "scope": memory.metadata.scope,
                            "version": memory.metadata.version,
                        },
                    }
                ],
                "edges": [],
            },
        )
        return {"success": True}

    async def scoped_ids(
        self,
        *,
        project: str,
        workspace: str,
    ) -> list[str]:
        memory = self.store.memory
        if (
            memory.metadata.project == project
            and memory.metadata.workspace == workspace
        ):
            return [str(memory.id)]
        return []

    def service(self) -> VerifiedProjectAssignmentService:
        return VerifiedProjectAssignmentService(
            self.store,
            self.graph,
            snapshot_path=self.snapshot_path,
            refresh_snapshot=self.refresh_snapshot,
            scoped_memory_ids=self.scoped_ids,
            now=lambda: FIXED_NOW,
            operation_id=lambda: OPERATION_ID,
        )


async def _plan(harness: Harness, *, confirm_protected: bool = False):
    return await harness.service().plan(
        MEMORY_ID,
        project_id=PROJECT_ID,
        project_name=PROJECT_NAME,
        workspace=WORKSPACE,
        scope=SCOPE,
        confirm_protected=confirm_protected,
    )


async def _execute(harness: Harness, *, confirm_protected: bool = False, **overrides):
    plan = await _plan(harness, confirm_protected=confirm_protected)
    arguments = {
        "project_id": PROJECT_ID,
        "project_name": PROJECT_NAME,
        "workspace": WORKSPACE,
        "scope": SCOPE,
        "confirm_protected": confirm_protected,
        "expected_record_sha256": plan.record_sha256 or "",
        "expected_graph_existed": plan.graph_existed,
        "expected_graph_sha256": plan.graph_sha256,
        "expected_relationship_sha256": plan.relationship_sha256 or "",
        "expected_target_scope_sha256": plan.target_scope_sha256 or "",
    }
    arguments.update(overrides)
    return await harness.service().execute(MEMORY_ID, **arguments)


@pytest.mark.asyncio
async def test_assigns_one_unscoped_memory_and_verifies_every_projection(
    tmp_path: Path,
) -> None:
    harness = Harness(tmp_path)

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert harness.store.memory.metadata.project == PROJECT_ID
    assert harness.store.memory.metadata.workspace == WORKSPACE
    assert harness.store.memory.metadata.scope == SCOPE
    assert harness.store.memory.metadata.version == 2
    assert harness.graph.entity is not None
    assert harness.graph.entity.properties["project"] == PROJECT_ID
    assert [check.name for check in result.receipt.checks] == [
        "authoritative_store_and_graph",
        "relationship_projection",
        "dashboard_snapshot",
        "project_filter",
    ]
    assert all(check.passed for check in result.receipt.checks)
    assert result.to_dict()["assigned"]["project"] == {
        "project_id": PROJECT_ID,
        "name": PROJECT_NAME,
    }
    receipt_text = json.dumps(result.receipt.to_dict(), sort_keys=True)
    assert WORKSPACE not in receipt_text
    assert "Use SQLite" not in receipt_text


@pytest.mark.asyncio
async def test_missing_empty_graph_projection_is_created_safely(tmp_path: Path) -> None:
    harness = Harness(tmp_path, include_entity=False)

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert harness.graph.entity is not None
    assert harness.graph.entity.properties["scope"] == SCOPE


@pytest.mark.asyncio
async def test_partial_or_existing_scope_is_never_reassigned(tmp_path: Path) -> None:
    harness = Harness(tmp_path, memory=_memory(project="legacy-project"))

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.plan.reason_code == "LEGACY_UNSCOPED_MEMORY_REQUIRED"
    assert harness.store.replace_calls == 0
    assert harness.store.memory.metadata.project == "legacy-project"


@pytest.mark.asyncio
async def test_protected_memory_requires_explicit_confirmation(tmp_path: Path) -> None:
    harness = Harness(tmp_path, memory=_memory(locked=True))

    blocked = await _execute(harness)
    completed = await _execute(harness, confirm_protected=True)

    assert blocked.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert blocked.plan.reason_code == "PROTECTED_CONFIRMATION_REQUIRED"
    assert completed.status is VerifiedOperationStatus.VERIFIED_COMPLETE


@pytest.mark.asyncio
async def test_stale_plan_stops_without_change(tmp_path: Path) -> None:
    harness = Harness(tmp_path)

    result = await _execute(harness, expected_record_sha256="0" * 64)

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.receipt.error_codes == ("PROJECT_ASSIGNMENT_PLAN_STALE",)
    assert harness.store.replace_calls == 0
    assert harness.store.memory.metadata.project is None


@pytest.mark.asyncio
async def test_failed_snapshot_restores_exact_memory_graph_and_home(tmp_path: Path) -> None:
    harness = Harness(tmp_path, fail_snapshot=True)
    memory_before = harness.store.memory.model_copy(deep=True)
    entity_before = harness.graph.entity.model_copy(deep=True)

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.receipt.rollback == "verified"
    assert result.receipt.changed is False
    assert harness.store.memory == memory_before
    assert harness.graph.entity == entity_before
    assert harness.snapshot_path.read_bytes() == harness.snapshot_before


@pytest.mark.asyncio
async def test_incomplete_rollback_is_unsafe(tmp_path: Path) -> None:
    harness = Harness(tmp_path, fail_snapshot=True)
    harness.store.fail_unscoped_replace = True

    result = await _execute(harness)

    assert result.status is VerifiedOperationStatus.UNSAFE
    assert result.receipt.rollback == "incomplete"
    assert result.receipt.changed is True
    assert "PROJECT_ASSIGNMENT_ROLLBACK_INCOMPLETE" in result.receipt.error_codes
