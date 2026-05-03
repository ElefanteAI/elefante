#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : verify_e2e_tests.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Authoritative self-protocol harness: launches MCP server in an
#           isolated temp environment and proves the full live tool/prompt surface.
# WHEN    : Before any release. After changes to server.py, orchestrator.py,
#           or any core module. After a version bump to confirm the deployed
#           surface is intact. This is the ONLY script that proves the live
#           MCP surface end-to-end — do not substitute with unit tests.
# USAGE   : python scripts/verify/verify_e2e_tests.py [--with-dashboard-open]
# NOTES   : Launches a real MCP server subprocess in a temp dir. Slow (~60s)
#           but definitive. --with-dashboard-open enables the optional 20-tool
#           sweep including dashboard tools. Requires all dependencies installed.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Elefante self-protocol verification harness.

Runs the real MCP server in an isolated temporary Elefante home/data dir and
verifies the live MCP surface one feature family at a time.

Default mode is safe and self-contained:
    - verifies 19/20 tools + 2 prompts
    - excludes `elefante-DashboardOpen` because that tool binds fixed port 8000
      and attempts to open a browser outside the temp store

Optional full-surface mode:
    - pass `--with-dashboard-open` to include `elefante-DashboardOpen(refresh=True)`
    - only runs if port 8000 is free before the harness starts
    - stubs browser launch via `BROWSER=/usr/bin/true`
    - kills the spawned dashboard server during cleanup

Runs:
    .venv/bin/python scripts/verify/verify_e2e_tests.py

Full surface:
    .venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open

Isolation:
    Creates a temporary HOME/USERPROFILE and ELEFANTE_DATA_DIR for spawned MCP servers.
    Also enables ELEFANTE_ALLOW_TEST_MEMORIES=1 so the harness never pollutes the user's
    durable store and does not depend on external shell setup.

What it verifies:
    1. MCP initialize/handshake succeeds
    2. Current tool and prompt inventories are exposed over the real MCP surface
    3. Prompt retrieval works for both grounding and live context lookup
    4. Success and failure responses inject routing/directive contracts
    5. System, directive, memory, graph, context, session, task, ETL, and refinery tools work
    6. The Compliance Gate blocks ungrounded writes
    7. Stored state survives a simulated MCP restart
    8. Cleanup stays isolated from the user's durable store
    9. Optional dashboard open/refresh runs only in explicit full-surface mode

Documentation:
    - agents/orchestrator.md
    - docs/reference/self-protocol.md
    - tests/README.md
    - scripts/README.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src import __version__ as ELEFANTE_VERSION


REQUEST_TIMEOUT_SECONDS = 180
STREAM_LIMIT_BYTES = 1024 * 1024
PASS = "PASS"
FAIL = "FAIL"

EXPECTED_TOOLS = {
    # Memory operations consolidated into single tool with action discriminator (v2.10.0 atomic swap, 2026-05-02)
    "elefante-Memory",
    "elefante-GraphConnect",
    "elefante-GraphQuery",
    "elefante-ContextGet",
    "elefante-SessionsList",
    "elefante-SystemStatusGet",
    "elefante-System",
    "elefante-DashboardOpen",
    "elefante-ETLProcess",
    "elefante-ETLClassify",
    "elefante-TaskCreate",
    "elefante-TaskUpdate",
    "elefante-TaskGraph",
    "elefante-DirectiveAdd",
    "elefante-DirectiveList",
    "elefante-DirectiveRemove",
}

EXPECTED_PROMPTS = {"elefante-grounding", "elefante-context"}


class MCPClient:
    """Thin JSON-RPC 2.0 client over stdin/stdout to a real MCP server subprocess."""

    def __init__(self, env: dict[str, str]):
        self.process: asyncio.subprocess.Process | None = None
        self._id = 0
        self._env = env

    async def start(self) -> dict:
        cmd = [sys.executable, "-m", "src.mcp.server"]
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env=self._env,
            limit=STREAM_LIMIT_BYTES,
        )
        response = await self._send(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "SelfProtocolHarness", "version": ELEFANTE_VERSION},
            },
        )
        await self._notify("notifications/initialized", {})
        return response

    async def list_tools(self) -> dict | list:
        return await self._send("tools/list", {})

    async def list_prompts(self) -> dict | list:
        return await self._send("prompts/list", {})

    async def get_prompt(self, name: str, arguments: dict | None = None) -> dict:
        return await self._send(
            "prompts/get",
            {
                "name": name,
                "arguments": arguments or {},
            },
        )

    async def call_tool(self, name: str, args: dict) -> dict:
        response = await self._send(
            "tools/call",
            {
                "name": name,
                "arguments": args,
            },
        )
        if isinstance(response, dict) and "content" in response:
            for block in response["content"]:
                if block.get("type") == "text":
                    try:
                        return json.loads(block["text"])
                    except json.JSONDecodeError:
                        return {"raw": block["text"]}
        return response if isinstance(response, dict) else {"raw": response}

    async def stop(self) -> None:
        if self.process is None:
            return
        if self.process.returncode is not None:
            return
        self.process.terminate()
        try:
            await asyncio.wait_for(self.process.wait(), timeout=5)
        except asyncio.TimeoutError:
            self.process.kill()
            await self.process.wait()

    def _require_streams(self):
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
            or self.process.stderr is None
        ):
            raise RuntimeError("MCP subprocess streams are not initialized")
        return self.process.stdin, self.process.stdout, self.process.stderr

    async def _send(self, method: str, params: dict) -> dict | list:
        self._id += 1
        message = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        stdin, stdout, stderr = self._require_streams()
        stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        await stdin.drain()
        line = await asyncio.wait_for(stdout.readline(), timeout=REQUEST_TIMEOUT_SECONDS)
        if not line:
            stderr_text = (await stderr.read()).decode("utf-8", errors="replace")
            raise RuntimeError(f"Server closed. stderr: {stderr_text[:800]}")
        response = json.loads(line.decode("utf-8"))
        if "error" in response:
            raise RuntimeError(f"RPC error: {response['error']}")
        return response.get("result", response)

    async def _notify(self, method: str, params: dict) -> None:
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        stdin, _, _ = self._require_streams()
        stdin.write(json.dumps(message).encode("utf-8") + b"\n")
        await stdin.drain()


def _header(text: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def _result(name: str, ok: bool, detail: str = "") -> bool:
    tag = f"  [{PASS}]" if ok else f"  [{FAIL}]"
    line = f"{tag} {name}"
    if detail:
        line += f" -- {detail}"
    print(line)
    return ok


def _as_list(payload: dict | list, key: str) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    return []


def _json_text(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, default=str)


def _prompt_text(payload: dict) -> str:
    parts: list[str] = []
    for message in payload.get("messages", []):
        content = message.get("content", {})
        if isinstance(content, dict) and content.get("type") == "text":
            parts.append(content.get("text", ""))
    return "\n\n".join(parts)


def _search_contains(response: dict, needle: str) -> bool:
    for item in response.get("results", []):
        content = item.get("memory", {}).get("content", "")
        if needle in content:
            return True
    return False


def _memory_by_id(memories: list[dict], memory_id: str) -> dict | None:
    for memory in memories:
        if memory.get("id") == memory_id:
            return memory
    return None


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _kill_port(port: int) -> None:
    try:
        result = subprocess.run(
            ["lsof", "-ti", f":{port}"],
            capture_output=True,
            text=True,
            check=False,
        )
        for pid in result.stdout.split():
            subprocess.run(["kill", pid], capture_output=True, text=True, check=False)
    except Exception:
        pass


async def _store_memory(
    client: MCPClient,
    *,
    content: str,
    memory_type: str,
    category: str,
    tags: list[str],
) -> tuple[bool, str, dict]:
    response = await client.call_tool(
        "elefante-Memory",
        {"action": "add", 
            "content": content,
            "memory_type": memory_type,
            "domain": "project",
            "category": category,
            "tags": tags,
        },
    )
    memory_id = response.get("memory_id") or response.get("embedding_id") or ""
    ok = response.get("status") == "stored" and bool(memory_id)
    return ok, memory_id, response


async def _list_protocol_memories(client: MCPClient, tag: str) -> tuple[dict, list[dict]]:
    response = await client.call_tool(
        "elefante-Memory",
        {"action": "search", 
            "query": tag,
            "list_all": True,
            "limit": 100,
        },
    )
    memories = [memory for memory in response.get("memories", []) if tag in memory.get("content", "")]
    return response, memories


async def run_e2e(with_dashboard_open: bool) -> int:
    results: list[bool] = []
    test_tag = f"self-protocol-{uuid4().hex[:8]}"
    temp_root_manager = tempfile.TemporaryDirectory(prefix="elefante-e2e-")
    temp_root = Path(temp_root_manager.name)
    temp_home = temp_root / "home"
    temp_data_dir = temp_root / "data"
    temp_home.mkdir(parents=True, exist_ok=True)
    temp_data_dir.mkdir(parents=True, exist_ok=True)

    # Preserve real model cache paths so the isolated subprocess does not
    # re-download embedding models.  HOME/USERPROFILE are overridden for
    # Elefante data isolation, but HuggingFace and torch resolve their caches
    # from those vars on Windows.  Pin the real cache locations explicitly.
    real_home = os.environ.get("USERPROFILE") or os.environ.get("HOME", "")
    real_hf_home = os.environ.get("HF_HOME", os.path.join(real_home, ".cache", "huggingface"))
    real_torch_home = os.environ.get("TORCH_HOME", os.path.join(real_home, ".cache", "torch"))

    harness_env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "HOME": str(temp_home),
        "USERPROFILE": str(temp_home),
        "ELEFANTE_DATA_DIR": str(temp_data_dir),
        "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
        "BROWSER": "/usr/bin/true",
        "HF_HOME": real_hf_home,
        "TORCH_HOME": real_torch_home,
        "SENTENCE_TRANSFORMERS_HOME": os.environ.get(
            "SENTENCE_TRANSFORMERS_HOME",
            os.path.join(real_hf_home, "hub"),
        ),
    }

    client: MCPClient | None = None
    client2: MCPClient | None = None
    dashboard_started = False

    memory_ids: dict[str, str] = {}
    task_id = ""
    session_entity_name = f"Harness Session {test_tag}"
    project_entity_name = f"Harness Project {test_tag}"
    directive_id = ""

    _header(f"Elefante Self-Protocol Harness v{ELEFANTE_VERSION}")
    print("  Purpose : whole-system MCP proof in isolated temp HOME + data")
    print("  Surface : 19/20 tools + 2 prompts by default")
    print("  Dashboard tool:", "enabled" if with_dashboard_open else "skipped by default")
    print(f"  Tag     : {test_tag}")

    try:
        if with_dashboard_open:
            dashboard_port_free = not _port_in_use(8000)
            results.append(
                _result(
                    "Dashboard preflight port 8000 free",
                    dashboard_port_free,
                    "required for opt-in DashboardOpen verification",
                )
            )
            if not dashboard_port_free:
                return 1

        _header("PHASE 1: Boot MCP server")
        client = MCPClient(harness_env)
        await client.start()
        results.append(_result("MCP handshake", True, "server initialized"))

        _header("PHASE 2: Surface inventory")
        tool_listing = await client.list_tools()
        tools = _as_list(tool_listing, "tools")
        tool_names = {tool.get("name") for tool in tools if isinstance(tool, dict)}
        results.append(
            _result(
                "Tool inventory matches live MCP surface",
                tool_names == EXPECTED_TOOLS,
                f"expected {len(EXPECTED_TOOLS)}, got {len(tool_names)}",
            )
        )

        prompt_listing = await client.list_prompts()
        prompts = _as_list(prompt_listing, "prompts")
        prompt_names = {prompt.get("name") for prompt in prompts if isinstance(prompt, dict)}
        results.append(
            _result(
                "Prompt inventory matches live MCP surface",
                prompt_names == EXPECTED_PROMPTS,
                f"expected {len(EXPECTED_PROMPTS)}, got {len(prompt_names)}",
            )
        )

        grounding_prompt = await client.get_prompt("elefante-grounding")
        grounding_text = _prompt_text(grounding_prompt)
        results.append(
            _result(
                "Grounding prompt retrieved",
                "elefante-Memory" in grounding_text and "When in doubt, SEARCH." in grounding_text,
                "prompt contains search-first grounding contract",
            )
        )

        _header("PHASE 3: Baseline routing and system status")
        baseline_search = await client.call_tool(
            "elefante-Memory",
            {"action": "search", 
                "query": "SDD Gate 2 leakage surface scan table specification",
                "limit": 3,
            },
        )
        results.append(
            _result(
                "Baseline specification search surfaces system memory",
                _search_contains(baseline_search, "leakage surface scan table"),
                "fresh isolated store still contains required specification baseline",
            )
        )
        results.append(
            _result(
                "Successful tool response injects routing and directives",
                "DIRECTIVES" in baseline_search
                and "ENTRYPOINT_SEQUENCE_READ_THIS_FIRST" in baseline_search
                and any(
                    "workspace/ISSUES.md" in step
                    for step in baseline_search.get("ENTRYPOINT_SEQUENCE_READ_THIS_FIRST", [])
                ),
                "first successful tool response carries the response contract",
            )
        )
        token_stats = baseline_search.get("TOKEN_STATS", {})
        results.append(
            _result(
                "Successful response includes TOKEN_STATS",
                isinstance(token_stats, dict)
                and isinstance(token_stats.get("output_tokens"), int)
                and isinstance(token_stats.get("overhead_tokens"), int)
                and isinstance(token_stats.get("signal_ratio"), (int, float))
                and 0.0 <= token_stats.get("signal_ratio", -1) <= 1.0,
                f"output={token_stats.get('output_tokens')}, overhead={token_stats.get('overhead_tokens')}, signal={token_stats.get('signal_ratio')}",
            )
        )

        error_response = await client.call_tool("elefante-NotARealTool", {})
        results.append(
            _result(
                "Failing tool response injects routing and directives",
                not error_response.get("success", True)
                and "DIRECTIVES" in error_response
                and "ENTRYPOINT_SEQUENCE_READ_THIS_FIRST" in error_response
                and "workspace/ISSUES.md" in str(error_response.get("error", "")),
                "failure path still routes to Known Issues",
            )
        )
        error_token_stats = error_response.get("TOKEN_STATS", {})
        results.append(
            _result(
                "Error response includes TOKEN_STATS",
                isinstance(error_token_stats, dict)
                and isinstance(error_token_stats.get("output_tokens"), int)
                and isinstance(error_token_stats.get("signal_ratio"), (int, float)),
                f"output={error_token_stats.get('output_tokens')}, signal={error_token_stats.get('signal_ratio')}",
            )
        )

        system_status = await client.call_tool("elefante-SystemStatusGet", {})
        results.append(
            _result(
                "System status reports operational mode",
                system_status.get("success") is True
                and system_status.get("mode") == "enabled"
                and system_status.get("stats") is not None,
                system_status.get("message", ""),
            )
        )

        system_enable = await client.call_tool("elefante-System", {"action": "enable"})
        results.append(
            _result(
                "System enable compatibility tool responds",
                system_enable.get("success") is True,
                system_enable.get("message", ""),
            )
        )

        _header("PHASE 4: Directive tools")
        directive_list = await client.call_tool("elefante-DirectiveList", {})
        directives = directive_list.get("directives", [])
        sdd_gate_count = sum(
            1
            for directive in directives
            if isinstance(directive, dict) and directive.get("content", "").startswith("SDD ")
        )
        results.append(
            _result(
                "Directive baseline is present",
                directive_list.get("count", 0) >= 13 and sdd_gate_count >= 5,
                f"count={directive_list.get('count', 0)} sdd={sdd_gate_count}",
            )
        )

        directive_add = await client.call_tool(
            "elefante-DirectiveAdd",
            {"content": f"SELF-PROTOCOL {test_tag}: prefer exact read-back over success flags."},
        )
        directive_id = directive_add.get("directive", {}).get("id", "")
        results.append(
            _result(
                "Directive add stores a persistent rule",
                directive_add.get("success") is True and bool(directive_id),
                f"id={directive_id[:12]}..." if directive_id else _json_text(directive_add)[:120],
            )
        )

        directive_list_after_add = await client.call_tool("elefante-DirectiveList", {})
        results.append(
            _result(
                "Directive list surfaces the added rule",
                any(
                    isinstance(directive, dict)
                    and directive.get("id") == directive_id
                    and test_tag in directive.get("content", "")
                    for directive in directive_list_after_add.get("directives", [])
                ),
                "custom directive visible in persistent directive store",
            )
        )

        directive_remove = await client.call_tool(
            "elefante-DirectiveRemove",
            {"directive_id": directive_id},
        )
        results.append(
            _result(
                "Directive remove clears the custom rule",
                directive_remove.get("success") is True,
                directive_remove.get("message", ""),
            )
        )

        directive_list_after_remove = await client.call_tool("elefante-DirectiveList", {})
        results.append(
            _result(
                "Removed directive no longer appears",
                not any(
                    isinstance(directive, dict) and directive.get("id") == directive_id
                    for directive in directive_list_after_remove.get("directives", [])
                ),
                "directive cleanup confirmed",
            )
        )

        _header("PHASE 5: Compliance Gate")
        await client.stop()
        client = None

        compliance_file = temp_home / ".elefante" / "compliance_state.json"
        if compliance_file.exists():
            compliance_file.unlink()

        gate_client = MCPClient(harness_env)
        try:
            await gate_client.start()
            gate_response = await gate_client.call_tool(
                "elefante-Memory",
                {"action": "delete", 
                    "memory_id": "00000000-0000-0000-0000-000000000000",
                    "reason": "compliance gate self-protocol probe",
                },
            )
            gate_blocked = (
                not gate_response.get("success", True)
                and any(term in _json_text(gate_response).lower() for term in ("compliance", "search", "gate"))
            )
            results.append(
                _result(
                    "Compliance Gate blocks ungrounded mutations",
                    gate_blocked,
                    "fresh session refuses write before search" if gate_blocked else _json_text(gate_response)[:120],
                )
            )
        finally:
            await gate_client.stop()

        client = MCPClient(harness_env)
        await client.start()

        post_gate_search = await client.call_tool(
            "elefante-Memory",
            {"action": "search", 
                "query": "Elefante Developer Etiquette specification versioning CLEAN DOC_SYNC",
                "limit": 3,
            },
        )
        results.append(
            _result(
                "Compliance reset session can unlock through search again",
                any(
                    item.get("memory", {}).get("metadata", {}).get("memory_type") == "specification"
                    for item in post_gate_search.get("results", [])
                ),
                "search reopens gated write path in fresh session",
            )
        )

        _header("PHASE 6: Memory lifecycle")
        graph_memory_content = (
            f"[{test_tag}] Graph memory for context proof. "
            "Link this runtime decision to a synthetic harness project and session."
        )
        active_memory_content = (
            f"[{test_tag}] Active cleanup memory. "
            "This record exists only to prove delete and read-back behavior."
        )
        mutable_memory_old = (
            f"[{test_tag}] Mutable memory OLD phrase. "
            "This content should be replaced by MemoryUpdate."
        )
        mutable_memory_new = (
            f"[{test_tag}] Mutable memory NEW phrase. "
            "MemoryUpdate wrote this replacement content."
        )
        etl_memory_content = (
            f"[{test_tag}] ETL raw memory. "
            "This record exists to prove ETLProcess and ETLClassify."
        )

        memory_specs = [
            ("graph", graph_memory_content, "decision", "self-protocol"),
            ("active", active_memory_content, "preference", "self-protocol"),
            ("mutable", mutable_memory_old, "fact", "self-protocol"),
            ("etl", etl_memory_content, "note", "self-protocol"),
        ]

        stored_all = True
        last_store_response: dict = {}
        for key, content, memory_type, category in memory_specs:
            ok, memory_id, response = await _store_memory(
                client,
                content=content,
                memory_type=memory_type,
                category=category,
                tags=[test_tag, key],
            )
            stored_all = stored_all and ok
            memory_ids[key] = memory_id
            last_store_response = response
            if not ok:
                print(f"  store failed for {key}: {_json_text(response)[:180]}")

        results.append(
            _result(
                "MemoryAdd stores protocol fixtures",
                stored_all and all(memory_ids.values()),
                f"stored={sum(1 for value in memory_ids.values() if value)}/{len(memory_specs)}",
            )
        )
        results.append(
            _result(
                "MemoryAdd response includes token intelligence fields",
                isinstance(last_store_response.get("content_tokens"), int)
                and last_store_response.get("content_tokens", 0) > 0
                and isinstance(last_store_response.get("token_density"), (int, float))
                and last_store_response.get("token_density", 0) > 0
                and isinstance(last_store_response.get("TOKEN_STATS"), dict),
                f"content_tokens={last_store_response.get('content_tokens')}, density={last_store_response.get('token_density')}",
            )
        )

        active_search = await client.call_tool(
            "elefante-Memory",
            {"action": "search", 
                "query": "Active cleanup memory exists only to prove delete and read-back behavior",
                "limit": 5,
            },
        )
        results.append(
            _result(
                "MemorySearch surfaces stored memory",
                _search_contains(active_search, test_tag),
                "semantic search finds live stored test memory",
            )
        )

        all_memories_response, protocol_memories = await _list_protocol_memories(client, test_tag)
        results.append(
            _result(
                "MemorySearch list_all surfaces protocol-owned records",
                len(protocol_memories) >= 4,
                f"tagged_memories={len(protocol_memories)}",
            )
        )

        update_response = await client.call_tool(
            "elefante-Memory",
            {"action": "update", 
                "memory_id": memory_ids["mutable"],
                "content": mutable_memory_new,
                "tags": [test_tag, "mutable", "updated"],
            },
        )
        results.append(
            _result(
                "MemoryUpdate amends stored content",
                update_response.get("success") is True,
                update_response.get("message", ""),
            )
        )

        _, protocol_memories_after_update = await _list_protocol_memories(client, test_tag)
        updated_memory = _memory_by_id(protocol_memories_after_update, memory_ids["mutable"])
        results.append(
            _result(
                "MemoryUpdate read-back shows replacement content",
                updated_memory is not None and updated_memory.get("content") == mutable_memory_new,
                "list_all returns the updated content for the same memory id",
            )
        )

        delete_response = await client.call_tool(
            "elefante-Memory",
            {"action": "delete", 
                "memory_id": memory_ids["active"],
                "reason": f"self-protocol delete probe {test_tag}",
            },
        )
        results.append(
            _result(
                "MemoryDelete removes a stored record",
                delete_response.get("success") is True,
                delete_response.get("message", ""),
            )
        )

        _, protocol_memories_after_delete = await _list_protocol_memories(client, test_tag)
        results.append(
            _result(
                "MemoryDelete read-back confirms removal",
                _memory_by_id(protocol_memories_after_delete, memory_ids["active"]) is None,
                f"remaining={len(protocol_memories_after_delete)} tagged memories",
            )
        )

        context_prompt = await client.get_prompt(
            "elefante-context",
            {"topic": "Graph memory for context proof"},
        )
        context_prompt_text = _prompt_text(context_prompt)
        results.append(
            _result(
                "Context prompt performs live memory lookup",
                test_tag in context_prompt_text and "Relevant Memories" in context_prompt_text,
                "prompt retrieval includes current isolated memory state",
            )
        )

        _header("PHASE 7: Graph, context, and sessions")
        graph_connect = await client.call_tool(
            "elefante-GraphConnect",
            {
                "entities": [
                    {"ref": "memory", "id": memory_ids["graph"]},
                    {"ref": "session", "name": session_entity_name, "type": "session"},
                    {"ref": "project", "name": project_entity_name, "type": "project"},
                ],
                "relationships": [
                    {"from_ref": "memory", "to_ref": "session", "relationship_type": "CREATED_IN"},
                    {"from_ref": "memory", "to_ref": "project", "relationship_type": "RELATES_TO"},
                    {"from_ref": "session", "to_ref": "project", "relationship_type": "WORKS_ON"},
                ],
                "include_system_status": True,
            },
        )
        results.append(
            _result(
                "GraphConnect upserts entities and relationships",
                graph_connect.get("success") is True
                and len(graph_connect.get("relationships", [])) == 3,
                graph_connect.get("message", ""),
            )
        )

        graph_query = await client.call_tool(
            "elefante-GraphQuery",
            {
                "cypher_query": (
                    f"MATCH (a:Entity)-[r]->(b:Entity) "
                    f"WHERE a.name CONTAINS '{test_tag}' OR b.name CONTAINS '{test_tag}' "
                    f"RETURN a.name, label(r), b.name ORDER BY a.name"
                )
            },
        )
        graph_query_text = _json_text(graph_query)
        results.append(
            _result(
                "GraphQuery surfaces tagged graph relationships",
                graph_query.get("success") is True
                and graph_query.get("count", 0) >= 2
                and "CREATED_IN" in graph_query_text
                and session_entity_name in graph_query_text
                and project_entity_name in graph_query_text,
                f"count={graph_query.get('count', 0)}",
            )
        )

        context_response = await client.call_tool(
            "elefante-ContextGet",
            {
                "depth": 2,
                "limit": 20,
            },
        )
        context_text = _json_text(context_response)
        results.append(
            _result(
                "ContextGet assembles graph-backed context",
                context_response.get("success") is True
                and test_tag in context_text
                and context_response.get("context", {}).get("stats", {}).get("num_entities", 0) >= 1,
                f"entities={context_response.get('context', {}).get('stats', {}).get('num_entities', 0)}",
            )
        )

        sessions_response = await client.call_tool(
            "elefante-SessionsList",
            {
                "limit": 20,
                "offset": 0,
            },
        )
        sessions_text = _json_text(sessions_response)
        results.append(
            _result(
                "SessionsList surfaces the synthetic session entity",
                sessions_response.get("success") is True and test_tag in sessions_text,
                f"count={sessions_response.get('count', 0)}",
            )
        )

        _header("PHASE 8: Task orchestration")
        task_create = await client.call_tool(
            "elefante-TaskCreate",
            {
                "description": f"[{test_tag}] Root verification task",
                "priority": 5,
                "assigned_agent": "self-protocol",
                "subtasks": [
                    {"description": f"[{test_tag}] verify child A", "priority": 3, "assigned_agent": "self-protocol"},
                    {"description": f"[{test_tag}] verify child B", "priority": 3, "assigned_agent": "self-protocol"},
                ],
            },
        )
        task_id = task_create.get("task_id", "")
        results.append(
            _result(
                "TaskCreate stores a task tree",
                task_create.get("success") is True and bool(task_id) and task_create.get("subtask_count") == 2,
                task_create.get("message", ""),
            )
        )

        task_graph_before_update = await client.call_tool(
            "elefante-TaskGraph",
            {"task_id": task_id},
        )
        results.append(
            _result(
                "TaskGraph surfaces the created hierarchy",
                task_graph_before_update.get("success") is True
                and "verify child A" in _json_text(task_graph_before_update),
                "task graph returns stored root and subtasks",
            )
        )

        task_update = await client.call_tool(
            "elefante-TaskUpdate",
            {
                "task_id": task_id,
                "status": "completed",
                "output": f"[{test_tag}] verification root completed",
            },
        )
        results.append(
            _result(
                "TaskUpdate changes task state",
                task_update.get("success") is True,
                task_update.get("message", ""),
            )
        )

        task_graph_after_update = await client.call_tool(
            "elefante-TaskGraph",
            {"task_id": task_id},
        )
        results.append(
            _result(
                "TaskGraph read-back shows updated status",
                task_graph_after_update.get("success") is True and "completed" in _json_text(task_graph_after_update),
                "updated task status persisted in graph",
            )
        )

        _header("PHASE 9: ETL and consolidation")
        etl_before = await client.call_tool(
            "elefante-ETLProcess",
            {
                "limit": 20,
                "include_stats": True,
            },
        )
        etl_before_text = _json_text(etl_before)
        results.append(
            _result(
                "ETLProcess surfaces raw memories",
                etl_before.get("success") is True
                and memory_ids["etl"] in etl_before_text,
                f"raw_count={etl_before.get('count', 0)}",
            )
        )

        etl_classify = await client.call_tool(
            "elefante-ETLClassify",
            {
                "memory_id": memory_ids["etl"],
                "summary": f"{test_tag} ETL memory classified by self protocol",
                "concepts": [test_tag, "etl", "self-protocol"],
                "surfaces_when": [f"{test_tag} etl", "self protocol classification"],
            },
        )
        results.append(
            _result(
                "ETLClassify stores agent enrichment",
                etl_classify.get("success") is True,
                _json_text(etl_classify)[:120],
            )
        )

        etl_after = await client.call_tool(
            "elefante-ETLProcess",
            {
                "limit": 20,
            },
        )
        results.append(
            _result(
                "ETLProcess no longer returns the classified memory as raw",
                memory_ids["etl"] not in _json_text(etl_after),
                f"remaining_raw={etl_after.get('count', 0)}",
            )
        )

        consolidate_response = await client.call_tool(
            "elefante-Memory",
            {"action": "consolidate", "force": False},
        )
        refinery_stats = consolidate_response.get("refinery", {}).get("stats", {})
        results.append(
            _result(
                "MemoryConsolidate dry-run returns refinery stats",
                consolidate_response.get("success") is True
                and consolidate_response.get("refinery", {}).get("applied") is False
                and refinery_stats.get("total_memories", 0) >= 1,
                f"total_memories={refinery_stats.get('total_memories', 0)}",
            )
        )

        _header("PHASE 10: System compatibility and restart")
        system_disable = await client.call_tool("elefante-System", {"action": "disable"})
        results.append(
            _result(
                "System disable compatibility tool responds",
                system_disable.get("success") is True,
                system_disable.get("message", ""),
            )
        )

        search_after_disable = await client.call_tool(
            "elefante-Memory",
            {"action": "search", 
                "query": "Graph memory for context proof synthetic harness project and session",
                "limit": 5,
            },
        )
        results.append(
            _result(
                "Search still works after System disable compatibility call",
                _search_contains(search_after_disable, test_tag),
                "transaction-scoped mode remains operational after backward-compatible disable",
            )
        )

        await client.stop()
        client = None
        await asyncio.sleep(1)

        client2 = MCPClient(harness_env)
        await client2.start()
        restart_search = await client2.call_tool(
            "elefante-Memory",
            {
                "action": "search",
                "query": "Graph memory for context proof synthetic harness project and session",
                "limit": 5,
            },
        )
        results.append(
            _result(
                "Stored memory survives MCP restart",
                _search_contains(restart_search, test_tag),
                "memory persisted across full subprocess restart",
            )
        )

        restart_task_graph = await client2.call_tool(
            "elefante-TaskGraph",
            {"task_id": task_id},
        )
        restart_sessions = await client2.call_tool(
            "elefante-SessionsList",
            {"limit": 20, "offset": 0},
        )
        results.append(
            _result(
                "Graph, task, and session state survive MCP restart",
                restart_task_graph.get("success") is True
                and "completed" in _json_text(restart_task_graph)
                and test_tag in _json_text(restart_sessions),
                "graph-backed state persisted across restart",
            )
        )

        if with_dashboard_open:
            _header("PHASE 11: Optional dashboard tool")
            dashboard_response = await client2.call_tool(
                "elefante-DashboardOpen",
                {"refresh": True},
            )
            dashboard_started = True
            # Dashboard refresh currently writes through src.mcp.server.DATA_DIR,
            # which is derived from HOME at import time. Accept the current
            # home-derived path and the config-driven temp-data path so the
            # verifier follows the live runtime contract instead of one stale
            # path assumption.
            candidate_snapshot_paths = [
                temp_home / ".elefante" / "data" / "dashboard_snapshot.json",
                temp_data_dir / "dashboard_snapshot.json",
            ]
            snapshot_path = next(
                (path for path in candidate_snapshot_paths if path.exists()),
                candidate_snapshot_paths[0],
            )
            snapshot_text = snapshot_path.read_text(encoding="utf-8") if snapshot_path.exists() else ""
            results.append(
                _result(
                    "DashboardOpen refresh writes snapshot and reports ready state",
                    dashboard_response.get("success") is True
                    and dashboard_response.get("opened", {}).get("success") is True
                    and dashboard_response.get("refreshed", {}).get("success") is True
                    and snapshot_path.exists()
                    and test_tag in snapshot_text,
                    f"{dashboard_response.get('opened', {}).get('message', '')} | snapshot={snapshot_path}",
                )
            )
        else:
            print(
                "  [SKIP] DashboardOpen not run. Default self-protocol stays self-contained and avoids fixed-port/browser side effects."
            )

        _header("PHASE 12: Cleanup")
        await client2.call_tool(
            "elefante-Memory",
            {
                "action": "search",
                "query": test_tag,
                "limit": 5,
            },
        )

        cleanup_targets = [memory_ids["graph"], memory_ids["mutable"], memory_ids["etl"]]
        deleted_count = 0
        for memory_id in cleanup_targets:
            delete_result = await client2.call_tool(
                "elefante-Memory",
                {
                    "action": "delete",
                    "memory_id": memory_id,
                    "reason": f"self-protocol cleanup {test_tag}",
                },
            )
            if delete_result.get("success") is True:
                deleted_count += 1

        results.append(
            _result(
                "Cleanup deletes remaining protocol memories",
                deleted_count == len(cleanup_targets),
                f"deleted={deleted_count}/{len(cleanup_targets)}",
            )
        )

        _, remaining_protocol_memories = await _list_protocol_memories(client2, test_tag)
        results.append(
            _result(
                "No protocol-tagged memories remain in isolated store",
                len(remaining_protocol_memories) == 0,
                f"remaining={len(remaining_protocol_memories)}",
            )
        )

    except Exception as exc:
        exc_type = type(exc).__name__
        results.append(_result("Harness execution", False, f"[{exc_type}] {str(exc)[:160]}"))

    finally:
        if client is not None:
            await client.stop()
        if client2 is not None:
            await client2.stop()
        if with_dashboard_open and dashboard_started:
            _kill_port(8000)

    temp_root_manager.cleanup()
    results.append(
        _result(
            "Isolated temp HOME/data removed",
            not temp_root.exists(),
            str(temp_root),
        )
    )

    _header("RESULTS")
    passed = sum(1 for result in results if result)
    total = len(results)
    print(f"\n  {passed}/{total} checks passed\n")

    if passed == total:
        print("  Verified:")
        print("    - The real MCP server completes initialize over stdio")
        print("    - The live MCP surface exposes the expected tools and prompts")
        print("    - Prompt retrieval, routing injection, and directive contracts are active")
        print("    - Memory, graph, context, session, task, ETL, and refinery flows work in isolation")
        print("    - The Compliance Gate blocks ungrounded mutations")
        print("    - Stored state survives a simulated restart")
        if with_dashboard_open:
            print("    - DashboardOpen refresh writes a snapshot and reports readiness in opt-in full-surface mode")
        else:
            print("    - DashboardOpen remains intentionally opt-in because it is not self-contained")
        print("    - Cleanup succeeds without touching the user's durable Elefante store")
    else:
        print(f"  {total - passed} check(s) failed. Review output above.")

    return 0 if passed == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Elefante self-protocol MCP verifier")
    parser.add_argument(
        "--with-dashboard-open",
        action="store_true",
        help="Include elefante-DashboardOpen(refresh=true). Requires port 8000 to be free.",
    )
    args = parser.parse_args()
    return asyncio.run(run_e2e(with_dashboard_open=args.with_dashboard_open))


if __name__ == "__main__":
    raise SystemExit(main())
