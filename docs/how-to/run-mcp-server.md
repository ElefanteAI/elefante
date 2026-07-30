# MCP Server Startup & Troubleshooting Guide

**Applies to**: v2.0.0+

---

## Quick Start

### Local daemon (recommended for multiple agent hosts)

```bash
python -m src.mcp.daemon
```

The daemon listens only on `127.0.0.1:8765`, exposes Streamable HTTP at `http://127.0.0.1:8765/mcp/`, and has `GET /health`. Remote binding is intentionally rejected. It rejects declared or streamed MCP request bodies over 1 MiB before the transport parses them. Every supported bridge adapter uses this shared daemon; compatibility tiers and individual host coverage are documented in the [IDE configuration guide](configure-ide.md).

Install the user-scope service before configuring bridge-based hosts:

```bash
python scripts/lifecycle/daemon_service.py install --apply
```

This installs a launchd user agent on macOS, a systemd user unit on Linux, or a logon-scoped Task Scheduler task on Windows. It never creates a system-wide service or opens a non-loopback listener.

The installer waits up to 15 seconds for the exact loopback `/health` payload before it emits IDE configuration. If the daemon cannot become healthy, installation fails rather than configuring clients against an unproven service.

On a later run, Elefante refreshes only a service definition that exactly matches its install manifest. A modified or user-managed service file is preserved and the command exits nonzero rather than pretending the shared daemon is ready.

Diagnose the installed service without changing it:

```bash
python scripts/lifecycle/daemon_service.py status
```

The status output reports the service file and whether it is Elefante-owned, the platform service-manager state, and the loopback `/health` result. `status` never starts, stops, or edits a service.

For one read-only product readiness report covering the runtime, daemon, installer ownership, and declared integration tiers:

```bash
python scripts/lifecycle/doctor.py
python scripts/lifecycle/doctor.py --json
```

`doctor` exits `0` only when the repository runtime and loopback daemon are ready. It does not start services, alter host configuration, or migrate data.

### Stdio compatibility bridge

Start the daemon first, then configure a stdio-only MCP host to run:

```bash
python -m src.mcp.stdio_bridge
```

The bridge forwards MCP JSON-RPC to the local daemon and owns no databases. Override its endpoint only with a loopback URL through `ELEFANTE_DAEMON_URL`. It rejects malformed messages and messages larger than 1 MiB before they are parsed or forwarded.

For provenance, the host installer should set `ELEFANTE_CLIENT_TOOL` and may set `ELEFANTE_CLIENT_CWD`; each bridge process creates a distinct instance ID. The daemon derives and persists the complete source tuple from the bridge headers and its MCP session. Header and environment values are untrusted: Elefante rejects control characters and bounds the persisted tool (128 characters), instance/session (256 characters), and workspace path (1024 characters) fields to safe defaults.

### Safe removal

Preview removal before changing user configuration:

```bash
python scripts/lifecycle/uninstall_elefante.py
```

Re-run with `--apply` only after reviewing the output. Elefante stops and removes its unchanged daemon service, then removes only its exact, unchanged entries from shared IDE JSON files. Modified configuration is preserved.

### Starting the MCP Server (Manual)

```bash
cd /path/to/Elefante
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate  # Windows

python -m src.mcp.server
```

**Expected Output**:

```json
{"event": "MCP Server initialized", "level": "info", "timestamp": "2025-12-10T17:55:00.000000Z"}
{"event": "Listening on stdio", "level": "info", "timestamp": "2025-12-10T17:55:00.000000Z"}
```

The server will **block** and wait for JSON-RPC messages from the IDE.

### Stopping the Server

Press `Ctrl+C` in the terminal. The direct stdio process then closes its
orchestrator resources before exiting, including the SQLite vector-store handle.

---

## Expected Behavior

### What MCP Server Does

The MCP Server:

1. Starts and waits for connections on **stdin/stdout** (stdio protocol)
2. Receives JSON-RPC requests for manual diagnostics or direct stdio clients
3. Exposes 16 MCP tools for memory and knowledge operations
4. Returns JSON-RPC responses
5. Bootstraps the runtime directive/specification baseline on first orchestrator use so fresh installs immediately have built-in directives and searchable specification memories

### What It Does NOT Do

- Does NOT output "Server listening on port 8000"
- Does NOT create a web interface
- Does NOT print regular status messages
- Does NOT require manual connection - IDE connects automatically

### Stdio Protocol (Not HTTP)

**Important**: direct MCP uses **stdio** (standard input/output). Installed
compatible hosts use the same stdio protocol with Elefante's transport-only
bridge, which forwards it to the loopback-only daemon. This keeps one daemon
responsible for durable stores when several agents connect.

```text
IDE or CLI agent
  ↓
  ├─ stdin: {"jsonrpc": "2.0", "method": "initialize", ...}
  ├─ stdout: {"jsonrpc": "2.0", "result": {...}}
  └─ (bidirectional messaging)
  ↓
Elefante stdio bridge (Python subprocess)
  ↓ loopback Streamable HTTP
Elefante daemon (one durable store owner)
```

The host starts the bridge as a subprocess and communicates through pipes; the
bridge accepts only the local daemon endpoint and never owns a database.

---

## Verification: Is the Server Working?

### Method 1: Manual Handshake Test

```bash
# Run in separate terminal
cd /path/to/Elefante
source .venv/bin/activate

python scripts/verify/verify_mcp_handshake.py
```

**Expected Output**:

```json
{"event": " Testing MCP Server Handshake...", "level": "info", "timestamp": "..."}
{"event": " Sending 'initialize'...", "level": "info", "timestamp": "..."}
{"event": " Server responded with 'initialize'", "level": "info", "timestamp": "..."}
{"event": " Handshake SUCCESSFUL", "level": "info", "timestamp": "..."}
```

**What This Tests**:

- Server process starts
- Server listens to stdin
- Server responds to JSON-RPC
- Protocol is working

### Method 2: Check Health

```bash
source .venv/bin/activate
python scripts/verify/verify_health.py
```

**Expected Output** (includes MCP check):

```text
 MCP Server: Running
 All systems operational!
```

Health check now also confirms:

- system directives are present
- `STDOUT Purity Law` is active
- required specification memories exist for fresh installs

### Method 2b: Run the Full MCP E2E Harness

```bash
.venv/bin/python scripts/verify/verify_e2e_tests.py
```

This is the highest-signal startup verification because it launches the real server, performs the MCP handshake, exercises live tool calls, and checks the shutdown-race regression path by forcing repeated search/co-activation traffic.

### Method 3: List Available Tools

```bash
./.venv/bin/python scripts/ci/list_mcp_tools.py
```

**Expected Output**:

```text
Available MCP Tools: 16
  - elefante-ContextGet
  - elefante-DashboardOpen
  - elefante-DirectiveAdd
  - elefante-DirectiveList
  - elefante-DirectiveRemove
  - elefante-ETLClassify
  - elefante-ETLProcess
  - elefante-GraphConnect
  - elefante-GraphQuery
  - elefante-Memory
  - elefante-SessionsList
  - elefante-System
  - elefante-SystemStatusGet
  - elefante-TaskCreate
  - elefante-TaskGraph
  - elefante-TaskUpdate
```

---

## Common Issues & Fixes

### Issue #1: "ModuleNotFoundError: No module named 'mcp'"

**Symptom**:

```text
Traceback (most recent call last):
  File "src/mcp/server.py", line 15, in <module>
    from mcp.server import Server
ModuleNotFoundError: No module named 'mcp'
```

**Root Causes**:

1. Virtual environment not activated
2. MCP not installed in venv
3. Wrong Python being used

**Fix**:

```bash
# 1. Verify venv is activated
which python  # Mac/Linux - should show .venv/bin/python
# or
where python  # Windows - should show .venv\Scripts\python

# 2. Verify Python 3.11
python --version  # Should be Python 3.11.x

# 3. Verify MCP is installed
pip list | grep mcp  # Should show mcp==1.28.1

# 4. If not installed, install it
pip install --require-hashes -r requirements.lock

# 5. Try again
python -m src.mcp.server
```

---

### Issue #2: Server Starts But IDE Can't Connect

**Symptom**:

- Server starts fine (no errors)
- IDE says "MCP connection failed"
- IDE still can't use memory tools

**Root Causes**:

1. MCP config points to wrong Python path
2. PYTHONPATH not set in IDE config
3. Server is using global Python instead of venv

**Fix**:

All IDE-specific MCP config file paths and JSON formats are documented here:

- See [configure-ide.md](configure-ide.md)

**Key Points**:

- Use ABSOLUTE path to `.venv/bin/python` (not relative path)
- Include `.venv/bin/python` in command (not just `python`)
- Set `PYTHONPATH` to project directory
- Set `cwd` to project directory
- If the server starts but the runtime baseline looks incomplete, run `scripts/verify/verify_health.py` once to verify built-in directives and auto-seeded specification memories

---

### Issue #3: "Server closed connection unexpectedly"

**Symptom**:

```text
Traceback (most recent call last):
  ...
  Server closed connection unexpectedly.
```

**Root Cause**: Server crashes when starting (imports fail, etc.)

**Fix**:

1. Try running server manually to see error:

```bash
source .venv/bin/activate
python -m src.mcp.server
```

1. Look for import errors or exceptions in output
1. Fix the error (usually missing module or config issue)

---

### Issue #4: "Kuzu lock: Cannot acquire lock"

**Symptom**:

```text
RuntimeError: Kuzu database is locked by another process.
Read workspace/postmortems/database.md Issue #2 for resolution.
```

**Root Cause**: Another live process currently owns Kuzu, or Elefante's transaction-scoped `~/.elefante/locks/write.lock` has gone stale.

**Fix**:

```bash
# 1. Stop the competing process or wait for the current transaction to finish
pkill -f "dashboard.server"  # Mac/Linux, if an old dashboard/export process is still live

# 2. Inspect the Elefante transaction lock
cat ~/.elefante/locks/write.lock

# 3. Only if the PID is dead and the lock is stale, remove the write lock
rm ~/.elefante/locks/write.lock  # Mac/Linux

# 4. Start MCP server again
python -m src.mcp.server
```

Do not remove Kuzu's internal lockfile as a default fix. Current recovery routing lives in Issue #2 of the database compendium.

---

### Issue #5: "Uvicorn logs corrupt JSON-RPC"

**Symptom**:

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize"}INFO:     Application startup complete
{"jsonrpc": "2.0", "result": {...}}
```

**Root Cause**: Uvicorn (used by Dashboard) logs to stdout, corrupting JSON-RPC protocol

**Fix**: This affects Dashboard, not MCP server. Separate them:

1. Don't run Dashboard and MCP server simultaneously
2. Use separate terminals for each
3. Or redirect Dashboard logs: `python -m src.dashboard.server 2>/dev/null`

---

## Debugging: Enable Detailed Logging

### Method 1: Set Logging Level

```bash
export LOGLEVEL=DEBUG  # Mac/Linux
# or
set LOGLEVEL=DEBUG  # Windows

python -m src.mcp.server
```

**Output** will show detailed debug messages.

### Method 2: Capture Stderr

```bash
python -m src.mcp.server 2>&1 | tee server.log

# Later analyze logs
cat server.log
```

### Method 3: Check Server Code

Edit `src/mcp/__init__.py` to add debug prints:

```python
import sys
print(f"[DEBUG] MCP Server starting with Python {sys.version}", file=sys.stderr)
print(f"[DEBUG] Current directory: {os.getcwd()}", file=sys.stderr)
```

---

## IDE Integration: Automatic MCP Startup

Once configured properly, your IDE will:

1. **Auto-Start** the MCP server on IDE launch
2. **Auto-Stop** the server on IDE shutdown
3. **Auto-Restart** if server crashes
4. **Show Status** in IDE (connected/disconnected)

### Verify IDE Integration

**VS Code (Roo-Cline)**:

1. Open Settings (Cmd+,)
2. Search "roo-cline.mcpServers"
3. Check "elefante" is listed and enabled
4. Restart VS Code
5. Check bottom right for "MCP: Connected"

**Cursor**:

1. Open Settings
2. Check MCP config has "elefante" entry
3. Restart Cursor
4. Should see MCP indicator active

---

## Testing MCP Tools

Once server is running, test tools:

### Test elefante-Memory(action="add")

```python
import subprocess
import json

# Start server in subprocess
proc = subprocess.Popen(
    ["python", "-m", "src.mcp.server"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True
)

# Send elefante-Memory(action="add") request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "elefante-Memory(action="add")",
        "arguments": {
            "content": "Test memory",
            "memory_type": "note"
        }
    }
}

proc.stdin.write(json.dumps(request) + "\n")
proc.stdin.flush()

# Read response
response = json.loads(proc.stdout.readline())
print(f"Response: {response}")

proc.terminate()
```

---

## Production Deployment

### Running the daemon as a service

Use Elefante's user-scope service manager rather than creating a privileged system service manually:

```bash
python scripts/lifecycle/daemon_service.py status
python scripts/lifecycle/daemon_service.py install --apply
python scripts/lifecycle/daemon_service.py uninstall --apply
```

The manager writes a manifest-tracked service definition and refuses to remove a user-modified one. It supports macOS launchd, Linux systemd-user, and Windows Task Scheduler.

---

## Summary Checklist

Before claiming "MCP Server is working":

- [ ] Python 3.11 active in venv
- [ ] `python -m src.mcp.daemon` starts without errors, or the user service is installed
- [ ] `http://127.0.0.1:8765/health` reports `status: ok`
- [ ] Handshake test passes: `python scripts/verify/verify_mcp_handshake.py`
- [ ] Health check passes: `python scripts/verify/verify_health.py`
- [ ] IDE config points to venv Python (absolute path)
- [ ] IDE shows "MCP Connected" status
- [ ] Can use memory tools in IDE (elefante-Memory(action="add"), elefante-Memory(action="search"), etc.)
- [ ] IDE configuration launches `src.mcp.stdio_bridge`, not a database-owning server

For restarting a running server, see [`restart.md`](restart.md).

---

**Last Validated**: 2026-02-25
