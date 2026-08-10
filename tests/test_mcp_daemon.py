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
from mcp import types as mcp_types

from src.mcp.server import (
    ElefanteMCPServer,
    MEMORY_SEARCH_GUIDANCE,
    answer_context_metadata,
    compile_answer_context,
)
from src.models.memory import Memory, MemoryMetadata, MemoryStatus, MemoryType
from src.models.query import SearchResult
from src.utils.token_counter import estimate_tokens


BRIDGE_RESPONSE_TIMEOUT_SECONDS = 60


def _context_result(
    content: str,
    *,
    category: str = "project",
    memory_type: MemoryType = MemoryType.FACT,
    score: float = 0.7,
    vector_score: float = 0.7,
) -> SearchResult:
    return SearchResult(
        memory=Memory(
            content=content,
            metadata=MemoryMetadata(
                category=category,
                memory_type=memory_type,
            ),
        ),
        score=score,
        vector_score=vector_score,
        source="vector",
    )


def test_answer_context_selects_answer_bearing_memory_and_rejects_related_noise():
    relevant = _context_result(
        "Elefante customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        vector_score=0.70,
    )
    relevant.explanation = {
        "signals": [{"name": "concept_overlap", "score": 0.40}]
    }
    noise = _context_result(
        "Cognitive retrieval combines vector, authority, temporal, and concept scores.",
        score=0.95,
        vector_score=0.60,
    )

    context = compile_answer_context(
        "What did we decide about global installation across IDEs?",
        [noise, relevant],
    )

    assert "one global runtime" in context.text
    assert "Cognitive retrieval" not in context.text
    assert context.text.startswith("# Elefante answer context")
    assert context.selected_count == 1
    assert "decision" in context.selection_reasons[0]
    assert "signals=lexical" in context.selection_reasons[0]
    assert str(relevant.memory.id) not in context.text
    assert "[Evidence 1]" in context.text
    assert estimate_tokens(context.text) <= 450
    metadata = answer_context_metadata(
        "What did we decide about global installation across IDEs?",
        [noise, relevant],
    )
    assert metadata["selected_result_numbers"] == [2]
    assert metadata["selected_evidence"][0]["verified"] is False
    assert metadata["selected_evidence"][0]["reason_selected"] == context.selection_reasons[0]


def test_answer_context_abstains_and_withholds_unrequested_system_test_memory():
    passcode = _context_result(
        "The Elefante test passcode is Indigo-Echo.",
        category="system-test",
        score=0.99,
        vector_score=0.99,
    )

    unrelated = compile_answer_context(
        "How should Elefante improve answers using prior decisions?",
        [passcode],
    )
    explicit = compile_answer_context(
        "What is my Elefante test passcode?",
        [passcode],
    )

    assert unrelated.selected_count == 0
    assert "Indigo-Echo" not in unrelated.text
    assert explicit.selected_count == 1
    assert "Indigo-Echo" in explicit.text


def test_answer_context_abstains_when_only_one_weak_signal_matches():
    lexical_only = _context_result(
        "The global runtime decision is retained for compatible IDEs.",
        score=0.70,
        vector_score=0.70,
    )

    context = compile_answer_context(
        "What is the global runtime decision for compatible IDEs?",
        [lexical_only],
    )

    assert context.selected_count == 0
    assert context.selection_reasons == ()


def test_answer_context_reserves_user_locked_always_memory() -> None:
    mandatory = _context_result(
        "The customer release must use the signed installer.",
        score=0.05,
        vector_score=0.05,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    context = compile_answer_context("What is the release rule?", [mandatory])

    assert context.selected_count == 1
    assert str(mandatory.memory.id) in context.selected_memory_ids
    assert "user-locked always-inject" in context.selection_reasons[0]


def test_answer_context_rejects_unmatched_triggered_memory() -> None:
    triggered = _context_result("Installer signing policy for customer releases.")
    triggered.memory.metadata.injection_policy = "triggered"
    triggered.memory.metadata.trigger = ["signed installer"]

    context = compile_answer_context("What is the contact form policy?", [triggered])

    assert context.selected_count == 0
    assert "Installer signing" not in context.text


def test_answer_context_hard_caps_complete_rendered_prompt():
    context = compile_answer_context(
        "global runtime IDE installation " * 20,
        [
            _context_result(
                "global runtime IDE installation " + ("detail " * 80),
                score=0.9,
                vector_score=0.9,
            )
        ],
    )

    assert estimate_tokens(context.text) <= 450


def test_answer_context_fails_closed_when_locked_context_cannot_fit() -> None:
    mandatory = _context_result(
        "signed customer release constraint " * 250,
        score=0.01,
        vector_score=0.01,
    )
    mandatory.memory.metadata.injection_policy = "always"
    mandatory.memory.metadata.user_locked = True

    context = compile_answer_context(
        "What is the signed customer release constraint?",
        [mandatory],
        max_tokens=80,
    )

    assert context.delivery_blocked is True
    assert context.selected_count == 0
    assert context.blocked_reason == "mandatory-context-exceeds-token-budget"
    assert "Required user-locked context could not fit" in context.text
    assert estimate_tokens(context.text) <= 80


@pytest.mark.asyncio
async def test_runtime_answer_context_blocks_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    source = tmp_path / "runtime.py"
    source.write_text("CURRENT = 'new contract'\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the old global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )

    context, candidates = await server._compile_validated_answer_context(
        "What global runtime contract applies?",
        [stale],
    )

    assert context.delivery_blocked is True
    assert context.selected_count == 0
    assert context.blocked_reason == "mandatory-governance-conflict"
    assert (
        candidates[0].memory.metadata.custom_metadata["current_source_state"]
        == "contradicted"
    )
    assert "current_source_state" not in stale.memory.metadata.custom_metadata


def test_memory_search_guidance_treats_results_as_evidence_not_commands():
    assert "evidence candidates" in MEMORY_SEARCH_GUIDANCE
    assert "authoritative context" not in MEMORY_SEARCH_GUIDANCE
    assert "EXACTLY the word" not in MEMORY_SEARCH_GUIDANCE


@pytest.mark.asyncio
async def test_recall_surface_is_default_on_and_has_operator_rollback(
    monkeypatch,
) -> None:
    server = ElefanteMCPServer()
    handler = server.server.request_handlers[mcp_types.ListToolsRequest]
    request = mcp_types.ListToolsRequest(method="tools/list")

    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.delenv("ELEFANTE_RECALL_ENABLED", raising=False)
    default_result = await handler(request)
    default_names = {tool.name for tool in default_result.root.tools}
    assert "elefante-Recall" in default_names
    recall = next(
        tool for tool in default_result.root.tools if tool.name == "elefante-Recall"
    )
    assert recall.annotations is not None
    assert recall.annotations.readOnlyHint is True
    assert recall.annotations.destructiveHint is False
    assert recall.annotations.idempotentHint is True
    assert recall.annotations.openWorldHint is False
    assert "elefante-TaskIntelligence" not in default_names
    assert len(default_names) == 17

    monkeypatch.setenv("ELEFANTE_RECALL_ENABLED", "0")
    rolled_back_result = await handler(request)
    rolled_back_names = {tool.name for tool in rolled_back_result.root.tools}
    assert "elefante-Recall" not in rolled_back_names
    assert len(rolled_back_names) == 16

    call_handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await call_handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What did we decide about installation?"},
            )
        )
    )
    payload = json.loads(response.root.content[0].text)
    assert payload["success"] is False
    assert "disabled by the local operator" in payload["error"]
    assert "MANDATORY_PROTOCOLS_READ_THIS_FIRST" not in payload
    assert "ENTRYPOINT_SEQUENCE_READ_THIS_FIRST" not in payload
    assert "DIRECTIVES" not in payload
    assert "TOKEN_STATS" not in payload


@pytest.mark.asyncio
async def test_recall_call_boundary_keeps_customer_payload_minimal(monkeypatch) -> None:
    server = ElefanteMCPServer()

    async def recall(_arguments):
        return {
            "success": True,
            "status": "supplied",
            "context": "# Elefante answer context\n\n- [Evidence 1] Copper-Orbit",
            "supplied_count": 1,
            "abstained": False,
            "delivery_blocked": False,
            "read_only": True,
        }

    monkeypatch.setattr(server, "_handle_recall", recall)
    handler = server.server.request_handlers[mcp_types.CallToolRequest]
    response = await handler(
        mcp_types.CallToolRequest(
            params=mcp_types.CallToolRequestParams(
                name="elefante-Recall",
                arguments={"question": "What is the launch codename?"},
            )
        )
    )
    payload = json.loads(response.root.content[0].text)

    assert set(payload) == {
        "success",
        "status",
        "context",
        "supplied_count",
        "abstained",
        "delivery_blocked",
        "read_only",
    }


@pytest.mark.asyncio
async def test_recall_returns_only_bounded_governed_context_without_internal_ids(
    monkeypatch,
) -> None:
    relevant = _context_result(
        "Elefante customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.7,
        vector_score=0.7,
    )
    noise = _context_result(
        "Cognitive retrieval combines vector, temporal, and authority scores.",
        score=0.99,
        vector_score=0.6,
    )

    class Orchestrator:
        async def search_memories(self, **kwargs):
            assert kwargs["mode"].value == "hybrid"
            assert kwargs["limit"] == 12
            assert kwargs["include_conversation"] is False
            assert kwargs["include_stored"] is True
            assert kwargs["reinforce_access"] is False
            return [noise, relevant]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_recall(
        {"question": "What did we decide about global installation across IDEs?"}
    )

    assert response["success"] is True
    assert response["status"] == "supplied"
    assert response["supplied_count"] == 1
    assert response["read_only"] is True
    assert "one global runtime" in response["context"]
    assert "Cognitive retrieval" not in response["context"]
    assert estimate_tokens(response["context"]) <= 450
    rendered = json.dumps(response)
    assert str(relevant.memory.id) not in rendered
    assert str(noise.memory.id) not in rendered


@pytest.mark.asyncio
async def test_recall_abstains_when_no_memory_safely_answers_question(
    monkeypatch,
) -> None:
    passcode = _context_result(
        "The Elefante system test passcode is Indigo-Echo.",
        category="system-test",
        score=0.99,
        vector_score=0.99,
    )

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [passcode]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_recall(
        {"question": "How should Elefante answer using prior project decisions?"}
    )

    assert response["success"] is True
    assert response["status"] == "no_match"
    assert response["supplied_count"] == 0
    assert response["abstained"] is True
    assert "Indigo-Echo" not in response["context"]


@pytest.mark.asyncio
async def test_legacy_implicit_context_is_default_off(monkeypatch) -> None:
    class FailIfCalled:
        async def search_memories(self, **_kwargs):
            raise AssertionError("default-off context must not search")

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", raising=False)
    monkeypatch.delenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", raising=False)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FailIfCalled()))

    payload = {"success": True}
    returned = await server._inject_context(
        payload,
        "elefante-TaskCreate",
        {"description": "Configure global runtime installation"},
    )

    assert returned is payload
    assert "RELEVANT_CONTEXT" not in returned


@pytest.mark.asyncio
async def test_opt_in_tool_context_uses_governed_answer_selector(monkeypatch) -> None:
    relevant = _context_result(
        "Decision: customer installation uses one global runtime for every compatible IDE.",
        memory_type=MemoryType.DECISION,
        score=0.7,
        vector_score=0.7,
    )
    noise = _context_result(
        "Cognitive retrieval uses temporal and authority scores.",
        score=0.99,
        vector_score=0.6,
    )

    class Orchestrator:
        async def search_memories(self, **kwargs):
            assert kwargs["mode"].value == "hybrid"
            assert kwargs["reinforce_access"] is False
            assert kwargs["apply_temporal_decay"] is False
            return [noise, relevant]

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    returned = await server._inject_context(
        {"success": True},
        "elefante-TaskCreate",
        {"description": "Use the global runtime installation decision across IDEs"},
    )

    context = returned["RELEVANT_CONTEXT"]
    assert context["status"] == "delivered"
    assert "one global runtime" in context["rendered_context"]
    assert "Cognitive retrieval" not in context["rendered_context"]
    assert context["selected_memory_ids"] == [str(relevant.memory.id)]


@pytest.mark.asyncio
async def test_opt_in_tool_context_never_injects_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_ENABLED", "1")
    monkeypatch.setenv("ELEFANTE_TASK_INTELLIGENCE_PILOT", "1")
    monkeypatch.setenv("ELEFANTE_TASK_CONTEXT_ON_TOOL_CALL", "1")
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    returned = await server._inject_context(
        {"success": True},
        "elefante-TaskCreate",
        {"description": "Apply the global runtime contract"},
    )

    assert returned["RELEVANT_CONTEXT"]["status"] == "blocked"
    assert stale.memory.content not in returned["RELEVANT_CONTEXT"]["rendered_context"]


def test_compliance_receipts_are_session_bound_one_use_and_hash_queries(monkeypatch) -> None:
    server = ElefanteMCPServer()
    active = {
        "tool": "codex",
        "instance_id": "window-a",
        "session_id": "session-a",
        "cwd": "/repo",
        "transport": "streamable-http",
    }
    monkeypatch.setattr(server, "_request_provenance", lambda: dict(active))

    receipt = server._record_compliance_search("private project decision", 2)
    stored = server._compliance_receipts[("codex", "window-a", "session-a")]

    assert stored["receipt_id"] == receipt
    assert stored["query_sha256"] != "private project decision"
    assert "private project decision" not in json.dumps(stored)

    active.update(tool="claude-code", instance_id="window-b", session_id="session-b")
    assert server._check_compliance_gate("elefante-MemoryAdd") is not None

    active.update(tool="codex", instance_id="window-a", session_id="session-a")
    assert server._check_compliance_gate("elefante-MemoryAdd") is None
    assert server._check_compliance_gate("elefante-MemoryAdd") is not None


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
async def test_memory_add_forwards_governance_fields(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **kwargs: object) -> Memory:
            captured.update(kwargs)
            return Memory(content="protected", metadata=MemoryMetadata())

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))
    monkeypatch.setattr(server, "_with_request_provenance", lambda args: args)

    result = await server._handle_add_memory(
        {
            "content": "protected",
            "memory_type": "fact",
            "retention_policy": "permanent",
            "injection_policy": "always",
            "scope": "global",
            "trigger": ["protected"],
            "user_locked": True,
            "invocation_mode": "user_directed",
        }
    )

    assert result["status"] == "stored"
    metadata = captured["metadata"]
    assert isinstance(metadata, dict)
    assert metadata["retention_policy"] == "permanent"
    assert metadata["injection_policy"] == "always"
    assert metadata["scope"] == "global"
    assert metadata["trigger"] == ["protected"]
    assert metadata["user_locked"] is True
    assert metadata["invocation_mode"] == "user_directed"


@pytest.mark.asyncio
async def test_workflow_cannot_claim_user_memory_authority(monkeypatch):
    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: (_ for _ in ()).throw(AssertionError("blocked before storage")),
    )

    result = await server._handle_add_memory(
        {
            "content": "automation cannot lock this",
            "memory_type": "fact",
            "user_locked": True,
        }
    )

    assert result["success"] is False
    assert result["authority_status"] == "BLOCKED"
    assert "cannot assert user_locked" in result["error"]


@pytest.mark.asyncio
async def test_memory_add_scrubs_secrets_before_storage(monkeypatch):
    captured: dict[str, object] = {}

    class FakeOrchestrator:
        _last_rejection_reason = None

        async def add_memory(self, **kwargs):
            captured.update(kwargs)
            return Memory(content=str(kwargs["content"]), metadata=MemoryMetadata())

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(FakeOrchestrator()))

    secret = "sk-" + ("a" * 32)
    result = await server._handle_add_memory(
        {
            "content": f"Never persist this key {secret}",
            "memory_type": "fact",
            "metadata": {"private_note": f"duplicate {secret}"},
        }
    )

    assert secret not in str(captured["content"])
    assert secret not in json.dumps(captured["metadata"])
    assert "[REDACTED:OPENAI_KEY]" in str(captured["content"])
    assert result["privacy_redactions"] == 2


@pytest.mark.asyncio
async def test_memory_update_scrubs_secrets_before_storage(monkeypatch):
    memory = Memory(content="existing decision", metadata=MemoryMetadata())
    captured: dict[str, object] = {}

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

        async def update_memory(self, _memory_id, values):
            captured.update(values)
            return True

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    secret = "sk-" + ("a" * 32)
    result = await server._handle_update_memory(
        {
            "memory_id": str(memory.id),
            "content": f"Never persist this key {secret}",
        }
    )

    assert secret not in str(captured["content"])
    assert "[REDACTED:OPENAI_KEY]" in str(captured["content"])
    assert result["privacy_redactions"] == 1


@pytest.mark.asyncio
async def test_memory_search_scrubs_legacy_secrets_from_complete_response(monkeypatch):
    secret = "sk-" + ("a" * 32)
    memory = Memory(
        content=f"Legacy content {secret}",
        metadata=MemoryMetadata(source_detail=f"api_key={secret.removeprefix('sk-')}"),
    )
    result = SearchResult(
        memory=memory,
        score=0.9,
        vector_score=0.9,
        source="vector",
    )

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [result]

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_search_memories(
        {"query": "legacy content", "include_conversation": False}
    )

    assert secret not in json.dumps(response)
    assert response["privacy_redactions"] == 2
    assert response["answer_context"]["selected_count"] == 0


@pytest.mark.asyncio
async def test_memory_search_answer_context_blocks_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {
            "tool": "pytest",
            "instance_id": "instance",
            "session_id": "session",
            "transport": "stdio",
            "cwd": str(tmp_path),
        },
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_search_memories(
        {"query": "What global runtime contract applies?", "include_conversation": False}
    )

    assert response["count"] == 1  # Broad search remains available for inspection.
    assert response["answer_context"]["delivery_blocked"] is True
    assert response["answer_context"]["selected_count"] == 0
    assert response["answer_context"]["blocked_reason"] == "mandatory-governance-conflict"


@pytest.mark.asyncio
async def test_prompt_and_recall_block_digest_stale_locked_memory(
    monkeypatch,
    tmp_path,
) -> None:
    from mcp.types import GetPromptRequest, GetPromptRequestParams

    (tmp_path / "runtime.py").write_text("CURRENT = True\n", encoding="utf-8")
    stale = _context_result(
        "Decision: use the stale global runtime contract.",
        memory_type=MemoryType.DECISION,
        score=0.99,
        vector_score=0.99,
    )
    stale.memory.metadata.file_path = "runtime.py"
    stale.memory.metadata.user_locked = True
    stale.memory.metadata.injection_policy = "always"
    stale.memory.metadata.custom_metadata = {"source_file_sha256": "0" * 64}

    class Orchestrator:
        async def search_memories(self, **_kwargs):
            return [stale]

    server = ElefanteMCPServer()
    monkeypatch.setattr(
        server,
        "_request_provenance",
        lambda: {"cwd": str(tmp_path)},
    )
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))
    handler = server.server.request_handlers[GetPromptRequest]

    response = await handler(
        GetPromptRequest(
            params=GetPromptRequestParams(
                name="elefante-context",
                arguments={"topic": "What global runtime contract applies?"},
            )
        )
    )
    rendered = response.root.messages[0].content.text

    assert "BLOCKED" in rendered
    assert stale.memory.content not in rendered

    recall = await server._handle_recall(
        {"question": "What global runtime contract applies?"}
    )
    assert recall["success"] is False
    assert recall["status"] == "blocked"
    assert recall["delivery_blocked"] is True
    assert stale.memory.content not in recall["context"]


@pytest.mark.asyncio
async def test_context_get_scrubs_nested_legacy_secrets(monkeypatch):
    secret = "sk-" + ("a" * 32)

    class Orchestrator:
        async def get_context(self, **_kwargs):
            return {
                "memories": [{"content": f"Legacy content {secret}"}],
                "entities": [{"properties": {"token": f"Bearer {secret}"}}],
            }

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(Orchestrator()))

    response = await server._handle_get_context({})

    assert secret not in json.dumps(response)
    assert response["privacy_redactions"] == 2


@pytest.mark.asyncio
async def test_workflow_cannot_change_protected_memory(monkeypatch):
    protected = Memory(
        content="user decision",
        metadata=MemoryMetadata(user_locked=True),
    )

    class VectorStore:
        async def get_memory(self, _memory_id):
            return protected

        async def update_memory(self, *_args, **_kwargs):
            raise AssertionError("protected memory must not be changed")

    orchestrator = SimpleNamespace(vector_store=VectorStore())
    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(server, "_get_orchestrator", lambda: _async_value(orchestrator))

    result = await server._handle_update_memory(
        {"memory_id": str(protected.id), "content": "automation rewrite"}
    )

    assert result["success"] is False
    assert result["authority_status"] == "BLOCKED"
    assert "user-directed" in result["error"]


@pytest.mark.asyncio
async def test_delete_archives_by_default_and_keeps_graph(monkeypatch):
    memory = Memory(content="recoverable decision", metadata=MemoryMetadata())
    updates: dict[str, object] = {}

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

        async def update_memory(self, _memory_id, values):
            updates.update(values)
            return True

        async def delete_memory(self, _memory_id):
            raise AssertionError("default delete must not be permanent")

    class GraphStore:
        async def delete_entity(self, _memory_id):
            raise AssertionError("archive must preserve graph provenance")

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(
            SimpleNamespace(vector_store=VectorStore(), graph_store=GraphStore())
        ),
    )
    monkeypatch.setattr(server, "_save_session_history", lambda: None)

    result = await server._handle_delete_memory(
        {"memory_id": str(memory.id), "reason": "no longer active"}
    )

    assert result["success"] is True
    assert result["delete_mode"] == "archive"
    assert result["recoverable"] is True
    assert updates["archived"] is True
    assert updates["deprecated"] is True
    assert updates["status"] == MemoryStatus.ARCHIVED


@pytest.mark.asyncio
async def test_permanent_delete_requires_user_confirmation(monkeypatch):
    memory = Memory(content="ordinary note", metadata=MemoryMetadata())

    class VectorStore:
        async def get_memory(self, _memory_id):
            return memory

    server = ElefanteMCPServer()
    monkeypatch.setattr(server, "_check_compliance_gate", lambda _: None)
    monkeypatch.setattr(
        server,
        "_get_orchestrator",
        lambda: _async_value(SimpleNamespace(vector_store=VectorStore())),
    )

    result = await server._handle_delete_memory(
        {
            "memory_id": str(memory.id),
            "reason": "requested cleanup",
            "delete_mode": "permanent",
        }
    )

    assert result["success"] is False
    assert result["authority_status"] == "CONFIRMATION_REQUIRED"
    assert "confirm_permanent=true" in result["error"]


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
