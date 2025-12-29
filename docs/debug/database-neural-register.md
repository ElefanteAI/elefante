#  DATABASE NEURAL REGISTER
## System Immunity: Database Failure Laws

**Purpose**: Permanent record of database failure patterns and prevention protocols  
**Status**: Active Neural Register  
**Last Updated**: 2025-12-26

---

##  THE LAWS (Immutable Truths)

### LAW #1: Reserved Word Prohibition
**Statement**: NEVER use Cypher reserved words as property names in Kuzu schemas.

**The Kuzu Anomaly**: Kuzu uses SQL for schema (DDL) but Cypher for operations (DML). Property names must be valid in BOTH.

**Critical Reserved Words**:
-  `properties` - **MOST DANGEROUS** - Valid in SQL schema, breaks in Cypher CREATE
-  `type` - Use `entity_type`, `node_type`, `category`
-  `label` - Use `entity_label`, `tag`, `name`
-  `id` - Use `entity_id`, `identifier` (though often works, be cautious)

**Safe Alternatives**:
|  Forbidden |  Use Instead |
|-------------|---------------|
| `properties` | `props`, `metadata`, `attributes`, `data` |
| `type` | `entity_type`, `node_type`, `category` |
| `label` | `entity_label`, `tag`, `name` |

**Origin**: 2025-12-04 - Entity creation failure  
**Symptom**: `RuntimeError: Binder exception: Cannot find property properties for e.`  
**Fix**: Renamed `properties` -> `props` in Entity schema (line 178, `graph_store.py`)

---

### LAW #2: Transaction-Scoped Locking (v1.1.0+)
**Statement**: Database locks MUST be per-operation (milliseconds), not per-session (hours).

**SUPERSEDES**: Previous "Single-Writer Lock Architecture" guidance from v1.0.1.

**The Session Lock Trap** (v1.0.1 - OBSOLETE):
```
IDE 1: enable() → locks held indefinitely
IDE 2: enable() → BLOCKED forever
IDE 1: crashes → locks remain stale for days/weeks
```

**Transaction-Scoped Model** (v1.1.0+):
```
IDE 1: add_memory() → acquire_lock → write → release_lock (5ms)
IDE 2: add_memory() → wait briefly → acquire_lock → write → release_lock (5ms)
Both IDEs can interleave operations!
```

**Lock Files** (v1.1.0):
```
~/.elefante/locks/
├── write.lock          # Short-lived write lock (contains PID|timestamp)
└── elefante.lock       # Master lock (rarely used)
```

**Stale Lock Detection**:
- Lock is stale if: PID is dead OR timestamp > 30 seconds old
- Stale locks are automatically cleared on next operation

**Key Code** (`src/utils/elefante_mode.py`):
```python
from src.utils.elefante_mode import write_lock

# Write operations use transaction-scoped lock
with write_lock() as lock:
    if lock.acquired:
        # Safe to write - lock held briefly
        await orchestrator.add_memory(...)
    # Lock auto-released here
```

**Origin**: 2025-12-26 - Multi-IDE deadlock analysis  
**Symptom**: Stale lock from PID 4563 (Dec 14) blocking all access on Dec 26  
**Fix**: Implemented `TransactionLock` class with auto-expiry

---

### LAW #3: Schema-Operation Validation
**Statement**: Test BOTH schema creation AND data operations before deploying schema changes.

**Testing Protocol**:
```python
# 1. Create test database
import kuzu
db = kuzu.Database('./test_db')
conn = kuzu.Connection(db)

# 2. Test schema (SQL DDL)
conn.execute("""
    CREATE NODE TABLE Entity(
        id STRING,
        props STRING,  # Test new property name
        PRIMARY KEY(id)
    )
""")

# 3. Test operations (Cypher DML)
conn.execute("""
    CREATE (e:Entity {
        id: 'test123',
        props: '{}'  # Verify property works in CREATE
    })
""")

# 4. Test queries (Cypher)
result = conn.execute("MATCH (e:Entity) RETURN e.props")
```

**Anti-Pattern**: Assuming SQL-valid names work in Cypher operations

---

### LAW #4: Database Corruption Detection
**Statement**: Kuzu database MUST be a directory structure, not a single file.

**Expected Structure**:
```
kuzu_db/                    (directory)
├── .lock                   (lock file)
├── catalog/                (metadata)
├── wal/                    (write-ahead log)
└── storage/                (data files)
```

**Corruption Indicator**:
```
kuzu_db                     (single file - CORRUPTED!)
```

**Detection**: Check if `kuzu_db` is file vs directory  
**Resolution**: Nuclear reset - backup, delete, reinitialize  
**Prevention**: Proper error handling during database creation

**Origin**: 2025-12-02 - Database corruption event  
**Symptom**: "Cannot open file" error 15105  
**Impact**: Complete graph database loss (ChromaDB unaffected)

---

### LAW #5: Connection Lifecycle Management
**Statement**: GraphStore MUST implement proper connection cleanup.

**Missing Implementation** (as of v1.0.0):
-  No `close()` method for explicit cleanup
-  No `__enter__`/`__exit__` for context manager support
-  No `__del__` for destructor cleanup
-  No stale lock detection and recovery

**Required Implementation**:
```python
class GraphStore:
    def close(self):
        """Explicit connection cleanup"""
        if self.connection:
            self.connection.close()
        if self.database:
            self.database.close()
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup"""
        self.close()
    
    def __del__(self):
        """Destructor cleanup"""
        self.close()
```

**Impact**: Stale locks persist after process crashes, blocking all access

---

##  FAILURE PATTERNS (Documented Cases)

### Pattern #1: Reserved Word Schema Trap (2025-12-04)
**Trigger**: Using `properties` as column name in Entity schema  
**Symptom**: "Cannot find property properties for e"  
**Root Cause**: SQL accepts it, Cypher rejects it  
**Impact**: All entity creation operations fail  
**Resolution**: Rename to `props`, update all CREATE queries  
**Prevention**: Reserved word checklist, automated testing

### Pattern #2: Concurrent Access Deadlock (2025-12-04)
**Trigger**: Dashboard + MCP server both accessing Kuzu  
**Symptom**: "Cannot acquire lock" or process hangs  
**Root Cause**: Single-writer architecture  
**Impact**: One process blocks, user confused  
**Resolution**: Kill processes, remove lock, restart IDE  
**Prevention**: Document limitation, implement read-only mode

### Pattern #3: Database File Corruption (2025-12-02)
**Trigger**: Interrupted database creation or permissions issue  
**Symptom**: `kuzu_db` is single file instead of directory  
**Root Cause**: Failed directory structure creation  
**Impact**: Complete graph database loss  
**Resolution**: Nuclear reset, rebuild from ChromaDB  
**Prevention**: Proper error handling, atomic operations

### Pattern #4: Session-Based Lock Deadlock (2025-12-26) - RESOLVED in v1.1.0
**Trigger**: IDE crashes or closes without calling `elefanteSystemDisable`  
**Symptom**: New IDE instances blocked with "Elefante Mode is DISABLED" or "Could not acquire lock"  
**Root Cause**: v1.0.1 used session-based locks that held indefinitely until explicit release  
**Impact**: Complete lockout - stale lock from Dec 14 blocking all access on Dec 26 (12 days!)  
**Resolution**: Implemented transaction-scoped locking in v1.1.0  
**Prevention**: 
- Locks now auto-expire after 30 seconds
- Dead PID detection clears stale locks automatically
- Each operation acquires/releases lock in milliseconds

**Debug Commands** (if you encounter stale locks on older versions):
```bash
# Check for stale locks
ls -la ~/.elefante/locks/

# Clear all locks (safe if no Elefante processes running)
rm -f ~/.elefante/locks/*.lock

# Check what process holds a lock
cat ~/.elefante/locks/write.lock  # Shows PID|timestamp

# Verify PID is still alive
ps aux | grep <PID>
```

---

##  SAFEGUARDS (Active Protections)

### Safeguard #1: Reserved Word Validation
**Location**: `docs/technical/kuzu-best-practices.md`  
**Action**: Comprehensive list of forbidden property names  
**Response**: Developer reference, code review checklist

### Safeguard #2: Schema Testing Protocol
**Location**: Test scripts (`test_kuzu_create.py`, `test_kuzu_syntax.py`)  
**Action**: Verify schema AND operations before deployment  
**Response**: Catch reserved word issues before production

### Safeguard #3: Lock Cleanup Scripts
**Location**: `scripts/debug/remove_kuzu_lock.py`  
**Action**: Automated stale lock detection and removal  
**Response**: Quick recovery from lock issues

---

##  METRICS

### Entity Creation Success Rate
- **Before Fix**: 0% (all operations failed)
- **After Fix**: 100% (v1.0.0+)

### Lock-Related Issues
- **Before Documentation**: Frequent user confusion
- **After Documentation**: Clear resolution path

### Database Corruption Events
- **Detected**: 1 (2025-12-02)
- **Resolved**: Nuclear reset + rebuild
- **Prevention**: Improved error handling

---

##  RELATED REGISTERS

- **INSTALLATION_NEURAL_REGISTER.md**: Kuzu path conflicts, pre-flight checks
- **MCP_CODE_NEURAL_REGISTER.md**: Type signatures, protocol enforcement

---

##  SOURCE DOCUMENTS

- `docs/debug/kuzu-reserved-words-issue.md`
- `docs/debug/database-compendium.md`
- `docs/technical/kuzu-best-practices.md`
- `docs/technical/kuzu-lock-monitoring.md`

---

**Neural Register Status**:  ACTIVE  
**Enforcement**: Code review, testing protocols  
**Last Validation**: 2025-12-05