"""
Tests for memory persistence - verifies that memories are stored directly
in ChromaDB and Kuzu without generating temporary scripts.

This test suite ensures the write-path architecture is correct.
"""

import pytest
import asyncio
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
            importance=7,
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
            importance=8,
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
            memory_type="note",
            importance=5
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
            memory_type="conversation",
            importance=6
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
            importance=6,
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
            importance=7,
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
    async def test_hybrid_search_returns_persisted_memories(self, orchestrator):
        """Test that hybrid search finds persisted memories"""
        # Add multiple memories
        test_tag = f"hybrid_test_{uuid4().hex[:8]}"
        
        memories = []
        for i in range(3):
            memory = await orchestrator.add_memory(
                content=f"Hybrid search test memory {i}",
                memory_type="fact",
                importance=5 + i,
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
        """Verify that database directories are created"""
        from src.utils.config import CHROMA_DIR, KUZU_DIR, DATA_DIR, LOGS_DIR
        
        # Directories should exist
        assert DATA_DIR.exists(), f"DATA_DIR does not exist: {DATA_DIR}"
        assert CHROMA_DIR.exists(), f"CHROMA_DIR does not exist: {CHROMA_DIR}"
        assert KUZU_DIR.exists(), f"KUZU_DIR does not exist: {KUZU_DIR}"
        assert LOGS_DIR.exists(), f"LOGS_DIR does not exist: {LOGS_DIR}"
    
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


