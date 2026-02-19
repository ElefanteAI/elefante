# Kuzu Database Lock Monitoring & Troubleshooting

**Status**: UPDATED for v1.1.0 (Transaction-Scoped Locking)  
**Last Updated**: 2025-12-26  
**Applies to**: v1.1.0+ (Transaction-scoped) and v1.0.x (Session-based, legacy)

---

## v1.1.0: Transaction-Scoped Locking (Current)

### How It Works Now

In v1.1.0, Elefante uses **transaction-scoped locking**:

```
IDE 1: add_memory()
  └─ acquire write.lock (5ms) → write → release write.lock
  
IDE 2: add_memory()  
  └─ wait briefly if needed → acquire write.lock (5ms) → write → release
  
Both IDEs can interleave operations!
```

**Key Changes from v1.0.x**:
- Locks held for milliseconds, not hours
- Stale locks auto-expire after 30 seconds
- Dead process detection clears orphaned locks
- No more `elefante-System` enable/disable ceremony needed

### Elefante Lock Files (v1.1.0)

```
~/.elefante/locks/
├── write.lock          # Transaction lock (contains: PID|timestamp)
└── elefante.lock       # Master lock (rarely used)
```

### Checking Elefante Lock Status (v1.1.0)

```bash
# See current locks
ls -la ~/.elefante/locks/

# Check who holds write lock
cat ~/.elefante/locks/write.lock
# Output: 12345|2025-12-26T15:30:00.123456

# Verify if that PID is alive
ps aux | grep 12345
```

### Troubleshooting Elefante Locks (v1.1.0)

**Issue**: "Could not acquire write lock - another process is writing"

This is normal - another IDE is in the middle of a write operation. The lock should release within milliseconds. If persistent:

```bash
# Check lock file age
stat ~/.elefante/locks/write.lock

# If timestamp is > 30 seconds old and PID is dead, lock is stale
# The system should auto-clear it, but you can force:
rm ~/.elefante/locks/write.lock
```

---

## Kuzu's Internal Single-Writer Lock

### The Architecture (Kuzu Level)

Kuzu itself uses **file-based locking** to enforce single-writer access:

```
~/.elefante/data/kuzu_db/
├── .lock                    <- Lock file (exists when in use)
├── catalog/                 <- Metadata
├── wal/                     <- Write-ahead log
└── storage/                 <- Data files
```

**Rule**: Only ONE process can access Kuzu database at a time.

### When Lock is Acquired

```
Process A opens Kuzu -> .lock file created -> Process A has exclusive access
Process B tries to open Kuzu -> Waits for lock -> Blocked until Process A closes
Process A closes Kuzu -> .lock file removed -> Process B acquires lock
```

### Why This Matters for Elefante

MCP Server and Dashboard both use Kuzu:

```
MCP Server (Write memories)
  ↓
Kuzu (Single-writer lock)
  ↑
Dashboard (Read memories)
```

**Problem**: If both start simultaneously, one will block or fail.

**Solution**: Run them in separate terminals, one at a time.

---

## Checking Lock Status

### Method 1: List Lock File

```bash
# Check if lock exists
ls -la ~/.elefante/data/kuzu_db/.lock

# If exists: file is locked
# If doesn't exist: database is free
```

### Method 2: Try to Access Database

```bash
# Attempt to open Kuzu
python -c "
import kuzu
db = kuzu.Database('data/kuzu_db')  # Use your project's data path
print(' Database unlocked and accessible')
"

# If fails with "Cannot acquire lock": database is locked
# If succeeds: database is free
```

### Method 3: Find What Process Holds Lock

```bash
# List all Python processes
ps aux | grep python

# Example output:
# jay    1234  python -m src.mcp.server    <- MCP server holding lock
# jay    5678  python -m src.dashboard.server
```

### Method 4: Check File Descriptor

```bash
# Find process using kuzu_db directory
lsof ~/.elefante/data/kuzu_db/

# Output shows which PID has the lock
# Example:
# COMMAND    PID    USER   FD   TYPE       FILE
# python   1234    user    9    DIR        /path/to/data/kuzu_db
```

---

## Fixing Lock Issues

### Scenario 1: Dashboard Won't Start (MCP is Running)

**Error**:

```
RuntimeError: Cannot acquire lock
```

**Why**: MCP server is holding the lock.

**Fix**:

```bash
# Option A: Stop MCP server in other terminal
# Terminal 1 (MCP): Press Ctrl+C
# Terminal 2 (Dashboard): Run dashboard

# Option B: Run dashboard first, then MCP
# Terminal 1: python -m src.dashboard.server
# Terminal 2: python -m src.mcp.server (will wait for dashboard to stop)
```

### Scenario 2: Lock Stuck (Process Crashed)

**Error**:

```
RuntimeError: Cannot acquire lock
```

But no process is using it (process crashed and didn't clean up).

**Symptom**: `.lock` file exists but process is gone.

**Fix**:

```bash
# 1. Verify no process is using it
ps aux | grep -E "mcp.server|dashboard.server"
# Should return nothing (or only grep itself)

# 2. Remove stale lock file
rm ~/.elefante/data/kuzu_db/.lock

# 3. Try again
python -m src.mcp.server
# Should work now
```

### Scenario 3: Both Processes Deadlocked

**Symptom**: Both MCP and Dashboard running but both stuck.

**Fix**:

```bash
# 1. Kill all Python processes in project
pkill -f "src.mcp.server"
pkill -f "src.dashboard.server"

# 2. Remove lock file
rm ~/.elefante/data/kuzu_db/.lock

# 3. Start one process at a time
python -m src.mcp.server
# (In separate terminal when done)
python -m src.dashboard.server
```

---

## Preventing Lock Issues

### Best Practice #1: One at a Time

**DO THIS**:

```bash
# Terminal 1: Start MCP
python -m src.mcp.server

# Use it, then Ctrl+C to stop

# Terminal 2: Start Dashboard
python -m src.dashboard.server
```

**DON'T DO THIS**:

```bash
# Terminal 1
python -m src.mcp.server &

# Terminal 2 (immediately)
python -m src.dashboard.server  # Will block or fail
```

### Best Practice #2: Dashboard Uses Snapshot

From [dashboard-startup.md](dashboard-startup.md):

Dashboard reads from **static snapshot**, not live database:

```
MCP (Write) -> Kuzu -> Export Script -> Snapshot File -> Dashboard (Read)
```

This prevents lock conflicts: Dashboard can run anytime without accessing Kuzu directly.

```bash
# Update snapshot
python scripts/update_dashboard_data.py

# Dashboard can now run without locking Kuzu
python -m src.dashboard.server
```

### Best Practice #3: Separate Data Directories (Advanced)

For advanced users needing concurrent access, use separate databases:

**NOT RECOMMENDED** for normal users. Requires:
- Duplicated data (memory bloat)
- Sync complexity
- Maintenance burden

Only use if absolutely necessary for your workflow.

---

## Monitoring Lock in Production

### Systemd Service (Linux/macOS)

**Create lock monitor**:

```bash
#!/bin/bash
# /usr/local/bin/elefante-monitor-lock

while true; do
    if [ -f ~/.elefante/data/kuzu_db/.lock ]; then
        # Lock exists - find which process holds it
        PID=$(lsof ~/.elefante/data/kuzu_db/.lock 2>/dev/null | tail -1 | awk '{print $2}')
        if [ -z "$PID" ]; then
            # Lock exists but no process found (stale)
            echo "$(date): STALE LOCK DETECTED - Removing"
            rm ~/.elefante/data/kuzu_db/.lock
        else
            echo "$(date): Lock held by PID $PID (normal)"
        fi
    fi
    sleep 300  # Check every 5 minutes
done
```

**Make executable**:

```bash
chmod +x /usr/local/bin/elefante-monitor-lock
```

**Run in background**:

```bash
/usr/local/bin/elefante-monitor-lock &
```

### Automated Stale Lock Cleanup

**Create cleanup script**:

```bash
#!/bin/bash
# /usr/local/bin/elefante-cleanup-lock

LOCK_FILE=~/.elefante/data/kuzu_db/.lock

if [ -f "$LOCK_FILE" ]; then
    # Lock exists - check if process still exists
    PID=$(lsof "$LOCK_FILE" 2>/dev/null | tail -1 | awk '{print $2}')
    
    if [ -z "$PID" ] || ! kill -0 "$PID" 2>/dev/null; then
        # Process doesn't exist - lock is stale
        echo "$(date): Removing stale lock"
        rm "$LOCK_FILE"
        exit 0
    fi
    
    # Process exists - lock is valid
    exit 1
fi

# No lock
exit 0
```

**Schedule with cron**:

```bash
# Run cleanup every minute
* * * * * /usr/local/bin/elefante-cleanup-lock
```

---

## Debugging Lock Issues

### Enable Debug Logging

Edit `src/core/graph_store.py`:

```python
# Add after import statements
import logging
logging.basicConfig(level=logging.DEBUG)

# In GraphStore.__init__:
logger.debug(f"Acquiring lock for {self.database_path}")
```

Restart MCP server to see detailed lock debugging.

### Check Lock File Timestamp

```bash
# See when lock was created
stat ~/.elefante/data/kuzu_db/.lock

# Example:
# Modify: 2025-12-10 17:55:00.000000000
# Access: 2025-12-10 17:55:00.000000000
# Change: 2025-12-10 17:55:00.000000000
```

If timestamp is very old, lock is likely stale.

---

## From Pitfall Index

See [`docs/pitfall-index.md`](../pitfall-index.md) — search `pitfall: kuzu stale lock`:

**LAW #2: Transaction-Scoped Locking (v1.1.0+)**

> "Kuzu uses file-based locking. Only ONE process can access database at a time."

**Architectural Limitation**: Dashboard and MCP server CANNOT run simultaneously.

**Lock Mechanism**:
- Lock file: `kuzu_db/.lock`
- File-based locking (not network-based)
- Prevents all concurrent access

**Resolution Protocol**:
1. Kill all Python processes: `pkill -f python`
2. Remove stale lock: `rm kuzu_db/.lock`
3. Restart IDE to let autoStart handle server lifecycle
4. NEVER run MCP server manually when IDE has autoStart enabled

---

## Summary Checklist

Before claiming "Lock is healthy":

- [ ] Only one process (MCP or Dashboard) running at a time
- [ ] Lock file doesn't exist: `ls ~/.elefante/data/kuzu_db/.lock`
  - Returns "No such file or directory" 
- [ ] Database is accessible: `python -c "import kuzu; kuzu.Database(...)"`
- [ ] No stale processes: `ps aux | grep python` shows expected processes only
- [ ] Dashboard uses snapshot, not direct Kuzu access
- [ ] Snapshot is updated before running Dashboard: `python scripts/update_dashboard_data.py`

---

**Document Version**: 1.0  
**Status**: CRITICAL  
**Last Validated**: 2025-12-10
