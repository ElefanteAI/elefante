# Kuzu Operations & Best Practices

**Status**: UPDATED for Transaction-Scoped Locking  
**Last Updated**: 2026-04-13  
**Applies to**: v2.3.0+

---

## 1. Kuzu's Hybrid Nature

**Kuzu uses SQL for schema, Cypher for operations. Property names must be valid in BOTH.**

---

## 2. Reserved Words

These words are reserved in Cypher and will cause runtime errors:

### Critical (Confirmed to Break)

- `properties` — **MOST DANGEROUS** — Valid in SQL schema, breaks in Cypher CREATE
- `type` — Use `entity_type`, `node_type`, or `item_type`
- `label` — Use `entity_label` or `tag`
- `id` — Use `entity_id` or `identifier` (though `id` often works, be cautious)

### High Risk (Avoid)

`node`, `relationship`, `path`, `match`, `create`, `merge`, `delete`, `set`, `remove`, `return`, `where`, `with`, `union`, `optional`, `limit`, `skip`, `order`, `distinct`

### Safe Alternatives

| Don't Use | Use Instead |
|-----------|-------------|
| `properties` | `props`, `metadata`, `attributes`, `data` |
| `type` | `entity_type`, `node_type`, `category` |
| `label` | `entity_label`, `tag`, `name` |
| `id` | `entity_id`, `identifier`, `uid` |
| `node` | `entity`, `item`, `record` |
| `relationship` | `relation`, `edge`, `link` |
| `path` | `route`, `trail`, `sequence` |

---

## 3. Schema Definition Checklist

When adding new properties to Entity or other node tables:

```python
# GOOD
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    entity_type STRING,      # Not 'type'
    props STRING,            # Not 'properties'
    metadata_json STRING,    # Not 'metadata' (might conflict)
    PRIMARY KEY(id)
)

# BAD
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    type STRING,             # Reserved in Cypher!
    properties STRING,       # Reserved in Cypher!
    label STRING,            # Reserved in Cypher!
    PRIMARY KEY(id)
)
```

---

## 4. Testing New Properties

Before deploying schema changes:

```python
import kuzu
db = kuzu.Database('./test_db')
conn = kuzu.Connection(db)

conn.execute("""
    CREATE NODE TABLE TestEntity(
        id STRING,
        your_new_property STRING,
        PRIMARY KEY(id)
    )
""")

conn.execute("""
    CREATE (e:TestEntity {
        id: 'test123',
        your_new_property: 'test_value'
    })
""")
# If no error, property name is safe
```

---

## 5. Transaction-Scoped Locking (v1.1.0+)

### How It Works

```
IDE 1: add_memory()
  └─ acquire write.lock (5ms) → write → release write.lock

IDE 2: add_memory()
  └─ wait briefly if needed → acquire write.lock (5ms) → write → release

Both IDEs can interleave operations.
```

**Key properties**:

- Locks held for milliseconds, not hours
- Stale locks auto-expire after 30 seconds
- Dead process detection clears orphaned locks
- No more `elefante-System` enable/disable ceremony needed

### Elefante Lock Files

```
~/.elefante/locks/
├── write.lock          # Transaction lock (contains: PID|timestamp)
└── elefante.lock       # Master lock (rarely used)
```

### Checking Lock Status

```bash
# See current locks
ls -la ~/.elefante/locks/

# Check who holds write lock
cat ~/.elefante/locks/write.lock
# Output: 12345|2025-12-26T15:30:00.123456

# Verify if that PID is alive
ps aux | grep 12345
```

### Troubleshooting Stale Locks

**Issue**: "Could not acquire write lock - another process is writing"

This is normal — another IDE is writing. Lock releases within milliseconds. If persistent:

```bash
# Check lock file age
stat ~/.elefante/locks/write.lock

# If timestamp > 30 seconds old and PID is dead, lock is stale
# System should auto-clear it, but you can force:
rm ~/.elefante/locks/write.lock
```

---

## 6. Kuzu Internal Single-Writer Lock

### Architecture

```
~/.elefante/data/kuzu_db/
├── .lock                    <- Lock file (exists when in use)
├── catalog/                 <- Metadata
├── wal/                     <- Write-ahead log
└── storage/                 <- Data files
```

**Rule**: Only ONE process can access Kuzu database at a time.

### Lock Lifecycle

```
Process A opens Kuzu -> .lock created -> exclusive access
Process B tries to open -> blocked until Process A closes
Process A closes -> .lock removed -> Process B acquires
```

### Why This Matters

MCP Server and Dashboard both use Kuzu:

```
MCP Server (Write) → Kuzu (Single-writer lock) ← Dashboard (Read)
```

**Solution**: Dashboard reads from **static snapshot**, not live database:

```
MCP (Write) → Kuzu → Export Script → Snapshot File → Dashboard (Read)
```

```bash
# Update snapshot
python scripts/pipeline/update_dashboard_data.py

# Dashboard can now run without locking Kuzu
python -m src.dashboard.server
```

---

## 7. Checking Kuzu Lock Status

### Method 1: List Lock File

```bash
ls -la ~/.elefante/data/kuzu_db/.lock
# If exists: locked. If doesn't exist: free.
```

### Method 2: Try to Access

```bash
python -c "
import kuzu
db = kuzu.Database('data/kuzu_db')
print('Database unlocked and accessible')
"
```

### Method 3: Find Holding Process

```bash
lsof ~/.elefante/data/kuzu_db/
```

---

## 8. Fixing Kuzu Lock Issues

### Scenario 1: Dashboard Won't Start (MCP Running)

```bash
# Stop MCP server first (Ctrl+C), then start dashboard
# Or use snapshot mode (recommended)
```

### Scenario 2: Lock Stuck (Process Crashed)

```bash
# 1. Verify no process is using it
ps aux | grep -E "mcp.server|dashboard.server"

# 2. Remove stale lock file
rm ~/.elefante/data/kuzu_db/.lock

# 3. Try again
python -m src.mcp.server
```

### Scenario 3: Both Processes Deadlocked

```bash
# 1. Kill all
pkill -f "src.mcp.server"
pkill -f "src.dashboard.server"

# 2. Remove lock
rm ~/.elefante/data/kuzu_db/.lock

# 3. Start one at a time
python -m src.mcp.server
```

---

## See Also

- [`ops-dashboard.md`](ops-dashboard.md) — Dashboard startup and verification
- [`ops-restart.md`](ops-restart.md) — Safe restart procedures
- [`spec-architecture.md`](spec-architecture.md) — Transaction-scoped locking design
