"""Runtime and operator-surface contracts for Session Intelligence."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from mcp import types as mcp_types
from mcp.shared.memory import create_connected_server_and_client_session

from src.dashboard import server as dashboard_server
from src.mcp import server as mcp_server_module
from src.mcp.server import ElefanteMCPServer
from src.session_intelligence import (
    PURPOSE_ENTERPRISE_TRAINING,
    PURPOSE_PROVIDER_USAGE,
    PURPOSE_USAGE_ANALYTICS,
    ConsentRequiredError,
    InvocationEvent,
    RateCard,
    RuntimeUsageCapture,
    SessionIntelligenceLedger,
    ingest_runtime_usage,
)
from src.session_intelligence import runtime as usage_runtime


NOW = datetime(2026, 8, 28, 16, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def isolate_mcp_auxiliary_state(tmp_path, monkeypatch):
    from src.utils import config

    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        mcp_server_module,
        "get_directive_store",
        lambda: SimpleNamespace(get_active_texts=lambda: []),
    )


def _event() -> dict:
    return {
        "event_id": "provider-event-1",
        "invocation_id": "provider-invocation-1",
        "session_id": "session-1",
        "client_name": "codex",
        "tool_name": "elefante-Recall",
        "started_at": NOW.isoformat(),
        "finished_at": (NOW + timedelta(seconds=2)).isoformat(),
        "usage": {
            "kind": "provider_actual",
            "provider": "provider-a",
            "model": "model-a",
            "input_tokens": 1_000_000,
            "cached_input_tokens": 500_000,
            "output_tokens": 100_000,
            "usage_source": "provider-sdk",
        },
        "rate_card_id": "provider-a-model-a",
        "rate_card_version": "2026-08",
    }


def _rate_card() -> RateCard:
    return RateCard(
        rate_card_id="provider-a-model-a",
        version="2026-08",
        provider="provider-a",
        model="model-a",
        currency="USD",
        effective_from=NOW - timedelta(days=1),
        source="provider-published-rate-card",
        input_uncached_per_million="3",
        input_cached_per_million="1",
        output_per_million="5",
    )


def test_runtime_ingest_never_creates_an_unconsented_ledger(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    with pytest.raises(ConsentRequiredError):
        ingest_runtime_usage(_event(), ledger_path=ledger_path)
    assert not ledger_path.exists()


def test_runtime_ingest_persists_actual_usage_and_refreshes_safe_snapshot(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "session-snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent(
            {
                PURPOSE_USAGE_ANALYTICS,
                PURPOSE_PROVIDER_USAGE,
                PURPOSE_ENTERPRISE_TRAINING,
            },
            at=NOW,
        )
        ledger.register_rate_card(_rate_card())

    result = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )

    assert result["receipt"]["evidence_class"] == "provider_actual"
    assert result["snapshot_refreshed"] is True
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert payload["signal_card"]["usage"]["actual"]["input_tokens"] == 1_000_000
    assert payload["signal_card"]["cost"]["status"] == "known"
    assert payload["enterprise_report"]["employee_ranking"] is False
    assert payload["privacy"]["prompts_stored"] is False
    encoded = snapshot_path.read_text(encoding="utf-8").lower()
    assert "prompt text" not in encoded
    assert "transcript" in encoded  # the privacy declaration, never transcript data


def test_duplicate_runtime_ingest_is_idempotent_and_refreshes_snapshot(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "session-snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent(
            {PURPOSE_USAGE_ANALYTICS, PURPOSE_PROVIDER_USAGE}, at=NOW
        )

    first = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )
    second = ingest_runtime_usage(
        _event(), ledger_path=ledger_path, snapshot_path=snapshot_path
    )

    assert first["receipt"]["persisted"] is True
    assert second["receipt"]["duplicate"] is True
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1


@pytest.mark.asyncio
async def test_normal_mcp_call_is_captured_in_ledger_snapshot_and_dashboard(
    tmp_path, monkeypatch
) -> None:
    """SI-1: prove automatic capture without mocking or calling ingestion."""
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "session-snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)

    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger_path))
    monkeypatch.setenv(
        "ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(snapshot_path)
    )
    monkeypatch.setenv("ELEFANTE_CLIENT_TOOL", "codex-test")
    monkeypatch.setenv("ELEFANTE_CLIENT_INSTANCE_ID", "si-test-instance")

    server = ElefanteMCPServer()

    async def no_match(_arguments):
        return {
            "success": True,
            "status": "no_match",
            "context": "# Elefante answer context\n\nNo safe relevant memory was found.",
            "supplied_count": 0,
            "abstained": True,
            "delivery_blocked": False,
            "read_only": True,
        }

    monkeypatch.setattr(server, "_handle_recall", no_match)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What evidence applies to this task?"},
            )
        )
    )
    assert json.loads(response.root.content[0].text)["status"] == "no_match"

    for _ in range(100):
        if snapshot_path.is_file():
            break
        await asyncio.sleep(0.01)

    assert snapshot_path.is_file(), "the MCP call did not refresh Session Intelligence"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        events = ledger.inspect_events()
    assert len(events) == 1
    assert events[0]["tool_name"] == "elefante-Recall"
    assert events[0]["client_name"] == "codex-test"
    assert events[0]["status"] == "success"
    assert events[0]["usage"]["kind"] == "estimated"

    dashboard_payload = await dashboard_server.get_session_intelligence()
    assert dashboard_payload["signal_card"]["usage"]["event_count"] == 1
    assert (
        dashboard_payload["signal_card"]["usage"]["estimated"]["event_count"]
        == 1
    )
    await server.close()


def _estimated_event(identifier: str = "call-1") -> InvocationEvent:
    return InvocationEvent.estimated(
        event_id=identifier,
        session_id="mcp-session-test",
        client_name="test-host",
        tool_name="elefante-Recall",
        started_at=NOW,
        finished_at=NOW + timedelta(milliseconds=10),
        input_tokens=10,
        output_tokens=20,
        estimator="elefante-mcp-character-ratio",
    )


@pytest.mark.asyncio
async def test_automatic_capture_never_creates_an_unconsented_ledger(tmp_path) -> None:
    ledger_path = tmp_path / "absent.sqlite3"
    capture = RuntimeUsageCapture(ledger_path=ledger_path)
    assert capture.submit(_estimated_event()) is False
    await capture.close()
    assert not ledger_path.exists()
    assert capture.accepted_count == 0


@pytest.mark.asyncio
async def test_automatic_capture_rechecks_revoked_consent(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
        ledger.revoke_consent()
    capture = RuntimeUsageCapture(ledger_path=ledger_path)
    assert capture.submit(_estimated_event()) is True
    await capture.close()
    assert capture.last_error_code == "ConsentRequiredError"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert ledger.inspect_events() == []


@pytest.mark.asyncio
async def test_automatic_capture_duplicate_event_does_not_double_count(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
    capture = RuntimeUsageCapture(ledger_path=ledger_path)
    event = _estimated_event()
    assert capture.submit(event) is True
    assert capture.submit(event) is True
    await capture.close()
    assert capture.last_error_code is None
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1


@pytest.mark.asyncio
async def test_automatic_capture_queue_is_bounded(tmp_path) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
    capture = RuntimeUsageCapture(ledger_path=ledger_path, pending_limit=1)
    assert capture.submit(_estimated_event("call-1")) is True
    assert capture.submit(_estimated_event("call-2")) is False
    assert capture.dropped_count == 1
    assert capture.last_error_code == "capture_capacity_exceeded"
    await capture.close()
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result", "expected_status"),
    [
        ({"success": True, "status": "no_match"}, "success"),
        ({"success": False, "status": "blocked"}, "blocked"),
        ({"success": False, "status": "unavailable"}, "error"),
    ],
)
async def test_mcp_capture_preserves_result_and_classifies_status(
    tmp_path, monkeypatch, result, expected_status
) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger_path))
    server = ElefanteMCPServer()

    async def recall(_arguments):
        return dict(result)

    monkeypatch.setattr(server, "_handle_recall", recall)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    request = mcp_types.CallToolRequest(
        params=mcp_types.CallToolRequestParams(
            name="elefante-Recall", arguments={"question": "private question marker"}
        )
    )
    before = await handler(request)
    assert not ledger_path.exists()
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
    after = await handler(request)
    await server.close()

    assert after.root.content[0].text == before.root.content[0].text
    with SessionIntelligenceLedger(ledger_path) as ledger:
        events = ledger.inspect_events()
    assert len(events) == 1
    assert events[0]["status"] == expected_status
    assert "private question marker" not in json.dumps(events)


@pytest.mark.asyncio
async def test_locked_usage_ledger_does_not_block_mcp_response(tmp_path, monkeypatch) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger_path))
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
    server = ElefanteMCPServer()

    async def recall(_arguments):
        return {"success": True, "status": "no_match"}

    monkeypatch.setattr(server, "_handle_recall", recall)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    lock = sqlite3.connect(ledger_path)
    lock.execute("BEGIN EXCLUSIVE")
    try:
        response = await asyncio.wait_for(
            handler(
                mcp_types.CallToolRequest(
                    params=mcp_types.CallToolRequestParams(
                        name="elefante-Recall", arguments={"question": "Any relevant fact?"}
                    )
                )
            ),
            timeout=0.5,
        )
        assert json.loads(response.root.content[0].text)["status"] == "no_match"
    finally:
        lock.rollback()
        lock.close()
        await server.close()
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1


@pytest.mark.asyncio
async def test_real_mcp_protocol_records_each_dispatch_without_manual_ingest(
    tmp_path, monkeypatch
) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger_path))
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
    server = ElefanteMCPServer()
    async with create_connected_server_and_client_session(server.server) as client:
        # The actual Recall validator rejects the empty question before any
        # memory store or model is opened. No tool handler is mocked here.
        for _ in range(2):
            response = await client.call_tool("elefante-Recall", {"question": ""})
            assert json.loads(response.content[0].text)["status"] == "blocked"
        await server.close()
    with SessionIntelligenceLedger(ledger_path) as ledger:
        events = ledger.inspect_events()
    assert len(events) == 2
    assert len({event["invocation_id"] for event in events}) == 2
    assert {event["status"] for event in events} == {"blocked"}
    assert server._session_intelligence_capture.status()["persisted_count"] == 2


@pytest.mark.asyncio
async def test_snapshot_write_failure_preserves_mcp_result_and_exposes_partial_health(
    tmp_path, monkeypatch
) -> None:
    ledger_path = tmp_path / "session.sqlite3"
    snapshot_path = tmp_path / "snapshot.json"
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_DB", str(ledger_path))
    monkeypatch.setenv("ELEFANTE_SESSION_INTELLIGENCE_SNAPSHOT", str(snapshot_path))
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS}, at=NOW)
        usage_runtime.write_runtime_snapshot(ledger, snapshot_path)
    original_snapshot = snapshot_path.read_bytes()
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        dashboard_server.app.state,
        "session_intelligence_capture_status",
        server._session_intelligence_capture.status,
        raising=False,
    )

    def fail_write(*_args, **_kwargs):
        raise OSError("private failure detail must not enter health metadata")

    monkeypatch.setattr(usage_runtime, "write_runtime_snapshot", fail_write)
    async with create_connected_server_and_client_session(server.server) as client:
        response = await client.call_tool("elefante-Recall", {"question": ""})
        assert json.loads(response.content[0].text)["status"] == "blocked"
        await server.close()

    assert snapshot_path.read_bytes() == original_snapshot
    payload = await dashboard_server.get_session_intelligence()
    assert payload["capture"]["state"] == "partial"
    assert payload["capture"]["failed_count"] == 1
    assert payload["capture"]["last_error_code"] == "OSError"
    assert "private failure detail" not in json.dumps(payload)
    assert payload["signal_card"]["usage"]["event_count"] == 0
    with SessionIntelligenceLedger(ledger_path) as ledger:
        assert len(ledger.inspect_events()) == 1


@pytest.mark.asyncio
async def test_capture_identity_failure_does_not_change_tool_result(monkeypatch):
    server = ElefanteMCPServer()

    def fail_context():
        raise RuntimeError("private source detail")

    monkeypatch.setattr(server, "_new_usage_capture_context", fail_context)
    async with create_connected_server_and_client_session(server.server) as client:
        response = await client.call_tool("elefante-Recall", {"question": ""})
        assert json.loads(response.content[0].text)["status"] == "blocked"
    assert server._session_intelligence_capture.status()["failed_count"] == 1
    assert "private source detail" not in json.dumps(server._session_intelligence_capture.status())
    await server.close()


@pytest.mark.asyncio
async def test_interrupted_tool_is_not_counted_as_completed_usage(monkeypatch):
    server = ElefanteMCPServer()

    async def interrupted(_arguments):
        raise asyncio.CancelledError()

    monkeypatch.setattr(server, "_handle_recall", interrupted)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    with pytest.raises(asyncio.CancelledError):
        await handler(mcp_types.CallToolRequest(params=mcp_types.CallToolRequestParams(
            name="elefante-Recall", arguments={"question": "a task"}
        )))
    health = server._session_intelligence_capture.status()
    assert health["state"] == "partial"
    assert health["dropped_count"] == 1
    assert health["persisted_count"] == 0
    await server.close()


@pytest.mark.asyncio
async def test_concurrent_ingress_and_capture_keep_one_current_snapshot(tmp_path):
    ledger_path = tmp_path / "usage.db"
    snapshot_path = tmp_path / "snapshot.json"
    with SessionIntelligenceLedger(ledger_path) as ledger:
        ledger.grant_consent({PURPOSE_USAGE_ANALYTICS, PURPOSE_PROVIDER_USAGE}, at=NOW)
    capture = RuntimeUsageCapture(ledger_path=ledger_path, snapshot_path=snapshot_path)
    for index in range(8):
        assert capture.submit(_estimated_event(f"mcp-{index}"))
    actual = _event()
    result = await asyncio.to_thread(
        ingest_runtime_usage, actual, ledger_path=ledger_path, snapshot_path=snapshot_path
    )
    assert result["receipt"]["persisted"]
    await capture.close()
    payload = json.loads(snapshot_path.read_text())
    assert payload["signal_card"]["usage"]["event_count"] == 9
    assert payload["signal_card"]["usage"]["actual"]["event_count"] == 1
    assert payload["signal_card"]["usage"]["estimated"]["event_count"] == 8
