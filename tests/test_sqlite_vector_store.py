"""Runtime contract tests for the opt-in SQLite vector-store backend."""

import asyncio
import importlib.util
import json
import pytest
from types import SimpleNamespace
from datetime import datetime, timedelta
from uuid import uuid4

import src.core.vector_store as vector_store_module
from src.core.orchestrator import MemoryOrchestrator
from src.core.sqlite_vector_store import SQLiteVectorStore
from src.core.vector_store import VectorStore
from src.models.memory import Memory, MemoryMetadata
from src.models.query import SearchFilters
from src.utils.config import Config
from scripts.lifecycle.backup_elefante_data import create_backup
from scripts.lifecycle.migrate_chroma_to_sqlite import _close_chroma_snapshot, migrate_chroma_to_sqlite


ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeEmbeddingService:
    async def generate_embedding(self, text):
        return [1.0, 0.0, 0.0] if "database" in text.lower() else [0.0, 1.0, 0.0]

    def get_embedding_dimension(self):
        return 3


class CloseTrackingGraphStore:
    def __init__(self):
        self.closed = False

    async def close(self):
        self.closed = True


async def _write_chroma_migration_fixture(vector_directory):
    store = VectorStore(collection_name="memories", persist_directory=str(vector_directory))
    memories = [
        Memory(
            content="Database backups must be verified before migration.",
            embedding=[1.0, 0.0, 0.0],
            metadata=MemoryMetadata(
                category="operations",
                tags=["backup", "migration"],
                custom_metadata={
                    "title": "Backup contract",
                    "elefante_source": {"tool": "codex", "transport": "stdio-bridge"},
                },
            ),
        ),
        Memory(
            content="SQLite migration keeps the Chroma source unchanged.",
            embedding=[0.9, 0.1, 0.0],
            metadata=MemoryMetadata(category="storage", tags=["sqlite"]),
        ),
        Memory(
            content="The dashboard reads a redacted local snapshot.",
            embedding=[0.0, 1.0, 0.0],
            metadata=MemoryMetadata(category="dashboard", tags=["privacy"]),
        ),
    ]
    for memory in memories:
        await store.add_memory(memory)
    _close_chroma_snapshot(store)
    return memories


@pytest.mark.asyncio
async def test_sqlite_vector_store_round_trips_metadata_and_retrieves_locally(tmp_path):
    store = SQLiteVectorStore(
        collection_name="memories",
        persist_directory=str(tmp_path / "vectors"),
    )
    store._embedding_service = FakeEmbeddingService()
    memory = Memory(
        content="The production database uses encrypted backups.",
        metadata=MemoryMetadata(
            tags=["security", "database"],
            custom_metadata={
                "title": "Database backups",
                "elefante_source": {"tool": "codex", "transport": "streamable-http"},
            },
        ),
    )

    stored_id = await store.add_memory(memory)
    recovered = await store.get_memory(memory.id)
    matches = await store.search("database recovery", limit=3)

    assert stored_id == str(memory.id)
    assert store.database_path.is_file()
    assert recovered is not None
    assert recovered.metadata.tags == ["security", "database"]
    assert recovered.metadata.custom_metadata["elefante_source"]["tool"] == "codex"
    assert [result.memory.id for result in matches] == [memory.id]
    assert matches[0].memory.embedding == [1.0, 0.0, 0.0]
    assert await store.find_by_title("Database backups") is not None


@pytest.mark.asyncio
async def test_sqlite_vector_store_updates_filters_and_deletes_without_chromadb(tmp_path):
    store = SQLiteVectorStore(persist_directory=str(tmp_path / "vectors"))
    store._embedding_service = FakeEmbeddingService()
    migration_memory = Memory(
        content="A database migration must be reversible.",
        related_entities=[uuid4()],
        metadata=MemoryMetadata(
            category="operations",
            project="elefante",
            file_path="docs/migration.md",
            tags=["migration", "security"],
            score=65,
            created_at=datetime.utcnow() - timedelta(days=2),
        ),
    )
    unrelated_memory = Memory(
        content="The UI needs a visual refresh.",
        metadata=MemoryMetadata(tags=["frontend"], score=90),
    )
    await store.add_memory(migration_memory)
    await store.add_memory(unrelated_memory)

    assert await store.update_memory(migration_memory.id, {"tags": ["migration", "verified"], "score": 77})
    updated = await store.get_memory(migration_memory.id)
    assert updated is not None
    assert updated.metadata.tags == ["migration", "verified"]
    assert updated.metadata.score == 77
    filters = SearchFilters(
        category="operations",
        project="elefante",
        file_path="docs/migration.md",
        tags=["migration", "verified"],
        min_score=70,
        max_score=80,
        related_entities=migration_memory.related_entities,
        start_date=datetime.utcnow() - timedelta(days=3),
        end_date=datetime.utcnow(),
    )
    assert [memory.id for memory in await store.get_all(limit=1, offset=0, filters=filters)] == [migration_memory.id]
    assert await store.get_all(limit=1, offset=1, filters=filters) == []
    assert [result.memory.id for result in await store.search("database", filters=filters)] == [migration_memory.id]
    assert (await store.get_stats())["total_memories"] == 2
    assert await store.delete_memory(migration_memory.id)
    assert await store.get_memory(migration_memory.id) is None


@pytest.mark.asyncio
async def test_orchestrator_close_releases_sqlite_and_graph_resources(tmp_path):
    store = SQLiteVectorStore(persist_directory=str(tmp_path / "vectors"))
    store._initialize_client()
    graph_store = CloseTrackingGraphStore()
    orchestrator = MemoryOrchestrator(
        vector_store=store,
        graph_store=graph_store,
        embedding_service=FakeEmbeddingService(),
    )

    await orchestrator.close()

    assert store._connection is None
    assert graph_store.closed


def test_vector_store_factory_selects_sqlite_only_when_explicitly_configured(monkeypatch):
    config = SimpleNamespace(
        elefante=SimpleNamespace(
            vector_store=SimpleNamespace(
                type="sqlite",
                collection_name="memories",
                persist_directory="/tmp/elefante-sqlite-factory-test",
                distance_metric="cosine",
            ),
            embeddings=SimpleNamespace(),
        )
    )
    monkeypatch.setattr(vector_store_module, "get_config", lambda: config)
    vector_store_module.reset_vector_store()

    try:
        assert isinstance(vector_store_module.get_vector_store(), SQLiteVectorStore)
    finally:
        vector_store_module.reset_vector_store()


def test_sqlite_environment_opt_in_uses_an_isolated_data_directory(tmp_path, monkeypatch):
    data_directory = tmp_path / "elefante-data"
    config = Config()
    with monkeypatch.context() as environment:
        environment.setenv("ELEFANTE_DATA_DIR", str(data_directory))
        environment.setenv("ELEFANTE_VECTOR_STORE_TYPE", "sqlite")
        config.reload()

        assert config.elefante.vector_store.type == "sqlite"
        assert config.elefante.vector_store.persist_directory == str(data_directory / "vector")

    config.reload()


def test_sqlite_benchmark_uses_disposable_data_and_reports_latency(tmp_path):
    module = _load_module(
        ROOT / "scripts/demo/benchmark_sqlite_vector_store.py", "sqlite_benchmark_module"
    )

    report = asyncio.run(
        module.run_benchmark(records=24, queries=3, dimension=16, limit=3, temporary_parent=tmp_path)
    )

    assert report["backend"] == "sqlite-exact-cosine"
    assert report["records"] == 24
    assert report["queries"] == 3
    assert report["search_ms"]["p95"] >= report["search_ms"]["min"]
    assert list(tmp_path.iterdir()) == []


def test_chroma_to_sqlite_migration_dry_run_is_temporary_and_proves_parity(tmp_path):
    source = tmp_path / "data" / "chroma"
    destination = tmp_path / "data" / "vector"
    expected = asyncio.run(_write_chroma_migration_fixture(source))

    report = asyncio.run(
        migrate_chroma_to_sqlite(
            source,
            destination,
            probe_count=3,
            minimum_search_overlap=1.0,
            temporary_parent=tmp_path / "temporary",
        )
    )

    assert report["mode"] == "dry-run"
    assert report["records"] == len(expected)
    assert report["uuid_sets_equal"] is True
    assert report["memory_json_equal"] is True
    assert report["embeddings_equal"] is True
    assert report["lowest_search_overlap"] == 1.0
    assert report["source_unchanged"] is True
    assert report["configuration_changed"] is False
    assert not destination.exists()
    assert list((tmp_path / "temporary").iterdir()) == []

    from chromadb.api.shared_system_client import SharedSystemClient

    assert not any("elefante-vector-migration" in identifier for identifier in SharedSystemClient._identifier_to_system)


def test_chroma_to_sqlite_apply_requires_matching_backup_and_keeps_chroma(tmp_path):
    data_directory = tmp_path / "home" / "data"
    source = data_directory / "chroma"
    destination = data_directory / "vector"
    expected = asyncio.run(_write_chroma_migration_fixture(source))
    backup = create_backup(data_directory, tmp_path / "home" / "backups")

    with pytest.raises(ValueError, match="confirm-stopped STOPPED"):
        asyncio.run(
            migrate_chroma_to_sqlite(
                source,
                destination,
                apply=True,
                backup_archive=backup,
            )
        )

    report = asyncio.run(
        migrate_chroma_to_sqlite(
            source,
            destination,
            apply=True,
            stopped_confirmation="STOPPED",
            backup_archive=backup,
            probe_count=3,
            minimum_search_overlap=1.0,
        )
    )

    assert report["applied"] is True
    assert report["backup_verified"] is True
    assert source.is_dir()
    assert (destination / "memories.sqlite3").is_file()
    sqlite_store = SQLiteVectorStore(collection_name="memories", persist_directory=str(destination))
    migrated = asyncio.run(sqlite_store.get_all(limit=10))
    sqlite_store.close()
    assert {str(memory.id) for memory in migrated} == {str(memory.id) for memory in expected}

    with __import__("zipfile").ZipFile(backup) as archive:
        backup_payload = json.loads(archive.read("elefante-backup-manifest.json"))
    (source / "changed-after-backup").write_text("new state", encoding="utf-8")
    assert any(entry["path"].startswith("chroma/") for entry in backup_payload["files"])
    second_destination = data_directory / "second-vector"
    with pytest.raises(ValueError, match="does not exactly match"):
        asyncio.run(
            migrate_chroma_to_sqlite(
                source,
                second_destination,
                apply=True,
                stopped_confirmation="STOPPED",
                backup_archive=backup,
            )
        )
    assert not second_destination.exists()


def test_export_pipeline_reads_the_configured_sqlite_store(tmp_path):
    module = _load_module(ROOT / "scripts/pipeline/export_memories.py", "sqlite_export_module")
    vector_directory = tmp_path / "vectors"
    store = SQLiteVectorStore(collection_name="memories", persist_directory=str(vector_directory))
    store._embedding_service = FakeEmbeddingService()
    memory = Memory(
        content="SQLite exports keep local project decisions portable.",
        metadata=MemoryMetadata(custom_metadata={"title": "SQLite export contract"}),
    )
    asyncio.run(store.add_memory(memory))
    store.close()
    config = SimpleNamespace(
        elefante=SimpleNamespace(
            vector_store=SimpleNamespace(
                type="sqlite",
                collection_name="memories",
                persist_directory=str(vector_directory),
            )
        )
    )

    ids, metadatas, documents = module._fetch(config)
    output = tmp_path / "memory-export.json"
    module.export_json(config, output)

    assert ids == [str(memory.id)]
    assert documents == [memory.content]
    assert metadatas[0]["custom_metadata"]["title"] == "SQLite export contract"
    exported = __import__("json").loads(output.read_text(encoding="utf-8"))
    assert exported["vector_store_type"] == "sqlite"
    assert exported["vector_store_path"] == str(vector_directory)
    assert exported["memories"][0]["id"] == str(memory.id)


def test_dashboard_snapshot_pipeline_reads_the_configured_sqlite_store(tmp_path, monkeypatch):
    module = _load_module(ROOT / "scripts/pipeline/update_dashboard_data.py", "sqlite_dashboard_module")
    vector_directory = tmp_path / "vectors"
    data_directory = tmp_path / "data"
    store = SQLiteVectorStore(collection_name="memories", persist_directory=str(vector_directory))
    store._embedding_service = FakeEmbeddingService()
    memory = Memory(
        content="SQLite-backed dashboards retain private architecture decisions.",
        metadata=MemoryMetadata(
            category="architecture",
            custom_metadata={"title": "SQLite dashboard contract"},
        ),
    )
    asyncio.run(store.add_memory(memory))
    store.close()

    class EmptyGraphStore:
        def __init__(self, *_args, **_kwargs):
            pass

        async def execute_query(self, _query):
            return []

        def close(self):
            pass

    config = SimpleNamespace(
        elefante=SimpleNamespace(
            data_dir=str(data_directory),
            vector_store=SimpleNamespace(
                type="sqlite",
                collection_name="memories",
                persist_directory=str(vector_directory),
            ),
            graph_store=SimpleNamespace(database_path=str(tmp_path / "kuzu_db")),
        )
    )
    monkeypatch.setattr(module, "get_config", lambda: config)
    monkeypatch.setattr(module, "GraphStore", EmptyGraphStore)

    asyncio.run(module.main())

    snapshot = __import__("json").loads((data_directory / "dashboard_snapshot.json").read_text(encoding="utf-8"))
    node = next(item for item in snapshot["nodes"] if item["id"] == str(memory.id))
    assert snapshot["stats"]["memories"] == 1
    assert node["properties"]["source"] == "sqlite"
    assert node["properties"]["title"] == "SQLite dashboard contract"


def test_dashboard_snapshot_pipeline_preserves_the_configured_chroma_path(tmp_path, monkeypatch):
    module = _load_module(ROOT / "scripts/pipeline/update_dashboard_data.py", "chroma_dashboard_module")
    vector_directory = tmp_path / "chroma"
    data_directory = tmp_path / "data"
    store = VectorStore(collection_name="memories", persist_directory=str(vector_directory))
    store._embedding_service = FakeEmbeddingService()
    memory = Memory(
        content="Chroma-backed dashboards retain the existing snapshot contract.",
        metadata=MemoryMetadata(
            category="architecture",
            custom_metadata={"title": "Chroma dashboard contract"},
        ),
    )
    asyncio.run(store.add_memory(memory))

    class EmptyGraphStore:
        def __init__(self, *_args, **_kwargs):
            pass

        async def execute_query(self, _query):
            return []

        def close(self):
            pass

    config = SimpleNamespace(
        elefante=SimpleNamespace(
            data_dir=str(data_directory),
            vector_store=SimpleNamespace(
                type="chromadb",
                collection_name="memories",
                persist_directory=str(vector_directory),
            ),
            graph_store=SimpleNamespace(database_path=str(tmp_path / "kuzu_db")),
        )
    )
    monkeypatch.setattr(module, "get_config", lambda: config)
    monkeypatch.setattr(module, "GraphStore", EmptyGraphStore)

    asyncio.run(module.main())

    snapshot = __import__("json").loads((data_directory / "dashboard_snapshot.json").read_text(encoding="utf-8"))
    node = next(item for item in snapshot["nodes"] if item["id"] == str(memory.id))
    assert snapshot["stats"]["memories"] == 1
    assert node["properties"]["source"] == "chromadb"
    assert node["properties"]["title"] == "Chroma dashboard contract"
