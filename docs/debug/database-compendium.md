# Database Debug Compendium

> **Domain:** Kuzu Graph Database & ChromaDB Vector Store  
> **Last Updated:** 2025-12-05  
> **Total Issues Documented:** 6  
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

---

## Table of Contents

- [Issue #1: Reserved Word Collision](#issue-1-reserved-word-collision)
- [Issue #2: Database Lock Persistence](#issue-2-database-lock-persistence)
- [Issue #3: Database Path Format Change](#issue-3-database-path-format-change)
- [Issue #4: Database Structure Corruption](#issue-4-database-structure-corruption)
- [Issue #5: Duplicate Entity Creation](#issue-5-duplicate-entity-creation)
- [Issue #6: ChromaDB Schema vs Memory Model](#issue-6-chromadb-schema-vs-memory-model)
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
python scripts/init_databases.py
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
        "importance": 8,
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
    importance: int  # Direct attribute
    domain: str      # Direct attribute
    # ... typed fields
```

### Solution
Use `MemoryModel.from_chromadb_result()` helper that handles translation:
```python
# Don't do this:
memory.importance = result["metadata"]["importance"]

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
python scripts/init_databases.py
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
