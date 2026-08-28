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
import json
import os
import sys
from pathlib import Path
from typing import Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from src.utils.logger import get_logger  # noqa: E402

logger = get_logger("verification")

MCP_MODULE = "src.mcp.stdio_bridge"
HANDSHAKE_TIMEOUT_SECONDS = 30.0
RECALL_TOOL_NAME = "elefante-Recall"
RECALL_PROBE_QUESTION = (
    "Elefante read-only readiness probe; use no prior project or user context."
)
RECALL_READY_STATUSES = frozenset({"supplied", "no_match", "blocked"})


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
    success = asyncio.run(verify_handshake())
    if not success:
        sys.exit(1)
    sys.exit(0)
