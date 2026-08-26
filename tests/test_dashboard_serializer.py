# ─────────────────────────────────────────────────────────────────────────────
# TEST    : tests/test_dashboard_serializer.py
# PROVES  : Dashboard serialization correctness and launch safeguards; ensures
#           Memory objects are converted to valid dashboard node/edge JSON.
# RUN     : pytest tests/test_dashboard_serializer.py -v
# WHEN    : After changes to src/utils/dashboard_serializer.py or
#           update_dashboard_data.py node schema.
# ─────────────────────────────────────────────────────────────────────────────
"""Pytest coverage for dashboard serialization and launch safeguards."""

import re
import asyncio
import hashlib
import json
import importlib.util
import struct
from pathlib import Path
from types import SimpleNamespace

from datetime import datetime

import pytest

from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.utils.dashboard_serializer import (
    _derive_topic,
    _redact_secrets,
    compute_live_score,
    compute_live_score_from_raw,
    is_test_artifact,
    memory_to_dashboard_node,
)


def _load_showcase_builder():
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "scripts" / "demo" / "generate_showcase_snapshot.py"
    spec = importlib.util.spec_from_file_location("generate_showcase_snapshot", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.build_showcase_snapshot


def _sample_raw_metadata() -> dict:
    return {
        "memory_type": "preference",
        "created_at": "2025-05-01T12:00:00",
        "last_accessed": "2025-06-01T12:00:00",
        "access_count": 5,
    }


def _sample_memory() -> Memory:
    return Memory(
        content="Test preference about coding style",
        metadata=MemoryMetadata(
            memory_type=MemoryType.PREFERENCE,
            created_at=datetime(2025, 5, 1, 12, 0, 0),
            last_accessed=datetime(2025, 6, 1, 12, 0, 0),
            access_count=5,
            decay_rate=0.002,
            custom_metadata={"title": "Code Style | PEP8"},
        ),
    )


def test_compute_live_score_from_raw_returns_reasonable_range():
    score = compute_live_score_from_raw(_sample_raw_metadata())
    assert 20 < score < 95, f"Score {score} out of expected range"


def test_is_test_artifact_filters_known_patterns():
    assert is_test_artifact(content="elefante e2e test memory xyz", title="") is True
    assert is_test_artifact(content="[battery_test] something", title="") is True
    assert is_test_artifact(content="real memory about Python", title="My Pref") is False


def test_derive_topic_prefers_title_prefix_then_category_then_general():
    assert _derive_topic("Code Style | PEP8 rules", None) == "Code Style"
    assert _derive_topic("", "mycat") == "mycat"
    assert _derive_topic("", None) == "General"


def test_redact_secrets_removes_api_key_pattern():
    assert "sk-" not in _redact_secrets("key is sk-abcdefghijklmnopqrstuvwxyz")


def test_compute_live_score_for_memory_object_returns_reasonable_range():
    memory = _sample_memory()
    score = compute_live_score(memory)
    assert 20 < score < 95, f"Memory score {score} out of expected range"


def test_memory_to_dashboard_node_serializes_score_and_topic():
    memory = _sample_memory()
    score = compute_live_score(memory)
    node = memory_to_dashboard_node(memory)

    assert node is not None
    assert node["properties"]["score"] == score
    assert node["name"] == "Code Style | PEP8"
    assert node["properties"]["topic"] == "Code Style"


def test_memory_to_dashboard_node_uses_explicit_configured_backend_label():
    node = memory_to_dashboard_node(_sample_memory(), vector_source="sqlite")

    assert node is not None
    assert node["properties"]["source"] == "sqlite"


def test_raw_and_memory_scores_stay_close():
    raw_score = compute_live_score_from_raw(_sample_raw_metadata())
    memory_score = compute_live_score(_sample_memory())
    delta = abs(raw_score - memory_score)
    assert delta <= 3, f"Scores diverged too much: raw={raw_score} mem={memory_score}"


def test_dashboard_open_waits_for_readiness_before_browser_launch():
    repo_root = Path(__file__).resolve().parents[1]
    server_source = (repo_root / "src" / "mcp" / "server.py").read_text(encoding="utf-8")

    assert "def _wait_for_ready" in server_source
    assert "ready = _wait_for_ready(max_wait=15.0)" in server_source
    assert re.search(r"if ready:\n\s+try:\n\s+webbrowser\.open\(url\)", server_source)
    assert "Dashboard server is still starting on port" in server_source


def test_dashboard_refresh_forces_restart_of_existing_server():
    repo_root = Path(__file__).resolve().parents[1]
    server_source = (repo_root / "src" / "mcp" / "server.py").read_text(encoding="utf-8")

    assert "if force_restart and already_running:" in server_source
    assert "Dashboard restart requested: killing existing server process." in server_source
    assert "_kill_existing()" in server_source
    assert "already_running = False" in server_source
    assert "DASHBOARD_STARTED = False" in server_source


def test_dashboard_frontend_retries_stats_and_snapshot_fetches():
    repo_root = Path(__file__).resolve().parents[1]
    store_source = (repo_root / "src" / "dashboard" / "ui" / "src" / "store.ts").read_text(encoding="utf-8")

    assert store_source.count("const maxRetries = 4;") >= 2
    assert store_source.count("1000 * Math.pow(2, attempt)") >= 2
    assert "fetch('/api/graph')" in store_source
    assert "fetch('/api/stats')" in store_source


def test_dashboard_frontend_normalizes_production_edge_endpoints():
    repo_root = Path(__file__).resolve().parents[1]
    types_source = (repo_root / "src" / "dashboard" / "ui" / "src" / "types.ts").read_text(encoding="utf-8")
    graph_source = (repo_root / "src" / "dashboard" / "ui" / "src" / "components" / "KnowledgeGraph.tsx").read_text(encoding="utf-8")
    memories_source = (repo_root / "src" / "dashboard" / "ui" / "src" / "components" / "MemoriesTab.tsx").read_text(encoding="utf-8")

    assert "edge.source ?? edge.from" in types_source
    assert "edge.target ?? edge.to" in types_source
    assert "edgeEndpoints(" in graph_source
    assert "edgeEndpoints(e)" in memories_source


def test_dashboard_labels_snapshot_search_truthfully():
    repo_root = Path(__file__).resolve().parents[1]
    memories_source = (repo_root / "src" / "dashboard" / "ui" / "src" / "components" / "MemoriesTab.tsx").read_text(encoding="utf-8")

    assert "Snapshot search... (2+ characters)" in memories_source
    assert "snapshot results" in memories_source
    assert "Semantic search" not in memories_source
    assert "semantic results" not in memories_source


def test_dashboard_shell_uses_elefante_brand_assets_not_vite_defaults():
    repo_root = Path(__file__).resolve().parents[1]
    html = (repo_root / "src" / "dashboard" / "ui" / "index.html").read_text(encoding="utf-8")
    emblem = (repo_root / "src" / "dashboard" / "ui" / "public" / "elefante-emblem.png").read_bytes()

    assert "<title>Elefante Memory Intelligence</title>" in html
    assert 'href="/elefante-emblem.png"' in html
    assert "vite.svg" not in html
    assert emblem[:8] == b"\x89PNG\r\n\x1a\n"
    assert struct.unpack(">II", emblem[16:24]) == (582, 458)
    assert hashlib.sha256(emblem).hexdigest() == (
        "06178da5ba2c145cb6b3516cdfc4e84c8695e0abc01d38a44cebc9a62ea46f6b"
    )


def test_showcase_snapshot_is_deterministic_grounded_and_contract_complete():
    build_showcase_snapshot = _load_showcase_builder()
    snapshot = build_showcase_snapshot()
    repeated = build_showcase_snapshot()

    assert snapshot == repeated
    assert snapshot["curation"] == {
        "purpose": "Elefante Memory Intelligence dashboard showcase",
        "product_baseline": "v2.12.2",
        "deterministic": True,
        "synthetic_behavioral_metadata": True,
        "source_grounded_content": True,
        "contains_user_data": False,
        "disclaimer": "Counts and access history demonstrate the interface; they are not observed customer behavior or performance claims.",
    }
    assert snapshot["stats"] == {
        "total_nodes": 48,
        "memories": 37,
        "entities": 11,
        "edges": 95,
    }

    node_ids = {node["id"] for node in snapshot["nodes"]}
    assert len(node_ids) == 48
    assert all(edge["from"] in node_ids and edge["to"] in node_ids for edge in snapshot["edges"])
    assert snapshot["featured_chain"] == [
        "demo:daemon-assumption",
        "demo:kuzu-evidence",
        "demo:daemon-decision",
        "demo:bridge-guard",
    ]

    memories = [node for node in snapshot["nodes"] if node["type"] == "memory"]
    assert all(memory["properties"]["evidence"] for memory in memories)
    assert all(memory["properties"]["namespace"] == "showcase" for memory in memories)
    corpus = json.dumps(snapshot).lower()
    assert "six signals" not in corpus
    assert "chromadb" not in corpus
    assert "migration" not in corpus

    memory_relationships = {
        (edge["from"], edge["to"], edge["label"])
        for edge in snapshot["edges"]
        if edge["from"].startswith("demo:") and edge["to"].startswith("demo:")
    }
    assert {
        (
            "demo:daemon-assumption",
            "demo:kuzu-evidence",
            "CHALLENGED_BY",
        ),
        ("demo:kuzu-evidence", "demo:daemon-decision", "LED_TO"),
        ("demo:daemon-decision", "demo:bridge-guard", "GUARDED_BY"),
        (
            "demo:dashboard-live-assumption",
            "demo:snapshot-evidence",
            "CHALLENGED_BY",
        ),
        ("demo:snapshot-evidence", "demo:snapshot-decision", "LED_TO"),
        ("demo:snapshot-decision", "demo:loopback-guard", "GUARDED_BY"),
        ("demo:dependency-audit", "demo:runtime-lock", "LED_TO"),
        ("demo:runtime-lock", "demo:sqlite-default", "ENABLES"),
        ("demo:sqlite-default", "demo:data-control", "GUARDED_BY"),
    } <= memory_relationships
    semantic_relationships = [
        edge
        for edge in snapshot["edges"]
        if edge["type"] == "semantic"
    ]
    assert len(semantic_relationships) == 4
    assert all(edge["label"] == "RELATED_TO" for edge in semantic_relationships)


def test_dashboard_graph_uses_real_decision_trails_not_invented_topic_topology():
    repo_root = Path(__file__).resolve().parents[1]
    graph_source = (
        repo_root
        / "src"
        / "dashboard"
        / "ui"
        / "src"
        / "components"
        / "KnowledgeGraph.tsx"
    ).read_text(encoding="utf-8")
    explore_source = (
        repo_root
        / "src"
        / "dashboard"
        / "ui"
        / "src"
        / "components"
        / "ExploreTab.tsx"
    ).read_text(encoding="utf-8")

    assert "Decision graph" in graph_source
    assert "See why the current truth won." in graph_source
    assert "CAUSAL_LABELS.has(edge.label)" in graph_source
    assert "Inter-hub edges" not in graph_source
    assert "hub:" not in graph_source
    assert "Topic hub-spoke network" not in explore_source
    assert "Decisions, evidence & safeguards" in explore_source


def test_dashboard_defaults_to_loopback_and_explicit_cors(monkeypatch):
    from src.dashboard import server

    monkeypatch.delenv("ELEFANTE_DASHBOARD_HOST", raising=False)
    monkeypatch.delenv("ELEFANTE_DASHBOARD_CORS_ORIGINS", raising=False)

    assert server._dashboard_host() == "127.0.0.1"
    assert server._dashboard_cors_origins() == [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]


def test_dashboard_allows_only_explicit_origin_configuration(monkeypatch):
    from src.dashboard import server

    monkeypatch.setenv(
        "ELEFANTE_DASHBOARD_CORS_ORIGINS",
        "https://dashboard.example.test, https://admin.example.test",
    )

    assert server._dashboard_cors_origins() == [
        "https://dashboard.example.test",
        "https://admin.example.test",
    ]


def test_dashboard_container_defaults_remain_host_loopback_only():
    repo_root = Path(__file__).resolve().parents[1]
    dockerfile = (repo_root / "Dockerfile").read_text(encoding="utf-8")
    compose = (repo_root / "docker-compose.yml").read_text(encoding="utf-8")

    assert "ELEFANTE_DASHBOARD_HOST=0.0.0.0" not in dockerfile
    assert '"127.0.0.1:8000:8000"' in compose
    assert "ELEFANTE_DASHBOARD_HOST: 0.0.0.0" in compose


@pytest.mark.asyncio
async def test_dashboard_reads_and_searches_only_the_redacted_snapshot(monkeypatch, tmp_path):
    from src.dashboard import server

    snapshot_path = tmp_path / "dashboard_snapshot.json"
    snapshot_path.write_text(
        """{
          "generated_at": "2026-07-22T12:00:00Z",
          "stats": {"memories": 1, "entities": 0, "edges": 0, "total_nodes": 1},
          "nodes": [
            {"id": "memory-1", "type": "memory", "name": "Python style", "description": "Use black for Python formatting", "properties": {"content": "Use black for Python formatting", "title": "Python style", "tags": "python,formatting", "topic": "Code Style", "access_count": 4}},
            {"id": "entity-1", "type": "entity", "name": "Python", "description": "language", "properties": {}}
          ],
          "edges": []
        }""",
        encoding="utf-8",
    )
    monkeypatch.setattr(server, "_snapshot_path", lambda: snapshot_path)
    monkeypatch.setattr(
        server,
        "get_config",
        lambda: SimpleNamespace(elefante=SimpleNamespace(version="test-version")),
    )

    graph = await server.get_graph(limit=10)
    search = await server.search_memories("python formatting", limit=10, min_similarity=1.0)
    stats = await server.get_stats()

    assert {node["id"] for node in graph["nodes"]} == {"memory-1", "entity-1"}
    assert search == {
        "success": True,
        "count": 1,
        "results": [
            {
                "id": "memory-1",
                "content": "Use black for Python formatting",
                "metadata": {
                    "content": "Use black for Python formatting",
                    "title": "Python style",
                    "tags": "python,formatting",
                    "topic": "Code Style",
                    "access_count": 4,
                },
                "similarity": 1.0,
            }
        ],
    }
    assert "data_dir" not in stats["elefante"]
    assert "path" not in stats["snapshot"]


def test_dashboard_has_no_browser_triggered_snapshot_mutation_or_live_store_import():
    from src.dashboard import server

    route_paths = {route.path for route in server.app.routes}
    source = Path(server.__file__).read_text(encoding="utf-8")

    assert "/api/refresh" not in route_paths
    assert "get_vector_store" not in source
    assert "subprocess.run" not in source
    assert "allow_methods=[\"GET\"]" in source


@pytest.mark.parametrize("mutation", ["CREATE", "MERGE", "SET", "DELETE", "DROP", "REMOVE"])
def test_graph_query_validator_rejects_mutations(mutation):
    from src.utils.validators import ValidationError, validate_cypher_query

    with pytest.raises(ValidationError, match="read-only"):
        validate_cypher_query(f"{mutation} (n:Entity)")


def test_graph_query_validator_accepts_read_only_match():
    from src.utils.validators import validate_cypher_query

    assert validate_cypher_query("MATCH (n:Entity) RETURN n LIMIT 10") == "MATCH (n:Entity) RETURN n LIMIT 10"


def test_provenance_backfill_is_dry_run_by_default():
    repo_root = Path(__file__).resolve().parents[1]
    source = (repo_root / "scripts" / "lifecycle" / "backfill_memory_provenance.py").read_text(encoding="utf-8")

    assert 'parser.add_argument("--apply", action="store_true"' in source
    assert 'backfill(apply=args.apply)' in source
    assert '"tool": "legacy"' in source
    assert "REPO_ROOT = Path(__file__).resolve().parents[2]" in source


def test_provenance_backfill_reports_only_missing_graph_links(monkeypatch):
    import scripts.lifecycle.backfill_memory_provenance as migration
    from src.core.graph_store import GraphStore

    source = {
        "tool": "legacy",
        "instance_id": "pre-daemon",
        "session_id": "pre-daemon",
        "transport": "legacy-stdio",
    }
    memory = Memory(
        content="legacy memory",
        metadata=MemoryMetadata(custom_metadata={"elefante_source": source}),
    )
    memory.metadata.memory_type = memory.metadata.memory_type.value
    memory.metadata.status = memory.metadata.status.value

    class VectorStore:
        async def get_all(self, **_kwargs):
            return [memory]

    class Graph:
        def __init__(self):
            self.entities = set()
            self.links = set()

        _source_id = staticmethod(GraphStore._source_id)

        async def execute_query(self, query):
            if "WRITTEN_BY" not in query:
                return [{"memory_id": memory_id} for memory_id in self.entities]
            return [
                {"memory_id": memory_id, "source_id": source_id}
                for memory_id, source_id in self.links
            ]

        async def create_entity(self, entity):
            self.entities.add(str(entity.id))

        async def record_memory_source(self, memory_id, provenance):
            self.links.add((str(memory_id), self._source_id(provenance)))

    graph = Graph()
    monkeypatch.setattr(migration, "get_vector_store", VectorStore)
    monkeypatch.setattr(migration, "get_graph_store", lambda: graph)

    assert asyncio.run(migration.backfill(apply=False)) == (0, 0, 1, 1)
    assert asyncio.run(migration.backfill(apply=True)) == (0, 0, 1, 1)
    assert asyncio.run(migration.backfill(apply=False)) == (0, 0, 0, 0)


def test_get_graph_handles_null_name_safely(monkeypatch):
    from src.dashboard import server

    mock_snapshot = {
        "nodes": [
            {"id": "node-1", "name": None, "type": "memory", "properties": None},
            {"id": "node-2", "name": "Valid Node", "type": "concept", "properties": {}},
        ],
        "edges": [],
        "stats": {"total_nodes": 2},
    }

    monkeypatch.setattr(server, "_read_snapshot", lambda: mock_snapshot)

    result = asyncio.run(server.get_graph(limit=10))
    assert len(result["nodes"]) == 2
    assert result["nodes"][0]["label"] == ""
    assert result["nodes"][0]["name"] == ""
    assert result["nodes"][1]["label"] == "Valid Node"
