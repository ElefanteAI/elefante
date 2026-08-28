"""Loopback provider-usage ingestion endpoint contracts."""

from __future__ import annotations

import json

import pytest
from starlette.requests import Request

from src.mcp import daemon
from src.session_intelligence import ConsentRequiredError


def _request(payload: bytes) -> Request:
    delivered = False

    async def receive():
        nonlocal delivered
        if delivered:
            return {"type": "http.disconnect"}
        delivered = True
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/events/usage",
            "raw_path": b"/events/usage",
            "query_string": b"",
            "headers": [],
            "client": ("127.0.0.1", 1),
            "server": ("127.0.0.1", 8765),
        },
        receive,
    )


def _endpoint():
    app = daemon.create_app()
    route = next(route for route in app.routes if getattr(route, "path", None) == "/events/usage")
    assert route.methods == {"POST"}
    return route.endpoint


@pytest.mark.asyncio
async def test_usage_endpoint_passes_only_json_to_consent_gated_runtime(monkeypatch) -> None:
    captured = {}

    def ingest(payload):
        captured.update(payload)
        return {"success": True, "receipt": {"evidence_class": "provider_actual"}}

    monkeypatch.setattr(daemon, "ingest_runtime_usage", ingest)
    response = await _endpoint()(_request(json.dumps({"event_id": "event-1"}).encode()))

    assert response.status_code == 200
    assert captured == {"event_id": "event-1"}
    assert json.loads(response.body)["receipt"]["evidence_class"] == "provider_actual"


@pytest.mark.asyncio
async def test_usage_endpoint_reports_consent_and_size_failures(monkeypatch) -> None:
    def blocked(_payload):
        raise ConsentRequiredError("explicit provider_usage consent required")

    monkeypatch.setattr(daemon, "ingest_runtime_usage", blocked)
    response = await _endpoint()(_request(b"{}"))
    assert response.status_code == 403
    assert json.loads(response.body)["consent_required"] is True

    oversized = await _endpoint()(
        _request(b"x" * (daemon.MAX_USAGE_EVENT_BYTES + 1))
    )
    assert oversized.status_code == 413
