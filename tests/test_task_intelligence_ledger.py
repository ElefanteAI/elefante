"""Production contracts for Task Intelligence traces, use, and outcomes."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from mcp import types

from src.core.task_intelligence_ledger import (
    TaskIntelligenceLedger,
    TaskIntelligenceLedgerError,
    canonical_digest,
    sha256_text,
)
from src.core.project_registry import ProjectRegistry
from src.mcp.server import ElefanteMCPServer
from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.models.query import SearchResult


PROVENANCE = {
    "tool": "codex",
    "instance_id": "window-a",
    "session_id": "session-a",
    "transport": "streamable-http",
    "cwd": "/repo/elefante",
}


@pytest.mark.asyncio
async def test_task_intelligence_surface_is_default_off_and_explicitly_enabled(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[types.ListToolsRequest]
    request = types.ListToolsRequest(method="tools/list")

    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", raising=False)
    default_result = await handler(request)
    default_names = {tool.name for tool in default_result.root.tools}
    assert "elefante-TaskIntelligence" not in default_names
    assert "elefante-Recall" in default_names
    assert "elefante-Recover" in default_names
    assert len(default_names) == 18

    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    enabled_result = await handler(request)
    enabled_names = {tool.name for tool in enabled_result.root.tools}
    assert "elefante-TaskIntelligence" in enabled_names
    assert "elefante-Recall" in enabled_names
    assert "elefante-Recover" in enabled_names
    assert len(enabled_names) == 19


def _trace(
    ledger: TaskIntelligenceLedger,
    *,
    delivered: list[str],
    now: datetime | None = None,
) -> dict:
    return ledger.create_trace(
        provenance=PROVENANCE,
        invocation_mode="workflow_managed",
        task="Fix the private customer installer failure without exposing secrets",
        success_criteria=["Installer launches"],
        task_id="customer-installer-42",
        project="elefante",
        workspace="/repo/elefante",
        stage="execution",
        profile="v2",
        delivery_mode="pilot" if delivered else "shadow",
        brief_digest=canonical_digest({"selected": delivered}),
        selected_memory_ids=delivered,
        delivered_memory_ids=delivered,
        omission_count=2,
        conflict_count=0,
        abstained=not delivered,
        delivery_blocked=False,
        estimated_tokens=120,
        token_budget=1500,
        now=now,
    )


def test_ledger_stores_hashes_not_task_text_and_enforces_session(tmp_path) -> None:
    path = tmp_path / "task-ledger.sqlite3"
    ledger = TaskIntelligenceLedger(path)
    memory_id = str(uuid4())
    trace = _trace(ledger, delivered=[memory_id])

    connection = sqlite3.connect(path)
    row = connection.execute(
        "SELECT task_sha256, criteria_sha256, task_id_sha256, project_sha256, workspace_sha256 FROM task_traces"
    ).fetchone()
    dump = "\n".join(connection.iterdump())
    connection.close()

    assert all(value and len(value) == 64 for value in row)
    assert "private customer installer" not in dump
    assert "Installer launches" not in dump
    assert "customer-installer-42" not in dump

    wrong_session = {**PROVENANCE, "session_id": "session-b"}
    with pytest.raises(TaskIntelligenceLedgerError, match="different tool instance"):
        ledger.validate_trace(trace["trace_id"], provenance=wrong_session)
    ledger.close()


def test_new_trace_prunes_rows_past_retention_in_long_running_daemon(tmp_path) -> None:
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    current = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    expired = _trace(ledger, delivered=[], now=current - timedelta(days=31))

    _trace(ledger, delivered=[], now=current)

    with pytest.raises(TaskIntelligenceLedgerError, match="Unknown task trace"):
        ledger.inspect(expired["trace_id"], provenance=PROVENANCE, now=current)
    ledger.close()


def test_declared_use_is_subset_bound_idempotent_and_reversible(tmp_path) -> None:
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    delivered_id = str(uuid4())
    trace = _trace(ledger, delivered=[delivered_id])

    with pytest.raises(TaskIntelligenceLedgerError, match="subset delivered"):
        ledger.record_use(
            trace_id=trace["trace_id"],
            provenance=PROVENANCE,
            memory_ids=[str(uuid4())],
            idempotency_key="use-1",
        )
    with pytest.raises(TaskIntelligenceLedgerError, match="at most 256"):
        ledger.record_use(
            trace_id=trace["trace_id"],
            provenance=PROVENANCE,
            memory_ids=[delivered_id],
            idempotency_key="x" * 257,
        )

    first = ledger.record_use(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        memory_ids=[delivered_id],
        idempotency_key="use-1",
    )
    duplicate = ledger.record_use(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        memory_ids=[delivered_id],
        idempotency_key="use-1",
    )
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    assert duplicate["event_id"] == first["event_id"]

    retracted = ledger.retract_use(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        event_id=first["event_id"],
    )
    assert retracted["retracted"] is True
    assert (
        ledger.inspect(trace["trace_id"], provenance=PROVENANCE)["use_events"][0][
            "retracted"
        ]
        is True
    )
    ledger.close()


def test_outcome_is_metadata_only_exactly_idempotent_and_trace_expires(
    tmp_path,
) -> None:
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    created = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
    trace = _trace(ledger, delivered=[], now=created)
    outcome = {
        "status": "succeeded",
        "accepted": True,
        "evidence_source": "test",
        "retries": 0,
        "corrections": 0,
        "duration_ms": 250,
        "input_tokens": 100,
        "output_tokens": 30,
        "failure_category": None,
    }
    first = ledger.record_outcome(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        idempotency_key="outcome-1",
        outcome=outcome,
        now=created + timedelta(minutes=1),
    )
    duplicate = ledger.record_outcome(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        idempotency_key="outcome-1",
        outcome=outcome,
        now=created + timedelta(minutes=2),
    )
    assert first["duplicate"] is False
    assert duplicate["duplicate"] is True
    summary = ledger.summary()
    assert summary["groups"][0]["acceptance_rate"] == 1.0
    assert summary["causal_promotion_evidence"] is False
    retracted = ledger.retract_outcome(
        trace_id=trace["trace_id"],
        provenance=PROVENANCE,
        now=created + timedelta(minutes=3),
    )
    assert retracted["retracted"] is True
    assert (
        ledger.inspect(
            trace["trace_id"], provenance=PROVENANCE, now=created + timedelta(days=2)
        )["outcome"]["retracted"]
        is True
    )

    with pytest.raises(TaskIntelligenceLedgerError, match="expired"):
        ledger.validate_trace(
            trace["trace_id"],
            provenance=PROVENANCE,
            now=created + timedelta(hours=24, minutes=1),
        )
    ledger.close()


class _VectorStore:
    def __init__(self, memory: Memory) -> None:
        self.memory = memory

    async def get_memory(self, memory_id):
        return self.memory if memory_id == self.memory.id else None


class _GraphStore:
    async def get_relationships(self, *_args, **_kwargs):
        return []


class _Orchestrator:
    def __init__(self, result: SearchResult) -> None:
        self.result = result
        self.vector_store = _VectorStore(result.memory)
        self.graph_store = _GraphStore()

    async def search_memories(self, *_args, **kwargs):
        assert kwargs["reinforce_access"] is False
        assert kwargs["apply_temporal_decay"] is False
        return [self.result]


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_server_pilot_closes_prepare_use_outcome_loop_without_ranking_mutation(
    monkeypatch, tmp_path
) -> None:
    memory = Memory(
        content=(
            "Decision: customer installation uses one global runtime for every "
            "compatible IDE."
        ),
        metadata=MemoryMetadata(
            memory_type=MemoryType.DECISION,
            source_reliability=0.9,
            verified=True,
            project="elefante",
            workspace="/repo/elefante",
        ),
    )
    result = SearchResult(
        memory=memory,
        score=0.9,
        vector_score=0.9,
        source="vector",
    )
    server = ElefanteMCPServer()
    server._project_registry = ProjectRegistry(tmp_path / "projects.json")
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setattr(server, "_request_provenance", lambda: dict(PROVENANCE))
    monkeypatch.setattr(
        server, "_get_orchestrator", lambda: _async_value(_Orchestrator(result))
    )
    monkeypatch.setattr(server, "_get_task_intelligence_ledger", lambda: ledger)

    prepared = await server._handle_task_intelligence(
        {
            "action": "prepare",
            "task": "What runtime installation decision applies across compatible IDEs?",
            "success_criteria": ["State the chosen runtime topology"],
            "project": "elefante",
            "workspace": "/repo/elefante",
            "profile": "v2",
            "delivery_mode": "pilot",
        }
    )
    assert prepared["success"] is True
    assert prepared["status"] == "delivered"
    assert prepared["delivered_memory_ids"] == [str(memory.id)]
    assert "one global runtime" in prepared["rendered_context"]

    use = await server._handle_task_intelligence(
        {
            "action": "record_use",
            "trace_id": prepared["trace_id"],
            "memory_ids": [str(memory.id)],
            "idempotency_key": "use-attempt-1",
        }
    )
    assert use["success"] is True
    assert use["recorded_count"] == 1
    assert use["ranking_mutated"] is False
    assert memory.metadata.access_count == 0

    outcome = await server._handle_task_intelligence(
        {
            "action": "record_outcome",
            "trace_id": prepared["trace_id"],
            "idempotency_key": "outcome-attempt-1",
            "status": "succeeded",
            "accepted": True,
            "evidence_source": "test",
            "retries": 0,
            "corrections": 0,
        }
    )
    assert outcome["success"] is True
    inspected = server._handle_task_trace_inspect({"trace_id": prepared["trace_id"]})
    assert inspected["success"] is True
    assert inspected["trace"]["outcome"]["status"] == "succeeded"
    ledger.close()


@pytest.mark.asyncio
async def test_task_intelligence_canonicalizes_registered_workspace_before_selection(
    monkeypatch, tmp_path
) -> None:
    real_workspace = tmp_path / "real-project"
    real_workspace.mkdir()
    alias_workspace = tmp_path / "project-alias"
    alias_workspace.symlink_to(real_workspace, target_is_directory=True)
    registry = ProjectRegistry(tmp_path / "projects.json")
    project = registry.register("Canonical project", real_workspace)
    registry.set_mode("strict")

    memory = Memory(
        content="Decision: use the canonical registered project path for retrieval.",
        metadata=MemoryMetadata(
            memory_type=MemoryType.DECISION,
            source_reliability=0.9,
            verified=True,
            project=project.project_id,
            workspace=project.root,
        ),
    )
    result = SearchResult(memory=memory, score=0.9, vector_score=0.9, source="vector")
    server = ElefanteMCPServer()
    server._project_registry = registry
    ledger = TaskIntelligenceLedger(tmp_path / "canonical-task-ledger.sqlite3")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {**PROVENANCE, "cwd": str(alias_workspace)},
    )
    monkeypatch.setattr(
        server, "_get_orchestrator", lambda: _async_value(_Orchestrator(result))
    )
    monkeypatch.setattr(server, "_get_task_intelligence_ledger", lambda: ledger)

    prepared = await server._handle_task_intelligence(
        {
            "action": "prepare",
            "task": "Which canonical project path applies to retrieval?",
            "project": project.project_id,
            "workspace": str(alias_workspace),
            "profile": "v2",
            "delivery_mode": "pilot",
        }
    )

    assert prepared["status"] == "delivered"
    trace = ledger.validate_trace(
        prepared["trace_id"],
        provenance={**PROVENANCE, "cwd": str(alias_workspace)},
    )
    assert trace["project_sha256"] == sha256_text(project.project_id)
    assert trace["workspace_sha256"] == sha256_text(project.root)
    ledger.close()


@pytest.mark.asyncio
async def test_server_shadow_never_delivers_context_and_pilot_has_kill_switch(
    monkeypatch, tmp_path
) -> None:
    memory = Memory(
        content="Decision: use a global runtime.", metadata=MemoryMetadata()
    )
    result = SearchResult(memory=memory, score=0.9, vector_score=0.9, source="vector")
    server = ElefanteMCPServer()
    server._project_registry = ProjectRegistry(tmp_path / "projects.json")
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", raising=False)
    monkeypatch.setattr(server, "_request_provenance", lambda: dict(PROVENANCE))
    monkeypatch.setattr(
        server, "_get_orchestrator", lambda: _async_value(_Orchestrator(result))
    )
    monkeypatch.setattr(server, "_get_task_intelligence_ledger", lambda: ledger)

    shadow = await server._handle_task_intelligence(
        {
            "action": "prepare",
            "task": "What is the global runtime decision?",
            "profile": "v2",
            "delivery_mode": "shadow",
        }
    )
    assert shadow["success"] is True
    assert shadow["delivered_memory_ids"] == []
    assert "rendered_context" not in shadow
    assert "evidence" not in shadow

    disabled = await server._handle_task_intelligence(
        {
            "action": "prepare",
            "task": "What is the global runtime decision?",
            "profile": "v2",
            "delivery_mode": "pilot",
        }
    )
    assert disabled["success"] is False
    assert disabled["status"] == "PILOT_DISABLED"
    ledger.close()


@pytest.mark.asyncio
async def test_server_pilot_rejects_v1_profile(monkeypatch, tmp_path) -> None:
    server = ElefanteMCPServer()
    ledger = TaskIntelligenceLedger(tmp_path / "task-ledger.sqlite3")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setattr(server, "_get_task_intelligence_ledger", lambda: ledger)

    result = await server._handle_task_intelligence(
        {
            "action": "prepare",
            "task": "What is the global runtime decision?",
            "profile": "v1",
            "delivery_mode": "pilot",
        }
    )

    assert result["success"] is False
    assert result["status"] == "PILOT_PROFILE_REQUIRED"
    ledger.close()
