"""Runtime contracts for the shared local MCP daemon and its bridge."""

from contextlib import contextmanager
import concurrent.futures
import io
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

import httpx
import pytest

from src.mcp.server import ElefanteMCPServer
from src.models.memory import Memory, MemoryMetadata, MemoryType


BRIDGE_RESPONSE_TIMEOUT_SECONDS = 60


def test_stdio_bridge_accepts_only_loopback_and_emits_client_identity(monkeypatch):
    from src.mcp import stdio_bridge

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setenv("ELEFANTE_CLIENT_TOOL", "codex")
    monkeypatch.setenv("ELEFANTE_CLIENT_CWD", "/workspace/product")
    assert stdio_bridge.daemon_url() == "http://127.0.0.1:8765/mcp/"

    headers = stdio_bridge.provenance_headers()
    assert headers["X-Elefante-Client-Tool"] == "codex"
    assert headers["X-Elefante-Client-Instance-ID"] == stdio_bridge.BRIDGE_INSTANCE_ID
    assert headers["X-Elefante-Client-CWD"] == "/workspace/product"

    for unsafe_url in (
        "http://localhost:8765/mcp/",
        "https://memory.example.test/mcp",
        "http://127.0.0.1:8765/not-mcp",
        "http://127.0.0.1:70000/mcp",
    ):
        monkeypatch.setenv("ELEFANTE_DAEMON_URL", unsafe_url)
        with pytest.raises(RuntimeError, match="requires"):
            stdio_bridge.daemon_url()


def test_stdio_bridge_rejects_oversized_or_non_object_messages_before_forwarding():
    from src.mcp import stdio_bridge

    assert stdio_bridge.parse_request_line('{"jsonrpc":"2.0","id":1,"method":"ping"}') == {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "ping",
    }
    with pytest.raises(ValueError, match="bridge limit"):
        stdio_bridge.parse_request_line("x" * (stdio_bridge.MAX_BRIDGE_MESSAGE_BYTES + 1))
    with pytest.raises(ValueError, match="JSON object"):
        stdio_bridge.parse_request_line("[]")


def test_stdio_bridge_does_not_reuse_an_id_after_a_later_parse_failure(monkeypatch):
    from src.mcp import stdio_bridge

    class FakeResponse:
        headers = {}

        def raise_for_status(self):
            return None

        def json(self):
            return {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setenv("ELEFANTE_DAEMON_URL", "http://127.0.0.1:8765/mcp/")
    monkeypatch.setattr(stdio_bridge.httpx, "Client", lambda **_: FakeClient())
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"id":7,"method":"ping"}\nnot json\n'))
    stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stdout)

    stdio_bridge.main()

    assert [json.loads(line) for line in stdout.getvalue().splitlines()] == [
        {"jsonrpc": "2.0", "id": 7, "result": {"ok": True}}
    ]


def test_daemon_rejects_non_loopback_bind(monkeypatch):
    from src.mcp import daemon

    monkeypatch.setenv("ELEFANTE_DAEMON_HOST", "0.0.0.0")
    with pytest.raises(RuntimeError, match="127.0.0.1"):
        daemon.main()


@pytest.mark.asyncio
async def test_daemon_request_boundary_replays_valid_bodies_and_rejects_oversized_ones():
    """Direct HTTP clients must not bypass the bridge's input-size boundary."""
    from src.mcp.daemon import BoundedRequestBody

    received_bodies: list[bytes] = []

    async def inner_app(_scope, receive, send):
        received_bodies.append((await receive())["body"])
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    async def invoke(messages, headers=()):
        sent = []
        pending = iter(messages)

        async def receive():
            return next(pending, {"type": "http.disconnect"})

        async def send(message):
            sent.append(message)

        await BoundedRequestBody(inner_app, max_bytes=4)(
            {"type": "http", "method": "POST", "headers": list(headers)}, receive, send
        )
        return sent

    valid = await invoke([{"type": "http.request", "body": b"ping", "more_body": False}])
    assert received_bodies == [b"ping"]
    assert valid[0]["status"] == 204

    declared = await invoke(
        [{"type": "http.request", "body": b"", "more_body": False}],
        [(b"content-length", b"5")],
    )
    chunked = await invoke(
        [
            {"type": "http.request", "body": b"pin", "more_body": True},
            {"type": "http.request", "body": b"gg", "more_body": False},
        ]
    )
    assert received_bodies == [b"ping"]
    assert declared[0]["status"] == 413
    assert chunked[0]["status"] == 413


@pytest.mark.parametrize("port", ("0", "65536", "invalid"))
def test_daemon_rejects_invalid_local_port(monkeypatch, port):
    from src.mcp import daemon

    monkeypatch.setenv("ELEFANTE_DAEMON_PORT", port)
    with pytest.raises(RuntimeError, match="1 to 65535"):
        daemon.daemon_port()


def test_configuration_creates_a_clean_home_directory(monkeypatch, tmp_path):
    """A first-run home may not exist yet in containers or fresh accounts."""
    from src.utils.config import Config

    clean_home = tmp_path / "new-user-home"
    monkeypatch.setenv("HOME", str(clean_home))
    monkeypatch.setenv("ELEFANTE_DATA_DIR", str(clean_home / ".elefante" / "data"))
    config = Config()
    config._config = None
    config.load()

    assert (clean_home / ".elefante" / "data" / "vector").is_dir()


def test_server_uses_transport_owned_http_provenance(monkeypatch):
    server = ElefanteMCPServer()
    request = SimpleNamespace(
        headers={
            "mcp-session-id": "session-a",
            "x-elefante-client-tool": "claude-code",
            "x-elefante-client-instance-id": "window-a",
            "x-elefante-client-cwd": "/repo/elefante",
        }
    )
    # The SDK exposes request_context as a property. Patch the class-level
    # property for this unit boundary rather than manufacturing an HTTP stack.
    monkeypatch.setattr(
        type(server.server),
        "request_context",
        property(lambda _: SimpleNamespace(request=request, session=SimpleNamespace(client_params=None))),
    )

    args = server._with_request_provenance({"action": "add", "content": "remember"})
    assert args["metadata"]["elefante_source"] == {
        "tool": "claude-code",
        "instance_id": "window-a",
        "session_id": "session-a",
        "cwd": "/repo/elefante",
        "transport": "streamable-http",
    }


def test_server_rejects_control_characters_and_bounds_http_provenance(monkeypatch):
    """Untrusted bridge headers must remain safe to persist and render."""
    server = ElefanteMCPServer()
    request = SimpleNamespace(
        headers={
            "mcp-session-id": "session\nspoofed",
            "x-elefante-client-tool": "tool-" + ("a" * 200),
            "x-elefante-client-instance-id": "window\tspoofed",
            "x-elefante-client-cwd": "/repo/" + ("nested/" * 300),
        }
    )
    monkeypatch.setattr(
        type(server.server),
        "request_context",
        property(lambda _: SimpleNamespace(request=request, session=SimpleNamespace(client_params=None))),
    )

    source = server._with_request_provenance({"action": "add", "content": "remember"})[
        "metadata"
    ]["elefante_source"]

    assert source["tool"] == "tool-" + ("a" * 123)
    assert source["instance_id"] == "unknown-http-instance"
    assert source["session_id"] == "initializing"
    assert source["cwd"] == ("/repo/" + ("nested/" * 300))[:1024]


def test_server_rejects_control_characters_in_stdio_provenance(monkeypatch):
    monkeypatch.setenv("ELEFANTE_CLIENT_TOOL", "codex\r\nspoofed")
    monkeypatch.setenv("ELEFANTE_CLIENT_INSTANCE_ID", "window\tspoofed")
    monkeypatch.setenv("ELEFANTE_CLIENT_CWD", "/repo\tspoofed")

    source = ElefanteMCPServer()._request_provenance()

    assert source == {
        "tool": "unknown-stdio",
        "instance_id": source["instance_id"],
        "session_id": "stdio",
        "cwd": "",
        "transport": "stdio",
    }
    assert len(source["instance_id"]) == 32


def test_entrypoint_protocol_routes_to_the_current_issue_tracker():
    result = ElefanteMCPServer._inject_entrypoint_protocol(object(), {})
    pitfalls = ElefanteMCPServer._inject_pitfalls(object(), {}, "elefante-Memory")

    assert all("docs/debug" not in step for step in result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"])
    assert any("workspace/ISSUES.md" in step for step in result["ENTRYPOINT_SEQUENCE_READ_THIS_FIRST"])
    assert any("workspace/ISSUES.md" in item for item in pitfalls["MANDATORY_PROTOCOLS_READ_THIS_FIRST"])


def test_client_protocol_excludes_developer_workspace_routing(monkeypatch):
    from src.mcp import server as server_module

    monkeypatch.setattr(server_module, "is_client_runtime", lambda: True)
    result = ElefanteMCPServer._inject_entrypoint_protocol(object(), {})
    pitfalls = ElefanteMCPServer._inject_pitfalls(object(), {}, "elefante-Memory")
    rendered = json.dumps({"result": result, "pitfalls": pitfalls})

    assert "workspace/" not in rendered
    assert "tests/" not in rendered
    assert "API keys" in rendered


@pytest.mark.asyncio
async def test_memory_write_lock_encloses_the_actual_store_operation(monkeypatch):
    from src.mcp import server as server_module

    events: list[str] = []

    @contextmanager
    def recording_lock():
        events.append("entered")
        yield SimpleNamespace(acquired=True)
        events.append("exited")

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **_: object) -> Memory:
            assert events == ["entered"]
            return Memory(content="remembered", metadata=MemoryMetadata(memory_type=MemoryType.NOTE))

    monkeypatch.setattr(server_module, "write_lock", recording_lock)
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))
    monkeypatch.setattr(server, "_with_request_provenance", lambda args: {**args, "metadata": {}})

    result = await server._handle_add_memory({"content": "remembered", "memory_type": "note"})
    assert result["status"] == "stored"
    assert events == ["entered", "exited"]


@pytest.mark.asyncio
async def test_daemon_lifespan_releases_a_loaded_orchestrator():
    from src.mcp import daemon

    class CloseTrackingOrchestrator:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    app = daemon.create_app()
    orchestrator = CloseTrackingOrchestrator()

    async with app.router.lifespan_context(app):
        app.state.elefante_server.orchestrator = orchestrator

    assert orchestrator.closed
    assert app.state.elefante_server.orchestrator is None


@pytest.mark.asyncio
async def test_direct_stdio_main_releases_server_resources(monkeypatch):
    from src.mcp import server as server_module

    events: list[str] = []

    class CloseTrackingServer:
        async def run(self):
            events.append("run")

        async def close(self):
            events.append("close")

    monkeypatch.setattr(server_module, "ElefanteMCPServer", CloseTrackingServer)

    await server_module.main()

    assert events == ["run", "close"]


async def _async_value(value):
    return value


@pytest.mark.integration
@pytest.mark.slow
def test_two_bridge_clients_share_one_daemon_with_distinct_sources():
    """Two hosts write concurrently through one daemon without Kuzu contention."""
    repo = Path(__file__).resolve().parents[1]
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.close()

    with tempfile.TemporaryDirectory(prefix="elefante-daemon-") as temp_dir:
        temp_root = Path(temp_dir)
        host_huggingface_cache = Path(
            os.environ.get("HF_HOME", Path.home() / ".cache" / "huggingface")
        )
        env = {
            **os.environ,
            "PYTHONPATH": str(repo),
            "HOME": str(temp_root / "home"),
            "USERPROFILE": str(temp_root / "home"),
            "ELEFANTE_DATA_DIR": str(temp_root / "data"),
            "ELEFANTE_DAEMON_PORT": str(port),
            "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
            # Isolate Elefante data without forcing a second model download.
            # The fast suite warms this cache before the slow runtime proof.
            "HF_HOME": str(host_huggingface_cache),
        }
        daemon = subprocess.Popen(
            [sys.executable, "-m", "src.mcp.daemon"],
            cwd=repo,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        bridges: list[subprocess.Popen[str]] = []
        memory_ids: list[str] = []
        try:
            _wait_for_daemon(port, daemon)
            first = _start_bridge(repo, env, port, "codex", "codex-window")
            second = _start_bridge(repo, env, port, "claude-code", "claude-window")
            bridges.extend((first, second))

            for bridge, client_name in ((first, "Codex"), (second, "Claude Code")):
                initialized = _bridge_request(
                    bridge,
                    1,
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": client_name, "version": "1"},
                    },
                )
                assert initialized["serverInfo"]["name"] == "elefante"
                _bridge_notification(bridge, "notifications/initialized", {})
                _bridge_request(
                    bridge,
                    2,
                    "tools/call",
                    {
                        "name": "elefante-Memory",
                        "arguments": {
                            "action": "search",
                            "query": "shared daemon provenance marker",
                            "limit": 1,
                        },
                    },
                )

            marker = f"shared-daemon-{port}"
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                futures = [
                    executor.submit(
                        _bridge_request,
                        bridge,
                        3,
                        "tools/call",
                        {
                            "name": "elefante-Memory",
                            "arguments": {
                                "action": "add",
                                "content": f"Daemon provenance {marker} host {index}",
                                "memory_type": "note",
                                "domain": "project",
                                "category": "provenance",
                                "force_new": True,
                            },
                        },
                    )
                    for index, bridge in enumerate((first, second), start=1)
                ]
                stored = [future.result() for future in futures]

            payloads = [json.loads(response["content"][0]["text"]) for response in stored]
            assert [payload["status"] for payload in payloads] == ["stored", "stored"]
            memory_ids = [payload["memory_id"] for payload in payloads]
        finally:
            for bridge in bridges:
                _terminate(bridge)
            _terminate(daemon)

        verifier = subprocess.run(
            [
                sys.executable,
                "-c",
                (
                    "import asyncio, json, sys; "
                    "from src.core.graph_store import GraphStore; "
                    "store = GraphStore(database_path=sys.argv[1]); "
                    "query = sys.argv[2]; "
                    "print(json.dumps(asyncio.run(store.execute_query(query)), default=str))"
                ),
                str(temp_root / "data" / "kuzu_db"),
                (
                    "MATCH (m:Entity)-[:WRITTEN_BY]->(s:Source) "
                    f"WHERE m.id IN ['{memory_ids[0]}', '{memory_ids[1]}'] "
                    "RETURN s.tool, s.instance_id, s.transport"
                ),
            ],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
            timeout=20,
        )
        assert verifier.returncode == 0, verifier.stderr
        rows = json.loads(verifier.stdout)
        provenance = {tuple(row["values"]) for row in rows}
        assert provenance == {
            ("codex", "codex-window", "streamable-http"),
            ("claude-code", "claude-window", "streamable-http"),
        }


def _wait_for_daemon(port: int, daemon: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            response = httpx.get(f"http://127.0.0.1:{port}/health", timeout=1)
            if response.json() == {
                "status": "ok",
                "service": "elefante-daemon",
                "transport": "streamable-http",
            }:
                return
        except (httpx.HTTPError, ValueError):
            time.sleep(0.1)
    stderr = daemon.stderr.read() if daemon.stderr else ""
    raise AssertionError(f"daemon did not become ready: {stderr[-1000:]}")


def _start_bridge(
    repo: Path, base_env: dict[str, str], port: int, tool: str, instance_id: str
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [sys.executable, "-m", "src.mcp.stdio_bridge"],
        cwd=repo,
        env={
            **base_env,
            "ELEFANTE_DAEMON_URL": f"http://127.0.0.1:{port}/mcp/",
            "ELEFANTE_CLIENT_TOOL": tool,
            "ELEFANTE_CLIENT_INSTANCE_ID": instance_id,
            "ELEFANTE_CLIENT_CWD": f"/workspace/{tool}",
        },
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        start_new_session=True,
    )


def _bridge_request(
    bridge: subprocess.Popen[str], request_id: int, method: str, params: dict
) -> dict:
    assert bridge.stdin is not None
    assert bridge.stdout is not None
    assert bridge.stderr is not None
    bridge.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n")
    bridge.stdin.flush()
    ready, _, _ = select.select([bridge.stdout], [], [], BRIDGE_RESPONSE_TIMEOUT_SECONDS)
    if not ready:
        raise AssertionError(f"bridge timed out during {method}: {_available_stderr(bridge)[-1000:]}")
    line = bridge.stdout.readline()
    if not line:
        raise AssertionError(f"bridge ended during {method}: {_available_stderr(bridge)[-1000:]}")
    response = json.loads(line)
    assert "error" not in response, response
    return response["result"]


def _available_stderr(process: subprocess.Popen[str]) -> str:
    """Read only buffered diagnostics; never deadlock a timeout reporter."""
    if process.stderr is None:
        return ""
    chunks: list[bytes] = []
    while select.select([process.stderr], [], [], 0)[0]:
        chunk = os.read(process.stderr.fileno(), 4096)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks).decode("utf-8", errors="replace")


def _bridge_notification(bridge: subprocess.Popen[str], method: str, params: dict) -> None:
    assert bridge.stdin is not None
    bridge.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n")
    bridge.stdin.flush()


def _terminate(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
