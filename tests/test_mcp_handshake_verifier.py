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


def _tool_response(payload: dict, *, request_id: int) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
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


def test_first_run_receipt_proves_disposable_recall_cleanup_and_backup() -> None:
    acceptance = _tool_response(
        {
            "success": True,
            "action": "installation_acceptance",
            "status": "VERIFIED_COMPLETE",
            "recovery_status": "VERIFIED_COMPLETE",
            "receipt": {
                "operation_id": "11111111-1111-4111-8111-111111111111",
                "memory_content_included": False,
                "project_path_included": False,
                "checks": [
                    {"name": "disposable_record_write", "passed": True},
                    {"name": "project_scoped_recall", "passed": True},
                    {"name": "disposable_record_cleanup", "passed": True},
                ],
            },
        },
        request_id=3,
    )
    plan = _tool_response(
        {
            "success": True,
            "plan": {
                "action": "backup",
                "applicable": True,
                "layout_sha256": "a" * 64,
            },
        },
        request_id=4,
    )
    backup = _tool_response(
        {
            "success": True,
            "status": "VERIFIED_COMPLETE",
            "recovery_status": "VERIFIED_COMPLETE",
            "receipt": {
                "operation_id": "22222222-2222-4222-8222-222222222222",
                "status": "VERIFIED_COMPLETE",
                "archive_name": "elefante_data_backup_20260830.zip",
                "archive_sha256": "b" * 64,
                "checks": [
                    {"name": "archive_readback", "passed": True},
                    {"name": "sqlite_integrity", "passed": True},
                ],
            },
        },
        request_id=5,
    )

    receipt = verify_mcp_handshake.summarize_installation_acceptance(
        acceptance,
        plan,
        backup,
        now="2026-08-30T14:00:00+00:00",
    )

    assert receipt["status"] == "VERIFIED_COMPLETE"
    assert [check["name"] for check in receipt["checks"]] == [
        "project_isolation",
        "disposable_recall",
        "acceptance_cleanup",
        "initial_backup",
    ]
    assert receipt["memory_content_included"] is False
    assert receipt["project_path_included"] is False
    serialized = json.dumps(receipt, sort_keys=True)
    assert "/private/" not in serialized
    assert "installation code" not in serialized


def test_first_run_receipt_rejects_unverified_cleanup() -> None:
    acceptance = _tool_response(
        {
            "success": False,
            "status": "NEEDS_HUMAN",
            "recovery_status": "NEEDS_HUMAN",
            "receipt": {
                "memory_content_included": False,
                "project_path_included": False,
                "checks": [
                    {"name": "disposable_record_cleanup", "passed": False}
                ],
            },
        },
        request_id=3,
    )

    try:
        verify_mcp_handshake.summarize_installation_acceptance(
            acceptance,
            _tool_response({}, request_id=4),
            _tool_response({}, request_id=5),
        )
    except ValueError as error:
        assert str(error) == "Disposable project Recall was not verified"
    else:
        raise AssertionError("unverified cleanup must fail closed")
