"""Black-box acceptance for null-safe dashboard graph responses."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_dashboard_graph_serializes_a_null_node_name(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "dashboard_snapshot.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {
                        "id": "node-1",
                        "name": None,
                        "type": "memory",
                        "properties": None,
                    }
                ],
                "edges": [],
                "stats": {"total_nodes": 1},
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"elefante:\n  data_dir: {json.dumps(str(data_dir))}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("ELEFANTE_CONFIG_PATH", str(config_path))

    from src.dashboard.server import app

    response = TestClient(app).get("/api/graph")

    assert response.status_code == 200
    payload = response.json()
    assert payload["nodes"][0]["label"] == ""
    assert payload["nodes"][0]["name"] == ""
