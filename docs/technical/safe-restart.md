# Elefante Safe Restart

**Version**: 1.5.0  
**Script**: `scripts/restart_elefante.py`  
**Purpose**: Safely restart MCP server to pick up code changes

---

## Overview

The Safe Restart utility cleanly restarts the Elefante MCP server without corruption or data loss. This is useful when:

- Code changes need to be loaded (version updates, bug fixes)
- Server becomes unresponsive
- After configuration changes
- Periodic maintenance

## Features

✅ **Graceful Shutdown**: Uses SIGTERM for clean exit  
✅ **Resource Cleanup**: Clears orchestrator references  
✅ **Lock Management**: Removes stale locks safely  
✅ **Transaction Safety**: Respects v1.1.0+ transaction-scoped locking  
✅ **No Data Loss**: All data persists in ChromaDB/Kuzu  
✅ **Verification**: Optional startup verification  
✅ **Force Option**: Fallback SIGKILL if needed

---

## Usage

### Basic Restart

```bash
python scripts/restart_elefante.py
```

### With Verification

```bash
python scripts/restart_elefante.py --verify
```

### Force Restart

If graceful shutdown fails:

```bash
python scripts/restart_elefante.py --force
```

### Custom Timeout

Wait longer for graceful shutdown:

```bash
python scripts/restart_elefante.py --timeout 30
```

### All Options

```bash
python scripts/restart_elefante.py --force --timeout 20 --verify
```

---

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--force` | False | Use SIGKILL if SIGTERM fails |
| `--timeout SECONDS` | 10 | Max wait for graceful shutdown |
| `--verify` | False | Verify process after restart |
| `--version VERSION` | None | Expected version (future feature) |

---

## How It Works

### Phase 1: Find Process

Searches for running `python -m src.mcp.server` process:

```bash
ps aux | grep "python.*src.mcp.server"
```

### Phase 2: Graceful Shutdown

1. Sends SIGTERM to MCP server process
2. Waits up to `--timeout` seconds
3. Checks process still exists every 0.5s
4. If timeout expires and `--force` set, sends SIGKILL

### Phase 3: Lock Cleanup

Scans `~/.elefante/locks/` for:

- **Empty locks**: Removed immediately
- **Dead PID locks**: Removed (process no longer exists)
- **Live PID locks**: Kept (another IDE using Elefante)
- **Very old locks**: Removed (exceeds stale threshold)

### Phase 4: Start Server

```bash
.venv/bin/python -m src.mcp.server
```

- Runs in detached background session
- Waits 2 seconds for startup
- Verifies process didn't exit immediately

### Phase 5: Verification (Optional)

If `--verify` flag set:

1. Wait 1 second for initialization
2. Find new MCP server process
3. Confirm PID exists
4. (Future: Check version matches expected)

---

## Safety Guarantees

### Data Persistence

All user data persists across restarts:

- **ChromaDB**: `~/.elefante/data/chroma/` (persistent on disk)
- **Kuzu**: `~/.elefante/data/kuzu_db/` (persistent on disk)
- **Logs**: `~/.elefante/logs/` (append-only)

### Transaction Safety

Respects v1.1.0+ transaction-scoped locking:

- SIGTERM triggers cleanup in orchestrator
- Ongoing transactions complete before exit
- Write locks auto-expire after 30s (stale detection)
- Read operations unaffected

### Lock Safety

Lock cleanup only removes:

- Empty lock files
- Locks from dead processes (PID doesn't exist)
- Locks exceeding stale threshold

**NEVER removes**:

- Locks held by live processes
- Locks from other active IDEs

---

## Common Scenarios

### After Code Update

```bash
# Pull latest changes
git pull origin main

# Restart to load new code
python scripts/restart_elefante.py --verify
```

### Server Unresponsive

```bash
# Force restart if needed
python scripts/restart_elefante.py --force --verify
```

### After Config Change

```bash
# Edit config.yaml
vim config.yaml

# Restart to apply
python scripts/restart_elefante.py
```

### Switching IDEs

```bash
# Clean shutdown before switching
python scripts/restart_elefante.py
```

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Failed to stop server |
| 1 | Failed to start server |
| 1 | Verification failed |

---

## Logging

Logs output in JSON format to stdout:

```json
{"event": "Found MCP server: PID 12345", "level": "info", "timestamp": "..."}
{"event": "Process 12345 exited gracefully", "level": "info", "timestamp": "..."}
{"event": "Removed empty lock: write.lock", "level": "info", "timestamp": "..."}
{"event": "MCP server started with PID 12346", "level": "info", "timestamp": "..."}
```

Errors logged with context:

```json
{"event": "Failed to stop MCP server", "level": "error", "timestamp": "..."}
{"event": "Permission denied when stopping PID 12345", "level": "error", "timestamp": "..."}
```

---

## Troubleshooting

### "MCP server process not found"

**Cause**: Server not running  
**Solution**: Just run restart - it will start a new instance

### "Permission denied when stopping PID"

**Cause**: Server owned by different user  
**Solution**: Run with sudo or as correct user

### "Failed to kill process"

**Cause**: Process stuck in uninterruptible state  
**Solution**: System reboot (rare edge case)

### "Process exited immediately with code X"

**Cause**: Server failed to start (config error, port conflict, etc.)  
**Solution**: Check logs in `~/.elefante/logs/elefante.log`

### "Lock held by live PID"

**Cause**: Another IDE is using Elefante  
**Solution**: Disable Elefante in other IDE first, or use `--force` (risky)

---

## Integration with MCP Tools

### Future Enhancement

Could add an MCP tool `elefanteSystemRestart`:

```json
Tool: elefanteSystemRestart
Arguments: {
  "force": false,
  "verify": true
}
```

**Challenge**: MCP tools run INSIDE the server process. Killing the server from inside requires:

1. Tool sets "restart requested" flag
2. Tool returns success immediately
3. Server detects flag after response sent
4. Server cleans up and exits
5. External watchdog (systemd, launchd) restarts server

---

## Comparison: Restart vs Enable/Disable

| Action | Purpose | Code Reload | Data Loss |
|--------|---------|-------------|-----------|
| **Disable/Enable** | Switch IDEs | ❌ No | ❌ No |
| **Restart** | Load new code | ✅ Yes | ❌ No |
| **Kill/Start** | Emergency | ✅ Yes | ⚠️ Risk if mid-write |
| **Safe Restart** | Best practice | ✅ Yes | ❌ No |

---

## Related Documentation

- [`architecture.md`](architecture.md) - Transaction-scoped locking
- [`mcp-server-startup.md`](mcp-server-startup.md) - Manual startup
- [`installation.md`](installation.md) - Initial setup

---

**Version**: 1.5.0  
**Last Updated**: 2025-12-27  
**Status**: Production Ready
