# Kuzu Operations & Best Practices

**Status**: UPDATED for Transaction-Scoped Locking  
**Last Updated**: 2026-04-13  
**Applies to**: v2.5.0+

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

## 6. Live Kuzu Access Model

### Architecture

```
~/.elefante/data/kuzu_db        # Kuzu database path on disk
~/.elefante/locks/write.lock    # Elefante transaction-scoped write lock
```

Current runtime behavior:

- A fresh `GraphStore` init materializes `kuzu_db` as a single file path.
- Kuzu access is still effectively single-owner across live processes.
- `read_only=True` is for short-lived export and snapshot workflows. Do not treat it as a guarantee that a second live process can share Kuzu while another writer is active.
- The dashboard reads `dashboard_snapshot.json`, not live Kuzu.

### Why This Matters

```
MCP Server (Write) -> Kuzu
Snapshot Export (Short-lived read_only GraphStore) -> dashboard_snapshot.json
Dashboard Server -> static snapshot only
```

```bash
# Update snapshot
python scripts/pipeline/update_dashboard_data.py

# Dashboard reads the snapshot, not live Kuzu
python -m src.dashboard.server
```

---

## 7. Checking Lock Status

### Method 1: Inspect Elefante Transaction Locks

```bash
ls -la ~/.elefante/locks/
cat ~/.elefante/locks/write.lock
```

### Method 2: Find the Process Holding Kuzu

```bash
lsof ~/.elefante/data/kuzu_db
```

### Method 3: Reproduce Access Safely

```bash
python -c "
from src.core.graph_store import GraphStore
store = GraphStore('~/.elefante/data/kuzu_db')
store._initialize_connection()
print('Database accessible from this process')
store.close()
"
```

If this fails, the runtime error should route you to `docs/debug/ops-database-compendium.md` Issue #2.

---

## 8. Fixing Kuzu Lock Issues

### Scenario 1: Snapshot Refresh Collides With Active Writes

```bash
# Wait for the current write transaction to finish, then retry the snapshot export.
python scripts/pipeline/update_dashboard_data.py
```

### Scenario 2: Transaction Lock Looks Stale

```bash
# 1. Inspect the lock holder
cat ~/.elefante/locks/write.lock
ps aux | grep -E "src.mcp.server|restart_elefante"

# 2. Only if the PID is dead and the lock is stale, remove the write lock
rm ~/.elefante/locks/write.lock

# 3. Restart and verify
python scripts/lifecycle/restart_elefante.py --verify
```

### Scenario 3: Another Live Process Owns Kuzu

```bash
# Stop the competing process or wait for it to release Kuzu.
pkill -f "src.mcp.server"

# Then retry cleanly
python -m src.mcp.server
```

Do NOT use manual deletion of Kuzu's internal lockfile as a standard recovery path. That is stale guidance.

---

## See Also

- [`ops-dashboard.md`](ops-dashboard.md) — Dashboard startup and verification
- [`ops-restart.md`](ops-restart.md) — Safe restart procedures
- [`spec-architecture.md`](spec-architecture.md) — Transaction-scoped locking design
