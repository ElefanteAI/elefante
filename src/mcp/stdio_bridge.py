"""Transport-only stdio to Streamable HTTP bridge for Elefante MCP clients."""

from __future__ import annotations

import json
import os
import sys
from urllib.parse import urlparse
from uuid import uuid4

import httpx


DEFAULT_DAEMON_URL = "http://127.0.0.1:8765/mcp/"
MAX_BRIDGE_MESSAGE_BYTES = 1_048_576
BRIDGE_INSTANCE_ID = os.environ.get("ELEFANTE_CLIENT_INSTANCE_ID", uuid4().hex)


def daemon_url() -> str:
    """Return a loopback-only daemon endpoint; bridges never own local storage."""
    url = os.environ.get("ELEFANTE_DAEMON_URL", DEFAULT_DAEMON_URL).strip()
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as error:
        raise RuntimeError("Elefante stdio bridge requires a valid local daemon port") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname != "127.0.0.1"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path.rstrip("/") != "/mcp"
        or port is not None and not 1 <= port <= 65535
    ):
        raise RuntimeError("Elefante stdio bridge requires a 127.0.0.1 /mcp daemon URL")
    return url


def provenance_headers() -> dict[str, str]:
    """Return the bridge identity headers consumed by the local daemon."""
    return {
        "X-Elefante-Client-Tool": os.environ.get("ELEFANTE_CLIENT_TOOL", "unknown-stdio"),
        "X-Elefante-Client-Instance-ID": BRIDGE_INSTANCE_ID,
        "X-Elefante-Client-CWD": os.environ.get("ELEFANTE_CLIENT_CWD", ""),
    }


def parse_request_line(line: str) -> dict:
    """Validate one bounded JSON-RPC line before forwarding it locally."""
    if len(line.encode("utf-8")) > MAX_BRIDGE_MESSAGE_BYTES:
        raise ValueError(f"MCP message exceeds {MAX_BRIDGE_MESSAGE_BYTES} byte bridge limit")
    request = json.loads(line)
    if not isinstance(request, dict):
        raise ValueError("MCP request must be a JSON object")
    return request


def main() -> None:
    """Forward newline-delimited MCP JSON-RPC messages between stdio and daemon HTTP."""
    url = daemon_url()
    session_id: str | None = None
    with httpx.Client(timeout=120.0) as client:
        for line in sys.stdin:
            if not line.strip():
                continue
            request = None
            try:
                request = parse_request_line(line)
                headers = {
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json",
                    **provenance_headers(),
                }
                if session_id:
                    headers["mcp-session-id"] = session_id
                response = client.post(url, json=request, headers=headers)
                response.raise_for_status()
                session_id = response.headers.get("mcp-session-id", session_id)
                # MCP notifications intentionally return 202 with no response
                # body. Only JSON-RPC requests with an id may write to stdout.
                if request.get("id") is not None:
                    payload = response.json()
                    print(json.dumps(payload, separators=(",", ":")), flush=True)
            except Exception as error:
                request_id = request.get("id") if isinstance(request, dict) else None
                if request_id is not None:
                    print(json.dumps({"jsonrpc": "2.0", "id": request_id, "error": {"code": -32000, "message": str(error)}}), flush=True)


if __name__ == "__main__":
    main()
