# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/conftest.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PROVES  : Shared pytest fixtures and test configuration for the whole suite.
# RUN     : loaded automatically by pytest — do not run directly.
# WHEN    : Modify when adding new shared fixtures, changing temp-dir setup,
#           or adjusting test-wide environment variables.
# ─────────────────────────────────────────────────────────────────────────────
"""
Pytest configuration and shared fixtures for Elefante test suite.
"""

import pytest
import os
from uuid import uuid4


@pytest.fixture(autouse=True)
def allow_test_memories(monkeypatch):
    """Allow test memories by default in all tests"""
    monkeypatch.setenv("ELEFANTE_ALLOW_TEST_MEMORIES", "1")


@pytest.fixture
def isolated_orchestrator(tmp_path, monkeypatch):
    """
    Create an orchestrator with isolated temporary databases.
    
    This fixture creates fresh ChromaDB and Kuzu databases in a temporary
    directory that is cleaned up after the test.
    """
    from src.core.orchestrator import MemoryOrchestrator
    from src.core.vector_store import VectorStore
    from src.core.graph_store import GraphStore
    
    chroma_dir = tmp_path / "chroma"
    kuzu_dir = tmp_path / "kuzu_db"
    
    vector_store = VectorStore(
        collection_name=f"test_{uuid4().hex}",
        persist_directory=str(chroma_dir),
    )
    graph_store = GraphStore(database_path=str(kuzu_dir))
    
    orch = MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)
    
    # Store references for tests that need to recreate stores
    orch._test_chroma_dir = chroma_dir
    orch._test_collection_name = vector_store.collection_name
    orch._test_kuzu_dir = kuzu_dir
    
    return orch


@pytest.fixture
def isolated_vector_store(tmp_path):
    """Create an isolated vector store for unit tests"""
    from src.core.vector_store import VectorStore
    
    chroma_dir = tmp_path / "chroma"
    return VectorStore(
        collection_name=f"test_{uuid4().hex}",
        persist_directory=str(chroma_dir),
    )


@pytest.fixture
def isolated_graph_store(tmp_path):
    """Create an isolated graph store for unit tests"""
    from src.core.graph_store import GraphStore
    
    kuzu_dir = tmp_path / "kuzu_db"
    return GraphStore(database_path=str(kuzu_dir))
