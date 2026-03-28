#!/usr/bin/env python3
"""Quick validation of the shared dashboard_serializer module."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.utils.dashboard_serializer import (
    compute_live_score,
    compute_live_score_from_raw,
    is_test_artifact,
    _redact_secrets,
    _derive_topic,
    _composite_dashboard_score,
    memory_to_dashboard_node,
)

print("All imports OK")

# 1. Raw score computation
meta = {
    "memory_type": "preference",
    "created_at": "2025-05-01T12:00:00",
    "last_accessed": "2025-06-01T12:00:00",
    "access_count": 5,
}
score = compute_live_score_from_raw(meta)
print(f"Raw score test: {score}")
assert 20 < score < 95, f"Score {score} out of expected range"

# 2. Test artifact detection
assert is_test_artifact(content="elefante e2e test memory xyz", title="") is True
assert is_test_artifact(content="[battery_test] something", title="") is True
assert is_test_artifact(content="real memory about Python", title="My Pref") is False
print("Test artifact filter OK")

# 3. Topic derivation
assert _derive_topic("Code Style | PEP8 rules", None) == "Code Style"
assert _derive_topic("", "mycat") == "mycat"
assert _derive_topic("", None) == "General"
print("Topic derivation OK")

# 4. Secret redaction
assert "sk-" not in _redact_secrets("key is sk-abcdefghijklmnopqrstuvwxyz")
print("Secret redaction OK")

# 5. Memory-object scoring (need a real Memory)
from src.models.memory import Memory, MemoryMetadata, MemoryType
from datetime import datetime

mem = Memory(
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
mem_score = compute_live_score(mem)
print(f"Memory-object score: {mem_score}")
assert 20 < mem_score < 95, f"Memory score {mem_score} out of expected range"

# 6. Full node serialization
node = memory_to_dashboard_node(mem)
assert node is not None
assert node["properties"]["score"] == mem_score
assert node["name"] == "Code Style | PEP8"
assert node["properties"]["topic"] == "Code Style"
print(f"Node serialization OK: {node['name']} score={node['properties']['score']}")

# 7. Verify raw-dict and Memory-object scores are close
# They use slightly different vitality paths but same composite formula
delta = abs(score - mem_score)
print(f"Score delta (raw vs Memory): {delta} points")
assert delta <= 3, f"Scores diverged too much: raw={score} mem={mem_score}"

print("\n=== ALL TESTS PASSED ===")
