# Dashboard Debug Compendium

> **Domain:** Dashboard & Visualization
> **Last Updated:** 2026-03-28
> **Total Issues Documented:** 9
> **Status:** Production Reference
> **Applies to**: v2.5.2+
>
> **HISTORICAL NOTE:** Some issues below reference V3 concepts(layer, sublayer, classifier.py, importance 1-10) that have since been removed. These entries document the debugging process and lessons learned; the referenced code/fields no longer exist.  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

## CRITICAL LAWS (Extracted from Pain)

| #   | Law                                                                            | Violation Cost       |
| --- | ------------------------------------------------------------------------------ | -------------------- |
| 1   | Dashboard reads from SNAPSHOT file, never query database directly              | 3 hours              |
| 2   | ChromaDB = memories (70+), Kuzu = entities (17) - DIFFERENT DATA               | 2 hours              |
| 3   | Always run `update_dashboard_data.py` after memory changes                     | Stale data           |
| 4   | Verify BOTH producer AND consumer when debugging data flow                     | Circular debugging   |
| 5   | Hard refresh browser after frontend changes (`Ctrl+Shift+R`)                   | "It's still broken!" |
| 6   | Frontend reads `n.properties`, NOT `n.full_data.props` - check ALL occurrences | 8 hours              |
| 7   | Long-running servers cache imports - restart after code changes                | Silent failures      |
| 8   | Scores MUST be live-computed via `dashboard_serializer.py` — never from stored `mem.metadata.score` | Stale 100s |
| 9   | ALL dashboard node building converges through `memory_to_dashboard_node()` — no inline serialization | Score divergence |

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the documented fix is intact.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #8 Blank dashboard | `pytest tests/test_dashboard_serializer.py -k "dashboard" -v` | Readiness wait, forced refresh restart, and frontend retry/backoff remain intact |
| #9 Scores stuck at 100 | `pytest tests/test_dashboard_serializer.py -v` | Live score computation, secret redaction, serialization |
| Full E2E | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Isolated end-to-end MCP workflow |

---

## Table of Contents

- [Issue #1: Kuzu Database Compatibility](#issue-1-kuzu-database-compatibility)
- [Issue #2: Stats Display Showing Zero](#issue-2-stats-display-showing-zero)
- [Issue #3: Memory Labels Missing](#issue-3-memory-labels-missing)
- [Issue #4: Dashboard Shows 11 Instead of 71](#issue-4-dashboard-shows-11-instead-of-71)
- [Issue #5: API Bypassed Snapshot File](#issue-5-api-bypassed-snapshot-file)
- [Issue #6: V3 Metadata Display Bug Chain](#issue-6-v3-metadata-display-bug-chain)
- [Issue #7: The Phantom Dashboard](#issue-7-the-phantom-dashboard-blank-screen--connection-death)
- [Issue #8: Persistent Blank Dashboard on First Launch](#issue-8-persistent-blank-dashboard-on-first-launch)
- [Issue #9: All Dashboard Scores Stuck at 100](#issue-9-all-dashboard-scores-stuck-at-100)
- [Methodology Failures](#methodology-failures)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Kuzu Database Compatibility

**Date:** 2025-11-28  
**Duration:** 45 minutes  
**Severity:** CRITICAL  
**Status:** FIXED

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
**Status:** FIXED

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
**Status:** FIXED

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
**Status:** FIXED

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

Rewrote `scripts/pipeline/update_dashboard_data.py` to pull from ChromaDB:

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
**Status:** FIXED

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
**Status:** FIXED

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

| #   | Location                            | Issue                                                | Hidden By                     |
| --- | ----------------------------------- | ---------------------------------------------------- | ----------------------------- |
| 1   | `classifier.py`                     | Only 5 regex patterns -> 90% defaulted to world/fact | "Migration succeeded" message |
| 2   | `VectorStore.add_memory()`          | Missing `layer`/`sublayer` in metadata dict          | Data never saved              |
| 3   | `VectorStore._reconstruct_memory()` | Missing `layer`/`sublayer` in reconstruction         | Even if saved, not read back  |
| 4   | MCP Server (12h running)            | Cached old code -> migration used unfixed code       | Tool reported success         |
| 5   | `GraphCanvas.tsx` colors            | Read `n.full_data.props` not `n.properties`          | Frontend path mismatch        |
| 6   | `GraphCanvas.tsx` sidebar           | Same path mismatch in different code location        | Same bug, different place     |

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

| What I Did                       | What I Should Do                               |
| -------------------------------- | ---------------------------------------------- |
| Tested API endpoint in isolation | Test complete flow: API -> Frontend -> Browser |
| Assumed API working = UI working | Verify actual user-facing behavior             |

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
python scripts/pipeline/update_dashboard_data.py

# 3. Verify snapshot content
python -c "import json; d = json.load(open('data/dashboard_snapshot.json')); print(f'Snapshot: {len(d.get(\"nodes\", []))} nodes')"

# 4. Verify API returns snapshot
$response = Invoke-RestMethod "http://127.0.0.1:8000/api/graph"
Write-Host "API nodes: $($response.nodes.Count)"
```

### After Any Dashboard Changes

1.  Run `python scripts/pipeline/update_dashboard_data.py`
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
**Status:** OPEN | IN PROGRESS | FIXED | DOCUMENTED

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

## Issue #7: The Phantom Dashboard (Blank Screen / Connection Death)

**Date:** 2026-02-25  
**Duration:** 1 hour  
**Severity:** CRITICAL  
**Status:** FIXED

### Problem

When the Agent opened the Dashboard using the `elefante-DashboardOpen` MCP tool, the user saw an entirely "EMPTY BLANK THING" on `http://localhost:8000` or the connection was immediately refused. The Agent would report that the dashboard was successfully opened, but the user could not see it.

### Symptom

Agent Zero logs: "The Elefante Knowledge Garden Dashboard is now open at http://localhost:8000. Data refreshed: 56 nodes, 41 edges."
User sees: A blank white screen in the browser, or `ERR_CONNECTION_REFUSED`.
`curl http://localhost:8000` returns `(7) Failed to connect to localhost port 8000`.

### Root Cause

**Transient MCP Client Connections vs Daemon Threads.**
Agent Zero (like many MCP clients) often spins up the `src.mcp.server` process to execute a single task or tool. When the tool call finishes, the MCP client gracefully or forcefully closes the `stdio` connection to save RAM.

In `src/mcp/server.py`, the dashboard was being launched like this:

```python
serve_dashboard_in_thread(port=port)
```

This started Uvicorn in a `daemon=True` background thread.

Because daemon threads are immediately forcefully terminated when the main Python process exists, the very moment the MCP Server process shut down, the Dashboard thread was instantly vaporized. If the user's browser fetched `index.html` from cache just beforehand, the subsequent asset requests failed, resulting in a blank React root canvas.

### Solution

Rewrote `_start_dashboard_and_open()` in `src/mcp/server.py` to launch the dashboard as an entirely independent, detached background process using `subprocess.Popen` instead of a thread.

```python
                subprocess.Popen(
                    [sys.executable, "-m", "src.dashboard.server"],
                    start_new_session=True,  # Detach from parent process group
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
```

### Why This Took So Long

1. **Misleading Logs:** The server logs in Python correctly indicated "Dashboard started", and test scripts (which didn't close immediately) proved Uvicorn could run in a thread.
2. **"Blank Screen" vs "Connection Error":** Assumed the issue was a Javascript exception or React fatal error in the frontend build, leading to unnecessary exploration of React hooks and rendering logic via headless browser screenshots.

### Lesson

> **Never bind long-living HTTP servers to daemon threads inside a transient/stateless worker process (like an MCP server). Always detach them into a true subprocess.**

---

_Last verified: 2026-02-25 | Run `python scripts/verify/verify_health.py` to validate dashboard data path_

---

## Issue #8: Persistent Blank Dashboard on First Launch

**Date:** 2026-03-20
**Duration:** 10 minutes
**Severity:** HIGH
**Status:** FIXED (guarded)

### Problem

Every time `elefante-DashboardOpen` was called (especially with `refresh=true`), the user saw a blank white page at `http://localhost:8000`.

### Symptom

- Agent reports "Dashboard opened" and correct node/edge counts.
- Browser shows a blank white page.
- The server IS running (`lsof -i :8000` confirms it).

### Root Cause

**Two compounding bugs in `_start_dashboard_and_open()` in `src/mcp/server.py`:**

**Bug 1 — Race condition (fresh start):**
`subprocess.Popen` returned before Uvicorn finished binding to port 8000. `webbrowser.open()` fired immediately after. The browser sent its first request before the server was ready, got an error, and React rendered a blank root — permanently.

**Bug 2 — Stale server (refresh case):**
When `refresh=true`, `_refresh_dashboard_snapshot()` updated the snapshot file on disk, but the existing long-running server process was NOT restarted. The `is_running` health check found the old server alive and skipped the `Popen`. The browser received the old (or empty) snapshot data.

### Solution

Rewrote `_start_dashboard_and_open()` with two fixes:

```python
# Fix 1: Poll /health for up to 5s before opening browser
def _wait_for_ready(max_wait: float = 5.0) -> bool:
    deadline = time.time() + max_wait
    while time.time() < deadline:
        if _is_server_up(timeout=1.0):
            return True
        time.sleep(0.3)
    return False

# Fix 2: force_restart=True when refresh=true → kill old, start fresh
if force_restart and already_running:
    _kill_existing()   # lsof -ti :8000 | xargs kill
    already_running = False
```

Handler call site updated:
```python
open_result = await self._start_dashboard_and_open(force_restart=refresh)
```

### Lesson

> **Never open the browser before the server is ready. When refreshing data, restart the server — a stale process cannot serve a new snapshot without a restart.**

### Verification

```bash
pytest tests/test_dashboard_serializer.py -k "dashboard" -v
```

This guard checks three contracts that caused the blank first-launch behavior:

1. `_start_dashboard_and_open()` waits for `/health` readiness before calling `webbrowser.open()`.
2. `force_restart=True` kills the existing dashboard server before reopening after refresh.
3. The frontend store retries `/api/stats` and `/api/graph` with exponential backoff so a just-started server can recover cleanly.

---

## Issue #9: All Dashboard Scores Stuck at 100

**Date:** 2026-03-28  
**Duration:** 3 hours (investigation + structural fix)  
**Severity:** CRITICAL  
**Status:** FIXED (structural)

### Problem

Almost all memory scores in the dashboard showed 100. Scores had no differentiation — the entire scoring system was effectively dead.

### Symptom

Dashboard showed 22/74 memories with score=100, average 94.6. Real computed scores should range 54-94 with average ~75.

### Root Cause

**Three independent code paths built dashboard nodes with different scoring logic:**

| Path | File | How it computed score | Result |
|---|---|---|---|
| MCP server refresh | `src/mcp/server.py` `_refresh_dashboard_snapshot()` | `mem.metadata.score` (stale stored value from ChromaDB) | **WRONG** — returns birth-time score, never recomputed |
| Standalone script | `scripts/pipeline/update_dashboard_data.py` | `_compute_live_score(meta)` (correct live formula) | Correct |
| Dashboard API | `src/dashboard/server.py` | Reads `dashboard_snapshot.json` as-is | Depends on who wrote the snapshot |

The MCP server's `_refresh_dashboard_snapshot()` read `mem.metadata.score` directly from ChromaDB. That stored value is set at memory creation time (defaults to 100) and only updated when `record_access()` is called during retrieval. Most memories are never retrieved — their stored score stays at 100 forever.

The standalone script had a correct `_compute_live_score()` function, but it was a local duplicate — never shared with the MCP path. This architectural debt was documented in memory `c15f3b69` months earlier but never fixed.

### Solution

**Structural fix: single source of truth for all dashboard serialization.**

Created `src/utils/dashboard_serializer.py` with:

```python
# THE scoring formula. Both Memory-object and raw-dict paths converge here.
def _composite_dashboard_score(vitality, memory_type, access_count) -> int:
    type_weight = _TYPE_WEIGHTS.get(memory_type, 0.60)
    engagement = min(1.0, log(max(access_count, 1) + 1) / log(20))
    composite = vitality * 0.50 + type_weight * 0.25 + engagement * 0.25
    return min(100, max(0, round(composite * 100)))

# Memory object path (MCP server)
def compute_live_score(mem: Memory) -> int

# Raw ChromaDB dict path (standalone script)
def compute_live_score_from_raw(meta: dict) -> int

# SINGLE node builder — no other code may build dashboard nodes
def memory_to_dashboard_node(mem: Memory) -> Optional[Dict]
```

**Wiring:**
- `src/mcp/server.py` `_refresh_dashboard_snapshot()`: Replaced ~50 lines of inline node-building with `memory_to_dashboard_node(mem)` import.
- `scripts/pipeline/update_dashboard_data.py`: Removed all local duplicates (`_redact_secrets`, `_derive_topic`, `_compute_live_score`, `_is_test_artifact`), now imports from shared module.

**Verification result:**
```
Memories: 74, Score=100: 0, Avg: 75.3, Min: 54, Max: 94
Cross-validation (5 samples): ALL SCORES VERIFIED (±1 for time-decay drift)
```

### Why This Took So Long

1. **The bug was invisible to the MCP server.** It faithfully serialized `mem.metadata.score` — a real field that happened to be stale. No error, no warning.
2. **Regression during fix.** Edited `server.py` on disk but forgot the running MCP process had old code in memory. Dashboard "Refresh" button triggered the old in-memory code, overwriting the correct snapshot.
3. **Three code paths.** The duplication was known debt but was tolerated because "both produce the same output." They didn't.

### Lesson

> **Never trust stored scores. Scores are derived values — always compute them live from behavioral signals. Enforce this architecturally with a single shared serializer, not with documentation or rules.**

### Files Changed

| File | Change |
|---|---|
| `src/utils/dashboard_serializer.py` | **NEW** — single source of truth for Memory → dashboard node |
| `src/mcp/server.py` | Replaced inline serialization with `memory_to_dashboard_node()` import |
| `scripts/pipeline/update_dashboard_data.py` | Replaced local helpers with imports from shared serializer |

### Verification

```bash
# Maintained serializer regression:
pytest tests/test_dashboard_serializer.py -v
```

Use the maintained pytest coverage above instead of recreating the deleted `tmp/verify_scores.py` scratch script.

