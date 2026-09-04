# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_memory_persistence.py
# PROVES  : Memories are durably stored in the configured vector store and Kuzu
#           without temporary scripts; graph/session schema contract and
#           relationship property constraints.
# RUN     : pytest tests/test_memory_persistence.py -v
# WHEN    : After changes to vector_store.py, graph_store.py, or memory.py schema.
# ─────────────────────────────────────────────────────────────────────────────
"""
Tests for memory persistence - verifies that memories are stored directly
in the configured vector store and Kuzu without generating temporary scripts.

This test suite ensures the write-path architecture is correct.
"""

import ast
import json
import os
import subprocess
import pytest
import asyncio
import sys
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from pathlib import Path

from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import VectorStore
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.core.graph_store import GraphStore
from src.models.entity import Entity, EntityType, Relationship, RelationshipType
from src.models.memory import MemoryStatus
from src.models.query import QueryMode, SearchResult


def test_vector_store_uses_embedded_chroma_client_not_server_transport(tmp_path, monkeypatch):
    """Elefante must not create the network Chroma client surface."""
    chromadb = pytest.importorskip("chromadb")

    calls = {}

    class FakeCollection:
        def count(self):
            return 0

    class FakePersistentClient:
        def __init__(self, *, path, settings):
            calls["path"] = path
            calls["settings"] = settings

        def get_or_create_collection(self, *, name, metadata):
            calls["collection"] = (name, metadata)
            return FakeCollection()

    def fail_if_network_client_is_used(*_args, **_kwargs):
        raise AssertionError("Elefante must not use Chroma's network client")

    monkeypatch.setattr(chromadb, "PersistentClient", FakePersistentClient)
    monkeypatch.setattr(chromadb, "HttpClient", fail_if_network_client_is_used)
    store = VectorStore(
        collection_name="embedded-only",
        persist_directory=str(tmp_path / "chroma"),
    )

    store._initialize_client()

    assert calls["path"] == str(tmp_path / "chroma")
    assert calls["collection"] == (
        "embedded-only",
        {"hnsw:space": store.distance_metric},
    )


class TestMemoryPersistence:
    """Test that memories persist correctly in both databases"""
    
    @pytest.fixture
    def orchestrator(self, tmp_path, monkeypatch):
        """Create an orchestrator isolated to a temp DB (no shared locks)"""
        monkeypatch.setenv("ELEFANTE_ALLOW_TEST_MEMORIES", "1")
        vector_dir = tmp_path / "vector"
        kuzu_dir = tmp_path / "kuzu_db"

        vector_store = SQLiteVectorStore(
            collection_name=f"test_memory_persistence_{uuid4().hex}",
            persist_directory=str(vector_dir),
        )
        graph_store = GraphStore(database_path=str(kuzu_dir))

        orch = MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)
        orch._test_vector_dir = vector_dir
        orch._test_collection_name = vector_store.collection_name
        orch._test_kuzu_dir = kuzu_dir
        return orch
    
    @pytest.mark.asyncio
    async def test_add_memory_persists_to_vector_store(self, orchestrator):
        """Test that add_memory stores data in ChromaDB"""
        # Add a unique memory
        test_content = f"Test memory for persistence {uuid4()}"
        
        memory = await orchestrator.add_memory(
            content=test_content,
            memory_type="fact",
            tags=["test", "persistence"]
        )
        
        # Verify memory was created
        assert memory is not None
        assert memory.id is not None
        assert memory.content == test_content
        
        # Search for the memory to verify it's in ChromaDB
        results = await orchestrator.search_memories(
            query=test_content,
            mode=QueryMode.SEMANTIC,
            limit=5
        )
        
        # Should find the memory we just added
        assert len(results) > 0
        found = any(r.memory.content == test_content for r in results)
        assert found, "Memory not found in vector store after adding"

    @pytest.mark.asyncio
    async def test_contradiction_persists_conflicting_memory_id(self, orchestrator, monkeypatch):
        """A detected contradiction remains inspectable after the write."""
        class FixedEmbedding:
            async def generate_embedding(self, _text):
                return [1.0, 0.0, 0.0]

        embedding = FixedEmbedding()
        orchestrator.embedding_service = embedding
        orchestrator.vector_store._embedding_service = embedding

        existing = await orchestrator.add_memory(
            content="The local daemon stores memory decisions.",
            memory_type="fact",
            metadata={"title": "Existing daemon storage"},
        )
        assert existing is not None

        async def no_title_match(_title):
            return None

        async def contradictory_match(**_kwargs):
            return [
                SearchResult(
                    memory=existing,
                    score=0.80,
                    vector_score=0.80,
                    source="vector",
                )
            ]

        monkeypatch.setattr(orchestrator.vector_store, "find_by_title", no_title_match)
        monkeypatch.setattr(orchestrator.vector_store, "search", contradictory_match)

        incoming = await orchestrator.add_memory(
            content="The local daemon does not store memory decisions.",
            memory_type="fact",
            metadata={"title": "Incoming daemon storage"},
        )

        assert incoming is not None
        assert incoming.metadata.status == MemoryStatus.CONTRADICTORY.value
        assert incoming.metadata.conflict_ids == [existing.id]

    @pytest.mark.asyncio
    async def test_preference_reassertion_does_not_merge_into_another_memory_type(
        self, orchestrator, monkeypatch
    ):
        """A close decision is related evidence, not an existing preference."""
        class FixedEmbedding:
            async def generate_embedding(self, _text):
                return [1.0, 0.0, 0.0]

        embedding = FixedEmbedding()
        orchestrator.embedding_service = embedding
        orchestrator.vector_store._embedding_service = embedding

        existing = await orchestrator.add_memory(
            content="Project Alpha uses local memory routing for agent decisions.",
            memory_type="decision",
            metadata={"title": "Existing routing decision"},
        )
        assert existing is not None

        async def no_title_match(_title):
            return None

        async def close_non_preference(**_kwargs):
            return [
                SearchResult(
                    memory=existing,
                    score=0.99,
                    vector_score=0.99,
                    source="vector",
                )
            ]

        monkeypatch.setattr(orchestrator.vector_store, "find_by_title", no_title_match)
        monkeypatch.setattr(orchestrator.vector_store, "search", close_non_preference)

        incoming = await orchestrator.add_memory(
            content="Project Alpha prefers local memory routing for dashboard advice.",
            memory_type="preference",
            metadata={"title": "Incoming routing preference"},
        )

        assert incoming is not None
        assert incoming.id != existing.id
        assert str(incoming.metadata.memory_type) == "preference"

    @pytest.mark.asyncio
    async def test_preference_reassertion_still_merges_an_existing_preference(
        self, orchestrator, monkeypatch
    ):
        """The cross-type guard must preserve genuine preference reinforcement."""
        class FixedEmbedding:
            async def generate_embedding(self, _text):
                return [1.0, 0.0, 0.0]

        embedding = FixedEmbedding()
        orchestrator.embedding_service = embedding
        orchestrator.vector_store._embedding_service = embedding

        existing = await orchestrator.add_memory(
            content="Project Alpha prefers local memory routing for agent advice.",
            memory_type="preference",
            metadata={"title": "Existing routing preference"},
        )
        assert existing is not None

        async def no_title_match(_title):
            return None

        async def close_preference(**_kwargs):
            return [
                SearchResult(
                    memory=existing,
                    score=0.99,
                    vector_score=0.99,
                    source="vector",
                )
            ]

        monkeypatch.setattr(orchestrator.vector_store, "find_by_title", no_title_match)
        monkeypatch.setattr(orchestrator.vector_store, "search", close_preference)

        incoming = await orchestrator.add_memory(
            content="Project Alpha prefers local memory routing for dashboard advice.",
            memory_type="preference",
            metadata={"title": "Reasserted routing preference"},
        )

        assert incoming is not None
        assert incoming.id == existing.id
        persisted = await orchestrator.vector_store.get_memory(existing.id)
        assert persisted is not None
        assert "Reasserted" in persisted.content
    
    @pytest.mark.asyncio
    async def test_add_memory_persists_to_graph_store(self, orchestrator):
        """Test that add_memory creates nodes in Kuzu"""
        # Add memory with entities
        test_content = f"Test graph memory {uuid4()}"
        
        memory = await orchestrator.add_memory(
            content=test_content,
            memory_type="insight",
            entities=[
                {"name": "TestEntity", "type": "concept"}
            ]
        )
        
        # Verify memory was created
        assert memory is not None
        
        # Query graph to verify node exists
        graph_store = orchestrator.graph_store
        # Query for Entity nodes with custom type (memories are stored as entities)
        query = "MATCH (e:Entity) RETURN e LIMIT 10"
        results = await graph_store.execute_query(query)
        
        # Should have at least one entity node
        assert len(results) > 0, "No entity nodes found in graph store"

    @pytest.mark.asyncio
    async def test_source_tuple_round_trips_and_links_to_graph_source(self, orchestrator):
        """Every new memory gets durable vector and graph provenance."""
        source = {
            "tool": "codex",
            "instance_id": "window-1",
            "session_id": "session-1",
            "cwd": "/workspace/elefante",
            "transport": "streamable-http",
        }
        memory = await orchestrator.add_memory(
            content=f"Provenance roundtrip {uuid4()}",
            memory_type="note",
            metadata={"elefante_source": source},
        )

        stored = await orchestrator.vector_store.get_memory(memory.id)
        assert stored is not None
        persisted_source = stored.metadata.custom_metadata["elefante_source"]
        assert persisted_source["tool"] == "codex"
        assert persisted_source["instance_id"] == "window-1"
        assert persisted_source["transport"] == "streamable-http"

        links = await orchestrator.graph_store.execute_query(
            """
            MATCH (m:Entity {id: $memory_id})-[:WRITTEN_BY]->(s:Source)
            RETURN s.tool, s.instance_id, s.session_id, s.transport
            """,
            {"memory_id": str(memory.id)},
        )
        assert len(links) == 1
        assert links[0]["values"] == ["codex", "window-1", "session-1", "streamable-http"]
    
    @pytest.mark.asyncio
    async def test_no_temporary_scripts_generated(self, orchestrator):
        """Verify that no temporary .py files are created during memory addition"""
        # Get current directory
        current_dir = Path.cwd()
        
        # List all .py files before
        py_files_before = set(current_dir.rglob("*.py"))
        
        # Add a memory
        test_content = f"Test no scripts {uuid4()}"
        await orchestrator.add_memory(
            content=test_content,
            memory_type="note"
        )
        
        # List all .py files after
        py_files_after = set(current_dir.rglob("*.py"))
        
        # Check for new .py files
        new_files = py_files_after - py_files_before
        
        # Filter out __pycache__ and legitimate files
        suspicious_files = [
            f for f in new_files 
            if "temp" in f.name.lower() or "script" in f.name.lower()
        ]
        
        assert len(suspicious_files) == 0, f"Temporary scripts generated: {suspicious_files}"
    
    @pytest.mark.asyncio
    async def test_memory_survives_orchestrator_restart(self, orchestrator):
        """Test that memories persist across orchestrator instances"""
        # Add a unique memory
        test_content = f"Persistence test {uuid4()}"
        
        memory = await orchestrator.add_memory(
            content=test_content,
            memory_type="conversation"
        )
        
        memory_id = memory.id
        
        # Create a NEW orchestrator instance (simulates restart)
        new_vector_store = SQLiteVectorStore(
            collection_name=orchestrator._test_collection_name,
            persist_directory=str(orchestrator._test_vector_dir),
        )
        new_graph_store = GraphStore(database_path=str(orchestrator._test_kuzu_dir))
        new_orchestrator = MemoryOrchestrator(vector_store=new_vector_store, graph_store=new_graph_store)
        
        # Search for the memory with the new instance
        results = await new_orchestrator.search_memories(
            query=test_content,
            mode=QueryMode.SEMANTIC,
            limit=5
        )
        
        # Should still find the memory
        assert len(results) > 0
        found = any(str(r.memory.id) == str(memory_id) for r in results)
        assert found, "Memory not found after orchestrator restart"

    @pytest.mark.asyncio
    async def test_cognitive_fields_roundtrip_in_vector_store(self, orchestrator):
        """V4 cognitive fields should persist and reconstruct as typed lists."""
        test_content = f"Cognitive fields persistence test {uuid4()}"

        memory = await orchestrator.add_memory(
            content=test_content,
            memory_type="fact",
            metadata={
                "concepts": ["Memory", "Souvenir", "Vector DB"],
                "surfaces_when": ["How to recall memory", "vector db retrieval"],
                "authority_score": 0.9,
            },
        )

        assert memory is not None
        assert isinstance(memory.metadata.concepts, list)
        assert isinstance(memory.metadata.surfaces_when, list)
        assert memory.metadata.concepts, "Expected non-empty concepts"
        assert memory.metadata.surfaces_when, "Expected non-empty surfaces_when"

        # New SQLiteVectorStore instance simulates a restart / new process.
        new_vector_store = SQLiteVectorStore(
            collection_name=orchestrator._test_collection_name,
            persist_directory=str(orchestrator._test_vector_dir),
        )
        reloaded = await new_vector_store.get_memory(memory.id)
        assert reloaded is not None

        assert isinstance(reloaded.metadata.concepts, list)
        assert isinstance(reloaded.metadata.surfaces_when, list)
        assert reloaded.metadata.concepts == memory.metadata.concepts
        assert reloaded.metadata.surfaces_when == memory.metadata.surfaces_when
        assert abs(float(reloaded.metadata.authority_score) - float(memory.metadata.authority_score)) < 1e-9
    
    @pytest.mark.asyncio
    async def test_add_memory_with_entities_creates_relationships(self, orchestrator):
        """Test that entities and relationships are created in graph"""
        test_content = f"Entity relationship test {uuid4()}"
        entity_name = f"TestEntity_{uuid4().hex[:8]}"
        
        memory = await orchestrator.add_memory(
            content=test_content,
            memory_type="fact",
            entities=[
                {"name": entity_name, "type": "concept"}
            ]
        )
        assert memory is not None
        
        # Query graph for the entity
        graph_store = orchestrator.graph_store
        query = f"MATCH (e) WHERE e.name = '{entity_name}' RETURN e"
        results = await graph_store.execute_query(query)
        
        # Entity should exist
        assert len(results) > 0, f"Entity '{entity_name}' not found in graph"
        
        # Query for relationships
        rel_query = f"MATCH (m)-[r]->(e) WHERE e.name = '{entity_name}' RETURN r"
        rel_results = await graph_store.execute_query(rel_query)
        
        # Should have at least one relationship
        assert len(rel_results) > 0, "No relationships found for entity"


@pytest.mark.asyncio
async def test_graph_store_close_waits_for_inflight_query(isolated_graph_store, monkeypatch):
    """close() must wait for active Kuzu work instead of destroying the store immediately."""

    class FakeResult:
        def __init__(self, columns, rows):
            self._columns = columns
            self._rows = list(rows)

        def get_column_names(self):
            return self._columns

        def has_next(self):
            return bool(self._rows)

        def get_next(self):
            return self._rows.pop(0)

    class BlockingConnection:
        def __init__(self):
            self.started = threading.Event()
            self.release = threading.Event()
            self.closed = False

        def execute(self, _query, params=None):
            self.started.set()
            assert self.release.wait(timeout=2.0), "Timed out waiting to release blocking query"
            return FakeResult(["value"], [[(params or {}).get("value", 0)]])

        def close(self):
            self.closed = True

    class FakeDatabase:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    connection = BlockingConnection()
    database = FakeDatabase()

    isolated_graph_store._conn = connection
    isolated_graph_store._db = database
    isolated_graph_store._schema_initialized = True
    monkeypatch.setattr(isolated_graph_store, "_initialize_connection", lambda: None)

    query_task = asyncio.create_task(
        isolated_graph_store.execute_query("RETURN $value AS value", {"value": 7})
    )

    assert await asyncio.to_thread(connection.started.wait, 1.0), "Query never started"

    close_task = asyncio.create_task(asyncio.to_thread(isolated_graph_store.close))
    await asyncio.sleep(0.05)

    assert not database.closed
    assert not connection.closed

    connection.release.set()

    results = await query_task
    await close_task

    assert results == [{"value": 7, "values": [7]}]
    assert database.closed
    assert connection.closed


def test_graph_store_raw_execute_calls_stay_in_safe_methods():
    graph_store_path = Path(__file__).resolve().parents[1] / "src" / "core" / "graph_store.py"
    source = graph_store_path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    allowed_functions = {"_initialize_schema", "_execute_query_sync"}
    violations = []

    class ExecuteVisitor(ast.NodeVisitor):
        def __init__(self):
            self.function_stack = []

        def visit_FunctionDef(self, node):
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_AsyncFunctionDef(self, node):
            self.function_stack.append(node.name)
            self.generic_visit(node)
            self.function_stack.pop()

        def visit_Call(self, node):
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "execute"
                and isinstance(func.value, ast.Attribute)
                and func.value.attr == "_conn"
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "self"
            ):
                current_function = self.function_stack[-1] if self.function_stack else "<module>"
                if current_function not in allowed_functions:
                    violations.append((current_function, node.lineno))
            self.generic_visit(node)

    ExecuteVisitor().visit(tree)

    assert not violations, f"Raw self._conn.execute escaped safe boundaries: {violations}"


@pytest.mark.asyncio
async def test_live_mcp_server_survives_shutdown_regression(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    temp_home = tmp_path / "home"
    temp_home.mkdir(parents=True, exist_ok=True)
    temp_data_dir = tmp_path / "elefante-data"
    token = f"pytest-crash-regression-{uuid4().hex[:8]}"
    shared_phrase = f"[{token}] shared MCP shutdown race regression phrase"

    class MCPClient:
        def __init__(self):
            self.process = None
            self._id = 0

        async def start(self):
            real_home = os.environ.get("USERPROFILE") or os.environ.get("HOME", "")
            real_hf_home = os.environ.get("HF_HOME", os.path.join(real_home, ".cache", "huggingface"))
            real_torch_home = os.environ.get("TORCH_HOME", os.path.join(real_home, ".cache", "torch"))
            env = {
                **os.environ,
                "PYTHONPATH": str(project_root),
                "HOME": str(temp_home),
                "USERPROFILE": str(temp_home),
                "ELEFANTE_DATA_DIR": str(temp_data_dir),
                "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
                "HF_HOME": real_hf_home,
                "TORCH_HOME": real_torch_home,
                "SENTENCE_TRANSFORMERS_HOME": os.environ.get(
                    "SENTENCE_TRANSFORMERS_HOME",
                    os.path.join(real_hf_home, "hub"),
                ),
            }
            self.process = await asyncio.create_subprocess_exec(
                sys.executable,
                "-m",
                "src.mcp.server",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(project_root),
                env=env,
            )
            init = await self._send(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "PytestCrashProbe", "version": "1.0"},
                },
            )
            await self._notify("notifications/initialized", {})
            return init

        async def stop(self):
            if self.process is None:
                return
            if self.process.returncode is None:
                self.process.terminate()
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5)
                except asyncio.TimeoutError:
                    self.process.kill()
                    await self.process.wait()

        async def call_tool(self, name, arguments):
            result = await self._send("tools/call", {"name": name, "arguments": arguments})
            if isinstance(result, dict) and "content" in result:
                for block in result["content"]:
                    if block.get("type") == "text":
                        return json.loads(block["text"])
            return result

        async def ensure_alive(self, label):
            await asyncio.sleep(0.35)
            if self.process.returncode is not None:
                stderr = (await self.process.stderr.read()).decode()
                raise RuntimeError(f"{label}: server exited rc={self.process.returncode} stderr={stderr[:1000]}")

        async def _send(self, method, params):
            self._id += 1
            payload = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
            self.process.stdin.write(json.dumps(payload).encode() + b"\n")
            await self.process.stdin.drain()
            line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
            if not line:
                stderr = (await self.process.stderr.read()).decode()
                raise RuntimeError(f"{method}: no response, stderr={stderr[:1000]}")
            response = json.loads(line.decode())
            if "error" in response:
                raise RuntimeError(f"{method}: {response['error']}")
            return response.get("result", response)

        async def _notify(self, method, params):
            payload = {"jsonrpc": "2.0", "method": method, "params": params}
            self.process.stdin.write(json.dumps(payload).encode() + b"\n")
            await self.process.stdin.drain()

    client = MCPClient()
    memory_ids = []

    try:
        init = await client.start()
        assert "capabilities" in init
        await client.ensure_alive("post-initialize")

        for index in range(2):
            search = await client.call_tool(
                "elefante-Memory",
                {"action": "search", "query": shared_phrase, "limit": 5},
            )
            assert search.get("success") is True, search
            assert search.get("gate_status") == "UNLOCKED_ONCE_FOR_THIS_SESSION"
            response = await client.call_tool(
                "elefante-Memory",
                {"action": "add", 
                    "content": f"{shared_phrase} memory {index} with distinct suffix {uuid4().hex[:6]}",
                    "memory_type": "note",
                    "domain": "project",
                    "category": "crash-regression",
                    "tags": [token, "crash-regression", "pytest-live"],
                    "scope": "project:live-mcp-regression",
                    "metadata": {
                        "project": "live-mcp-regression",
                        "workspace": str(project_root),
                    },
                    "force_new": True,
                },
            )
            memory_id = response.get("memory_id")
            assert memory_id, f"MemoryAdd did not return memory_id: {response}"
            memory_ids.append(memory_id)
            await client.ensure_alive(f"after add {index}")

        for round_index in range(3):
            response = await client.call_tool("elefante-Memory", {"action": "search", "query": shared_phrase, "limit": 10})
            tagged = [
                item for item in response.get("results", [])
                if token in item.get("memory", {}).get("content", "")
            ]
            assert len(tagged) >= 2, f"Expected >=2 tagged memories in round {round_index}, got {len(tagged)}"
            await client.ensure_alive(f"after search {round_index}")

        await client.call_tool("elefante-SystemStatusGet", {})
        await client.ensure_alive("after status check")

        for memory_id in memory_ids:
            search = await client.call_tool(
                "elefante-Memory",
                {"action": "search", "query": shared_phrase, "limit": 10},
            )
            assert search.get("success") is True, search
            plan_response = await client.call_tool(
                "elefante-Memory",
                {
                    "action": "correct",
                    "correction": "archive",
                    "memory_id": memory_id,
                },
            )
            assert plan_response.get("correction_status") == "READY", plan_response
            plan = plan_response["plan"]
            response = await client.call_tool(
                "elefante-Memory",
                {
                    "action": "correct",
                    "correction": "archive",
                    "memory_id": memory_id,
                    "apply": True,
                    "reason": f"Cleanup for live MCP crash regression probe {token}",
                    "verification_question": shared_phrase,
                    "expected_record_sha256": plan["record_sha256"],
                    "expected_graph_sha256": plan["graph_sha256"],
                    "invocation_mode": "user_directed",
                },
            )
            assert response.get("success", False), f"Correct archive failed for {memory_id}: {response}"
            assert response.get("correction_status") == "VERIFIED_COMPLETE", response
            await client.ensure_alive(f"after verified archive {memory_id[:8]}")

        final_search = await client.call_tool("elefante-Memory", {"action": "search", "query": shared_phrase, "limit": 10})
        tagged_after_delete = [
            item for item in final_search.get("results", [])
            if token in item.get("memory", {}).get("content", "")
        ]
        assert not tagged_after_delete, f"Archived memories still surfaced: {tagged_after_delete}"
        await client.ensure_alive("after final archive verification")
    finally:
        await client.stop()
    
    @pytest.mark.asyncio
    async def test_hybrid_search_returns_persisted_memories(self, orchestrator):
        """Test that hybrid search finds persisted memories"""
        # Add multiple memories
        test_tag = f"hybrid_test_{uuid4().hex[:8]}"
        
        memories = []
        for i in range(3):
            memory = await orchestrator.add_memory(
                content=f"Hybrid search test memory {i}",
                memory_type="fact",
                tags=[test_tag]
            )
            memories.append(memory)
        
        # Search using hybrid mode
        results = await orchestrator.search_memories(
            query="hybrid search test",
            mode=QueryMode.HYBRID,
            limit=10
        )
        
        # Should find at least some of our memories
        found_count = sum(1 for r in results if test_tag in r.memory.metadata.tags)
        assert found_count > 0, "Hybrid search didn't find any persisted memories"


class TestAbsolutePathResolution:
    """Test that absolute paths prevent database amnesia"""

    @pytest.mark.parametrize("selection", ["yaml", "environment"])
    def test_auxiliary_state_follows_configured_data_root(self, tmp_path, monkeypatch, selection):
        from src.core import directive_store
        from src.mcp.server import ElefanteMCPServer
        from src.utils import config
        from src.utils.logger import get_logger

        untouched = tmp_path / "account-default"
        untouched.mkdir()
        history_name = ElefanteMCPServer._SESSION_HISTORY_FILE
        original = json.dumps({"kind": "explicit-use-v1", "ids": ["unrelated"]})
        (untouched / history_name).write_text(original)
        monkeypatch.setattr(config, "DATA_DIR", untouched)
        monkeypatch.setattr(directive_store, "DIRECTIVES_FILE", untouched / "directives.json")
        monkeypatch.setattr(directive_store, "_store", None)
        monkeypatch.setattr(config, "_config_instance", None)
        monkeypatch.setattr(config.Config, "_instance", None)
        monkeypatch.setattr(config.Config, "_config", None)
        server = object.__new__(ElefanteMCPServer)
        server.logger = get_logger(__name__)

        for name in ("first", "second"):
            active = tmp_path / name / "data"
            configuration = tmp_path / f"{name}.yaml"
            configuration.write_text(json.dumps({"elefante": {"data_dir": str(active)}}))
            monkeypatch.setenv("ELEFANTE_CONFIG_PATH", str(configuration))
            if selection == "environment":
                configuration.write_text("elefante: {}\n")
                monkeypatch.setenv("ELEFANTE_DATA_DIR", str(active))
            else:
                monkeypatch.delenv("ELEFANTE_DATA_DIR", raising=False)
            store = directive_store.DirectiveStore(profile="client")
            assert store._path == active / "directives.json"
            assert store.user_count() == 0
            store.add(f"Keep {name} separate")
            assert directive_store.DirectiveStore(profile="client").user_count() == 1
            assert directive_store.get_directive_store()._path == active / "directives.json"
            assert directive_store.get_directive_store().user_count() == 1
            assert server._load_session_history() == []
            server._session_usage_history = [name]
            server._save_session_history()
            assert server._load_session_history() == [name]
            assert json.loads((active / history_name).read_text())["ids"] == [name]

        assert (untouched / history_name).read_text() == original
        assert not (untouched / "directives.json").exists()
    
    def test_config_uses_absolute_paths(self):
        """Verify that config.py uses absolute paths for databases"""
        from src.utils.config import CHROMA_DIR, KUZU_DIR, DATA_DIR
        
        # All paths should be absolute
        assert CHROMA_DIR.is_absolute(), "CHROMA_DIR is not absolute"
        assert KUZU_DIR.is_absolute(), "KUZU_DIR is not absolute"
        assert DATA_DIR.is_absolute(), "DATA_DIR is not absolute"
    
    def test_config_paths_exist(self):
        """Verify eager runtime roots and the configured store-path contract."""
        from src.utils.config import DATA_DIR, LOGS_DIR, get_config
        
        # Safe runtime directories are created eagerly.
        assert DATA_DIR.exists(), f"DATA_DIR does not exist: {DATA_DIR}"
        assert LOGS_DIR.exists(), f"LOGS_DIR does not exist: {LOGS_DIR}"

        # Config owns the active vector directory; the graph store owns its
        # database path and materializes it lazily.
        config = get_config().elefante
        configured_data_dir = Path(config.data_dir)
        vector_dir = Path(config.vector_store.persist_directory)
        graph_path = Path(config.graph_store.database_path)
        assert configured_data_dir.is_dir(), f"Configured data directory does not exist: {configured_data_dir}"
        assert vector_dir.parent == configured_data_dir, (
            f"Vector path is not rooted under configured data directory: {vector_dir}"
        )
        assert vector_dir.is_dir(), f"Configured vector directory does not exist: {vector_dir}"
        assert graph_path.parent == configured_data_dir, (
            f"Graph path is not rooted under configured data directory: {graph_path}"
        )
        if graph_path.exists():
            assert graph_path.is_file() or graph_path.is_dir(), (
                f"Graph path exists but is not a regular filesystem node: {graph_path}"
            )

    def test_config_uses_active_vector_path_without_legacy_chroma_in_a_fresh_home(self, tmp_path):
        """A clean SQLite install creates its active path, not retired Chroma state."""
        repo_root = Path(__file__).resolve().parents[1]
        script = """
from pathlib import Path
from src.utils.config import CHROMA_DIR, DATA_DIR, KUZU_DIR, LOGS_DIR, get_config
config = get_config()
vector_dir = Path(config.elefante.vector_store.persist_directory)
assert DATA_DIR.is_dir()
assert LOGS_DIR.is_dir()
assert vector_dir == DATA_DIR / "vector"
assert vector_dir.is_dir()
assert not CHROMA_DIR.exists()
assert not KUZU_DIR.exists()
"""
        env = {
            **os.environ,
            "HOME": str(tmp_path),
            "USERPROFILE": str(tmp_path),
            "PYTHONPATH": str(repo_root),
            "ELEFANTE_CONFIG_PATH": str(repo_root / "config.yaml"),
        }
        env.pop("ELEFANTE_DATA_DIR", None)
        env.pop("ELEFANTE_VECTOR_STORE_TYPE", None)

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr
    
    def test_vector_store_config_uses_absolute_path(self):
        """Verify VectorStoreConfig has absolute path"""
        from src.utils.config import get_config
        
        config = get_config()
        persist_dir = Path(config.elefante.vector_store.persist_directory)
        
        assert persist_dir.is_absolute(), "Vector store persist_directory is not absolute"
    
    def test_graph_store_config_uses_absolute_path(self):
        """Verify GraphStoreConfig has absolute path"""
        from src.utils.config import get_config
        
        config = get_config()
        db_path = Path(config.elefante.graph_store.database_path)
        
        assert db_path.is_absolute(), "Graph store database_path is not absolute"


class TestKuzuLockContract:
    """Guards the live Kuzu path and contention contract used by Elefante."""

    def test_graph_store_database_path_materializes_as_file(self, tmp_path):
        """Fresh GraphStore init should materialize the Kuzu path as a file."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))

        try:
            store._initialize_connection()
            assert db_path.exists(), f"Kuzu database path was not created: {db_path}"
            assert db_path.is_file(), f"Fresh Kuzu database path is not a file: {db_path}"
        finally:
            store.close()

    def test_cross_process_kuzu_lock_error_cites_issue_2(self, tmp_path):
        """A competing process must surface the Issue #2 runtime citation."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))
        repo_root = Path(__file__).resolve().parents[1]

        env = os.environ.copy()
        current_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{repo_root}{os.pathsep}{current_pythonpath}"
            if current_pythonpath
            else str(repo_root)
        )

        child_code = """
from src.core.graph_store import GraphStore
import sys

store = GraphStore(database_path=sys.argv[1], read_only=True)
try:
    store._initialize_connection()
    print('open-ok')
except Exception as exc:
    print(type(exc).__name__)
    print(str(exc))
finally:
    store.close()
"""

        try:
            store._initialize_connection()
            result = subprocess.run(
                [sys.executable, "-c", child_code, str(db_path)],
                capture_output=True,
                text=True,
                cwd=str(repo_root),
                env=env,
                check=False,
            )
        finally:
            store.close()

        output = result.stdout.strip()
        assert "RuntimeError" in output, output
        assert "workspace/postmortems/database.md Issue #2" in output, output
        assert "Database path:" in output, output
        assert "open-ok" not in output, output

    def test_dashboard_lock_avoidance_uses_snapshot_and_read_only_export(self):
        """Dashboard lock avoidance must stay on snapshot + read-only export."""
        repo_root = Path(__file__).resolve().parents[1]
        dashboard_source = (repo_root / "src" / "dashboard" / "server.py").read_text(encoding="utf-8")
        export_source = (repo_root / "scripts" / "pipeline" / "update_dashboard_data.py").read_text(encoding="utf-8")
        export_tree = ast.parse(export_source)

        assert "dashboard_snapshot.json" in dashboard_source
        assert "from src.core.graph_store" not in dashboard_source
        assert "import kuzu" not in dashboard_source

        found_read_only_graph_store = False
        for node in ast.walk(export_tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Name) or node.func.id != "GraphStore":
                continue
            for keyword in node.keywords:
                if keyword.arg != "read_only":
                    continue
                if isinstance(keyword.value, ast.Constant) and keyword.value.value is True:
                    found_read_only_graph_store = True
                    break

        assert found_read_only_graph_store, "Snapshot export no longer opens GraphStore(read_only=True)"

    def test_active_kuzu_docs_do_not_reference_internal_lock_path(self):
        """Active docs must not send users to a stale kuzu_db/.lock recovery path."""
        repo_root = Path(__file__).resolve().parents[1]
        active_docs = [
            repo_root / "docs" / "how-to" / "kuzu-troubleshooting.md",
            repo_root / "docs" / "how-to" / "view-dashboard.html",
            repo_root / "docs" / "how-to" / "run-mcp-server.md",
        ]

        for doc_path in active_docs:
            text = doc_path.read_text(encoding="utf-8")
            assert "kuzu_db/.lock" not in text, f"{doc_path.name} still references stale kuzu_db/.lock recovery"


class TestGraphToolContract:
    """Guards graph/session tool assumptions exposed by the self-protocol."""

    @pytest.mark.asyncio
    async def test_graph_relationship_tables_support_created_in_and_works_on(self, tmp_path):
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))

        memory_entity = Entity(name="Protocol Memory", type=EntityType.MEMORY)
        session_entity = Entity(name="Protocol Session", type=EntityType.SESSION)
        project_entity = Entity(name="Protocol Project", type=EntityType.PROJECT)

        try:
            await store.create_entity(memory_entity)
            await store.create_entity(session_entity)
            await store.create_entity(project_entity)

            await store.create_relationship(
                Relationship(
                    from_entity_id=memory_entity.id,
                    to_entity_id=session_entity.id,
                    relationship_type=RelationshipType.CREATED_IN,
                )
            )
            await store.create_relationship(
                Relationship(
                    from_entity_id=session_entity.id,
                    to_entity_id=project_entity.id,
                    relationship_type=RelationshipType.WORKS_ON,
                )
            )

            created_in_rows = await store.execute_query(
                "MATCH (a:Entity)-[r:CREATED_IN]->(b:Entity) RETURN a.id, b.id"
            )
            works_on_rows = await store.execute_query(
                "MATCH (a:Entity)-[r:WORKS_ON]->(b:Entity) RETURN a.id, b.id"
            )

            assert any(
                row.get("a.id") == str(memory_entity.id) and row.get("b.id") == str(session_entity.id)
                for row in created_in_rows
            )
            assert any(
                row.get("a.id") == str(session_entity.id) and row.get("b.id") == str(project_entity.id)
                for row in works_on_rows
            )
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_all_advertised_types_round_trip_full_payload(self, tmp_path):
        """Every public relationship enum must persist and read back its full payload."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))
        source = Entity(name="Relationship Source", type=EntityType.PROJECT)
        target = Entity(name="Relationship Target", type=EntityType.CONCEPT)
        expected_by_type = {}
        base_created_at = datetime(
            2026,
            9,
            3,
            12,
            34,
            56,
            789000,
            tzinfo=timezone(timedelta(hours=-4)),
        )

        try:
            await store.create_entity(source)
            await store.create_entity(target)

            for index, relationship_type in enumerate(RelationshipType):
                relationship = Relationship(
                    id=uuid4(),
                    from_entity_id=source.id,
                    to_entity_id=target.id,
                    relationship_type=relationship_type,
                    description=f"Description for {relationship_type.value}",
                    created_at=base_created_at + timedelta(microseconds=index),
                    strength=round((index + 1) / (len(RelationshipType) + 1), 6),
                    properties={
                        "custom_key": f"custom-{relationship_type.value}",
                        "ordinal": index,
                        "nested": {"relationship_type": relationship_type.value},
                    },
                )
                assert await store.create_relationship(relationship) == relationship.id
                expected_by_type[relationship_type] = relationship

            actual_relationships = await store.get_relationships(source.id, "outgoing")
            assert len(actual_relationships) == len(expected_by_type)
            actual_by_type = {relationship.relationship_type: relationship for relationship in actual_relationships}
            assert set(actual_by_type) == set(expected_by_type)

            for relationship_type, expected in expected_by_type.items():
                actual = actual_by_type[relationship_type]
                assert actual.id == expected.id
                assert actual.from_entity_id == expected.from_entity_id
                assert actual.to_entity_id == expected.to_entity_id
                assert actual.relationship_type == expected.relationship_type
                assert actual.description == expected.description
                assert actual.properties == expected.properties
                assert actual.created_at == expected.created_at
                assert actual.strength == expected.strength
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_created_in_datetime_property_round_trips_as_iso(self, tmp_path):
        """The real CREATED_IN caller's datetime property is JSON-encoded and readable."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))
        memory_entity = Entity(name="Datetime Memory", type=EntityType.MEMORY)
        session_entity = Entity(name="Datetime Session", type=EntityType.SESSION)
        property_created_at = datetime(2026, 9, 3, 14, 15, 16, 123456)
        relationship = Relationship(
            id=uuid4(),
            from_entity_id=memory_entity.id,
            to_entity_id=session_entity.id,
            relationship_type=RelationshipType.CREATED_IN,
            properties={"created_at": property_created_at},
        )

        try:
            await store.create_entity(memory_entity)
            await store.create_entity(session_entity)
            assert await store.create_relationship(relationship) == relationship.id

            raw_rows = await store.execute_query(
                """
                MATCH (fromNode:Entity)-[r:CREATED_IN]->(toNode:Entity)
                WHERE fromNode.id = $from_id AND toNode.id = $to_id
                RETURN r.props AS props
                """,
                {"from_id": str(memory_entity.id), "to_id": str(session_entity.id)},
            )
            assert len(raw_rows) == 1
            expected_properties = {"created_at": property_created_at.isoformat()}
            assert json.loads(raw_rows[0]["props"]) == expected_properties

            actual = await store.get_relationships(session_entity.id, "incoming")
            assert len(actual) == 1
            assert actual[0].properties == expected_properties
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_missing_endpoints_fail_without_edges_for_all_types(self, tmp_path):
        """No advertised relationship type may report success for absent endpoints."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))
        source = Entity(name="Existing Source", type=EntityType.PROJECT)
        target = Entity(name="Existing Target", type=EntityType.CONCEPT)

        try:
            await store.create_entity(source)
            await store.create_entity(target)
            missing_endpoint_cases = (
                (uuid4(), target.id),
                (source.id, uuid4()),
                (uuid4(), uuid4()),
            )

            for from_entity_id, to_entity_id in missing_endpoint_cases:
                for relationship_type in RelationshipType:
                    with pytest.raises(ValueError):
                        await store.create_relationship(
                            Relationship(
                                id=uuid4(),
                                from_entity_id=from_entity_id,
                                to_entity_id=to_entity_id,
                                relationship_type=relationship_type,
                            )
                        )

                    assert await store.get_relationships(source.id, "both") == []
                    assert await store.get_relationships(target.id, "both") == []
                    rows = await store.execute_query(
                        "MATCH (a:Entity)-[r]->(b:Entity) RETURN a.id, b.id, label(r)"
                    )
                    assert rows == []
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_reads_preserve_direction_and_skip_internal_edges(self, tmp_path):
        """Incoming and both-direction reads expose one public edge in its stored direction."""
        db_path = tmp_path / "kuzu_db"
        store = GraphStore(database_path=str(db_path))
        source = Entity(name="Directional Source", type=EntityType.PROJECT)
        target = Entity(name="Directional Target", type=EntityType.CONCEPT)
        relationship = Relationship(
            id=uuid4(),
            from_entity_id=source.id,
            to_entity_id=target.id,
            relationship_type=RelationshipType.GOVERNS,
            description="Governing edge",
            created_at=datetime(2026, 9, 3, 13, 14, 15, 123456, tzinfo=timezone.utc),
            strength=0.73,
            properties={"source": "contract-test", "ordinal": 1},
        )

        try:
            await store.create_entity(source)
            await store.create_entity(target)
            await store.create_relationship(relationship)
            await store.execute_query(
                """
                MATCH (fromNode:Entity), (toNode:Entity)
                WHERE fromNode.id = $from_id AND toNode.id = $to_id
                CREATE (fromNode)-[r:CO_ACTIVATED {
                    strength: $strength,
                    last_coactivated: $last_coactivated
                }]->(toNode)
                """,
                {
                    "from_id": str(source.id),
                    "to_id": str(target.id),
                    "strength": 0.5,
                    "last_coactivated": "contract-test",
                },
            )

            incoming = await store.get_relationships(target.id, "incoming")
            both = await store.get_relationships(target.id, "both")
            outgoing = await store.get_relationships(source.id, "outgoing")

            for actual_relationships in (incoming, both, outgoing):
                assert len(actual_relationships) == 1
                actual = actual_relationships[0]
                assert actual.id == relationship.id
                assert actual.from_entity_id == source.id
                assert actual.to_entity_id == target.id
                assert actual.relationship_type is RelationshipType.GOVERNS
                assert actual.description == relationship.description
                assert actual.properties == relationship.properties
                assert actual.created_at == relationship.created_at
                assert actual.strength == relationship.strength
        finally:
            store.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_legacy_rows_survive_reopen_with_stable_read_identity(self, tmp_path):
        """A genuinely old schema upgrades additively without changing legacy rows."""
        db_path = tmp_path / "kuzu_db"
        source = Entity(name="Legacy Source", type=EntityType.PROJECT)
        target = Entity(name="Legacy Target", type=EntityType.CONCEPT)
        legacy_strength = 0.41

        class LegacyGraphStore(GraphStore):
            """Seed the pre-repair relationship schema without migration."""

            def _ensure_relationship_schema(self) -> None:
                pass

        seed_store = LegacyGraphStore(database_path=str(db_path))
        try:
            await seed_store.create_entity(source)
            await seed_store.create_entity(target)
            legacy_schema_rows = await seed_store.execute_query(
                "CALL table_info('RELATES_TO') RETURN *"
            )
            legacy_schema_columns = {row["name"] for row in legacy_schema_rows}
            assert "id" not in legacy_schema_columns
            assert "props" not in legacy_schema_columns
            await seed_store.execute_query(
                """
                MATCH (fromNode:Entity), (toNode:Entity)
                WHERE fromNode.id = $from_id AND toNode.id = $to_id
                CREATE (fromNode)-[r:RELATES_TO {strength: $strength}]->(toNode)
                """,
                {
                    "from_id": str(source.id),
                    "to_id": str(target.id),
                    "strength": legacy_strength,
                },
            )
        finally:
            seed_store.close()

        store = GraphStore(database_path=str(db_path))
        try:
            raw_rows = await store.execute_query(
                """
                MATCH (fromNode:Entity)-[r:RELATES_TO]->(toNode:Entity)
                WHERE fromNode.id = $from_id AND toNode.id = $to_id
                RETURN fromNode.id AS from_id,
                       toNode.id AS to_id,
                       label(r) AS relationship_type,
                       r.id AS relationship_id,
                       r.description AS description,
                       r.created_at AS created_at,
                       r.strength AS strength,
                       r.props AS props
                """,
                {"from_id": str(source.id), "to_id": str(target.id)},
            )
            upgraded_schema_rows = await store.execute_query(
                "CALL table_info('RELATES_TO') RETURN *"
            )
            upgraded_schema_columns = {row["name"] for row in upgraded_schema_rows}
            assert {"id", "props"}.issubset(upgraded_schema_columns)
            assert len(raw_rows) == 1
            raw = raw_rows[0]
            assert raw["from_id"] == str(source.id)
            assert raw["to_id"] == str(target.id)
            assert raw["relationship_type"] == RelationshipType.RELATES_TO.value
            assert raw["relationship_id"] is None
            assert raw["description"] is None
            assert raw["created_at"] is None
            assert raw["strength"] == legacy_strength
            assert raw["props"] is None

            incoming = await store.get_relationships(target.id, "incoming")
            both = await store.get_relationships(target.id, "both")
            assert len(incoming) == 1
            assert len(both) == 1
            legacy = incoming[0]
            assert legacy.id is not None
            assert legacy.id.version == 5
            assert both[0].id == legacy.id
            assert legacy.from_entity_id == source.id
            assert legacy.to_entity_id == target.id
            assert legacy.relationship_type is RelationshipType.RELATES_TO
            assert legacy.description is None
            assert legacy.properties == {}
            assert legacy.created_at is None
            assert legacy.strength == legacy_strength
            legacy_read_identity = legacy.id
        finally:
            store.close()

        reopened = GraphStore(database_path=str(db_path))
        try:
            after_reopen = await reopened.get_relationships(target.id, "incoming")
            assert len(after_reopen) == 1
            assert after_reopen[0].id == legacy_read_identity
            assert after_reopen[0].from_entity_id == source.id
            assert after_reopen[0].to_entity_id == target.id
            assert after_reopen[0].created_at is None
            assert after_reopen[0].strength == legacy_strength
        finally:
            reopened.close()

    @pytest.mark.asyncio
    async def test_graph_relationship_legacy_type_specific_properties_survive_migration(self, tmp_path):
        """Old table-specific relationship fields remain public properties after upgrade."""
        db_path = tmp_path / "kuzu_db"
        source = Entity(name="Legacy Reference Source", type=EntityType.PROJECT)
        target = Entity(name="Legacy Reference Target", type=EntityType.CONCEPT)
        legacy_reference_type = "legacy-citation"

        class LegacyGraphStore(GraphStore):
            """Seed the pre-repair relationship schema without migration."""

            def _ensure_relationship_schema(self) -> None:
                pass

        seed_store = LegacyGraphStore(database_path=str(db_path))
        try:
            await seed_store.create_entity(source)
            await seed_store.create_entity(target)
            legacy_schema_rows = await seed_store.execute_query(
                "CALL table_info('REFERENCES') RETURN *"
            )
            legacy_schema_columns = {row["name"] for row in legacy_schema_rows}
            assert "reference_type" in legacy_schema_columns
            assert "id" not in legacy_schema_columns
            assert "props" not in legacy_schema_columns
            await seed_store.execute_query(
                """
                MATCH (fromNode:Entity), (toNode:Entity)
                WHERE fromNode.id = $from_id AND toNode.id = $to_id
                CREATE (fromNode)-[r:REFERENCES {reference_type: $reference_type}]->(toNode)
                """,
                {
                    "from_id": str(source.id),
                    "to_id": str(target.id),
                    "reference_type": legacy_reference_type,
                },
            )
        finally:
            seed_store.close()

        store = GraphStore(database_path=str(db_path))
        try:
            upgraded_schema_rows = await store.execute_query(
                "CALL table_info('REFERENCES') RETURN *"
            )
            upgraded_schema_columns = {row["name"] for row in upgraded_schema_rows}
            assert {"reference_type", "id", "props"}.issubset(upgraded_schema_columns)

            relationships = await store.get_relationships(target.id, "incoming")
            assert len(relationships) == 1
            legacy = relationships[0]
            assert legacy.from_entity_id == source.id
            assert legacy.to_entity_id == target.id
            assert legacy.relationship_type is RelationshipType.REFERENCES
            assert legacy.properties == {"reference_type": legacy_reference_type}
        finally:
            store.close()

    def test_sessions_list_handler_uses_entity_created_at_and_props(self):
        repo_root = Path(__file__).resolve().parents[1]
        server_source = (repo_root / "src" / "mcp" / "server.py").read_text(encoding="utf-8")

        assert "ORDER BY s.created_at DESC" in server_source
        assert "session.get(\"props\")" in server_source
        assert "json.loads(props_raw)" in server_source
        assert "ORDER BY s.last_active DESC" not in server_source
