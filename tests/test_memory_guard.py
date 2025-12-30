import pytest
from uuid import uuid4

from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore


@pytest.fixture
def isolated_orchestrator(tmp_path):
    chroma_dir = tmp_path / "chroma"
    kuzu_dir = tmp_path / "kuzu_db"

    vector_store = VectorStore(
        collection_name=f"test_guard_{uuid4().hex}",
        persist_directory=str(chroma_dir),
    )
    graph_store = GraphStore(database_path=str(kuzu_dir))

    return MemoryOrchestrator(vector_store=vector_store, graph_store=graph_store)


@pytest.mark.asyncio
async def test_blocks_test_tag_by_default(isolated_orchestrator, monkeypatch):
    monkeypatch.delenv("ELEFANTE_ALLOW_TEST_MEMORIES", raising=False)

    mem = await isolated_orchestrator.add_memory(
        content=f"Test memory for guard {uuid4()}",
        memory_type="note",
        importance=5,
        tags=["test"],
    )

    assert mem is None


@pytest.mark.asyncio
async def test_allows_test_memories_with_override(isolated_orchestrator, monkeypatch):
    monkeypatch.setenv("ELEFANTE_ALLOW_TEST_MEMORIES", "1")

    mem = await isolated_orchestrator.add_memory(
        content=f"Test memory for guard override {uuid4()}",
        memory_type="note",
        importance=5,
        tags=["test"],
        metadata={"namespace": "test", "category": "test"},
    )

    assert mem is not None
    assert mem.id is not None
