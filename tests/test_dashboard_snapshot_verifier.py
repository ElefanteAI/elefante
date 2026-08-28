"""Regression tests for dashboard snapshot health and usage validation."""

from __future__ import annotations

from copy import deepcopy

from scripts.verify.verify_dashboard_snapshot import validate_snapshot


def _snapshot() -> dict:
    return {
        "generated_at": "2026-08-27T12:00:00",
        "stats": {
            "total_nodes": 3,
            "memories": 2,
            "entities": 1,
            "edges": 1,
            "health": {
                "score": 50,
                "freshness": 50,
                "coverage": 50,
                "usage": 50,
                "connectivity": 50,
                "counts": {"healthy": 1, "orphan": 1},
            },
            "usage": {
                "total_accesses": 2,
                "retrieved_memories": 1,
                "never_retrieved": 1,
                "retrieval_rate": 50,
                "average_access_count": 1.0,
                "max_access_count": 2,
            },
        },
        "nodes": [
            {
                "id": "m1",
                "name": "A decision",
                "type": "memory",
                "description": "Decision",
                "created_at": "2026-08-27T12:00:00",
                "properties": {
                    "title": "A decision",
                    "summary": "Decision",
                    "health_status": "healthy",
                    "health_reason": "current and connected",
                    "connection_count": 1,
                    "score": 75,
                },
            },
            {
                "id": "m2",
                "name": "An orphan",
                "type": "memory",
                "description": "Orphan",
                "created_at": "2026-08-27T12:00:00",
                "properties": {
                    "title": "An orphan",
                    "summary": "Orphan",
                    "health_status": "orphan",
                    "health_reason": "has no graph connections",
                    "connection_count": 0,
                    "score": 75,
                },
            },
            {
                "id": "e1",
                "name": "Project",
                "type": "entity",
                "description": "Project",
                "properties": {},
            },
        ],
        "edges": [{"from": "m1", "to": "e1"}],
    }


def test_snapshot_verifier_accepts_canonical_health_and_usage():
    result = validate_snapshot(_snapshot(), require_curation=True)

    assert result.ok(strict=False)
    assert result.errors == []
    assert any("Isolated nodes" in message for message in result.warnings)
    assert any("Health score: 50" in message for message in result.info)
    assert any("Usage: 50%" in message for message in result.info)


def test_snapshot_verifier_rejects_health_and_usage_drift():
    snapshot = deepcopy(_snapshot())
    snapshot["stats"]["health"]["counts"] = {"healthy": 2}
    snapshot["nodes"][1]["properties"]["health_status"] = "unknown"
    snapshot["stats"]["usage"]["retrieved_memories"] = 2

    result = validate_snapshot(snapshot, require_curation=False)

    assert not result.ok(strict=True)
    assert any("invalid health_status" in message for message in result.errors)
    assert any("counts does not match" in message for message in result.errors)
    assert any("memory counts do not match" in message for message in result.errors)
