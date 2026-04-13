"""
Tests for memory persistence - verifies that memories are stored directly
in ChromaDB and Kuzu without generating temporary scripts.

This test suite ensures the write-path architecture is correct.
"""

import ast
import json
import os
import pytest
import asyncio
import sys
import threading
from uuid import uuid4
from pathlib import Path

from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.models.query import QueryMode


class TestMemoryPersistence:
    """Test that memories persist correctly in both databases"""
    
    @pytest.fixture
    def orchestrator(self, tmp_path, monkeypatch):
        """Create an orchestrator isolated to a temp DB (no shared locks)"""
        monkeypatch.setenv("ELEFANTE_ALLOW_TEST_MEMORIES", "1")
        chroma_dir = tmp_path / "chroma"
        kuzu_dir = tmp_path / "kuzu_db"

        vector_store = VectorStore(
            collection_name=f"test_memory_persistence_{uuid4().hex}",
            persist_directory=str(chroma_dir),
        )
        graph_store = GraphStore(database_path=str(kuzu_dir))

        orch = MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)
        orch._test_chroma_dir = chroma_dir
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
        new_vector_store = VectorStore(
            collection_name=orchestrator._test_collection_name,
            persist_directory=str(orchestrator._test_chroma_dir),
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

        # New VectorStore instance simulates a restart / new process.
        new_vector_store = VectorStore(
            collection_name=orchestrator._test_collection_name,
            persist_directory=str(orchestrator._test_chroma_dir),
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
            env = {
                **os.environ,
                "PYTHONPATH": str(project_root),
                "HOME": str(temp_home),
                "USERPROFILE": str(temp_home),
                "ELEFANTE_DATA_DIR": str(temp_data_dir),
                "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
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

        initial = await client.call_tool("elefante-MemorySearch", {"query": shared_phrase, "limit": 5})
        assert isinstance(initial, dict)
        await client.ensure_alive("after initial search")

        for index in range(2):
            response = await client.call_tool(
                "elefante-MemoryAdd",
                {
                    "content": f"{shared_phrase} memory {index} with distinct suffix {uuid4().hex[:6]}",
                    "memory_type": "note",
                    "domain": "project",
                    "category": "crash-regression",
                    "tags": [token, "crash-regression", "pytest-live"],
                    "force_new": True,
                },
            )
            memory_id = response.get("memory_id")
            assert memory_id, f"MemoryAdd did not return memory_id: {response}"
            memory_ids.append(memory_id)
            await client.ensure_alive(f"after add {index}")

        for round_index in range(3):
            response = await client.call_tool("elefante-MemorySearch", {"query": shared_phrase, "limit": 10})
            tagged = [
                item for item in response.get("results", [])
                if token in item.get("memory", {}).get("content", "")
            ]
            assert len(tagged) >= 2, f"Expected >=2 tagged memories in round {round_index}, got {len(tagged)}"
            await client.ensure_alive(f"after search {round_index}")

        await client.call_tool("elefante-SystemStatusGet", {})
        await client.ensure_alive("after status check")

        for memory_id in memory_ids:
            response = await client.call_tool(
                "elefante-MemoryDelete",
                {
                    "memory_id": memory_id,
                    "reason": f"Cleanup for live MCP crash regression probe {token}",
                },
            )
            assert response.get("success", False), f"MemoryDelete failed for {memory_id}: {response}"
            await client.ensure_alive(f"after delete {memory_id[:8]}")

        final_search = await client.call_tool("elefante-MemorySearch", {"query": shared_phrase, "limit": 10})
        tagged_after_delete = [
            item for item in final_search.get("results", [])
            if token in item.get("memory", {}).get("content", "")
        ]
        assert not tagged_after_delete, f"Deleted memories still surfaced after delete: {tagged_after_delete}"
        await client.ensure_alive("after final delete verification")
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
    
    def test_config_uses_absolute_paths(self):
        """Verify that config.py uses absolute paths for databases"""
        from src.utils.config import CHROMA_DIR, KUZU_DIR, DATA_DIR
        
        # All paths should be absolute
        assert CHROMA_DIR.is_absolute(), "CHROMA_DIR is not absolute"
        assert KUZU_DIR.is_absolute(), "KUZU_DIR is not absolute"
        assert DATA_DIR.is_absolute(), "DATA_DIR is not absolute"
    
    def test_config_paths_exist(self):
        """Verify the configured runtime directories reflect the current lazy-Kuzu contract."""
        from src.utils.config import CHROMA_DIR, KUZU_DIR, DATA_DIR, LOGS_DIR
        
        # Safe runtime directories are created eagerly.
        assert DATA_DIR.exists(), f"DATA_DIR does not exist: {DATA_DIR}"
        assert CHROMA_DIR.exists(), f"CHROMA_DIR does not exist: {CHROMA_DIR}"
        assert LOGS_DIR.exists(), f"LOGS_DIR does not exist: {LOGS_DIR}"

        # Kuzu manages its own directory lifecycle and should not be pre-created
        # by config import. The configured path must still resolve correctly.
        assert KUZU_DIR.parent == DATA_DIR, f"KUZU_DIR is not rooted under DATA_DIR: {KUZU_DIR}"
        if KUZU_DIR.exists():
            assert KUZU_DIR.is_dir(), f"KUZU_DIR exists but is not a directory: {KUZU_DIR}"
    
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


