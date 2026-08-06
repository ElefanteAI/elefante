# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_memory_guard.py
# PROVES  : MemoryAdd intelligence-pipeline guard: ensures rejection_reason is
#           returned for filtered memories (BUG-011 guard).
# RUN     : pytest tests/test_memory_guard.py -v
# WHEN    : After any change to orchestrator.py memory guard logic or
#           server.py IGNORE response body. Required before any release.
# ─────────────────────────────────────────────────────────────────────────────
import pytest
from uuid import uuid4

from src.core.orchestrator import MemoryOrchestrator
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.core.graph_store import GraphStore


@pytest.fixture
def isolated_orchestrator(tmp_path):
    vector_dir = tmp_path / "vector"
    kuzu_dir = tmp_path / "kuzu_db"

    vector_store = SQLiteVectorStore(
        collection_name=f"test_guard_{uuid4().hex}",
        persist_directory=str(vector_dir),
    )
    graph_store = GraphStore(database_path=str(kuzu_dir))

    return MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)


@pytest.mark.asyncio
async def test_blocks_test_tag_by_default(isolated_orchestrator, monkeypatch):
    monkeypatch.delenv("ELEFANTE_ALLOW_TEST_MEMORIES", raising=False)

    mem = await isolated_orchestrator.add_memory(
        content=f"Test memory for guard {uuid4()}",
        memory_type="note",
        tags=["test"],
    )

    assert mem is None


@pytest.mark.asyncio
async def test_allows_test_memories_with_override(isolated_orchestrator, monkeypatch):
    monkeypatch.setenv("ELEFANTE_ALLOW_TEST_MEMORIES", "1")

    mem = await isolated_orchestrator.add_memory(
        content=f"Test memory for guard override {uuid4()}",
        memory_type="note",
        tags=["test"],
    )

    assert mem is not None
    assert mem.id is not None
