from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.core.orchestrator import MemoryOrchestrator
from src.core.project_registry import ProjectRegistry
from src.mcp.server import AnswerContext, ElefanteMCPServer
from src.models.memory import Memory, MemoryMetadata
from src.models.query import QueryMode, SearchFilters


def test_context_prompt_resolves_the_strict_project_before_recall() -> None:
    source = (Path(__file__).resolve().parents[1] / "src" / "mcp" / "server.py").read_text(
        encoding="utf-8"
    )

    prompt_block = source[source.index('elif name == "elefante-context"') : source.index(
        'raise ValueError(f"Unknown prompt: {name}")'
    )]
    assert "project_resolution = self._strict_project_resolution({})" in prompt_block
    assert "project=project.project_id" in prompt_block
    assert "workspace=project.root" in prompt_block
    assert "no cross-project memory was returned" in prompt_block


class _ProjectEmbeddingService:
    async def generate_embedding(self, _text):
        return [1.0, 0.0, 0.0]

    def get_embedding_dimension(self):
        return 3


def _strict_server(tmp_path: Path, monkeypatch) -> tuple[ElefanteMCPServer, object]:
    project_root = tmp_path / "company" / "alpha"
    workspace = project_root / "src"
    workspace.mkdir(parents=True)
    registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    project = registry.register("Alpha", project_root)
    registry.set_mode("strict")
    server = ElefanteMCPServer()
    server._project_registry = registry
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {
            "tool": "codex",
            "instance_id": "window-a",
            "session_id": "session-a",
            "cwd": str(workspace),
            "transport": "streamable-http",
        },
    )
    return server, project


@pytest.mark.asyncio
async def test_strict_remember_blocks_before_gate_or_store_without_registered_context(
    tmp_path,
    monkeypatch,
):
    registered = tmp_path / "registered"
    unregistered = tmp_path / "unregistered"
    registered.mkdir()
    unregistered.mkdir()
    registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    registry.register("Registered", registered)
    registry.set_mode("strict")
    server = ElefanteMCPServer()
    server._project_registry = registry
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(unregistered)},
    )
    monkeypatch.setattr(
        server,
        "_check_compliance_gate",
        lambda _tool: (_ for _ in ()).throw(
            AssertionError("Project rejection must happen before the compliance gate")
        ),
    )
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: (_ for _ in ()).throw(
            AssertionError("Project rejection must happen before the memory store")
        ),
    )

    result = await server._handle_add_memory(
        {"content": "Use SQLite.", "memory_type": "decision"}
    )

    assert result == {
        "success": False,
        "status": "PROJECT_REQUIRED",
        "error": (
            "Elefante could not identify one active registered project for this "
            "workspace. Choose or register the project before continuing."
        ),
        "error_code": "PROJECT_NOT_REGISTERED",
        "project_mode": "strict",
        "memory_read": False,
        "memory_written": False,
    }


@pytest.mark.asyncio
async def test_strict_remember_stamps_stable_project_identity(tmp_path, monkeypatch):
    server, project = _strict_server(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    class Orchestrator:
        async def add_memory(self, **kwargs):
            captured.update(kwargs)
            metadata = kwargs["metadata"]
            return Memory(
                content=kwargs["content"],
                metadata=MemoryMetadata(
                    memory_type=kwargs["memory_type"],
                    project=metadata["project"],
                    workspace=metadata["workspace"],
                    scope=metadata["scope"],
                ),
            )

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    async def orchestrator():
        return Orchestrator()

    monkeypatch.setattr(server, "_get_orchestrator", orchestrator)
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _tool: None)

    result = await server._handle_add_memory(
        {
            "content": "Use SQLite.",
            "memory_type": "decision",
            "invocation_mode": "user_directed",
        }
    )

    metadata = captured["metadata"]
    assert metadata["project"] == project.project_id
    assert metadata["workspace"] == project.root
    assert metadata["scope"] == project.scope
    assert result["status"] == "stored"
    assert result["project"] == {
        "project_id": project.project_id,
        "name": "Alpha",
        "scope": project.scope,
    }


@pytest.mark.asyncio
async def test_agent_remember_uses_one_project_scoped_verified_operation(
    tmp_path,
    monkeypatch,
):
    server, project = _strict_server(tmp_path, monkeypatch)
    captured: dict[str, object] = {}
    memory_id = "11111111-1111-4111-8111-111111111111"

    class Service:
        async def execute(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                success=True,
                receipt=SimpleNamespace(
                    changed=True,
                    memory_id=memory_id,
                ),
                plan=SimpleNamespace(memory_type="decision"),
                to_dict=lambda: {
                    "success": True,
                    "status": "VERIFIED_COMPLETE",
                    "remember_status": "VERIFIED_COMPLETE",
                    "receipt": {
                        "status": "VERIFIED_COMPLETE",
                        "memory_id": memory_id,
                    },
                    "remembered": {
                        "title": "SQLite",
                        "kind": "decision",
                        "project": {
                            "project_id": project.project_id,
                            "name": project.name,
                        },
                        "recall_verified": True,
                    },
                },
            )

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    orchestrator = SimpleNamespace()

    async def get_orchestrator():
        return orchestrator

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _tool: None)
    monkeypatch.setattr(
        server,
        "_verified_remember_service",
        lambda bound, **_kwargs: Service() if bound is orchestrator else None,
    )

    result = await server._handle_add_memory(
        {
            "content": "Decision: use SQLite.",
            "knowledge_kind": "decision",
            "invocation_mode": "user_directed",
            "verification_question": "Which database should this project use?",
        }
    )

    assert captured["project_id"] == project.project_id
    assert captured["project_name"] == project.name
    assert captured["workspace"] == project.root
    assert captured["scope"] == project.scope
    assert captured["knowledge_kind"] == "decision"
    assert captured["verification_question"] == "Which database should this project use?"
    assert result["remember_status"] == "VERIFIED_COMPLETE"
    assert result["memory_written"] is True
    assert result["memory_id"] == memory_id


@pytest.mark.asyncio
async def test_verified_remember_rejects_secret_before_persistence(
    tmp_path,
    monkeypatch,
):
    server, _ = _strict_server(tmp_path, monkeypatch)

    @asynccontextmanager
    async def acquired_write():
        yield SimpleNamespace(acquired=True)

    async def get_orchestrator():
        return SimpleNamespace()

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(server, "_write_operation", acquired_write)
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _tool: None)
    monkeypatch.setattr(
        server,
        "_verified_remember_service",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Secret-like content must not reach Remember persistence")
        ),
    )
    secret = "sk-" + ("a" * 32)

    result = await server._handle_add_memory(
        {
            "content": f"Remember this credential {secret}",
            "knowledge_kind": "constraint",
            "invocation_mode": "user_directed",
            "verification_question": "What credential is configured?",
        }
    )

    assert result["error_code"] == "REMEMBER_SECRET_REJECTED"
    assert result["memory_written"] is False
    assert secret not in json.dumps(result)


@pytest.mark.asyncio
async def test_strict_remember_rejects_caller_scope_override_before_write(
    tmp_path,
    monkeypatch,
):
    server, _ = _strict_server(tmp_path, monkeypatch)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: (_ for _ in ()).throw(AssertionError("No store access expected")),
    )

    result = await server._handle_add_memory(
        {
            "content": "Use SQLite.",
            "memory_type": "decision",
            "scope": "shared:all-projects",
        }
    )

    assert result["status"] == "PROJECT_REQUIRED"
    assert result["error_code"] == "PROJECT_SCOPE_MISMATCH"
    assert result["memory_written"] is False


@pytest.mark.asyncio
async def test_strict_search_forces_exact_project_filters(tmp_path, monkeypatch):
    server, project = _strict_server(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    class Orchestrator:
        async def search_memories(self, **kwargs):
            captured.update(kwargs)
            return []

    async def orchestrator():
        return Orchestrator()

    monkeypatch.setattr(server, "_get_orchestrator", orchestrator)

    result = await server._handle_search_memories(
        {
            "query": "Which database should we use?",
            "include_conversation": False,
        }
    )

    filters = captured["filters"]
    assert filters.project == project.project_id
    assert filters.workspace == project.root
    assert result["project"]["project_id"] == project.project_id
    assert result["count"] == 0


@pytest.mark.asyncio
async def test_strict_recall_blocks_without_read_and_passes_exact_context_when_matched(
    tmp_path,
    monkeypatch,
):
    server, project = _strict_server(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    async def recall_context(question, *, project, workspace):
        captured.update(
            {"question": question, "project": project, "workspace": workspace}
        )
        return AnswerContext(
            text="# Elefante Recall\n\nUse SQLite.",
            selected_count=1,
            omitted_count=0,
            selected_memory_ids=("memory-a",),
        )

    monkeypatch.setattr(server, "_recall_answer_context", recall_context)

    supplied = await server._handle_recall(
        {"question": "Which database should Alpha use?"}
    )

    assert supplied["status"] == "supplied"
    assert captured == {
        "question": "Which database should Alpha use?",
        "project": project.project_id,
        "workspace": project.root,
    }

    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(outside)},
    )
    monkeypatch.setattr(
        server,
        "_recall_answer_context",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("Blocked Recall must not read the store")
        ),
    )
    blocked = await server._handle_recall(
        {"question": "Which database should Alpha use?"}
    )

    assert set(blocked) == {
        "success",
        "status",
        "context",
        "supplied_count",
        "abstained",
        "delivery_blocked",
        "read_only",
    }
    assert blocked["status"] == "blocked"
    assert blocked["supplied_count"] == 0
    assert blocked["delivery_blocked"] is True
    assert "No memory was read" in blocked["context"]


def test_explicit_project_filter_rejects_unscoped_and_cross_project_results():
    filters = SearchFilters(project="project-a", workspace="/company/a")
    matching = Memory(
        content="Alpha decision",
        metadata=MemoryMetadata(project="project-a", workspace="/company/a"),
    )
    unscoped = Memory(content="Legacy global memory")
    wrong = Memory(
        content="Beta decision",
        metadata=MemoryMetadata(project="project-b", workspace="/company/b"),
    )

    assert MemoryOrchestrator._matches_explicit_scope(matching, filters) is True
    assert MemoryOrchestrator._matches_explicit_scope(unscoped, filters) is False
    assert MemoryOrchestrator._matches_explicit_scope(wrong, filters) is False


@pytest.mark.asyncio
async def test_structured_search_filters_graph_candidates_before_limit():
    matching_id = uuid4()
    excluded_id = uuid4()
    related_entity_id = uuid4()
    matching = Memory(
        id=matching_id,
        content="The matching structured memory",
        metadata=MemoryMetadata(
            memory_type="fact",
            tags=["wanted"],
            score=90,
            created_at=datetime(2024, 6, 1),
        ),
        related_entities=[related_entity_id],
    )
    excluded = Memory(
        id=excluded_id,
        content="The excluded structured memory",
        metadata=MemoryMetadata(
            memory_type="fact",
            tags=["wrong"],
            score=10,
            created_at=datetime(2020, 6, 1),
        ),
    )

    class Graph:
        def __init__(self):
            self.query = None

        async def execute_query(self, query):
            self.query = query
            return [
                {"m": {"id": str(excluded_id), "props": json.dumps({"score": 10})}},
                {"m": {"id": str(matching_id), "props": json.dumps({"score": 90})}},
            ]

    class Vectors:
        async def get_memory(self, memory_id):
            return {matching_id: matching, excluded_id: excluded}.get(memory_id)

    graph = Graph()
    orchestrator = MemoryOrchestrator.__new__(MemoryOrchestrator)
    orchestrator.graph_store = graph
    orchestrator.vector_store = Vectors()
    filters = SearchFilters(
        memory_type="fact",
        tags=["wanted"],
        min_score=80,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 1, 1),
        related_entities=[related_entity_id],
    )
    plan = orchestrator._create_query_plan(
        "structured proof",
        QueryMode.STRUCTURED,
        limit=1,
        filters=filters,
        min_similarity=0.0,
    )

    results = await orchestrator._search_structured(
        "structured proof",
        plan,
        apply_temporal_decay=False,
        reinforce_access=False,
        filters=filters,
    )

    assert "m.memory_type" not in graph.query
    assert "LIMIT 10" in graph.query
    assert [result.memory.id for result in results] == [matching_id]
    assert results[0].memory.related_entities == [related_entity_id]


@pytest.mark.asyncio
async def test_structured_search_pages_past_nonmatching_window():
    matching_id = uuid4()
    excluded_ids = [uuid4() for _ in range(10)]
    matching = Memory(
        id=matching_id,
        content="The eleventh structured memory matches",
        metadata=MemoryMetadata(
            tags=["wanted"],
            score=90,
            created_at=datetime(2024, 6, 1),
        ),
    )
    excluded = {
        memory_id: Memory(
            id=memory_id,
            content="An excluded structured memory",
            metadata=MemoryMetadata(
                tags=["wrong"],
                score=10,
                created_at=datetime(2020, 1, 1),
            ),
        )
        for memory_id in excluded_ids
    }
    memories = {**excluded, matching_id: matching}
    queries = []

    class Graph:
        async def execute_query(self, query):
            queries.append(query)
            offset = int(query.split("SKIP ", 1)[1].split(" ", 1)[0])
            limit = int(query.rsplit("LIMIT ", 1)[1])
            ids = excluded_ids + [matching_id]
            page = ids[offset:offset + limit]
            return [
                {"m": {"id": str(memory_id), "props": json.dumps({"score": memories[memory_id].metadata.score})}}
                for memory_id in page
            ]

    class Vectors:
        async def get_memory(self, memory_id):
            return memories.get(memory_id)

    orchestrator = MemoryOrchestrator.__new__(MemoryOrchestrator)
    orchestrator.graph_store = Graph()
    orchestrator.vector_store = Vectors()
    filters = SearchFilters(
        tags=["wanted"],
        min_score=80,
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2025, 1, 1),
    )
    plan = orchestrator._create_query_plan(
        "structured page proof",
        QueryMode.STRUCTURED,
        limit=1,
        filters=filters,
        min_similarity=0.0,
    )

    results = await orchestrator._search_structured(
        "structured page proof",
        plan,
        apply_temporal_decay=False,
        reinforce_access=False,
        filters=filters,
    )

    assert [result.memory.id for result in results] == [matching_id]
    assert len(queries) == 2
    assert "SKIP 0" in queries[0] and "LIMIT 10" in queries[0]
    assert "SKIP 10" in queries[1] and "LIMIT 10" in queries[1]


@pytest.mark.asyncio
async def test_two_real_projects_with_opposite_decisions_have_zero_cross_project_exposure(
    tmp_path,
    monkeypatch,
    isolated_orchestrator,
):
    alpha_root = tmp_path / "company" / "alpha"
    beta_root = tmp_path / "company" / "beta"
    alpha_workspace = alpha_root / "src"
    beta_workspace = beta_root / "src"
    alpha_workspace.mkdir(parents=True)
    beta_workspace.mkdir(parents=True)

    registry = ProjectRegistry(tmp_path / "data" / "projects.json")
    alpha = registry.register("Alpha", alpha_root)
    beta = registry.register("Beta", beta_root)
    registry.set_mode("strict")

    current_workspace = {"path": str(alpha_workspace)}
    isolated_orchestrator.vector_store._embedding_service = _ProjectEmbeddingService()
    isolated_orchestrator.embedding_service = _ProjectEmbeddingService()
    writer_server = ElefanteMCPServer()
    writer_server._project_registry = registry

    async def get_writer_orchestrator():
        return isolated_orchestrator

    monkeypatch.setattr(
        writer_server,
        "_get_orchestrator",
        get_writer_orchestrator,
    )
    monkeypatch.setattr(
        writer_server,
        "_request_provenance",
        lambda: {
            "tool": "codex",
            "instance_id": "project-isolation-test",
            "session_id": "session-a",
            "cwd": current_workspace["path"],
            "transport": "streamable-http",
        },
    )

    async def remember(workspace: Path, content: str) -> str:
        current_workspace["path"] = str(workspace)
        await writer_server._handle_search_memories(
            {
                "query": content,
                "include_conversation": False,
                "min_similarity": 0.0,
            }
        )
        result = await writer_server._handle_add_memory(
            {
                "content": content,
                "memory_type": "decision",
                "invocation_mode": "user_directed",
                "metadata": {
                    "verified": True,
                    "authority_score": 0.95,
                    "source_reliability": 0.95,
                },
            }
        )
        assert result["status"] == "stored"
        return str(result["memory_id"])

    alpha_memory_id = await remember(
        alpha_workspace,
        "Alpha payment retries allow exactly three attempts.",
    )
    beta_memory_id = await remember(
        beta_workspace,
        "Beta payment retries allow no retry attempts.",
    )

    await isolated_orchestrator.close()
    from src.core.graph_store import GraphStore
    from src.core.sqlite_vector_store import SQLiteVectorStore

    reopened_vector = SQLiteVectorStore(
        collection_name=isolated_orchestrator._test_collection_name,
        persist_directory=str(isolated_orchestrator._test_vector_dir),
    )
    reopened_vector._embedding_service = _ProjectEmbeddingService()
    reopened_orchestrator = MemoryOrchestrator(
        vector_store=reopened_vector,
        graph_store=GraphStore(
            database_path=str(isolated_orchestrator._test_kuzu_dir)
        ),
        embedding_service=_ProjectEmbeddingService(),
    )
    server = ElefanteMCPServer()
    server._project_registry = ProjectRegistry(registry.path)

    async def get_orchestrator():
        return reopened_orchestrator

    monkeypatch.setattr(server, "_get_orchestrator", get_orchestrator)
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {
            "tool": "codex",
            "instance_id": "project-isolation-test",
            "session_id": "session-b",
            "cwd": current_workspace["path"],
            "transport": "streamable-http",
        },
    )

    async def scoped_result(workspace: Path):
        current_workspace["path"] = str(workspace)
        return await server._handle_search_memories(
            {
                "query": "How many payment retry attempts are allowed?",
                "include_conversation": False,
                "min_similarity": 0.0,
            }
        )

    alpha_result = await scoped_result(alpha_workspace)
    beta_result = await scoped_result(beta_workspace)

    assert alpha_result["project"]["project_id"] == alpha.project_id
    assert [item["memory"]["id"] for item in alpha_result["results"]] == [
        alpha_memory_id
    ]
    assert "three attempts" in alpha_result["results"][0]["memory"]["content"]
    assert beta_memory_id not in json.dumps(alpha_result)

    assert beta_result["project"]["project_id"] == beta.project_id
    assert [item["memory"]["id"] for item in beta_result["results"]] == [
        beta_memory_id
    ]
    assert "no retry attempts" in beta_result["results"][0]["memory"]["content"]
    assert alpha_memory_id not in json.dumps(beta_result)

    current_workspace["path"] = str(alpha_workspace)
    alpha_recall = await server._handle_recall(
        {"question": "How many payment retry attempts are allowed?"}
    )
    current_workspace["path"] = str(beta_workspace)
    beta_recall = await server._handle_recall(
        {"question": "How many payment retry attempts are allowed?"}
    )

    assert alpha_recall["status"] == "supplied"
    assert "three attempts" in alpha_recall["context"]
    assert "no retry attempts" not in alpha_recall["context"]
    assert beta_recall["status"] == "supplied"
    assert "no retry attempts" in beta_recall["context"]
    assert "three attempts" not in beta_recall["context"]
    await reopened_orchestrator.close()
