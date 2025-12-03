# Kuzu Database Lock Issue - Root Cause Analysis

**Date**: 2025-12-03  
**Severity**: CRITICAL - Blocks all graph operations  
**Status**: INVESTIGATING

---

## Problem Statement

Kuzu database is permanently locked, preventing ANY access to the knowledge graph. This defeats the purpose of a memory system that should be continuously updatable.

**Error**:
```
RuntimeError: Cannot open file. path: C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db\.lock - Error 15105: unknown error
```

---

## Root Cause Analysis

### 1. Kuzu's Locking Mechanism

**From code inspection** ([`graph_store.py:112`](Elefante/src/core/graph_store.py:112)):
```python
db = kuzu.Database(self.database_path, buffer_pool_size=buffer_size_bytes)
self._conn = kuzu.Connection(db)
```

**Kuzu's Design**:
- Kuzu uses a **file-based lock** (`.lock` file) to ensure **single-writer** access
- This is a **database-level lock**, not connection-level
- Lock is created when `kuzu.Database()` is instantiated
- Lock should be released when database object is destroyed

### 2. Why Lock Persists

**Three possible causes**:

#### A. Stale Lock from Crash/Termination
- Previous process crashed without cleanup
- Lock file not deleted on abnormal exit
- **Evidence**: Lock exists but no process holds it

#### B. Active Process Holding Lock
- MCP server still running (we killed PID 34396 earlier)
- Dashboard server running
- Another Python process with Kuzu connection open
- **Evidence**: Need to check for active processes

#### C. Kuzu Connection Not Properly Closed
- Python garbage collection hasn't run
- No explicit `close()` or `__del__()` implementation
- **Evidence**: Code has no cleanup mechanism

---

## Code Analysis: Missing Cleanup

### Current Implementation Issues

**1. No Connection Cleanup** ([`graph_store.py:89-141`](Elefante/src/core/graph_store.py:89-141)):
```python
def _initialize_connection(self):
    # Creates connection but NEVER closes it
    db = kuzu.Database(self.database_path, buffer_pool_size=buffer_size_bytes)
    self._conn = kuzu.Connection(db)
    # NO cleanup code!
```

**2. No Context Manager**:
```python
# GraphStore has NO __enter__ or __exit__ methods
# Cannot use: with GraphStore() as store:
```

**3. No Destructor**:
```python
# GraphStore has NO __del__ method
# Connection persists until Python process exits
```

**4. Singleton Pattern Without Cleanup**:
```python
# get_graph_store() returns singleton
# Singleton NEVER gets destroyed during runtime
# Lock held for entire process lifetime
```

---

## Why This Is CATASTROPHIC

### Design Flaw

**Current Behavior**:
1. First process opens Kuzu → Lock created
2. Lock held until process exits
3. Second process tries to open → BLOCKED
4. Even after first process exits, lock may persist (crash scenario)

**Impact**:
- ❌ Cannot run multiple tools/scripts simultaneously
- ❌ Cannot run MCP server + verification script
- ❌ Cannot run dashboard + MCP server
- ❌ Stale locks require manual intervention
- ❌ Defeats "always updatable" requirement

---

## Solutions (Ordered by Priority)

### Solution 1: Implement Proper Connection Lifecycle ⭐ RECOMMENDED

**Add cleanup methods to GraphStore**:

```python
class GraphStore:
    def close(self):
        """Explicitly close connection and release lock"""
        if self._conn:
            self._conn.close()
            self._conn = None
        # Kuzu should auto-release lock when connection closes
    
    def __enter__(self):
        """Context manager entry"""
        self._initialize_connection()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup"""
        self.close()
    
    def __del__(self):
        """Destructor - last resort cleanup"""
        try:
            self.close()
        except:
            pass  # Ignore errors during cleanup
```

**Usage**:
```python
# Proper usage with auto-cleanup
with GraphStore() as store:
    store.add_entity(...)
# Lock released here automatically
```

**Pros**:
- Proper resource management
- Prevents stale locks
- Pythonic pattern
- Backward compatible (add methods, don't break existing code)

**Cons**:
- Requires code changes throughout codebase
- Need to update all GraphStore usage

---

### Solution 2: Implement Lock Recovery Mechanism

**Add automatic stale lock detection**:

```python
def _initialize_connection(self):
    # Before opening, check if lock is stale
    lock_file = Path(self.database_path) / ".lock"
    
    if lock_file.exists():
        # Check if process holding lock is still alive
        if self._is_lock_stale(lock_file):
            logger.warning("Removing stale lock file")
            lock_file.unlink()
    
    # Now open database
    db = kuzu.Database(self.database_path, ...)

def _is_lock_stale(self, lock_file: Path) -> bool:
    """Check if lock file is from dead process"""
    try:
        # Read PID from lock file (if Kuzu stores it)
        # Or check file age (>5 minutes = stale)
        age = time.time() - lock_file.stat().st_mtime
        return age > 300  # 5 minutes
    except:
        return True  # If can't read, assume stale
```

**Pros**:
- Automatic recovery
- No manual intervention needed
- Handles crash scenarios

**Cons**:
- Risk of removing valid lock (race condition)
- May corrupt database if two processes open simultaneously

---

### Solution 3: Use Read-Only Mode for Queries

**Separate read and write access**:

```python
# For queries (most operations)
store = GraphStore(read_only=True)  # No lock needed

# For writes (rare)
with GraphStore(read_only=False) as store:
    store.add_entity(...)  # Lock held briefly
```

**Pros**:
- Multiple readers allowed
- Lock only for writes
- Matches usage pattern (mostly reads)

**Cons**:
- Kuzu may not support read-only mode
- Need to verify Kuzu capabilities

---

### Solution 4: Connection Pooling with Timeout

**Implement connection pool**:

```python
class GraphStorePool:
    def __init__(self, max_connections=1, timeout=30):
        self.pool = []
        self.timeout = timeout
    
    def get_connection(self):
        """Get connection with timeout"""
        start = time.time()
        while time.time() - start < self.timeout:
            try:
                return GraphStore()
            except RuntimeError:
                time.sleep(1)
        raise TimeoutError("Could not acquire lock")
```

**Pros**:
- Handles contention gracefully
- Timeout prevents infinite wait

**Cons**:
- Still single-writer limitation
- Doesn't solve stale lock problem

---

## Immediate Action Plan

### Phase 1: Emergency Fix (NOW)

1. **Check for active processes**:
   ```bash
   tasklist | findstr python
   # Kill any holding Kuzu lock
   ```

2. **Remove stale lock**:
   ```bash
   del C:\Users\JaimeSubiabreCistern\.elefante\data\kuzu_db\.lock
   ```

3. **Verify fix**:
   ```bash
   python verify_memories.py
   ```

### Phase 2: Implement Solution 1 (NEXT)

1. Add `close()`, `__enter__`, `__exit__`, `__del__` to GraphStore
2. Update all GraphStore usage to use context managers
3. Test with concurrent access
4. Document proper usage patterns

### Phase 3: Implement Solution 2 (SAFETY NET)

1. Add stale lock detection
2. Add automatic recovery
3. Add logging for lock operations
4. Test crash scenarios

---

## Testing Protocol

**After implementing fixes**:

1. **Single Process Test**:
   ```python
   with GraphStore() as store:
       store.add_entity(...)
   # Verify lock released
   ```

2. **Concurrent Access Test**:
   ```python
   # Terminal 1: python verify_memories.py
   # Terminal 2: python verify_memories.py (should work!)
   ```

3. **Crash Recovery Test**:
   ```python
   # Kill process mid-operation
   # Restart - should auto-recover
   ```

4. **Long-Running Test**:
   ```python
   # MCP server running for hours
   # Should still allow other access
   ```

---

## Recommendations

**PRIORITY 1**: Implement Solution 1 (Connection Lifecycle)
- This is the ROOT FIX
- Prevents future lock issues
- Industry standard pattern

**PRIORITY 2**: Implement Solution 2 (Stale Lock Recovery)
- Safety net for crashes
- User-friendly recovery

**PRIORITY 3**: Document proper usage
- Update all examples
- Add warnings about lock behavior
- Create troubleshooting guide

---

## Next Steps

**AWAITING USER APPROVAL** to proceed with:

1. Remove current stale lock (immediate)
2. Implement Solution 1 (proper cleanup)
3. Test thoroughly
4. Continue with schema migration

**DO NOT PROCEED** without explicit approval.