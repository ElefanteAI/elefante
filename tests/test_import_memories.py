"""Safety and round-trip tests for the portable JSON memory importer."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from scripts.pipeline.import_memories import (
    ImportApplyError,
    ImportValidationError,
    apply_import,
    build_import_plan,
    load_import_memories,
)
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.models.memory import Memory, MemoryMetadata, MemoryType


class FakeVectorStore:
    def __init__(self, memories: list[Memory] | None = None, fail_on_add: int | None = None):
        self.memories = {str(memory.id): memory for memory in memories or []}
        self.collection_name = "memories"
        self.persist_directory = "/tmp/elefante-test-vector"
        self.fail_on_add = fail_on_add
        self.add_calls = 0
        self.delete_calls: list[str] = []

    async def get_all(self, limit: int = 100, offset: int = 0) -> list[Memory]:
        values = list(self.memories.values())
        return values[offset : offset + limit]

    async def add_memory(self, memory: Memory) -> str:
        self.add_calls += 1
        if self.fail_on_add is not None and self.add_calls == self.fail_on_add:
            raise RuntimeError("simulated vector-store write failure")
        if str(memory.id) in self.memories:
            raise RuntimeError("duplicate ID")
        self.memories[str(memory.id)] = memory
        return str(memory.id)

    async def delete_memory(self, memory_id: UUID) -> bool:
        key = str(memory_id)
        self.delete_calls.append(key)
        return self.memories.pop(key, None) is not None


class FakeEmbeddingService:
    def __init__(self, dimension: int = 3, vectors: list[list[float]] | None = None):
        self.dimension = dimension
        self.vectors = vectors
        self.calls: list[list[str]] = []

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        if self.vectors is not None:
            return self.vectors
        return [[float(index + 1)] * self.dimension for index, _ in enumerate(texts)]

    def get_embedding_dimension(self) -> int:
        return self.dimension


def _memory(content: str = "A portable memory") -> Memory:
    return Memory(
        id=uuid4(),
        content=content,
        metadata=MemoryMetadata(
            memory_type=MemoryType.DECISION,
            access_count=7,
            custom_metadata={"title": "Portable decision", "custom": {"keep": True}},
        ),
    )


def _write_export(path: Path, memories: list[Memory], *, count: int | None = None) -> None:
    payload = {
        "exported_at": "2026-08-27T00:00:00+00:00",
        "count": len(memories) if count is None else count,
        "vector_store_type": "sqlite",
        "collection": "memories",
        "memories": [memory.to_dict() for memory in memories],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_load_import_preserves_identity_and_metadata_but_discards_input_embedding(tmp_path: Path):
    source = _memory()
    record = source.to_dict()
    record["embedding"] = [999.0]
    path = tmp_path / "export.json"
    path.write_text(
        json.dumps({"count": 1, "memories": [record]}),
        encoding="utf-8",
    )

    loaded = load_import_memories(path)

    assert len(loaded) == 1
    assert loaded[0].id == source.id
    assert loaded[0].content == source.content
    assert loaded[0].metadata.access_count == 7
    assert loaded[0].metadata.custom_metadata["custom"] == {"keep": True}
    assert loaded[0].embedding is None


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda records: records + [records[0]], "duplicate id"),
        (lambda records: [{"content": "missing identity", "metadata": {}}], "requires a string id"),
    ],
)
def test_load_import_rejects_ambiguous_records(tmp_path: Path, mutator, message: str):
    memories = [_memory()]
    records = [memory.to_dict() for memory in memories]
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps({"count": len(mutator(records)), "memories": mutator(records)}),
        encoding="utf-8",
    )

    with pytest.raises(ImportValidationError, match=message):
        load_import_memories(path)


def test_load_import_rejects_count_mismatch(tmp_path: Path):
    path = tmp_path / "invalid-count.json"
    _write_export(path, [_memory()], count=2)

    with pytest.raises(ImportValidationError, match="does not match"):
        load_import_memories(path)


@pytest.mark.asyncio
async def test_plan_is_read_only_and_apply_regenerates_embeddings(tmp_path: Path):
    source = _memory("Preserve this durable decision")
    path = tmp_path / "export.json"
    _write_export(path, [source])
    store = FakeVectorStore()
    embeddings = FakeEmbeddingService()

    plan = await build_import_plan(path, store)

    assert plan.can_apply
    assert plan.target_count == 0
    assert plan.target_store_type == "FakeVectorStore"
    assert store.add_calls == 0

    result = await apply_import(plan, store, embeddings, stopped_confirmation="STOPPED")

    assert result.imported_ids == (str(source.id),)
    assert result.regenerated_embeddings == 1
    assert embeddings.calls == [[source.content]]
    imported = store.memories[str(source.id)]
    assert imported.embedding == [1.0, 1.0, 1.0]
    assert imported.metadata.access_count == source.metadata.access_count
    assert imported.metadata.custom_metadata == source.metadata.custom_metadata


@pytest.mark.asyncio
async def test_apply_requires_verified_backup_for_non_empty_target(tmp_path: Path):
    source = _memory()
    path = tmp_path / "export.json"
    _write_export(path, [source])
    store = FakeVectorStore([_memory("Existing target memory")])
    embeddings = FakeEmbeddingService()
    plan = await build_import_plan(path, store)

    with pytest.raises(ImportValidationError, match="verified binary backup"):
        await apply_import(plan, store, embeddings, stopped_confirmation="STOPPED")

    assert embeddings.calls == []
    assert store.add_calls == 0


@pytest.mark.asyncio
async def test_apply_requires_stopped_runtime_confirmation_before_any_write(
    tmp_path: Path,
):
    source = _memory()
    path = tmp_path / "export.json"
    _write_export(path, [source])
    store = FakeVectorStore()
    embeddings = FakeEmbeddingService()
    plan = await build_import_plan(path, store)

    with pytest.raises(ImportValidationError, match="confirm-stopped STOPPED"):
        await apply_import(plan, store, embeddings)

    assert embeddings.calls == []
    assert store.add_calls == 0


@pytest.mark.asyncio
async def test_apply_rejects_existing_id_before_embedding(tmp_path: Path):
    source = _memory()
    path = tmp_path / "export.json"
    _write_export(path, [source])
    existing = Memory(id=source.id, content="Already in target")
    store = FakeVectorStore([existing])
    embeddings = FakeEmbeddingService()
    plan = await build_import_plan(path, store)

    assert not plan.can_apply
    with pytest.raises(ImportValidationError, match="existing memory IDs"):
        await apply_import(
            plan,
            store,
            embeddings,
            backup_verified=True,
            stopped_confirmation="STOPPED",
        )
    assert embeddings.calls == []


@pytest.mark.asyncio
async def test_apply_rolls_back_partial_writes(tmp_path: Path):
    memories = [_memory("First"), _memory("Second")]
    path = tmp_path / "export.json"
    _write_export(path, memories)
    store = FakeVectorStore(fail_on_add=2)
    plan = await build_import_plan(path, store)

    with pytest.raises(ImportApplyError, match="rolled back 1 writes"):
        await apply_import(plan, store, FakeEmbeddingService(), stopped_confirmation="STOPPED")

    assert store.memories == {}
    assert store.delete_calls == [str(memories[0].id)]


@pytest.mark.asyncio
async def test_apply_rejects_embedding_dimension_before_writes(tmp_path: Path):
    source = _memory()
    path = tmp_path / "export.json"
    _write_export(path, [source])
    store = FakeVectorStore()
    plan = await build_import_plan(path, store)

    with pytest.raises(ImportApplyError, match="configured model requires 3"):
        await apply_import(
            plan,
            store,
            FakeEmbeddingService(vectors=[[1.0, 2.0]]),
            stopped_confirmation="STOPPED",
        )

    assert store.add_calls == 0


@pytest.mark.asyncio
async def test_apply_round_trips_through_sqlite_vector_store(tmp_path: Path):
    source = _memory("SQLite keeps the portable memory identity")
    path = tmp_path / "export.json"
    _write_export(path, [source])
    store = SQLiteVectorStore(
        collection_name="memories",
        persist_directory=str(tmp_path / "vectors"),
    )
    store._embedding_service = FakeEmbeddingService()

    try:
        plan = await build_import_plan(path, store)
        result = await apply_import(
            plan,
            store,
            FakeEmbeddingService(),
            stopped_confirmation="STOPPED",
        )
        recovered = await store.get_memory(source.id)
    finally:
        store.close()

    assert result.imported_ids == (str(source.id),)
    assert recovered is not None
    assert recovered.content == source.content
    assert recovered.embedding == [1.0, 1.0, 1.0]
    assert recovered.metadata.access_count == source.metadata.access_count
