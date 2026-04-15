# Dashboard Startup & Troubleshooting Guide

**Status**: ESSENTIAL - Visual interface for memory system  
**Last Updated**: 2026-02-25  
**Applies to**: v2.0.0+

---

## Quick Start

### Starting the Dashboard

```bash
cd /path/to/Elefante
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate  # Windows

python -m src.dashboard.server
```

**Expected Output**:

```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

### Accessing the Dashboard

1. Open browser to: **http://127.0.0.1:8000**
2. Should see the **Overview tab** with health score gauge and stat pills
3. Three tabs: Overview, Memories, Explore

### Stopping the Dashboard

Press `Ctrl+C` in the terminal.

---

## Expected Behavior

### Dashboard Features

The dashboard has three tabs:

- **Overview**: Health score gauge, diagnostic panels, agent impact metrics
- **Memories**: Searchable, sortable table of all memories (TanStack Table)
- **Explore**: Topics (card grid), Insights (charts), Graph (SVG hub-spoke)

All data comes from a static snapshot — no live database access.

### Data Source

**Important**: Dashboard reads from **static snapshot file**, NOT live database.

```
MCP Server (Live Write)
  ↓
~/.elefante/data/kuzu_db (Kuzu Graph DB path)
  ↓
scripts/pipeline/update_dashboard_data.py (Export)
  ↓
data/dashboard_snapshot.json (Static File)
  ↓
Dashboard (Read Only)
```

This prevents Kuzu single-writer lock conflicts.

---

## Verification: Is the Dashboard Working?

### Method 1: Check Server Status

```bash
# Terminal output should show:
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Method 2: Test URL Access

```bash
curl http://127.0.0.1:8000

# Should return HTML page (first 100 chars):
# <!DOCTYPE html><html><head><meta charset="utf-8">...
```

### Method 3: Test API Endpoint

```bash
curl http://127.0.0.1:8000/api/stats

# Should return JSON:
# {"total_memories": 7, "total_relationships": 0, ...}
```

### Method 3.5: Run the Health Check Script

```bash
python scripts/verify/verify_dashboard_health.py --port 8000
```

### Method 3.6: Validate the Snapshot File

```bash
python scripts/verify/verify_dashboard_snapshot.py --path ~/.elefante/data/dashboard_snapshot.json
```

### Method 4: Open in Browser

1. Open **http://127.0.0.1:8000**
2. Should NOT show blank page
3. Should show graph with nodes (even if empty at first)

---

## Common Issues & Fixes

### Issue #1: "Port 8000 already in use"

**Symptom**:

```
ERROR: Address already in use
[Errno 48] Address already in use: ('127.0.0.1', 8000)
```

**Root Cause**: Another process using port 8000 (Dashboard already running, etc.)

**Fix**:

```bash
# Find what's using port 8000
lsof -i :8000  # Mac/Linux
# or
netstat -ano | findstr :8000  # Windows

# Kill the process
kill -9 <PID>  # Mac/Linux
# or
taskkill /PID <PID> /F  # Windows

# Restart dashboard
python -m src.dashboard.server
```

---

### Issue #2: "Connection refused" or "Cannot reach localhost:8000"

**Symptom**:

- Browser shows "Connection refused"
- Or "Unable to reach this page"

**Root Cause**: Server not binding to network interface properly

**Fix**:

```bash
# Check server is actually running
ps aux | grep dashboard  # Mac/Linux
# or
tasklist | findstr python  # Windows

# If no process, restart:
python -m src.dashboard.server

# If running, check logs for errors:
# Should see: "Uvicorn running on http://127.0.0.1:8000"
```

---

### Issue #3: "Blank page with no graph"

**Symptom**:

- Dashboard loads (no connection error)
- But shows blank page or empty graph
- No nodes visible

**Root Cause #1: No memories in system**

```bash
# Check memory count
python scripts/verify/verify_health.py

# Look for: "total_memories: 0"

# If 0, add a test memory:
python -c "
import asyncio
from src.core.orchestrator import MemoryOrchestrator

async def add_test():
    orch = MemoryOrchestrator()
    await orch.add_memory(
        content='Test memory for dashboard',
        memory_type='note'
    )
    print(' Test memory added')

asyncio.run(add_test())
"

# Refresh dashboard (F5)
```

**Root Cause #2: Snapshot not updated**

```bash
# Update dashboard snapshot from live database
python scripts/pipeline/update_dashboard_data.py

# Expected output:
#  Snapshot updated: data/dashboard_snapshot.json

# Refresh dashboard (F5)
```

**Root Cause #3: Browser cache**

```bash
# Hard refresh to bypass cache
# Press: Ctrl+Shift+R  (Windows/Linux)
# Or:    Cmd+Shift+R   (Mac)
```

---

### Issue #4: "Kuzu lock: Cannot acquire lock"

MCP server or another process is using Kuzu. See [`ops-kuzu.md`](ops-kuzu.md) § 8 for full diagnostics and fix procedures.

**Quick fix**: Stop the other process or wait for the current transaction to finish, then rerun the snapshot export. If the transaction lock is stale, inspect `~/.elefante/locks/write.lock`. Do not remove Kuzu's internal lockfile as a default fix.

---

### Issue #5: "CORS error" or "Unable to load data"

**Symptom**:

```
Access to XMLHttpRequest at 'http://127.0.0.1:8000/api/stats'
from origin 'http://127.0.0.1:8000' has been blocked by CORS policy
```

**Root Cause**: API endpoint returning wrong content-type or CORS not configured

**Fix**:

1. Check API is working:

```bash
curl -H "Content-Type: application/json" http://127.0.0.1:8000/api/stats
```

2. Should return JSON without `{"success": true}` wrapper:

```json
{"total_memories": 7, "total_relationships": 0, ...}
```

3. If wrapped, check `src/dashboard/server.py` and ensure `/api/stats` returns raw JSON

---

### Issue #6: "Old data showing after adding memories"

**Symptom**:

- Add memory via MCP
- Refresh dashboard
- Memory not showing
- Still sees old data

**Root Cause**: Snapshot not updated after memory added

**Fix**:

```bash
# Update snapshot
python scripts/pipeline/update_dashboard_data.py

# Output should show:
#  Exported 8 memories to dashboard_snapshot.json

# Refresh dashboard (F5)
```

**Automation**: Schedule snapshot updates:

```bash
# Linux cron (every 5 minutes)
*/5 * * * * cd /path/to/Elefante && python scripts/pipeline/update_dashboard_data.py

# Or add to MCP server startup script
```

---

## Debugging: Enable Detailed Logging

### Method 1: Check Server Logs

Terminal output should show:

```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Method 2: Capture Full Output

```bash
python -m src.dashboard.server 2>&1 | tee dashboard.log

# Later view logs
cat dashboard.log
```

### Method 3: Test API Endpoints Manually

```bash
# Stats endpoint
curl http://127.0.0.1:8000/api/stats
echo

# Memories endpoint
curl http://127.0.0.1:8000/api/memories
echo

# Graph data
curl http://127.0.0.1:8000/api/graph
```

---

## Data Refresh Cycle

### Manual Update (Recommended for Testing)

```
1. Add memory via MCP
2. Run: python scripts/pipeline/update_dashboard_data.py
3. Refresh browser: F5
4. Graph updates with new memory
```

### Automatic Update (Production)

```
1. Schedule snapshot updates (cron, systemd timer, etc.)
2. Every 5-10 minutes: python scripts/pipeline/update_dashboard_data.py
3. Dashboard always shows recent data (with slight delay)
4. No manual updates needed
```

---

## Configuration

### Change Port (Default: 8000)

Edit `src/dashboard/server.py`:

```python
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8080,  # Change this
        reload=False,
        log_level="info"
    )
```

Restart dashboard to use new port.

### Change Binding Address

Default: `127.0.0.1` (localhost only)

To allow external access:

```python
uvicorn.run(
    app,
    host="0.0.0.0",  # Listen on all interfaces
    port=8000,
    reload=False,
    log_level="info"
)
```

**Warning**: Makes dashboard accessible to network. Use with caution in production.

---

## Performance Notes

### Memory Limit

- Efficiently handles 500+ nodes
- Beyond 1000 nodes, graph rendering slows
- Use semantic zoom (planned in v1.1.0) to filter nodes

### Optimization

For large graphs (500+ memories):

1. Filter by space/category before visualization
2. Hide low-score nodes
3. Use search to show subgraph only

---

## Browser Compatibility

### Tested Browsers

- Chrome/Chromium 120+
- Firefox 121+
- Safari 17+
- Edge 120+

### Known Issues

- Safari may have slower rendering (GPU acceleration varies)
- Firefox may require one hard refresh (Ctrl+Shift+R) on first load
- Chrome usually works perfectly

---

## Production Deployment

### Running as Service (Linux/macOS)

**Create systemd service** (`/etc/systemd/system/elefante-dashboard.service`):

```ini
[Unit]
Description=Elefante Dashboard
After=network.target

[Service]
Type=simple
User=<username>
WorkingDirectory=/path/to/Elefante
ExecStart=/path/to/Elefante/.venv/bin/python -m src.dashboard.server
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start**:

```bash
sudo systemctl daemon-reload
sudo systemctl enable elefante-dashboard
sudo systemctl start elefante-dashboard
sudo systemctl status elefante-dashboard
```

---

## Summary Checklist

Before claiming "Dashboard is working":

- [ ] Python 3.11 active in venv
- [ ] `python -m src.dashboard.server` starts without errors
- [ ] Terminal shows "Uvicorn running on http://127.0.0.1:8000"
- [ ] Browser opens to http://127.0.0.1:8000 with no connection error
- [ ] Page loads (no blank/error page)
- [ ] Overview tab shows health gauge and stats
- [ ] Memories tab shows memory table
- [ ] API endpoints respond: `curl http://127.0.0.1:8000/api/stats`
- [ ] Memory snapshot exists: `data/dashboard_snapshot.json`
- [ ] No Kuzu lock conflicts (MCP not running simultaneously)
- [ ] After adding memories, snapshot updates and dashboard refreshes

---

**Document Version**: 2.5.4  
**Status**: ESSENTIAL  
**Last Validated**: 2026-02-26
