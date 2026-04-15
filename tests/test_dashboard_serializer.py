"""Pytest coverage for dashboard serialization and launch safeguards."""

import re
from pathlib import Path

from datetime import datetime

from src.models.memory import Memory, MemoryMetadata, MemoryType
from src.utils.dashboard_serializer import (
    _derive_topic,
    _redact_secrets,
    compute_live_score,
    compute_live_score_from_raw,
    is_test_artifact,
    memory_to_dashboard_node,
)


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
