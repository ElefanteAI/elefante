# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_verified_resolve.py
# PROVES  : Resolve is complete only after store, snapshot, and scoped Recall
#           agree; failed verification restores the exact prior records.
# RUN     : pytest tests/test_verified_resolve.py -v
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from contextlib import asynccontextmanager
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from src.core.verified_resolve import (
    VerifiedResolveService,
    VerifiedResolveStatus,
    memory_record_sha256,
)
from src.models.memory import Memory, MemoryMetadata, MemoryStatus
from src.models.query import SearchResult


def _memory(content: str, **metadata: Any) -> Memory:
    return Memory(content=content, metadata=MemoryMetadata(**metadata))


class _Store:
    def __init__(
        self,
        *memories: Memory,
        fail_on_replace: set[int] | None = None,
        fail_after_replace: set[int] | None = None,
    ) -> None:
        self.memories = {
            memory.id: memory.model_copy(deep=True) for memory in memories
        }
        self.replace_count = 0
        self.fail_on_replace = fail_on_replace or set()
        self.fail_after_replace = fail_after_replace or set()

    async def get_memory(self, memory_id):
        memory = self.memories.get(memory_id)
        return memory.model_copy(deep=True) if memory else None

    async def replace_memory(self, memory):
        self.replace_count += 1
        if self.replace_count in self.fail_on_replace:
            return False
        self.memories[memory.id] = memory.model_copy(deep=True)
        if self.replace_count in self.fail_after_replace:
            return False
        return True


def _snapshot_node(memory: Memory) -> dict[str, Any]:
    status = getattr(memory.metadata.status, "value", memory.metadata.status)
    return {
        "id": str(memory.id),
        "type": "memory",
        "properties": {
            "status": str(status),
            "archived": memory.metadata.archived,
            "deprecated": memory.metadata.deprecated,
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
        },
    }


def _write_snapshot(path: Path, store: _Store, generation: int) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "generated_at": f"2026-08-29T18:00:{generation:02d}+00:00",
                "nodes": [
                    _snapshot_node(memory) for memory in store.memories.values()
                ],
                "edges": [],
            }
        ),
        encoding="utf-8",
    )


@pytest.mark.asyncio
async def test_plan_requires_one_exact_declared_scope_without_mutating(tmp_path):
    left = _memory("The feature is enabled.")
    right = _memory("The feature is disabled.")
    store = _Store(left, right)

    async def unused_refresh():
        raise AssertionError("Planning must not refresh the dashboard")

    async def unused_recall(*_args, **_kwargs):
        raise AssertionError("Planning must not call Recall")

    service = VerifiedResolveService(
        store,
        snapshot_path=tmp_path / "dashboard_snapshot.json",
        refresh_snapshot=unused_refresh,
        recall_selected_ids=unused_recall,
    )

    plan = await service.plan(
        left.id,
        right.id,
        winner_memory_id=left.id,
    )

    assert plan.applicable is False
    assert plan.reason_code == "DECLARED_SCOPE_REQUIRED"
    assert set(plan.record_sha256) == {"left", "right"}
    assert store.replace_count == 0


@pytest.mark.asyncio
async def test_verified_resolve_completes_only_after_store_snapshot_and_recall(
    tmp_path,
):
    winner = _memory(
        "Elefante uses the SQLite vector store.",
        project="elefante",
        workspace="workspace-elefante",
        scope="project:elefante",
    )
    loser = _memory(
        "Elefante uses the ChromaDB vector store.",
        project="elefante",
        workspace="workspace-elefante",
        scope="project:elefante",
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    store = _Store(winner, loser)
    snapshot_path = tmp_path / "private" / "dashboard_snapshot.json"
    snapshot_path.parent.mkdir()
    _write_snapshot(snapshot_path, store, 0)
    refresh_count = 0

    async def refresh_snapshot():
        nonlocal refresh_count
        refresh_count += 1
        _write_snapshot(snapshot_path, store, refresh_count)
        return {"success": True}

    async def recall_selected_ids(question, *, project, workspace):
        assert question == "Which vector store does Elefante use?"
        assert project == "elefante"
        assert workspace == "workspace-elefante"
        return [str(winner.id)]

    service = VerifiedResolveService(
        store,
        snapshot_path=snapshot_path,
        refresh_snapshot=refresh_snapshot,
        recall_selected_ids=recall_selected_ids,
    )

    result = await service.execute(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        reason="Current source verifies SQLite.",
        verification_question="Which vector store does Elefante use?",
    )

    assert result.status is VerifiedResolveStatus.VERIFIED_COMPLETE
    assert result.success is True
    assert result.receipt.status is VerifiedResolveStatus.VERIFIED_COMPLETE
    assert result.receipt.rollback == "not_required"
    assert [check.name for check in result.receipt.checks] == [
        "authoritative_store",
        "dashboard_snapshot",
        "scoped_recall",
    ]
    assert all(check.passed for check in result.receipt.checks)
    assert refresh_count == 1

    repaired_winner = store.memories[winner.id]
    repaired_loser = store.memories[loser.id]
    assert repaired_winner.metadata.status == MemoryStatus.VERIFIED.value
    assert repaired_winner.metadata.conflict_ids == []
    assert repaired_loser.metadata.status == MemoryStatus.ARCHIVED.value
    assert repaired_loser.metadata.archived is True
    assert repaired_loser.metadata.deprecated is True
    assert repaired_loser.metadata.superseded_by_id == winner.id

    receipt_text = json.dumps(result.receipt.to_dict(), sort_keys=True)
    for private_value in (
        winner.content,
        loser.content,
        "Current source verifies SQLite.",
        "Which vector store does Elefante use?",
        "elefante",
        "workspace-elefante",
        str(snapshot_path),
    ):
        assert private_value not in receipt_text
    assert result.receipt.record_sha256["winner_after"] == memory_record_sha256(
        repaired_winner
    )
    assert len(receipt_text.encode("utf-8")) < 8192


@pytest.mark.asyncio
async def test_failed_recall_verification_restores_records_and_snapshot(tmp_path):
    winner = _memory(
        "Elefante uses SQLite.",
        project="elefante",
        scope="project:elefante",
    )
    loser = _memory(
        "Elefante uses ChromaDB.",
        project="elefante",
        scope="project:elefante",
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    before = {
        winner.id: memory_record_sha256(winner),
        loser.id: memory_record_sha256(loser),
    }
    store = _Store(winner, loser)
    snapshot_path = tmp_path / "dashboard_snapshot.json"
    _write_snapshot(snapshot_path, store, 0)
    refresh_count = 0

    async def refresh_snapshot():
        nonlocal refresh_count
        refresh_count += 1
        _write_snapshot(snapshot_path, store, refresh_count)
        return {"success": True}

    async def recall_misses_winner(*_args, **_kwargs):
        return []

    service = VerifiedResolveService(
        store,
        snapshot_path=snapshot_path,
        refresh_snapshot=refresh_snapshot,
        recall_selected_ids=recall_misses_winner,
        verification_attempts=1,
    )

    result = await service.execute(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        reason="Current source verifies SQLite.",
        verification_question="Which database does Elefante use?",
    )

    assert result.status is VerifiedResolveStatus.FAILED_ROLLED_BACK
    assert result.success is False
    assert result.receipt.rollback == "verified"
    assert result.receipt.error_codes == ("RECALL_POSTCONDITION_FAILED",)
    assert refresh_count == 2
    assert memory_record_sha256(store.memories[winner.id]) == before[winner.id]
    assert memory_record_sha256(store.memories[loser.id]) == before[loser.id]
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    nodes = {node["id"]: node for node in snapshot["nodes"]}
    assert nodes[str(winner.id)]["properties"]["status"] == MemoryStatus.NEW.value
    assert nodes[str(loser.id)]["properties"]["archived"] is False


@pytest.mark.asyncio
async def test_incomplete_rollback_is_unsafe_and_never_reports_success(tmp_path):
    winner = _memory(
        "Elefante uses SQLite.", project="elefante", scope="project:elefante"
    )
    loser = _memory(
        "Elefante uses ChromaDB.", project="elefante", scope="project:elefante"
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    # Resolve uses writes 1-2. The first compensating write is write 3.
    store = _Store(winner, loser, fail_on_replace={3})
    snapshot_path = tmp_path / "dashboard_snapshot.json"
    _write_snapshot(snapshot_path, store, 0)

    async def refresh_snapshot():
        _write_snapshot(snapshot_path, store, store.replace_count)
        return {"success": True}

    async def recall_misses_winner(*_args, **_kwargs):
        return []

    service = VerifiedResolveService(
        store,
        snapshot_path=snapshot_path,
        refresh_snapshot=refresh_snapshot,
        recall_selected_ids=recall_misses_winner,
        verification_attempts=1,
    )

    result = await service.execute(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        reason="Current source verifies SQLite.",
        verification_question="Which database does Elefante use?",
    )

    assert result.status is VerifiedResolveStatus.UNSAFE
    assert result.success is False
    assert result.receipt.rollback == "incomplete"
    assert "ROLLBACK_INCOMPLETE" in result.receipt.error_codes


@pytest.mark.asyncio
async def test_partial_first_write_failure_is_read_back_and_compensated(tmp_path):
    winner = _memory(
        "Elefante uses SQLite.", project="elefante", scope="project:elefante"
    )
    loser = _memory(
        "Elefante uses ChromaDB.", project="elefante", scope="project:elefante"
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    before = {
        winner.id: memory_record_sha256(winner),
        loser.id: memory_record_sha256(loser),
    }
    # The adapter mutates the loser but reports failure on write 1.
    store = _Store(winner, loser, fail_after_replace={1})
    snapshot_path = tmp_path / "dashboard_snapshot.json"
    _write_snapshot(snapshot_path, store, 0)
    refresh_count = 0

    async def refresh_snapshot():
        nonlocal refresh_count
        refresh_count += 1
        _write_snapshot(snapshot_path, store, refresh_count)
        return {"success": True}

    async def recall_not_reached(*_args, **_kwargs):
        raise AssertionError("Recall must not run after a write failure")

    service = VerifiedResolveService(
        store,
        snapshot_path=snapshot_path,
        refresh_snapshot=refresh_snapshot,
        recall_selected_ids=recall_not_reached,
        verification_attempts=1,
    )

    result = await service.execute(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        reason="Current source verifies SQLite.",
        verification_question="Which database does Elefante use?",
    )

    assert result.status is VerifiedResolveStatus.FAILED_ROLLED_BACK
    assert result.receipt.rollback == "verified"
    assert result.receipt.changed is False
    assert refresh_count == 1
    assert memory_record_sha256(store.memories[winner.id]) == before[winner.id]
    assert memory_record_sha256(store.memories[loser.id]) == before[loser.id]


@pytest.mark.asyncio
async def test_execute_rejects_a_stale_home_plan_before_any_write(tmp_path):
    winner = _memory(
        "Elefante uses SQLite.", project="elefante", scope="project:elefante"
    )
    loser = _memory(
        "Elefante uses ChromaDB.", project="elefante", scope="project:elefante"
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    store = _Store(winner, loser)

    async def unused_refresh():
        raise AssertionError("A stale plan must not refresh the snapshot")

    async def unused_recall(*_args, **_kwargs):
        raise AssertionError("A stale plan must not call Recall")

    service = VerifiedResolveService(
        store,
        snapshot_path=tmp_path / "dashboard_snapshot.json",
        refresh_snapshot=unused_refresh,
        recall_selected_ids=unused_recall,
    )
    plan = await service.plan(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
    )
    store.memories[loser.id].content = "The memory changed after inspection."

    result = await service.execute(
        winner.id,
        loser.id,
        winner_memory_id=winner.id,
        reason="Current source verifies SQLite.",
        verification_question="Which database does Elefante use?",
        expected_record_sha256=plan.record_sha256,
    )

    assert result.status is VerifiedResolveStatus.NEEDS_HUMAN
    assert result.receipt.error_codes == ("PLAN_STALE",)
    assert result.receipt.changed is False
    assert store.replace_count == 0


@pytest.mark.asyncio
async def test_mcp_resolve_apply_routes_through_verified_operation(
    monkeypatch,
    tmp_path,
):
    from src.mcp.server import ElefanteMCPServer
    from src.utils import config

    winner = _memory(
        "Elefante uses SQLite.",
        project="elefante",
        workspace="workspace-elefante",
        scope="project:elefante",
    )
    loser = _memory(
        "Elefante uses ChromaDB.",
        project="elefante",
        workspace="workspace-elefante",
        scope="project:elefante",
    )
    winner.metadata.conflict_ids = [loser.id]
    loser.metadata.conflict_ids = [winner.id]
    store = _Store(winner, loser)
    snapshot_path = tmp_path / "dashboard_snapshot.json"
    _write_snapshot(snapshot_path, store, 0)
    search_calls = []

    class Orchestrator:
        vector_store = store

        async def search_memories(self, **kwargs):
            search_calls.append(kwargs)
            current = await store.get_memory(winner.id)
            return [SearchResult(memory=current, score=0.99, source="vector")]

    server = ElefanteMCPServer()

    async def get_orchestrator():
        return Orchestrator()

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    refresh_count = 0

    async def refresh_snapshot():
        nonlocal refresh_count
        refresh_count += 1
        _write_snapshot(snapshot_path, store, refresh_count)
        return {"success": True, "generation_id": f"generation-{refresh_count}"}

    async def compile_context(question, results, *, project, workspace, **_kwargs):
        assert question == "Which database does Elefante use?"
        assert project == "elefante"
        assert workspace == "workspace-elefante"
        return SimpleNamespace(selected_memory_ids=(str(winner.id),)), list(results)

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_refresh_dashboard_snapshot", refresh_snapshot)
    monkeypatch.setattr(server, "_compile_validated_answer_context", compile_context)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _tool: None)
    monkeypatch.setattr(server, "_authority_violation", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        config,
        "get_config",
        lambda: SimpleNamespace(elefante=SimpleNamespace(data_dir=str(tmp_path))),
    )

    result = await server._handle_resolve_memory(
        {
            "memory_id": str(winner.id),
            "related_memory_id": str(loser.id),
            "winner_memory_id": str(winner.id),
            "apply": True,
            "reason": "Current source verifies SQLite.",
            "verification_question": "Which database does Elefante use?",
            "invocation_mode": "user_directed",
        }
    )

    assert result["success"] is True
    assert result["resolution_status"] == "VERIFIED_COMPLETE"
    assert result["receipt"]["status"] == "VERIFIED_COMPLETE"
    assert refresh_count == 1
    assert search_calls[0]["reinforce_access"] is False
    assert search_calls[0]["apply_temporal_decay"] is False
    assert search_calls[0]["filters"].project == "elefante"
    assert "verification_question" not in json.dumps(result["receipt"])


@pytest.mark.asyncio
async def test_mcp_resolve_rejects_apply_without_disposable_recall_question(
    monkeypatch,
):
    from src.mcp.server import ElefanteMCPServer

    server = ElefanteMCPServer()
    gate_called = False

    def compliance_gate(_tool):
        nonlocal gate_called
        gate_called = True
        return None

    async def forbidden_orchestrator():
        raise AssertionError("Validation must finish before opening durable stores")

    monkeypatch.setattr(server, "_check_compliance_gate", compliance_gate)
    monkeypatch.setattr(server, "_get_orchestrator", forbidden_orchestrator)
    result = await server._handle_resolve_memory(
        {
            "memory_id": str(winner_id := _memory("left").id),
            "related_memory_id": str(_memory("right").id),
            "winner_memory_id": str(winner_id),
            "apply": True,
            "reason": "verified",
            "invocation_mode": "user_directed",
        }
    )

    assert result["success"] is False
    assert result["resolution_status"] == "NEEDS_HUMAN"
    assert result["error_code"] == "VERIFICATION_QUESTION_REQUIRED"
    assert gate_called is False
