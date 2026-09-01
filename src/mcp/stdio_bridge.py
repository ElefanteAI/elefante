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
SESSION_RECOVERY_POSTMORTEM = "workspace/postmortems/installation.md#issue-26"


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
        "X-Elefante-Client-CWD": os.environ.get("ELEFANTE_CLIENT_CWD") or os.getcwd(),
    }


def parse_request_line(line: str) -> dict:
    """Validate one bounded JSON-RPC line before forwarding it locally."""
    if len(line.encode("utf-8")) > MAX_BRIDGE_MESSAGE_BYTES:
        raise ValueError(f"MCP message exceeds {MAX_BRIDGE_MESSAGE_BYTES} byte bridge limit")
    request = json.loads(line)
    if not isinstance(request, dict):
        raise ValueError("MCP request must be a JSON object")
    return request


def request_headers(session_id: str | None = None) -> dict[str, str]:
    """Build one bounded bridge request header set."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        **provenance_headers(),
    }
    if session_id:
        headers["mcp-session-id"] = session_id
    return headers


def post_request(
    client: httpx.Client,
    url: str,
    request: dict,
    session_id: str | None = None,
) -> httpx.Response:
    """Forward one JSON-RPC request to the loopback daemon."""
    return client.post(url, json=request, headers=request_headers(session_id))


def recover_session(
    client: httpx.Client,
    url: str,
    initialize_request: dict,
    initialized_notification: dict | None,
) -> str:
    """Recreate one daemon session after its prior session ID became unknown."""
    initialize_response = post_request(client, url, initialize_request)
    initialize_response.raise_for_status()
    session_id = initialize_response.headers.get("mcp-session-id")
    if not session_id:
        raise RuntimeError(
            "Elefante daemon did not return an MCP session ID during recovery; "
            f"see {SESSION_RECOVERY_POSTMORTEM}"
        )
    if initialized_notification is not None:
        initialized_response = post_request(
            client,
            url,
            initialized_notification,
            session_id,
        )
        initialized_response.raise_for_status()
    return session_id


def main() -> None:
    """Forward newline-delimited MCP JSON-RPC messages between stdio and daemon HTTP."""
    url = daemon_url()
    session_id: str | None = None
    initialize_request: dict | None = None
    initialized_notification: dict | None = None
    with httpx.Client(timeout=120.0) as client:
        for line in sys.stdin:
            if not line.strip():
                continue
            request = None
            try:
                request = parse_request_line(line)
                response = post_request(client, url, request, session_id)
                if getattr(response, "status_code", None) == 404 and session_id:
                    method = request.get("method")
                    if method == "initialize":
                        session_id = None
                        response = post_request(client, url, request)
                    elif initialize_request is not None:
                        replay_notification = (
                            None
                            if method == "notifications/initialized"
                            else initialized_notification
                        )
                        session_id = recover_session(
                            client,
                            url,
                            initialize_request,
                            replay_notification,
                        )
                        response = post_request(client, url, request, session_id)
                    if getattr(response, "status_code", None) == 404:
                        raise RuntimeError(
                            "Elefante daemon rejected the MCP session after one "
                            "bounded recovery attempt; "
                            f"see {SESSION_RECOVERY_POSTMORTEM}"
                        )
                response.raise_for_status()
                session_id = response.headers.get("mcp-session-id", session_id)
                if request.get("method") == "initialize":
                    initialize_request = dict(request)
                    initialized_notification = None
                elif request.get("method") == "notifications/initialized":
                    initialized_notification = dict(request)
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
