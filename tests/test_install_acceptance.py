# TEST    : tests/test_install_acceptance.py
# PROVES  : first-install acceptance writes one private project-scoped record,
#           recalls it through the governed selector, and removes it exactly.
# RUN     : .venv/bin/python -m pytest tests/test_install_acceptance.py -q

from __future__ import annotations

from datetime import datetime, timezone
import json
from uuid import UUID

import pytest

from src.core.install_acceptance import (
    INSTALL_ACCEPTANCE_CATEGORY,
    INSTALL_ACCEPTANCE_CREATED_BY,
    INSTALL_ACCEPTANCE_SCHEMA_VERSION,
    InstallAcceptanceService,
)
from src.core.verified_operation import VerifiedOperationStatus
from src.models.memory import (
    Memory,
    MemoryMetadata,
    RetentionPolicy,
)


FIXED_NOW = datetime(2026, 8, 30, 14, 0, tzinfo=timezone.utc)
PROJECT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
PROJECT_SCOPE = f"project:{PROJECT_ID}"
WORKSPACE = "/private/tmp/elefante-acceptance/customer-project"


class FakeEmbeddingService:
    async def generate_embedding(self, _text: str) -> list[float]:
        return [1.0, 0.0, 0.0]


class FakeVectorStore:
    def __init__(self, memories: list[Memory] | None = None) -> None:
        self.memories = {
            memory.id: memory.model_copy(deep=True) for memory in memories or []
        }
        self.fail_delete_ids: set[UUID] = set()

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        ordered = sorted(self.memories.values(), key=lambda memory: str(memory.id))
        return [
            memory.model_copy(deep=True)
            for memory in ordered[offset : offset + limit]
        ]

    async def get_memory(self, memory_id: UUID) -> Memory | None:
        memory = self.memories.get(memory_id)
        return memory.model_copy(deep=True) if memory is not None else None

    async def add_memory(self, memory: Memory) -> str:
        if memory.id in self.memories:
            raise ValueError("duplicate")
        self.memories[memory.id] = memory.model_copy(deep=True)
        return str(memory.id)

    async def delete_memory(self, memory_id: UUID) -> bool:
        if memory_id in self.fail_delete_ids:
            return False
        return self.memories.pop(memory_id, None) is not None


def _ordinary_memory() -> Memory:
    return Memory(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        content="Keep this customer memory.",
        metadata=MemoryMetadata(
            project=PROJECT_ID,
            workspace=WORKSPACE,
            scope=PROJECT_SCOPE,
        ),
    )


def _stale_acceptance_memory() -> Memory:
    return Memory(
        id=UUID("22222222-2222-4222-8222-222222222222"),
        content="Stale disposable acceptance content.",
        metadata=MemoryMetadata(
            created_by=INSTALL_ACCEPTANCE_CREATED_BY,
            category=INSTALL_ACCEPTANCE_CATEGORY,
            project=PROJECT_ID,
            workspace=WORKSPACE,
            scope=PROJECT_SCOPE,
            retention_policy=RetentionPolicy.EPHEMERAL,
            custom_metadata={
                "install_acceptance_schema_version": (
                    INSTALL_ACCEPTANCE_SCHEMA_VERSION
                )
            },
        ),
    )


def _id_factory():
    values = iter(
        (
            UUID("33333333-3333-4333-8333-333333333333"),
            UUID("44444444-4444-4444-8444-444444444444"),
            UUID("55555555-5555-4555-8555-555555555555"),
        )
    )
    return lambda: next(values)


@pytest.mark.asyncio
async def test_acceptance_recalls_exact_record_then_removes_private_content() -> None:
    ordinary = _ordinary_memory()
    store = FakeVectorStore([ordinary])
    recalled: dict[str, str] = {}

    async def recall(question: str, project_id: str, workspace: str) -> list[str]:
        recalled.update(
            question=question,
            project_id=project_id,
            workspace=workspace,
        )
        acceptance = [
            memory
            for memory in store.memories.values()
            if memory.metadata.created_by == INSTALL_ACCEPTANCE_CREATED_BY
        ]
        assert len(acceptance) == 1
        assert acceptance[0].metadata.scope == PROJECT_SCOPE
        assert acceptance[0].metadata.recall_cues == [question]
        assert acceptance[0].metadata.trigger == [question]
        assert acceptance[0].metadata.source_reliability == 1.0
        return [str(acceptance[0].id)]

    result = await InstallAcceptanceService(
        store,
        FakeEmbeddingService(),
        recall_selected_ids=recall,
        id_factory=_id_factory(),
        now=lambda: FIXED_NOW,
    ).execute(
        project_id=PROJECT_ID,
        project_scope=PROJECT_SCOPE,
        workspace=WORKSPACE,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert list(store.memories) == [ordinary.id]
    assert recalled["project_id"] == PROJECT_ID
    assert recalled["workspace"] == WORKSPACE
    assert "444444444444" in recalled["question"]
    serialized = json.dumps(result.to_dict(), sort_keys=True)
    assert WORKSPACE not in serialized
    assert "The Elefante installation code" not in serialized
    assert result.receipt.next_action == "create_initial_backup"
    assert [check.passed for check in result.receipt.checks] == [True, True, True, True]


@pytest.mark.asyncio
async def test_failed_recall_rolls_back_disposable_record() -> None:
    store = FakeVectorStore()

    async def recall(_question: str, _project_id: str, _workspace: str) -> list[str]:
        return []

    result = await InstallAcceptanceService(
        store,
        FakeEmbeddingService(),
        recall_selected_ids=recall,
        id_factory=_id_factory(),
        now=lambda: FIXED_NOW,
    ).execute(
        project_id=PROJECT_ID,
        project_scope=PROJECT_SCOPE,
        workspace=WORKSPACE,
    )

    assert result.status is VerifiedOperationStatus.FAILED_ROLLED_BACK
    assert result.success is False
    assert store.memories == {}
    assert result.receipt.rollback == "verified_cleanup"
    assert "INSTALL_ACCEPTANCE_RECALL_NOT_VERIFIED" in result.receipt.error_codes


@pytest.mark.asyncio
async def test_failed_cleanup_never_overstates_rollback() -> None:
    store = FakeVectorStore()

    async def recall(_question: str, _project_id: str, _workspace: str) -> list[str]:
        acceptance_id = next(iter(store.memories))
        store.fail_delete_ids.add(acceptance_id)
        return [str(acceptance_id)]

    result = await InstallAcceptanceService(
        store,
        FakeEmbeddingService(),
        recall_selected_ids=recall,
        id_factory=_id_factory(),
        now=lambda: FIXED_NOW,
    ).execute(
        project_id=PROJECT_ID,
        project_scope=PROJECT_SCOPE,
        workspace=WORKSPACE,
    )

    assert result.status is VerifiedOperationStatus.NEEDS_HUMAN
    assert result.receipt.rollback == "incomplete"
    assert result.receipt.recoverable is False
    assert result.receipt.changed is True
    assert len(store.memories) == 1
    assert "INSTALL_ACCEPTANCE_CLEANUP_NOT_VERIFIED" in result.receipt.error_codes


@pytest.mark.asyncio
async def test_retry_cleans_only_stale_installer_acceptance() -> None:
    ordinary = _ordinary_memory()
    stale = _stale_acceptance_memory()
    store = FakeVectorStore([ordinary, stale])

    async def recall(_question: str, _project_id: str, _workspace: str) -> list[str]:
        return [
            str(memory.id)
            for memory in store.memories.values()
            if memory.metadata.created_by == INSTALL_ACCEPTANCE_CREATED_BY
        ]

    result = await InstallAcceptanceService(
        store,
        FakeEmbeddingService(),
        recall_selected_ids=recall,
        id_factory=_id_factory(),
        now=lambda: FIXED_NOW,
    ).execute(
        project_id=PROJECT_ID,
        project_scope=PROJECT_SCOPE,
        workspace=WORKSPACE,
    )

    assert result.status is VerifiedOperationStatus.VERIFIED_COMPLETE
    assert result.receipt.stale_records_removed == 1
    assert list(store.memories) == [ordinary.id]
