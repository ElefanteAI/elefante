# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_mcp_handshake.py
# PURPOSE : Minimal JSON-RPC initialize probe plus a reusable safe Recall
#           capability inspector for customer readiness.
# WHEN    : After restart_elefante.py, to quickly confirm the server came back
#           and is accepting connections before running the full self-protocol.
#           Use this as the second check in the verification ladder:
#           verify_health → verify_mcp_handshake → verify_e2e_tests.
# USAGE   : python scripts/verify/verify_mcp_handshake.py
# NOTES   : The CLI starts the server briefly and proves only the initialize
#           handshake. Doctor uses the reusable inspector to list tools,
#           validate Recall's read-only annotations, and make one bounded
#           read-only probe without returning a memory body.
# ─────────────────────────────────────────────────────────────────────────────
import asyncio
import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.logger import get_logger  # noqa: E402
from src.utils.atomic_json import write_json_atomically  # noqa: E402

logger = get_logger("verification")

MCP_MODULE = "src.mcp.stdio_bridge"
HANDSHAKE_TIMEOUT_SECONDS = 30.0
INSTALL_ACCEPTANCE_TIMEOUT_SECONDS = 120.0
RECALL_TOOL_NAME = "elefante-Recall"
RECOVER_TOOL_NAME = "elefante-Recover"
FIRST_RUN_RECEIPT_FILE_NAME = ".elefante-first-run-receipt.json"
RECALL_PROBE_QUESTION = (
    "Elefante read-only readiness probe; use no prior project or user context."
)
RECALL_READY_STATUSES = frozenset({"supplied", "no_match", "blocked"})
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


def _json_object_without_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("MCP response contains duplicate JSON keys")
        result[key] = value
    return result


def _tool_payload(response: dict[str, Any]) -> dict[str, Any]:
    """Return one strict tool payload without logging customer-visible bodies."""
    if "error" in response:
        raise ValueError("MCP tool call failed")
    result = response.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    if not isinstance(content, list):
        raise ValueError("MCP tool response is invalid")
    text = next(
        (
            item.get("text")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ),
        None,
    )
    if text is None:
        raise ValueError("MCP tool response is invalid")
    payload = json.loads(text, object_pairs_hook=_json_object_without_duplicates)
    if not isinstance(payload, dict):
        raise ValueError("MCP tool response is invalid")
    return payload


def _installation_acceptance_declared(response: dict[str, Any]) -> bool:
    result = response.get("result")
    tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(tools, list):
        return False
    recover = next(
        (
            tool
            for tool in tools
            if isinstance(tool, dict) and tool.get("name") == RECOVER_TOOL_NAME
        ),
        None,
    )
    if recover is None:
        return False
    schema = recover.get("inputSchema")
    properties = schema.get("properties") if isinstance(schema, dict) else None
    action = properties.get("action") if isinstance(properties, dict) else None
    actions = action.get("enum") if isinstance(action, dict) else None
    return isinstance(actions, list) and "installation_acceptance" in actions


def summarize_installation_acceptance(
    acceptance_response: dict[str, Any],
    backup_plan_response: dict[str, Any],
    backup_response: dict[str, Any],
    *,
    now: str | None = None,
) -> dict[str, Any]:
    """Build one content-free receipt only from fully verified MCP outcomes."""
    acceptance = _tool_payload(acceptance_response)
    acceptance_receipt = acceptance.get("receipt")
    acceptance_checks = (
        acceptance_receipt.get("checks")
        if isinstance(acceptance_receipt, dict)
        else None
    )
    acceptance_checks = (
        acceptance_checks if isinstance(acceptance_checks, list) else []
    )
    passed_acceptance = {
        str(check.get("name"))
        for check in acceptance_checks
        if isinstance(check, dict) and check.get("passed") is True
    }
    required_acceptance = {
        "disposable_record_write",
        "project_scoped_recall",
        "disposable_record_cleanup",
    }
    if not (
        acceptance.get("success") is True
        and acceptance.get("status") == "VERIFIED_COMPLETE"
        and acceptance.get("recovery_status") == "VERIFIED_COMPLETE"
        and isinstance(acceptance_receipt, dict)
        and acceptance_receipt.get("memory_content_included") is False
        and acceptance_receipt.get("project_path_included") is False
        and isinstance(acceptance_receipt.get("operation_id"), str)
        and UUID_PATTERN.fullmatch(str(acceptance_receipt["operation_id"]))
        is not None
        and required_acceptance <= passed_acceptance
    ):
        raise ValueError("Disposable project Recall was not verified")

    backup_plan_payload = _tool_payload(backup_plan_response)
    plan = backup_plan_payload.get("plan")
    if not (
        backup_plan_payload.get("success") is True
        and isinstance(plan, dict)
        and plan.get("action") == "backup"
        and plan.get("applicable") is True
        and isinstance(plan.get("layout_sha256"), str)
        and SHA256_PATTERN.fullmatch(str(plan["layout_sha256"])) is not None
    ):
        raise ValueError("Initial backup plan was not verified")

    backup = _tool_payload(backup_response)
    backup_receipt = backup.get("receipt")
    backup_checks = (
        backup_receipt.get("checks") if isinstance(backup_receipt, dict) else None
    )
    if not (
        backup.get("success") is True
        and backup.get("status") == "VERIFIED_COMPLETE"
        and backup.get("recovery_status") == "VERIFIED_COMPLETE"
        and isinstance(backup_receipt, dict)
        and backup_receipt.get("status") == "VERIFIED_COMPLETE"
        and isinstance(backup_checks, list)
        and backup_checks
        and all(
            isinstance(check, dict) and check.get("passed") is True
            for check in backup_checks
        )
        and isinstance(backup_receipt.get("archive_sha256"), str)
        and SHA256_PATTERN.fullmatch(str(backup_receipt["archive_sha256"]))
        is not None
        and isinstance(backup_receipt.get("archive_name"), str)
        and bool(str(backup_receipt["archive_name"]).strip())
        and "/" not in str(backup_receipt["archive_name"])
        and "\\" not in str(backup_receipt["archive_name"])
        and isinstance(backup_receipt.get("operation_id"), str)
        and UUID_PATTERN.fullmatch(str(backup_receipt["operation_id"])) is not None
    ):
        raise ValueError("Initial local backup was not verified")

    finished_at = now or datetime.datetime.now(datetime.timezone.utc).isoformat()
    return {
        "schema_version": 1,
        "operation": "first_run_acceptance",
        "status": "VERIFIED_COMPLETE",
        "finished_at": finished_at,
        "checks": [
            {
                "name": "project_isolation",
                "passed": True,
                "code": "STRICT_PROJECT_RESOLVED",
            },
            {
                "name": "disposable_recall",
                "passed": True,
                "code": "PROJECT_SCOPED_RECALL_VERIFIED",
            },
            {
                "name": "acceptance_cleanup",
                "passed": True,
                "code": "DISPOSABLE_RECORD_CLEANUP_VERIFIED",
            },
            {
                "name": "initial_backup",
                "passed": True,
                "code": "INITIAL_BACKUP_VERIFIED",
            },
        ],
        "acceptance_operation_id": acceptance_receipt.get("operation_id"),
        "backup_operation_id": backup_receipt.get("operation_id"),
        "initial_backup": {
            "archive_name": backup_receipt["archive_name"],
            "archive_sha256": backup_receipt["archive_sha256"],
        },
        "memory_content_included": False,
        "project_path_included": False,
        "next_action": "open_elefante_home",
    }


def summarize_recall_capability(
    tools_response: dict[str, Any],
    call_response: dict[str, Any] | None,
) -> dict[str, Any]:
    """Reduce MCP responses to a safe readiness summary without context bodies."""
    tools_result = tools_response.get("result")
    tools = tools_result.get("tools", []) if isinstance(tools_result, dict) else []
    tools = tools if isinstance(tools, list) else []
    recall_tool = next(
        (
            tool
            for tool in tools
            if isinstance(tool, dict) and tool.get("name") == RECALL_TOOL_NAME
        ),
        None,
    )
    summary: dict[str, Any] = {
        "tool_count": len(tools),
        "tool_present": recall_tool is not None,
        "annotations_read_only": False,
        "probe_status": None,
        "probe_read_only": False,
        "recall_ready": False,
        "diagnostic": "recall_tool_missing",
    }
    if recall_tool is None:
        return summary

    annotations = recall_tool.get("annotations")
    annotations = annotations if isinstance(annotations, dict) else {}
    annotations_read_only = (
        annotations.get("readOnlyHint") is True
        and annotations.get("destructiveHint") is False
        and annotations.get("idempotentHint") is True
        and annotations.get("openWorldHint") is False
    )
    summary["annotations_read_only"] = annotations_read_only
    if not annotations_read_only:
        summary["diagnostic"] = "recall_annotations_invalid"
        return summary
    if call_response is None:
        summary["diagnostic"] = "recall_probe_not_run"
        return summary
    if "error" in call_response:
        summary["diagnostic"] = "recall_probe_failed"
        return summary

    call_result = call_response.get("result")
    content = call_result.get("content", []) if isinstance(call_result, dict) else []
    content = content if isinstance(content, list) else []
    text = next(
        (
            item.get("text")
            for item in content
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        ),
        None,
    )
    if text is None:
        summary["diagnostic"] = "recall_probe_invalid"
        return summary
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        summary["diagnostic"] = "recall_probe_invalid"
        return summary
    if not isinstance(payload, dict):
        summary["diagnostic"] = "recall_probe_invalid"
        return summary

    status = payload.get("status")
    read_only = payload.get("read_only") is True
    summary["probe_status"] = status if isinstance(status, str) else None
    summary["probe_read_only"] = read_only
    if status == "unavailable":
        summary["diagnostic"] = "recall_probe_unavailable"
        return summary
    if status not in RECALL_READY_STATUSES or not read_only:
        summary["diagnostic"] = "recall_probe_invalid"
        return summary

    summary["recall_ready"] = True
    summary["diagnostic"] = None
    return summary


async def _write_message(process, payload: dict[str, Any]) -> None:
    if process.stdin is None:
        raise RuntimeError("MCP bridge stdin is unavailable")
    process.stdin.write(json.dumps(payload).encode() + b"\n")
    await process.stdin.drain()


async def _read_response(process, request_id: int, timeout_seconds: float) -> dict:
    if process.stdout is None:
        raise RuntimeError("MCP bridge stdout is unavailable")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    while True:
        remaining = deadline - loop.time()
        if remaining <= 0:
            raise asyncio.TimeoutError
        line = await asyncio.wait_for(process.stdout.readline(), timeout=remaining)
        if not line:
            raise RuntimeError("MCP bridge closed before responding")
        try:
            response = json.loads(line.decode())
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if isinstance(response, dict) and response.get("id") == request_id:
            return response


async def inspect_mcp(
    *,
    probe_recall: bool,
    timeout_seconds: float = HANDSHAKE_TIMEOUT_SECONDS,
    root: Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Inspect one real customer bridge and return only bounded capability state."""
    resolved_root = (root or project_root).resolve()
    command = [python_executable or sys.executable, "-m", MCP_MODULE]
    process = None
    report: dict[str, Any] = {
        "handshake_ready": False,
        "capabilities": [],
        "tool_count": 0,
        "tool_present": False,
        "annotations_read_only": False,
        "probe_status": None,
        "probe_read_only": False,
        "recall_ready": False if probe_recall else None,
        "diagnostic": "mcp_transport_unavailable",
    }
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resolved_root),
            env={**os.environ, "PYTHONPATH": str(resolved_root)},
        )
        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ElefanteVerifier",
                        "version": "1.0",
                    },
                },
            },
        )
        initialize = await _read_response(process, 1, timeout_seconds)
        initialize_result = initialize.get("result")
        if not isinstance(initialize_result, dict):
            report["diagnostic"] = "mcp_initialize_failed"
            return report
        capabilities = initialize_result.get("capabilities", {})
        capabilities = capabilities if isinstance(capabilities, dict) else {}
        report["handshake_ready"] = True
        report["capabilities"] = sorted(capabilities)
        report["diagnostic"] = None

        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        if not probe_recall:
            return report

        await _write_message(
            process,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        tools_response = await _read_response(process, 2, timeout_seconds)
        preliminary = summarize_recall_capability(tools_response, None)
        if preliminary["tool_present"] and preliminary["annotations_read_only"]:
            await _write_message(
                process,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": RECALL_TOOL_NAME,
                        "arguments": {"question": RECALL_PROBE_QUESTION},
                    },
                },
            )
            call_response = await _read_response(process, 3, timeout_seconds)
            preliminary = summarize_recall_capability(
                tools_response,
                call_response,
            )
        report.update(preliminary)
        return report
    except asyncio.TimeoutError:
        report["diagnostic"] = "mcp_probe_timeout"
        return report
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        report["diagnostic"] = "mcp_transport_unavailable"
        return report
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


async def inspect_recall_capability(
    *,
    timeout_seconds: float = HANDSHAKE_TIMEOUT_SECONDS,
    root: Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    return await inspect_mcp(
        probe_recall=True,
        timeout_seconds=timeout_seconds,
        root=root,
        python_executable=python_executable,
    )


async def verify_installation_acceptance(
    *,
    workspace: str,
    timeout_seconds: float = INSTALL_ACCEPTANCE_TIMEOUT_SECONDS,
    root: Path | None = None,
    python_executable: str | None = None,
) -> dict[str, Any]:
    """Prove disposable Recall plus a verified initial backup through MCP."""
    resolved_root = (root or project_root).resolve()
    raw_workspace = str(workspace or "").strip()
    report: dict[str, Any] = {
        "success": False,
        "diagnostic": "installation_acceptance_unavailable",
        "receipt_path": None,
    }
    try:
        selected_workspace = Path(raw_workspace).expanduser()
        if not selected_workspace.is_absolute():
            raise ValueError("installation workspace must be absolute")
        selected_workspace = selected_workspace.resolve(strict=True)
        if not selected_workspace.is_dir():
            raise ValueError("installation workspace must be a directory")
    except (OSError, RuntimeError, ValueError):
        report["diagnostic"] = "installation_workspace_invalid"
        return report

    command = [python_executable or sys.executable, "-m", MCP_MODULE]
    process = None
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resolved_root),
            env={
                **os.environ,
                "PYTHONPATH": str(resolved_root),
                "ELEFANTE_CLIENT_TOOL": "elefante-installer",
                "ELEFANTE_CLIENT_CWD": str(selected_workspace),
            },
        )
        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "ElefanteInstaller",
                        "version": "1.0",
                    },
                },
            },
        )
        initialize = await _read_response(process, 1, timeout_seconds)
        if not isinstance(initialize.get("result"), dict):
            report["diagnostic"] = "mcp_initialize_failed"
            return report
        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            },
        )
        await _write_message(
            process,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        tools_response = await _read_response(process, 2, timeout_seconds)
        if not _installation_acceptance_declared(tools_response):
            report["diagnostic"] = "installation_acceptance_not_declared"
            return report

        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": RECOVER_TOOL_NAME,
                    "arguments": {
                        "action": "installation_acceptance",
                        "workspace": str(selected_workspace),
                    },
                },
            },
        )
        acceptance_response = await _read_response(process, 3, timeout_seconds)

        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": RECOVER_TOOL_NAME,
                    "arguments": {"action": "backup"},
                },
            },
        )
        backup_plan_response = await _read_response(process, 4, timeout_seconds)
        plan_payload = _tool_payload(backup_plan_response)
        plan = plan_payload.get("plan")
        layout_sha256 = (
            plan.get("layout_sha256") if isinstance(plan, dict) else None
        )
        if (
            plan_payload.get("success") is not True
            or not isinstance(plan, dict)
            or plan.get("applicable") is not True
            or not isinstance(layout_sha256, str)
            or SHA256_PATTERN.fullmatch(layout_sha256) is None
        ):
            report["diagnostic"] = "initial_backup_plan_failed"
            return report

        await _write_message(
            process,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": RECOVER_TOOL_NAME,
                    "arguments": {
                        "action": "backup",
                        "apply": True,
                        "confirm": True,
                        "expected_layout_sha256": layout_sha256,
                        "invocation_mode": "workflow_managed",
                    },
                },
            },
        )
        backup_response = await _read_response(process, 5, timeout_seconds)
        receipt = summarize_installation_acceptance(
            acceptance_response,
            backup_plan_response,
            backup_response,
        )
        receipt_path = resolved_root / FIRST_RUN_RECEIPT_FILE_NAME
        if receipt_path.is_symlink() or receipt_path.parent.is_symlink():
            raise ValueError("installation receipt target is unsafe")
        write_json_atomically(receipt_path, receipt)
        persisted = json.loads(
            receipt_path.read_text(encoding="utf-8"),
            object_pairs_hook=_json_object_without_duplicates,
        )
        if persisted != receipt or receipt_path.stat().st_mode & 0o777 != 0o600:
            raise ValueError("installation receipt readback failed")
        report.update(
            success=True,
            diagnostic=None,
            receipt_path=str(receipt_path),
        )
        return report
    except asyncio.TimeoutError:
        report["diagnostic"] = "installation_acceptance_timeout"
        return report
    except (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError):
        report["diagnostic"] = "installation_acceptance_failed"
        return report
    finally:
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


async def verify_handshake(timeout_seconds: float = HANDSHAKE_TIMEOUT_SECONDS):
    """
    Simulates a real MCP connection handshake.
    1. Starts the server process.
    2. Sends 'initialize' JSON-RPC request.
    3. Expects valid 'initialize' result with capabilities.
    4. Sends 'notifications/initialized'.
    5. Validates server is truly responsive (not just a running process).
    """
    logger.info("Testing MCP Server Handshake...")
    report = await inspect_mcp(
        probe_recall=False,
        timeout_seconds=timeout_seconds,
    )
    if not report["handshake_ready"]:
        logger.error("Verification failed", diagnostic=report["diagnostic"])
        return False
    logger.info(
        "Handshake OK",
        capabilities=report["capabilities"],
    )
    logger.info("Verification complete: MCP Server is speaking protocol.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--installation-acceptance",
        action="store_true",
        help="Run the official disposable project Recall and initial-backup proof.",
    )
    options = parser.parse_args()
    if options.installation_acceptance:
        acceptance = asyncio.run(
            verify_installation_acceptance(
                workspace=os.environ.get("ELEFANTE_ACCEPTANCE_WORKSPACE", ""),
            )
        )
        success = acceptance["success"] is True
        if success:
            logger.info("Installation acceptance verified")
        else:
            logger.error(
                "Installation acceptance failed",
                diagnostic=acceptance["diagnostic"],
            )
    else:
        success = asyncio.run(verify_handshake())
    if not success:
        sys.exit(1)
    sys.exit(0)
