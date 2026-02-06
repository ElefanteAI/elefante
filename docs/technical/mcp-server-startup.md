# MCP Server Startup & Troubleshooting Guide

**Status**: ESSENTIAL - Required for IDE integration  
**Last Updated**: 2025-12-10  
**Applies to**: v1.0.0+

---

## Quick Start

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

Press `Ctrl+C` in the terminal.

---

## Expected Behavior

### What MCP Server Does

The MCP Server:

1. Starts and waits for connections on **stdin/stdout** (stdio protocol)
2. Receives JSON-RPC requests from the IDE (VS Code, Cursor, Bob)
3. Exposes 18 MCP tools for memory operations
4. Returns JSON-RPC responses

### What It Does NOT Do

- Does NOT output "Server listening on port 8000"
- Does NOT create a web interface
- Does NOT print regular status messages
- Does NOT require manual connection - IDE connects automatically

### Stdio Protocol (Not HTTP)

**Important**: MCP uses **stdio** (standard input/output), NOT HTTP.

```text
IDE (VS Code, Cursor, Bob)
  ↓
  ├─ stdin: {"jsonrpc": "2.0", "method": "initialize", ...}
  ├─ stdout: {"jsonrpc": "2.0", "result": {...}}
  └─ (bidirectional messaging)
  ↓
MCP Server (Python subprocess)
```

The IDE starts the server as a subprocess and communicates via pipes, not network sockets.

---

## Verification: Is the Server Working?

### Method 1: Manual Handshake Test

```bash
# Run in separate terminal
cd /path/to/Elefante
source .venv/bin/activate

python scripts/verify_mcp_handshake.py
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
python scripts/health_check.py
```

**Expected Output** (includes MCP check):

```text
 MCP Server: Running
 All systems operational!
```

### Method 3: List Available Tools

```bash
./.venv/bin/python scripts/list_mcp_tools.py
```

**Expected Output**:

```text
Available MCP Tools: 18
  - elefanteMemoryAdd
  - elefanteMemorySearch
  - elefanteGraphQuery
  - elefanteContextGet
  - elefanteGraphEntityCreate
  - elefanteGraphRelationshipCreate
  - elefanteSessionsList
  - elefanteSystemStatusGet
  - elefanteMemoryConsolidate
  - elefanteMemoryListAll
  - elefanteMemoryMigrateToV3
  - elefanteDashboardOpen
  - elefanteGraphConnect
  - elefanteSystemEnable
  - elefanteSystemDisable
  - elefanteETLProcess
  - elefanteETLClassify
  - elefanteETLStatus
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
pip list | grep mcp  # Should show mcp==1.23.1

# 4. If not installed, install it
pip install -r requirements.txt

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

- See [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md)

**Key Points**:

- Use ABSOLUTE path to `.venv/bin/python` (not relative path)
- Include `.venv/bin/python` in command (not just `python`)
- Set `PYTHONPATH` to project directory
- Set `cwd` to project directory

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
RuntimeError: Kuzu database lock in use
Cannot acquire lock at ~/.elefante/data/kuzu_db/.lock
```

**Root Cause**: Dashboard or another process is using Kuzu database (single-writer lock)

**Fix**:

```bash
# 1. Stop dashboard
# Ctrl+C in dashboard terminal

# 2. Kill any Python processes accessing Kuzu
pkill -f "dashboard.server"  # Mac/Linux
# or
taskkill /F /IM python.exe  # Windows

# 3. Remove stale lock
rm ~/.elefante/data/kuzu_db/.lock  # Mac/Linux
# or
del %USERPROFILE%\.elefante\data\kuzu_db\.lock  # Windows

# 4. Start MCP server again
python -m src.mcp.server
```

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

### Test elefanteMemoryAdd

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

# Send elefanteMemoryAdd request
request = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "elefanteMemoryAdd",
        "arguments": {
            "content": "Test memory",
            "importance": 5
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

### Running MCP Server as Service (Linux/macOS)

**Create systemd service** (`/etc/systemd/system/elefante-mcp.service`):

```ini
[Unit]
Description=Elefante MCP Server
After=network.target

[Service]
Type=simple
User=<username>
WorkingDirectory=/path/to/Elefante
ExecStart=/path/to/Elefante/.venv/bin/python -m src.mcp.server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable elefante-mcp
sudo systemctl start elefante-mcp
sudo systemctl status elefante-mcp
```

---

## Summary Checklist

Before claiming "MCP Server is working":

- [ ] Python 3.11 active in venv
- [ ] `python -m src.mcp.server` starts without errors
- [ ] Handshake test passes: `python scripts/verify_mcp_handshake.py`
- [ ] Health check passes: `python scripts/health_check.py`
- [ ] IDE config points to venv Python (absolute path)
- [ ] IDE shows "MCP Connected" status
- [ ] Can use memory tools in IDE (elefanteMemoryAdd, elefanteMemorySearch, etc.)
- [ ] No Kuzu lock conflicts (if dashboard running separately)

---

**Document Version**: 1.0  
**Status**: ESSENTIAL  
**Last Validated**: 2025-12-10
