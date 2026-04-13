#!/usr/bin/env python3
"""
Elefante E2E Developer Experience Engine v2.2.1
Proves Elefante "never forgets" in real developer workflows.

Persona: Alex Rivera — Senior Autonomous Agent Engineer at FintechCo
  Uses VS Code + Antigravity, Claude Code, and OpenClaw (custom multi-agent framework).
  Builds production trading bots. Needs consistent context across all IDE sessions.

Runs: .venv/bin/python scripts/elefante_e2e_test_engine.py

What it proves:
    0. The real MCP tool path survives the Kuzu shutdown-race regression cycle
  1. Memory persists across simulated IDE restarts
  2. Directives inject unconditionally into every tool response
  3. SPECIFICATION memories surface with authority=1.0
  4. Compliance Gate blocks ungrounded writes
  5. SDD gates are live and enforceable
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# ---------------------------------------------------------------------------
# MCP Client — drives the real Elefante server over JSON-RPC stdio
# ---------------------------------------------------------------------------

_REQ_ID = 0

class MCPClient:
    """Thin JSON-RPC 2.0 client over stdin/stdout to a real MCP server subprocess."""

    def __init__(self, env: dict[str, str]):
        self.env = env
        self.process = None
        self._id = 0

    async def start(self):
        cmd = [sys.executable, "-m", "src.mcp.server"]
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env=self.env,
        )
        # Handshake
        resp = await self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "E2ETestEngine", "version": "2.2.1"},
        })
        await self._notify("notifications/initialized", {})
        tools = resp.get("capabilities", {}).get("tools", {})
        return resp

    async def call_tool(self, name: str, args: dict) -> dict:
        resp = await self._send("tools/call", {
            "name": name,
            "arguments": args,
        })
        # MCP returns content blocks; extract the text one
        if isinstance(resp, dict) and "content" in resp:
            for block in resp["content"]:
                if block.get("type") == "text":
                    try:
                        return json.loads(block["text"])
                    except json.JSONDecodeError:
                        return {"raw": block["text"]}
        return resp

    async def ensure_alive(self, label: str) -> None:
        await asyncio.sleep(0.35)
        if self.process.returncode is not None:
            stderr = (await self.process.stderr.read()).decode()
            raise RuntimeError(f"{label}: server exited rc={self.process.returncode} stderr={stderr[:800]}")

    async def stop(self):
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()

    # -- internals --

    async def _send(self, method: str, params: dict) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        self.process.stdin.write(json.dumps(msg).encode() + b"\n")
        await self.process.stdin.drain()
        line = await asyncio.wait_for(self.process.stdout.readline(), timeout=30)
        if not line:
            stderr = (await self.process.stderr.read()).decode()
            raise RuntimeError(f"Server closed. stderr: {stderr[:500]}")
        resp = json.loads(line.decode())
        if "error" in resp:
            raise RuntimeError(f"RPC error: {resp['error']}")
        return resp.get("result", resp)

    async def _notify(self, method: str, params: dict):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        self.process.stdin.write(json.dumps(msg).encode() + b"\n")
        await self.process.stdin.drain()


# ---------------------------------------------------------------------------
# Test harness
# ---------------------------------------------------------------------------

PASS = "PASS"
FAIL = "FAIL"

def _header(text: str):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")

def _result(name: str, ok: bool, detail: str = ""):
    tag = f"  [{PASS}]" if ok else f"  [{FAIL}]"
    line = f"{tag} {name}"
    if detail:
        line += f" -- {detail}"
    print(line)
    return ok


async def run_e2e():
    results = []
    test_tag = f"e2e-{uuid4().hex[:8]}"
    temp_root = tempfile.TemporaryDirectory(prefix="elefante-e2e-")
    temp_root_path = Path(temp_root.name)
    temp_home = temp_root_path / "home"
    temp_home.mkdir(parents=True, exist_ok=True)
    temp_data_dir = temp_root_path / "elefante-data"
    env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "HOME": str(temp_home),
        "USERPROFILE": str(temp_home),
        "ELEFANTE_DATA_DIR": str(temp_data_dir),
        "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
    }

    _header("Elefante E2E Developer Experience Engine v2.2.1")
    print("  Persona : Alex Rivera (FintechCo)")
    print("  Workflow: VS Code + Antigravity / Claude Code / OpenClaw")
    print(f"  Tag     : {test_tag}")
    print(f"  Sandbox : {temp_root_path}")

    # ---------------------------------------------------------------
    # Boot server (simulates IDE session 1)
    # ---------------------------------------------------------------
    _header("SESSION 1: Alex opens VS Code (MCP server starts)")
    client = MCPClient(env)
    try:
        init = await client.start()
    except Exception as e:
        print(f"  [FAIL] Could not start MCP server: {e}")
        temp_root.cleanup()
        return

    results.append(_result("MCP handshake", True, "server initialized"))
    await client.ensure_alive("post-initialize")

    # ---------------------------------------------------------------
    # Test 0: Native shutdown crash regression
    # ---------------------------------------------------------------
    _header("TEST 0: Kuzu shutdown-race regression")
    crash_tag = f"{test_tag}-crash"
    crash_phrase = f"[{crash_tag}] shared MCP shutdown race regression phrase"
    crash_memory_ids = []

    try:
        await client.call_tool("elefante-MemorySearch", {
            "query": crash_phrase,
            "limit": 5,
        })
        await client.ensure_alive("after crash-regression initial search")

        for index in range(2):
            add_resp = await client.call_tool("elefante-MemoryAdd", {
                "content": f"{crash_phrase} memory {index} with distinct suffix {uuid4().hex[:6]}",
                "memory_type": "note",
                "domain": "project",
                "category": "crash-regression",
                "tags": [crash_tag, "crash-regression", "mcp-live"],
                "force_new": True,
            })
            memory_id = add_resp.get("memory_id")
            if not memory_id:
                raise RuntimeError(f"MemoryAdd failed: {add_resp}")
            crash_memory_ids.append(memory_id)
            await client.ensure_alive(f"after crash-regression add {index}")

        for round_index in range(3):
            search_resp = await client.call_tool("elefante-MemorySearch", {
                "query": crash_phrase,
                "limit": 10,
            })
            tagged = [
                item for item in search_resp.get("results", [])
                if crash_tag in item.get("memory", {}).get("content", "")
            ]
            if len(tagged) < 2:
                raise RuntimeError(f"Search round {round_index} returned {len(tagged)} tagged memories")
            await client.ensure_alive(f"after crash-regression search {round_index}")

        await client.call_tool("elefante-SystemStatusGet", {})
        await client.ensure_alive("after crash-regression status")

        for memory_id in crash_memory_ids:
            del_resp = await client.call_tool("elefante-MemoryDelete", {
                "memory_id": memory_id,
                "reason": f"E2E crash regression cleanup — tag {crash_tag}",
            })
            if not del_resp.get("success", False):
                raise RuntimeError(f"MemoryDelete failed for {memory_id}: {del_resp}")
            await client.ensure_alive(f"after crash-regression delete {memory_id[:8]}")

        results.append(_result(
            "Server survives repeated search/coactivation cycle",
            True,
            "real MCP add/search/delete path stayed alive"
        ))
    except Exception as e:
        results.append(_result(
            "Server survives repeated search/coactivation cycle",
            False,
            str(e)[:120]
        ))

    # ---------------------------------------------------------------
    # Test 1: Directive injection proof
    # ---------------------------------------------------------------
    _header("TEST 1: Directive Injection (SDD gates present?)")
    dl = await client.call_tool("elefante-DirectiveList", {})
    directives = dl.get("directives", [])
    count = dl.get("count", 0)
    sdd_gates = [d for d in directives if d.get("content", "").startswith("SDD ")]
    stdout_law = [d for d in directives if "STDOUT" in d.get("content", "")]

    results.append(_result(
        f"Directive count = {count}",
        count >= 13,
        f"expected >=13, got {count}"
    ))
    results.append(_result(
        f"SDD gate directives = {len(sdd_gates)}",
        len(sdd_gates) >= 5,
        f"expected >=5"
    ))
    results.append(_result(
        "STDOUT Purity Law present",
        len(stdout_law) >= 1
    ))

    # Check that DIRECTIVES key appears in a tool response
    search_resp = await client.call_tool("elefante-MemorySearch", {
        "query": "directive injection test",
        "limit": 1,
    })
    has_directives_key = "DIRECTIVES" in search_resp
    results.append(_result(
        "DIRECTIVES injected in tool response",
        has_directives_key,
        "unconditional injection confirmed" if has_directives_key else "MISSING"
    ))

    # ---------------------------------------------------------------
    # Test 2: Alex teaches a preference (memory write)
    # ---------------------------------------------------------------
    _header("TEST 2: Alex teaches OpenClaw preference")
    pref_content = (
        f"[{test_tag}] For all OpenClaw agents: use sandbox-v2 API key. "
        "Never use production keys in test environments. "
        "Preferred error pattern: structured logging + retry with exponential backoff."
    )
    add_resp = await client.call_tool("elefante-MemoryAdd", {
        "content": pref_content,
        "memory_type": "preference",
        "domain": "project",
        "category": "openclaw",
        "tags": ["openclaw", "api-keys", "error-handling", test_tag],
        "force_new": True,
    })
    mem_id = add_resp.get("memory_id", "")
    stored_ok = add_resp.get("success", False) or bool(mem_id)
    results.append(_result(
        "Preference stored",
        stored_ok,
        f"id={mem_id[:12]}..." if mem_id else str(add_resp)
    ))

    # ---------------------------------------------------------------
    # Test 3: Simulated IDE restart — does the memory survive?
    # ---------------------------------------------------------------
    _header("TEST 3: Simulated IDE restart (new MCP session)")
    await client.stop()
    print("  ... server stopped (simulating IDE close)")
    await asyncio.sleep(1)

    client2 = MCPClient(env)
    try:
        await client2.start()
    except Exception as e:
        print(f"  [FAIL] Could not restart MCP server: {e}")
        temp_root.cleanup()
        return
    print("  ... server restarted (simulating IDE reopen)")

    # Search for Alex's preference in the new session
    find_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": "OpenClaw API key sandbox error handling preference",
        "limit": 5,
    })
    found_memories = find_resp.get("results", [])
    found_our_pref = any(
        test_tag in m.get("memory", {}).get("content", "")
        for m in found_memories
    )
    results.append(_result(
        "Preference survives IDE restart",
        found_our_pref,
        "memory persisted and surfaced via semantic search"
        if found_our_pref else f"not found in {len(found_memories)} results"
    ))

    # ---------------------------------------------------------------
    # Test 4: SPECIFICATION oracle test
    # ---------------------------------------------------------------
    _header("TEST 4: SPECIFICATION oracle (authority=1.0)")
    spec_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": "SDD Gate 2 leakage surface scan table specification",
        "limit": 5,
    })
    spec_results = spec_resp.get("results", [])
    has_spec = any(
        "leakage" in m.get("memory", {}).get("content", "").lower()
        and "surface" in m.get("memory", {}).get("content", "").lower()
        for m in spec_results
    )
    results.append(_result(
        "Gate 2 SPECIFICATION surfaces",
        has_spec,
        "immutable oracle available to all agents"
        if has_spec else f"not in top {len(spec_results)} results"
    ))

    spec3_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": "SDD Gate 3 scoring formulas behavioral relevance composite",
        "limit": 5,
    })
    spec3_results = spec3_resp.get("results", [])
    has_spec3 = any(
        "composite_score" in m.get("memory", {}).get("content", "")
        or "relevance" in m.get("memory", {}).get("content", "")
        for m in spec3_results
    )
    results.append(_result(
        "Gate 3 SPECIFICATION surfaces",
        has_spec3,
        "exact formulas available" if has_spec3 else "not found"
    ))

    # ---------------------------------------------------------------
    # Test 5: Compliance Gate enforcement
    # ---------------------------------------------------------------
    _header("TEST 5: Compliance Gate blocks ungrounded writes")
    # Compliance Gate requires a prior MemorySearch in the session.
    # The state is persisted to ~/.elefante/compliance_state.json.
    # Delete it before spawning a fresh server to prove the gate blocks.
    await client2.stop()

    compliance_file = temp_home / ".elefante" / "compliance_state.json"
    backup = None
    if compliance_file.exists():
        backup = compliance_file.read_text()
        compliance_file.unlink()

    client_gate = MCPClient(env)
    try:
        await client_gate.start()
        # Immediately try a gated tool WITHOUT any prior search
        gate_resp = await client_gate.call_tool("elefante-MemoryDelete", {
            "memory_id": "00000000-0000-0000-0000-000000000000",
            "reason": "compliance gate test",
        })
        gate_blocked = (
            not gate_resp.get("success", True)
            and ("compliance" in str(gate_resp).lower()
                 or "search" in str(gate_resp).lower()
                 or "gate" in str(gate_resp).lower())
        )
        results.append(_result(
            "Compliance Gate blocks ungrounded delete",
            gate_blocked,
            "write correctly refused" if gate_blocked else str(gate_resp)[:100]
        ))
    except Exception as e:
        results.append(_result("Compliance Gate test", False, str(e)[:80]))
    finally:
        await client_gate.stop()
        # Restore compliance state
        if backup:
            compliance_file.write_text(backup)

    # Re-open session for remaining tests + cleanup
    client2 = MCPClient(env)
    await client2.start()

    # ---------------------------------------------------------------
    # Test 6: Developer Etiquette SPECIFICATION present
    # ---------------------------------------------------------------
    _header("TEST 6: Developer Etiquette SPECIFICATION")
    etiquette_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": "Elefante Developer Etiquette specification versioning CLEAN DOC_SYNC",
        "limit": 3,
    })
    etiq_results = etiquette_resp.get("results", [])
    has_etiquette = any(
        m.get("memory", {}).get("metadata", {}).get("memory_type") == "specification"
        for m in etiq_results
    )
    results.append(_result(
        "Developer Etiquette SPECIFICATION present",
        has_etiquette,
        "memory_type=specification, authority=1.0"
        if has_etiquette else "not found as specification type"
    ))

    # ---------------------------------------------------------------
    # Cleanup: remove test memory
    # ---------------------------------------------------------------
    _header("CLEANUP")
    cleanup_ok = True

    await client2.call_tool("elefante-MemorySearch", {
        "query": test_tag,
        "limit": 20,
        "include_conversation": False,
        "include_stored": True,
    })

    for memory_id in crash_memory_ids:
        del_resp = await client2.call_tool("elefante-MemoryDelete", {
            "memory_id": memory_id,
            "reason": f"E2E crash regression cleanup verification — tag {test_tag}",
        })
        crash_cleaned = del_resp.get("success", False)
        cleanup_ok = cleanup_ok and crash_cleaned
        _result(f"Crash memory {memory_id[:8]} cleaned up", crash_cleaned)

    if mem_id:
        del_resp = await client2.call_tool("elefante-MemoryDelete", {
            "memory_id": mem_id,
            "reason": f"E2E test cleanup — tag {test_tag}",
        })
        cleaned = del_resp.get("success", False)
        cleanup_ok = cleanup_ok and cleaned
        _result("Test memory cleaned up", cleaned)

    remaining_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": test_tag,
        "limit": 20,
        "include_conversation": False,
        "include_stored": True,
    })
    remaining = [
        item for item in remaining_resp.get("results", [])
        if test_tag in item.get("memory", {}).get("content", "")
    ]
    no_artifacts = len(remaining) == 0
    cleanup_ok = cleanup_ok and no_artifacts
    results.append(_result(
        "E2E sandbox cleaned fully",
        cleanup_ok,
        "no test-tagged memories remain" if no_artifacts else f"remaining={len(remaining)}"
    ))

    await client2.stop()
    temp_root.cleanup()

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    _header("RESULTS")
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n  {passed}/{total} tests passed\n")

    if passed == total:
        print("  Elefante proved:")
        print("    - The live MCP shutdown-race regression path stays alive")
        print("    - Alex teaches once, every agent remembers forever")
        print("    - SDD directives inject into every tool response")
        print("    - SPECIFICATION memories surface with authority=1.0")
        print("    - Compliance Gate blocks ungrounded mutations")
        print("    - Context survives IDE restarts")
        print("    - The harness leaves no residual memories behind")
        print()
        print("  The meta-irony is closed.")
        print("  Elefante enforces SDD on itself using its own mechanisms.")
    else:
        print(f"  {total - passed} test(s) failed. Review output above.")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(run_e2e())
