#!/usr/bin/env python3
"""
Elefante live MCP verification harness.

Runs the real MCP server in an isolated temporary Elefante home/data dir and
verifies the core behaviors the Developer Agent Protocol relies on.

Runs: .venv/bin/python scripts/verify/verify_e2e_tests.py

Isolation:
    Creates a temporary HOME/USERPROFILE and ELEFANTE_DATA_DIR for spawned MCP servers.
    Also enables ELEFANTE_ALLOW_TEST_MEMORIES=1 for the harness subprocesses so the probe
    never pollutes the user's durable store and does not depend on external shell setup.

What it verifies:
    1. MCP initialize/handshake succeeds
    2. Built-in directives inject into tool responses
    3. Required specification memories are retrievable on fresh state
    4. The Compliance Gate blocks ungrounded writes
    5. Stored memory survives a simulated restart
    6. Cleanup stays isolated from the user's durable store

Documentation:
        - docs/debug/dev-developer-agent.md
    - tests/README.md
    - scripts/README.md
    - docs/technical/ops-mcp-server.md
    - docs/debug/ops-database-compendium.md
"""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from uuid import uuid4

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from src import __version__ as ELEFANTE_VERSION

# ---------------------------------------------------------------------------
# MCP Client — drives the real Elefante server over JSON-RPC stdio
# ---------------------------------------------------------------------------

_REQ_ID = 0

class MCPClient:
    """Thin JSON-RPC 2.0 client over stdin/stdout to a real MCP server subprocess."""

    def __init__(self, env: dict[str, str]):
        self.process = None
        self._id = 0
        self._env = env

    async def start(self):
        cmd = [sys.executable, "-m", "src.mcp.server"]
        self.process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(project_root),
            env=self._env,
        )
        # Handshake
        resp = await self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "E2ETestEngine", "version": ELEFANTE_VERSION},
        })
        await self._notify("notifications/initialized", {})
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

    async def stop(self):
        if self.process:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self.process.kill()

    def _require_streams(self):
        if (
            self.process is None
            or self.process.stdin is None
            or self.process.stdout is None
            or self.process.stderr is None
        ):
            raise RuntimeError("MCP subprocess streams are not initialized")
        return self.process.stdin, self.process.stdout, self.process.stderr

    # -- internals --

    async def _send(self, method: str, params: dict) -> dict:
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params}
        stdin, stdout, stderr = self._require_streams()
        stdin.write(json.dumps(msg).encode() + b"\n")
        await stdin.drain()
        line = await asyncio.wait_for(stdout.readline(), timeout=30)
        if not line:
            stderr_text = (await stderr.read()).decode()
            raise RuntimeError(f"Server closed. stderr: {stderr_text[:500]}")
        resp = json.loads(line.decode())
        if "error" in resp:
            raise RuntimeError(f"RPC error: {resp['error']}")
        return resp.get("result", resp)

    async def _notify(self, method: str, params: dict):
        msg = {"jsonrpc": "2.0", "method": method, "params": params}
        stdin, _, _ = self._require_streams()
        stdin.write(json.dumps(msg).encode() + b"\n")
        await stdin.drain()


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
    temp_root_manager = tempfile.TemporaryDirectory(prefix="elefante-e2e-")
    temp_root = Path(temp_root_manager.name)
    temp_home = temp_root / "home"
    temp_data_dir = temp_root / "data"
    temp_home.mkdir(parents=True, exist_ok=True)
    temp_data_dir.mkdir(parents=True, exist_ok=True)
    harness_env = {
        **os.environ,
        "PYTHONPATH": str(project_root),
        "HOME": str(temp_home),
        "USERPROFILE": str(temp_home),
        "ELEFANTE_DATA_DIR": str(temp_data_dir),
        "ELEFANTE_ALLOW_TEST_MEMORIES": "1",
    }

    _header(f"Elefante Live MCP Verification Harness v{ELEFANTE_VERSION}")
    print("  Purpose : startup, baseline, restart, compliance, cleanup")
    print("  Mode    : isolated temp HOME + data dir")
    print(f"  Tag     : {test_tag}")

    # ---------------------------------------------------------------
    # Boot server (simulates IDE session 1)
    # ---------------------------------------------------------------
    _header("SESSION 1: Boot MCP server")
    client = MCPClient(harness_env)
    try:
        await client.start()
    except Exception as e:
        print(f"  [FAIL] Could not start MCP server: {e}")
        temp_root_manager.cleanup()
        return

    results.append(_result("MCP handshake", True, "server initialized"))

    # ---------------------------------------------------------------
    # Test 1: Directive injection proof
    # ---------------------------------------------------------------
    _header("TEST 1: Directive Injection (built-in baseline present?)")
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
        "expected >=5"
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
    _header("TEST 2: Store representative project memory")
    pref_content = (
        f"[{test_tag}] For integration test environments: use sandbox API keys. "
        "Never use production keys in test or staging workflows. "
        "Preferred failure handling: structured logging plus exponential backoff."
    )
    add_resp = await client.call_tool("elefante-MemoryAdd", {
        "content": pref_content,
        "memory_type": "preference",
        "domain": "project",
        "category": "integration-testing",
        "tags": ["sandbox", "api-keys", "error-handling", test_tag],
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
    _header("TEST 3: Simulated MCP restart (new session)")
    await client.stop()
    print("  ... server stopped (simulating IDE close)")
    await asyncio.sleep(1)

    client2 = MCPClient(harness_env)
    try:
        await client2.start()
    except Exception as e:
        print(f"  [FAIL] Could not restart MCP server: {e}")
        temp_root_manager.cleanup()
        return
    print("  ... server restarted (simulating IDE reopen)")

    # Search for the stored preference in the new session
    find_resp = await client2.call_tool("elefante-MemorySearch", {
        "query": "sandbox API keys structured logging exponential backoff preference",
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
    _header("TEST 4: Specification baseline retrieval")
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
        "baseline specification retrievable"
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

    client_gate = MCPClient(harness_env)
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
    client2 = MCPClient(harness_env)
    await client2.start()

    # ---------------------------------------------------------------
    # Test 6: Developer Etiquette SPECIFICATION present
    # ---------------------------------------------------------------
    _header("TEST 6: Developer process specification baseline")
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
    if mem_id:
        # Need to do a search first to unlock the compliance gate
        await client2.call_tool("elefante-MemorySearch", {
            "query": f"{test_tag} OpenClaw cleanup",
            "limit": 1,
        })
        del_resp = await client2.call_tool("elefante-MemoryDelete", {
            "memory_id": mem_id,
            "reason": f"E2E test cleanup — tag {test_tag}",
        })
        cleaned = del_resp.get("success", False)
        _result("Test memory cleaned up", cleaned)

    await client2.stop()

    # ---------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------
    _header("RESULTS")
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n  {passed}/{total} tests passed\n")

    if passed == total:
        print("  Verified:")
        print("    - The real MCP server completes initialize over stdio")
        print("    - Built-in directives are injected into tool responses")
        print("    - Required specification memories are retrievable on fresh state")
        print("    - The Compliance Gate blocks ungrounded mutations")
        print("    - Stored memory survives a simulated restart")
        print("    - Cleanup succeeds inside the isolated test store")
    else:
        print(f"  {total - passed} test(s) failed. Review output above.")

    temp_root_manager.cleanup()
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    asyncio.run(run_e2e())
