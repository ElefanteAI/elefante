"""Black-box acceptance for the dashboard browser-origin boundary."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_dashboard_rejects_untrusted_origin_and_keeps_local_origin(monkeypatch) -> None:
    monkeypatch.delenv("ELEFANTE_DASHBOARD_CORS_ORIGINS", raising=False)
    from src.dashboard.server import app

    client = TestClient(app)
    preflight = {
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    untrusted = "https://untrusted.example"
    rejected = client.options(
        "/api/graph",
        headers={"Origin": untrusted, **preflight},
    )
    allowed = client.options(
        "/api/graph",
        headers={"Origin": "http://localhost:8000", **preflight},
    )

    assert rejected.headers.get("access-control-allow-origin") not in {"*", untrusted}
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:8000"
