# Dashboard Debug Compendium

> **Domain:** Dashboard & Visualization  
> **Last Updated:** 2025-12-07  
> **Total Issues Documented:** 6  
> **Status:** Production Reference  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

##  CRITICAL LAWS (Extracted from Pain)

| #   | Law                                                                            | Violation Cost       |
| --- | ------------------------------------------------------------------------------ | -------------------- |
| 1   | Dashboard reads from SNAPSHOT file, never query database directly              | 3 hours              |
| 2   | ChromaDB = memories (70+), Kuzu = entities (17) - DIFFERENT DATA               | 2 hours              |
| 3   | Always run `update_dashboard_data.py` after memory changes                     | Stale data           |
| 4   | Verify BOTH producer AND consumer when debugging data flow                     | Circular debugging   |
| 5   | Hard refresh browser after frontend changes (`Ctrl+Shift+R`)                   | "It's still broken!" |
| 6   | Frontend reads `n.properties`, NOT `n.full_data.props` - check ALL occurrences | 8 hours              |
| 7   | Long-running servers cache imports - restart after code changes                | Silent failures      |

---

## Table of Contents

- [Issue #1: Kuzu Database Compatibility](#issue-1-kuzu-database-compatibility)
- [Issue #2: Stats Display Showing Zero](#issue-2-stats-display-showing-zero)
- [Issue #3: Memory Labels Missing](#issue-3-memory-labels-missing)
- [Issue #4: Dashboard Shows 11 Instead of 71](#issue-4-dashboard-shows-11-instead-of-71)
- [Issue #5: API Bypassed Snapshot File](#issue-5-api-bypassed-snapshot-file)
- [Issue #6: V3 Metadata Display Bug Chain](#issue-6-v3-metadata-display-bug-chain)
- [Methodology Failures](#methodology-failures)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Kuzu Database Compatibility

**Date:** 2025-11-28  
**Duration:** 45 minutes  
**Severity:** CRITICAL  
**Status:**  FIXED

### Problem

Kuzu 0.11.x changed from directory-based to single-file database format.

### Symptom

```
RuntimeError: Database path cannot be a directory
```

### Root Cause

Old directory-based database incompatible with new Kuzu version. The `config.py` was pre-creating directories that Kuzu 0.11+ needs to create itself.

### Solution

```python
# config.py - REMOVED this line:
# KUZU_DIR.mkdir(exist_ok=True)  # Kuzu 0.11.x cannot have pre-existing directory

# graph_store.py - Added buffer parsing:
def _parse_buffer_size(self):
    """Handle '512MB' string -> bytes conversion"""
```

### Why This Took So Long

- Error message was misleading ("cannot be a directory" sounds like permissions)
- Focused on `graph_store.py` instead of `config.py`
- Didn't check version changelog

### Lesson

> **Version upgrades can break database formats. Always check changelogs.**

---

## Issue #2: Stats Display Showing Zero

**Date:** 2025-11-28  
**Duration:** 30 minutes  
**Severity:** HIGH  
**Status:**  FIXED

### Problem

Dashboard showed "0 MEMORIES" despite 17 memories existing.

### Symptom

Stats panel displayed zero for all counts.

### Root Cause

Frontend reading wrong API response fields:

```typescript
// API returns:
{
  vector_store: {
    total_memories: 17;
  }
}

// Frontend was reading:
stats.total_memories; //  undefined

// Should read:
stats.vector_store.total_memories; // 
```

### Solution

Updated `App.tsx` line 36 to read nested fields correctly.

### Why This Took So Long

- API test passed (correct data returned)
- Assumed frontend would work if API worked
- Didn't inspect actual browser console

### Lesson

> **API working ≠ Dashboard working. Test the COMPLETE user experience.**

---

## Issue #3: Memory Labels Missing

**Date:** 2025-11-28  
**Duration:** 40 minutes  
**Severity:** MEDIUM  
**Status:**  FIXED

### Problem

Green dots had no labels - user couldn't identify memories.

### Symptom

User saw "meaningless dots" with no context.

### Root Cause

Canvas only showed labels on hover, not by default. Technical implementation worked but UX was broken.

### Solution

```typescript
// GraphCanvas.tsx modifications:
// - Display truncated labels (first 3 words) below each node by default
// - Show full description in tooltip on hover
// - Added TypeScript types for node properties
```

### Why This Took So Long

- Dots rendered = "working" in developer mind
- Didn't consider "what does user NEED to see?"
- Focused on technical correctness over usability

### Lesson

> **Technical correctness ≠ User satisfaction. Consider UX, not just functionality.**

---

## Issue #4: Dashboard Shows 11 Instead of 71

**Date:** 2025-12-05  
**Duration:** 2 hours  
**Severity:** CRITICAL  
**Status:**  FIXED

### Problem

User had 71+ memories but dashboard only showed 11 nodes.

### Symptom

```
Dashboard: 11 nodes visible
ChromaDB: 71 memories exist
Kuzu: 17 entities exist
```

### Root Cause

`update_dashboard_data.py` was querying **Kuzu only** (entities) instead of **ChromaDB** (memories). Fundamental confusion between data stores.

**The Data Architecture Reality:**
| Storage | Purpose | Count |
|---------|---------|-------|
| ChromaDB | Memories (semantic search) | 71 |
| Kuzu | Entities (graph relations) | 17 |

### Solution

Rewrote `scripts/update_dashboard_data.py` to pull from ChromaDB:

```python
# Before: Only queried Kuzu
# After: Pulls from ChromaDB directly
collection = vector_store._collection
results = collection.get(include=["metadatas", "documents"])
```

### Why This Took So Long

- Wasted 30 min on `graph_service.py` (dead code!)
- Assumed script name meant script was correct
- Didn't verify which data source was being queried

### Lesson

> **Verify the DATA SOURCE before debugging the data flow.**

---

## Issue #5: API Bypassed Snapshot File

**Date:** 2025-12-05  
**Duration:** 45 minutes  
**Severity:** CRITICAL  
**Status:**  FIXED

### Problem

Even after fixing `update_dashboard_data.py`, dashboard still showed wrong count.

### Symptom

Snapshot file had 71 nodes, but API returned 17.

### Root Cause

`server.py /api/graph` was querying Kuzu directly instead of reading the snapshot:

```python
# WRONG - what server.py was doing:
async with kuzu_conn as conn:
    result = conn.execute("MATCH (e:Entity) RETURN e")

# RIGHT - what it should do:
snapshot = json.load(open("data/dashboard_snapshot.json"))
```

### Solution

Complete rewrite of `/api/graph` endpoint:

```python
@router.get("/graph")
async def get_graph():
    snapshot_path = DATA_DIR / "dashboard_snapshot.json"
    if not snapshot_path.exists():
        return {"nodes": [], "edges": [], "stats": {}}
    with open(snapshot_path) as f:
        return json.load(f)
```

### Why This Took So Long

- Fixed producer (`update_dashboard_data.py`) but not consumer (`server.py`)
- Didn't trace data path END to END
- Assumed fixing one file would fix the whole flow

### Lesson

> **Fix BOTH producer AND consumer when debugging data flow.**

---

## Issue #6: V3 Metadata Display Bug Chain

**Date:** 2025-12-07  
**Duration:** 8+ hours across multiple sessions  
**Severity:** CRITICAL  
**Status:**  FIXED

### Problem

Dashboard showed "FACT • General" and "5/10" importance for ALL nodes despite correct V3 classification in database.

### Symptom

```
User clicks on multiple nodes -> All show:
- Layer: WORLD (blue color only)
- Sublayer: fact
- Importance: 5/10
- Category: General

Despite ChromaDB containing:
- 27 SELF, 39 WORLD, 12 INTENT nodes
- Varied sublayers (identity, preference, method, rule, fact)
- Importance ranging from 4-10
```

### Root Cause

**6-Layer Bug Chain** - Each bug hid the next:

| #   | Location                            | Issue                                               | Hidden By                     |
| --- | ----------------------------------- | --------------------------------------------------- | ----------------------------- |
| 1   | `classifier.py`                     | Only 5 regex patterns -> 90% defaulted to world/fact | "Migration succeeded" message |
| 2   | `VectorStore.add_memory()`          | Missing `layer`/`sublayer` in metadata dict         | Data never saved              |
| 3   | `VectorStore._reconstruct_memory()` | Missing `layer`/`sublayer` in reconstruction        | Even if saved, not read back  |
| 4   | MCP Server (12h running)            | Cached old code -> migration used unfixed code       | Tool reported success         |
| 5   | `GraphCanvas.tsx` colors            | Read `n.full_data.props` not `n.properties`         | Frontend path mismatch        |
| 6   | `GraphCanvas.tsx` sidebar           | Same path mismatch in different code location       | Same bug, different place     |

### Solution

**6 Sequential Fixes:**

```python
# Fix 1: Expanded classifier.py with 20+ patterns
if re.search(r'^i (am|live|speak|work)\b', content_lower):
    return "self", "identity"

# Fix 2: Added to VectorStore.add_memory()
metadata = {
    "layer": memory.metadata.layer,
    "sublayer": memory.metadata.sublayer,
    # ... other fields
}

# Fix 3: Added to VectorStore._reconstruct_memory()
layer=metadata.get("layer", "world"),
sublayer=metadata.get("sublayer", "fact"),

# Fix 4: Created standalone migration script
# scripts/migrate_memories_v3_direct.py (bypasses MCP cache)

# Fix 5: Fixed GraphCanvas.tsx colors
const layer = n.properties?.layer ?? props.layer ?? 'world';

# Fix 6: Added getProp helper for sidebar
const getProp = (key: string, fallback: any) => {
  const props = selectedNode.properties as Record<string, any>;
  return props?.[key] ?? selectedNode.full_data?.parsed_props?.[key] ?? fallback;
};
```

### Why This Took So Long

- **6 bugs in sequence**: Fixing one revealed the next
- **False positives**: Migration tool reported "78 migrated, 0 errors" but data unchanged (cached code)
- **Same bug twice**: `n.properties` vs `n.full_data.props` appeared in BOTH color AND sidebar code
- **No end-to-end verification**: Only checked one layer at a time instead of full pipeline
- **Server cache**: 12+ hour running server had old code cached

### Lesson

> **Data flows through 8 layers: Classifier -> add_memory -> ChromaDB -> reconstruct -> Snapshot -> API -> Frontend -> Sidebar. Verify at EACH layer, not just endpoints.**

### Prevention Checklist

```bash
# Verify ChromaDB has correct data
python3 -c "import chromadb; ..."

# Verify snapshot has correct data
cat data/dashboard_snapshot.json | python3 -c "..."

# Restart long-running servers after code changes
# Hard refresh browser: Cmd+Shift+R

# When fixing property paths, grep for ALL occurrences
grep -r "full_data.props" src/dashboard/ui/
```

---

## Methodology Failures

### Pattern 1: Testing API Without Testing UI

| What I Did                       | What I Should Do                             |
| -------------------------------- | -------------------------------------------- |
| Tested API endpoint in isolation | Test complete flow: API -> Frontend -> Browser |
| Assumed API working = UI working | Verify actual user-facing behavior           |

### Pattern 2: Fixing Wrong Files

| What I Did                         | What I Should Do                              |
| ---------------------------------- | --------------------------------------------- |
| Spent 30 min on `graph_service.py` | Verify file is actually USED before debugging |
| Assumed file name = purpose        | Check imports and call sites                  |

### Pattern 3: Confusing Data Stores

| What I Did                        | What I Should Do                           |
| --------------------------------- | ------------------------------------------ |
| Treated Kuzu and ChromaDB as same | Remember: ChromaDB=memories, Kuzu=entities |
| Queried wrong database            | Check data architecture diagram            |

### Pattern 4: Premature Success Claims

| What I Did                          | What I Should Do                       |
| ----------------------------------- | -------------------------------------- |
| Said "fixed" after API test passed  | Only claim success after USER confirms |
| Trusted my tests over user feedback | User's environment ≠ test environment  |

---

## Prevention Protocol

### Before Debugging Dashboard Issues

```powershell
# 1. Check actual data counts
python -c "from src.core.vector_store import VectorStore; vs = VectorStore(); print(f'ChromaDB: {vs._collection.count()}')"
python scripts/inspect_kuzu.py  # Check Kuzu count

# 2. Regenerate snapshot
python scripts/update_dashboard_data.py

# 3. Verify snapshot content
python -c "import json; d = json.load(open('data/dashboard_snapshot.json')); print(f'Snapshot: {len(d.get(\"nodes\", []))} nodes')"

# 4. Verify API returns snapshot
$response = Invoke-RestMethod "http://127.0.0.1:8000/api/graph"
Write-Host "API nodes: $($response.nodes.Count)"
```

### After Any Dashboard Changes

1.  Run `python scripts/update_dashboard_data.py`
2.  Restart server: `python -m src.dashboard.server`
3.  Hard refresh browser: `Ctrl+Shift+R`
4.  Verify stats panel shows correct numbers
5.  Verify graph shows ALL nodes with labels

### Verification Checklist

```
[ ] Backend: Database has correct data count
[ ] Script: update_dashboard_data.py ran successfully
[ ] Snapshot: JSON file has expected node count
[ ] API: /api/graph returns snapshot data
[ ] Frontend: Browser shows correct count
[ ] UX: Labels visible, tooltips work
[ ] User: Confirmed it works in THEIR browser
```

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

_Last verified: 2025-12-05 | Run `python scripts/health_check.py` to validate dashboard data path_
