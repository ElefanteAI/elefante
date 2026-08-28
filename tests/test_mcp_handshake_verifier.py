"""Regression guards for the installer MCP handshake verifier."""

import json

from scripts.verify import verify_mcp_handshake


def test_installer_handshake_verifies_the_customer_bridge() -> None:
    assert verify_mcp_handshake.MCP_MODULE == "src.mcp.stdio_bridge"


def test_installer_handshake_allows_for_cold_start() -> None:
    assert verify_mcp_handshake.HANDSHAKE_TIMEOUT_SECONDS >= 30.0


def _recall_tool_response(*, include_recall: bool = True, read_only: bool = True):
    tools = [{"name": "elefante-Memory"}]
    if include_recall:
        tools.append(
            {
                "name": "elefante-Recall",
                "annotations": {
                    "readOnlyHint": read_only,
                    "destructiveHint": False,
                    "idempotentHint": True,
                    "openWorldHint": False,
                },
            }
        )
    return {"jsonrpc": "2.0", "id": 2, "result": {"tools": tools}}


def _recall_call_response(status: str, *, read_only: bool = True):
    payload = {
        "success": status not in {"blocked", "unavailable"},
        "status": status,
        "context": "sensitive context must not enter the readiness summary",
        "supplied_count": 0,
        "abstained": status != "supplied",
        "delivery_blocked": status == "blocked",
        "read_only": read_only,
    }
    return {
        "jsonrpc": "2.0",
        "id": 3,
        "result": {
            "content": [{"type": "text", "text": json.dumps(payload)}]
        },
    }


def test_recall_capability_summary_accepts_safe_abstention_without_context_leak():
    summary = verify_mcp_handshake.summarize_recall_capability(
        _recall_tool_response(),
        _recall_call_response("no_match"),
    )

    assert summary == {
        "tool_count": 2,
        "tool_present": True,
        "annotations_read_only": True,
        "probe_status": "no_match",
        "probe_read_only": True,
        "recall_ready": True,
        "diagnostic": None,
    }
    assert "context" not in summary


def test_recall_capability_summary_rejects_missing_or_unsafe_tool():
    missing = verify_mcp_handshake.summarize_recall_capability(
        _recall_tool_response(include_recall=False),
        None,
    )
    unsafe = verify_mcp_handshake.summarize_recall_capability(
        _recall_tool_response(read_only=False),
        _recall_call_response("no_match"),
    )

    assert missing["diagnostic"] == "recall_tool_missing"
    assert missing["recall_ready"] is False
    assert unsafe["diagnostic"] == "recall_annotations_invalid"
    assert unsafe["recall_ready"] is False


def test_recall_capability_summary_rejects_unavailable_probe():
    summary = verify_mcp_handshake.summarize_recall_capability(
        _recall_tool_response(),
        _recall_call_response("unavailable"),
    )

    assert summary["probe_status"] == "unavailable"
    assert summary["diagnostic"] == "recall_probe_unavailable"
    assert summary["recall_ready"] is False
