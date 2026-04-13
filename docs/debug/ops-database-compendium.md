# Database Debug Compendium

> **Domain:** Kuzu Graph Database & ChromaDB Vector Store  
> **Last Updated:** 2026-04-13  
> **Total Issues Documented:** 7  
> **Status:** Production Reference  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

##  CRITICAL LAWS (Extracted from Pain)

| # | Law | Violation Cost |
|---|-----|----------------|
| 1 | NEVER use `properties` as column name - Cypher reserved word | Schema rewrite |
| 2 | Single-Writer Lock - only ONE process can access Kuzu at a time | Error 15105 |
| 3 | Kuzu 0.11+ creates its own directory - do NOT pre-create | Init failure |
| 4 | ChromaDB = memories, Kuzu = entities - DIFFERENT PURPOSES | Data confusion |
| 5 | Kill all Python processes before deleting `.lock` file | Stale locks |
| 6 | Use `read_only=True` for concurrent read access | Lock conflicts |
| 7 | Never let Kuzu work outlive `GraphStore.close()` | Native SIGSEGV |

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the documented fix is intact. If they fail, the regression is real.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #7 SIGSEGV crash | `pytest tests/test_memory_persistence.py -k "graph_store_close_waits_for_inflight_query or graph_store_raw_execute_calls_stay_in_safe_methods" -v` | Close barrier + ownership boundary enforced |
| #7 Live regression | `pytest tests/test_memory_persistence.py -k "live_mcp_server_survives_shutdown_regression" -v` | Real MCP subprocess survives add/search/shutdown cycle |
| #2 Lock / #4 Corruption | `pytest tests/test_memory_persistence.py -k "config_paths_exist" -v` | Data directory structure valid |
| Full E2E (all issues) | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Isolated live MCP workflow including shutdown-race probe |
| Factory reset safety | `pytest tests/test_factory_reset.py -v` | Dry-run, safety gates, backup creation, idempotency |

---

## Table of Contents

- [Issue #1: Reserved Word Collision](#issue-1-reserved-word-collision)
- [Issue #2: Database Lock Persistence](#issue-2-database-lock-persistence)
- [Issue #3: Database Path Format Change](#issue-3-database-path-format-change)
- [Issue #4: Database Structure Corruption](#issue-4-database-structure-corruption)
- [Issue #5: Duplicate Entity Creation](#issue-5-duplicate-entity-creation)
- [Issue #6: ChromaDB Schema vs Memory Model](#issue-6-chromadb-schema-vs-memory-model)
- [Issue #7: Async Shutdown Race / QueryResult Lifetime Leak](#issue-7-async-shutdown-race--queryresult-lifetime-leak)
- [Methodology Failures](#methodology-failures)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Reserved Word Collision

**Date:** 2025-12-04  
**Duration:** 1 hour  
**Severity:** HIGH  
**Status:**  FIXED

### Problem
Entity creation failed with cryptic binder exception.

### Symptom
```
RuntimeError: Binder exception: Cannot find property properties for e.
```

### Root Cause
Kuzu uses **hybrid SQL/Cypher syntax**:
- Schema definition (SQL): `properties` works as column name
- Data operations (Cypher): `properties` is a **RESERVED WORD**

```sql
-- Schema creation: Works fine
CREATE NODE TABLE Entity(id STRING, properties STRING, PRIMARY KEY(id))

-- Data insertion: FAILS!
CREATE (e:Entity {properties: '{}'})  --  properties is reserved in Cypher
```

### Solution
Renamed column from `properties` to `props`:
```python
# Before: properties STRING
# After:  props STRING
```

**Files Changed:** `src/core/graph_store.py`, schema definition

### Why This Took So Long
- Error message didn't say "reserved word"
- Schema creation succeeded, only data ops failed
- Had to research Kuzu's SQL/Cypher hybrid behavior

### Lesson
> **Kuzu uses hybrid syntax. Test BOTH schema AND data operations.**

---

## Issue #2: Database Lock Persistence

**Date:** 2025-12-03  
**Duration:** Multiple occurrences (30 min each)  
**Severity:** CRITICAL  
**Status:**  RESOLVED (Workaround documented)

### Problem
Kuzu database locked and inaccessible after crash or concurrent access.

### Symptom
```
RuntimeError: Cannot open file. path: .../kuzu_db/.lock - Error 15105: unknown error
```

### Root Cause
Kuzu uses **file-based locking** (`.lock` file):
1. Lock created when `kuzu.Database()` instantiated
2. Lock should release when object destroyed
3. **BUT:** Crashed processes leave stale locks
4. **AND:** Multiple processes can't share access

**Failure Scenarios:**
| Scenario | Cause |
|----------|-------|
| Stale Lock | Process crashed without cleanup |
| Concurrent Access | Dashboard + MCP server both accessing |
| Process Leak | Multiple Python processes competing |

### Solution
```powershell
# Recovery procedure:
# 1. Kill all Python processes
taskkill /F /IM python.exe

# 2. Delete stale lock (if exists)
Remove-Item "$env:USERPROFILE\.elefante\data\kuzu_db\.lock" -Force -ErrorAction SilentlyContinue

# 3. Restart single process
python -m src.mcp.server
```

**Prevention:** Dashboard now uses `read_only=True` mode:
```python
db = kuzu.Database(db_path, read_only=True)
```

### Why This Took So Long
- Error 15105 is generic Windows file error
- Didn't know about Kuzu's single-writer model
- Tried complex solutions before simple "kill processes"

### Lesson
> **Kuzu is single-writer. Use `read_only=True` for concurrent reads.**

---

## Issue #3: Database Path Format Change

**Date:** 2025-11-27  
**Duration:** 12 minutes (felt like eternity)  
**Severity:** CRITICAL  
**Status:**  FIXED

### Problem
Kuzu 0.11.x introduced breaking change in database path handling.

### Symptom
```
RuntimeError: Database path cannot be a directory: C:\Users\...\kuzu_db
```

### Root Cause
Kuzu 0.11.x changed from **directory-based** to expecting to create its own structure:
- Old (0.1.x): Could pre-create `kuzu_db/` directory
- New (0.11.x): **CANNOT** have pre-existing directory

`config.py` was pre-creating the directory:
```python
KUZU_DIR.mkdir(exist_ok=True)  #  This breaks Kuzu 0.11.x
```

### Solution
```python
# config.py - Removed:
# KUZU_DIR.mkdir(exist_ok=True)

# graph_store.py - Added directory handling:
def _ensure_database_path(self):
    if self.db_path.exists() and self.db_path.is_dir():
        shutil.rmtree(self.db_path)  # Remove pre-existing directory
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
```

### Why This Took So Long
- Error message misleading ("cannot be a directory" sounds like permissions)
- Debugged `graph_store.py` instead of `config.py`
- Didn't check Kuzu changelog for breaking changes

### Lesson
> **Check library changelogs when upgrading. Version changes break things.**

---

## Issue #4: Database Structure Corruption

**Date:** 2025-12-03  
**Duration:** 20 minutes  
**Severity:** CRITICAL  
**Status:**  RESOLVED (Reset required)

### Problem
`kuzu_db` was a **single file** instead of directory structure.

### Symptom
Database initialization failed silently or with structure errors.

**Expected Structure:**
```
kuzu_db/                    (directory)
├── .lock
├── catalog/
├── wal/
└── storage/
```

**Actual State:**
```
kuzu_db                     (single 10MB file - WRONG!)
```

### Root Cause
Likely caused by interrupted initialization or version mismatch between Kuzu versions.

### Solution
```powershell
# 1. Backup corrupted file (just in case)
Move-Item kuzu_db kuzu_db.backup

# 2. Re-initialize
python scripts/setup/init_databases.py
```

### Why This Took So Long
- File vs directory wasn't obvious at first glance
- Had to compare against known-good installation

### Lesson
> **When database acts weird, check if structure matches expected format.**

---

## Issue #5: Duplicate Entity Creation

**Date:** 2025-12-03  
**Duration:** Ongoing (design issue)  
**Severity:** MEDIUM  
**Status:**  DOCUMENTED (Design limitation)

### Problem
Same logical entity appears multiple times with different IDs.

### Symptom
```
Entity: "User Approval Protocol"
  - ID: 81b0c0cb (from session 1)
  - ID: 69dab3a0 (from session 2)
```

### Root Cause
Entity extraction doesn't check for existing entities before creating new ones. Each memory analysis creates fresh entities.

**Current Behavior:**
```python
# Every memory analysis does this:
entity_id = str(uuid.uuid4())  # Always creates new ID
graph_store.create_entity(entity_id, name, type)
```

### Solution (Not Yet Implemented)
```python
# Should do this:
existing = graph_store.find_entity_by_name(name, type)
if existing:
    entity_id = existing.id
else:
    entity_id = str(uuid.uuid4())
    graph_store.create_entity(entity_id, name, type)
```

### Why This Persists
- Deduplication adds complexity
- Name matching is fuzzy (typos, variations)
- Current impact is low (visualization only)

### Lesson
> **Entity deduplication requires fuzzy matching. Simple exact match insufficient.**

---

## Issue #6: ChromaDB Schema vs Memory Model

**Date:** 2025-12-04  
**Duration:** Documentation time  
**Severity:** LOW  
**Status:**  DOCUMENTED

### Problem
Memory model has 40+ fields but ChromaDB flattens everything into metadata dict.

### Symptom
Queries for specific fields sometimes fail or return unexpected formats.

### Root Cause
ChromaDB stores:
```python
{
    "id": "uuid",
    "document": "content text",
    "metadata": {  # All 40+ fields flattened here
        "score": 75,
        "domain": "technical",
        "created_at": "2025-12-04T...",
        # ... everything else
    }
}
```

**Memory Model expects:**
```python
class Memory:
    id: str
    content: str
    score: int  # Direct attribute
    domain: str      # Direct attribute
    # ... typed fields
```

### Solution
Use `MemoryModel.from_chromadb_result()` helper that handles translation:
```python
# Don't do this:
memory.score = result["metadata"]["score"]

# Do this:
memory = MemoryModel.from_chromadb_result(result)
```

### Why This Matters
- Direct metadata access is fragile
- Field names may change between versions
- Type coercion needed (strings -> enums)

### Lesson
> **Always use model helpers to translate between storage format and domain objects.**

---

## Issue #7: Async Shutdown Race / QueryResult Lifetime Leak

**Date:** 2026-04-12  
**Duration:** Multi-session investigation  
**Severity:** CRITICAL  
**Status:** FIXED

### Problem
Elefante could segfault natively on macOS inside Kuzu during or immediately after MCP tool execution.

### Symptom
Crash reports showed two closely related signatures:

```text
Thread N: kuzu::main::QueryResult::~QueryResult()
```

and later:

```text
Thread 94: kuzu::main::ClientContext::TransactionHelper::runFuncInTransaction(...)
Thread 0 : kuzu::main::Database::~Database()
```

The common pattern was a null or destroyed Kuzu object being touched while the database was closing.

### Root Cause
Elefante violated native Kuzu object ownership in two places at once:

1. `src/core/graph_store.py` executed `self._conn.execute(...)` via `asyncio.to_thread(...)` but then iterated the returned `QueryResult` on the event-loop thread. Native result lifetime escaped the worker thread that created it.
2. `src/mcp/server.py` launched `orchestrator.record_coactivation(...)` via `asyncio.create_task(...)`, then unconditionally called `close_graph_store()` in a `finally` block after every tool call.
3. `GraphStore` defined a thread-safety lock but never used it to serialize the shared `kuzu.Connection`.

Result: a background query or leaked native result could still be alive while `GraphStore.close()` destroyed the underlying `Connection` / `Database`.

### Solution
Implemented a safe Kuzu boundary:

```python
async def _run_query(...):
    return await asyncio.to_thread(self._execute_query_sync, ...)

def _execute_query_sync(...):
    self._begin_operation()
    try:
        with self._lock:
            result = self._conn.execute(...)
            rows = []
            while result.has_next():
                rows.append(result.get_next())
            return column_names, rows
    finally:
        self._end_operation()
```

And on shutdown:

```python
def close(self):
    self._closing = True
    while self._active_operations > 0:
        wait()
    self._conn.close()
    self._db.close()
```

Also removed fire-and-forget co-activation writes so graph maintenance stays inside the owning MCP tool lifecycle.

**Files Changed:** `src/core/graph_store.py`, `src/mcp/server.py`, `tests/test_memory_persistence.py`

### Permanent Regression Guards
- `tests/test_memory_persistence.py` now includes a live MCP subprocess regression that launches the real server against an isolated temporary `HOME` and `ELEFANTE_DATA_DIR`, then exercises repeated `MemorySearch` and co-activation traffic before cleanup.
- `tests/test_memory_persistence.py` also statically enforces that raw `self._conn.execute(...)` calls remain confined to `_initialize_schema()` and `_execute_query_sync()`.
- `scripts/verify/verify_e2e_tests.py` now embeds the shutdown-race regression probe so fresh installs can validate the real tool path without custom scratch code.

### Why This Took So Long
- The first crash looked like a `QueryResult` destructor bug, the second like a database destructor bug.
- They were the same bug class: native Kuzu lifetime escaping Elefante's ownership model.
- We initially inspected symptoms one by one instead of drawing the full lifecycle: query start -> background task -> tool return -> `finally` close.

### Lesson
> **Native database objects need a single owner. If you close Kuzu transaction-scoped, no Kuzu work may survive the tool call.**

---

## Methodology Failures

### Pattern 1: Assuming Error Location = Root Cause
| What I Did | What I Should Do |
|------------|------------------|
| Error in `graph_store.py` -> debug `graph_store.py` | Trace error back to configuration source |
| Fixed symptoms not causes | Ask "why does this value exist here?" |

### Pattern 2: Not Checking Breaking Changes
| What I Did | What I Should Do |
|------------|------------------|
| Upgraded Kuzu, assumed backward compatible | Read changelog before upgrading |
| Debugged code when config was wrong | Check if library behavior changed |

### Pattern 3: Complex Solutions Before Simple Ones
| What I Did | What I Should Do |
|------------|------------------|
| Wrote lock management code | Try "kill processes, delete lock" first |
| Built retry logic | Check if simpler solution exists |

---

## Prevention Protocol

### Code-Level Safeguards

- Keep all Kuzu query execution inside `GraphStore._execute_query_sync()` and materialize rows there before returning to async callers.
- Never launch Kuzu work with `asyncio.create_task(...)` if the owning tool or process can call `close_graph_store()` in `finally`.
- Treat `MemoryOrchestrator.record_coactivation()` as owned tool work that must be awaited inside the MCP lifecycle.
- Run the isolated live MCP subprocess regression before closing a crash investigation.

### Before Working with Kuzu

```powershell
# 1. Check no other processes accessing
Get-Process python -ErrorAction SilentlyContinue

# 2. Verify database structure
Get-ChildItem "$env:USERPROFILE\.elefante\data\kuzu_db" -Recurse | Select-Object Name

# 3. Check for stale locks
Test-Path "$env:USERPROFILE\.elefante\data\kuzu_db\.lock"
```

### After Kuzu Errors

```powershell
# Recovery sequence
taskkill /F /IM python.exe
Remove-Item "$env:USERPROFILE\.elefante\data\kuzu_db\.lock" -Force -ErrorAction SilentlyContinue
python scripts/setup/init_databases.py
```

### When Upgrading Kuzu

1.  Read changelog for breaking changes
2.  Backup existing database
3.  Test in isolation before production
4.  Check path handling behavior
5.  Verify schema compatibility

---

## Appendix: Issue Template

```markdown
## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:**  OPEN |  IN PROGRESS |  FIXED |  DOCUMENTED

### Problem
[One sentence: what is broken]

### Symptom
[What the user sees / exact error message]

### Root Cause
[Technical explanation of WHY it broke]

### Solution
[Code changes or steps that fixed it]

### Why This Took So Long
[Honest reflection on methodology mistakes]

### Lesson
> [One-line takeaway in blockquote format]
```

---

*Last verified: 2025-12-05 | Kuzu version: 0.11.x | ChromaDB version: check requirements.txt*
