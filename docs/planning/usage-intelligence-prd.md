# PRD: Usage Intelligence — Dashboard v2.2

> **Status**: DRAFT — Awaiting approval before any code changes
>
> **Author**: Agent (from ULTRATHINK analysis in DASHBOARD-V2-ANALYSIS.md)
>
> **Date**: 2026-02-18
>
> **Scope**: Surface existing usage data + add missing tracking + build dashboard UI

---

## 1. Problem Statement

The ULTRATHINK section of the analysis document identifies the core question:

> **"Is my second brain actually making my AI smarter?"**

The dashboard currently shows what memories exist (topic, score, health). It does NOT show whether memories are **actually being used** by agents. Without usage data, all curation is guessing.

---

## 2. Honest Assessment: What Already Exists

**Before writing any code, I audited the codebase. The situation is better than the ULTRATHINK section suggests.**

### Already Implemented (Backend)

| Feature | Location | Status |
|---------|----------|--------|
| `access_count` field | `MemoryMetadata` in `src/models/memory.py:232` | Exists, default=0 |
| `last_accessed` field | `MemoryMetadata` in `src/models/memory.py:230` | Exists, default=utcnow |
| `record_access()` method | `Memory` in `src/models/memory.py:340` | Increments count, updates timestamp, recomputes score |
| `update_memory_access()` | `vector_store.py:797` | Persists access_count + last_accessed to ChromaDB |
| Access tracking in search | `orchestrator.py:912-913` | Calls `update_memory_access()` for every retrieved memory |
| Access tracking in graph search | `orchestrator.py:1050-1053` | Same, for vector-backed graph results |
| Temporal decay using access data | `retrieval.py:237-244` | Uses `last_accessed` + `access_count` in authority scoring |
| `access_count` in snapshot | `update_dashboard_data.py:192` | Included in node properties |

### NOT Implemented

| Feature | Where It's Missing | Impact |
|---------|-------------------|--------|
| `last_accessed` in snapshot | `update_dashboard_data.py` — maps `last_modified` but NOT `last_accessed` | Dashboard can't show when a memory was last retrieved |
| Query logging | Nowhere in codebase | Can't answer "what queries triggered this memory?" |
| Retrieval context display | Dashboard frontend | No UI shows access_count, last_accessed, or usage patterns |
| "Never retrieved" analysis | Dashboard frontend | No component highlights unused memories |
| "Most retrieved" analysis | Dashboard frontend | No component highlights overused memories |
| Usage-based health metrics | `useVisualizationData.ts` | Health score ignores access_count entirely |

### Key Insight

**The backend is 80% done. The gap is in the snapshot pipeline (1 missing field) and the frontend (0% done).**

The ULTRATHINK section's claim that everything is "NOT TRACKED" is incorrect for `access_count` and `last_accessed` — they ARE tracked in ChromaDB. They just aren't surfaced in the dashboard.

---

## 3. What We're Building

### 3.1 Goal

Transform the OverviewTab from "here's your data health" to "here's how your memories are actually performing" by surfacing existing usage data and adding one new tracking dimension.

### 3.2 Non-Goals (Explicit Scope Limits)

- **NO new database schema** — ChromaDB metadata already has all needed fields
- **NO LLM-based analysis** — Pure data analysis from existing fields
- **NO real-time streaming** — Still snapshot-based (LAW #1)
- **NO query logging in v2.2** — Deferred to v2.3 (requires MCP protocol changes)
- **NO changes to the search/retrieval pipeline** — It already works
- **NO mobile responsiveness** — Separate workstream
- **NO write operations** — Separate workstream (Agent 1 in divide-and-conquer)

---

## 4. Exact Changes Required

### Phase A: Snapshot Pipeline Fix (1 file, 1 line)

**File**: `scripts/update_dashboard_data.py`

**Change**: Add `last_accessed` to node properties mapping (it maps `last_modified` but forgot `last_accessed`).

```python
# Currently missing, add after access_count line:
"last_accessed": meta.get("last_accessed"),
```

**Risk**: None — additive change, no existing behavior affected.

### Phase B: TypeScript Types (1 file, ~5 lines)

**File**: `src/dashboard/ui/src/types.ts`

**Change**: Add `access_count` and `last_accessed` to the node properties interface so TypeScript knows about them.

### Phase C: Usage Data Hook (1 file, ~60 lines)

**File**: `src/dashboard/ui/src/hooks/useVisualizationData.ts`

**Change**: Add `useUsageData()` hook that computes:

```typescript
interface UsageData {
  neverRetrieved: MemoryNode[]      // access_count === 0
  mostRetrieved: MemoryNode[]       // top 10 by access_count
  recentlyAccessed: MemoryNode[]    // last_accessed within 7 days
  staleButUsed: MemoryNode[]        // high access_count but old last_accessed
  avgAccessCount: number
  retrievalRate: number             // % of memories with access_count > 0
}
```

### Phase D: OverviewTab Enhancement (1 file, ~80 lines)

**File**: `src/dashboard/ui/src/components/OverviewTab.tsx`

**Change**: Add a "Usage Intelligence" row below the existing MetricCards row:

```
Row 5 (NEW): Usage Intelligence
  Left (3-col):  UsageGauge — % of memories ever retrieved
  Center (5-col): Top 5 most/least retrieved memories (mini table)
  Right (4-col):  Usage health diagnosis (similar to existing diagnosis panel)
```

**Diagnosis logic**:
- `retrievalRate < 30%` → CRITICAL: "70% of memories have never been retrieved"
- `retrievalRate < 60%` → WARNING: "40% of memories may be dead weight"
- Any memory with `access_count > 20` → INFO: "Memory X may be too generic"

### Phase E: Health Score Update (1 file, ~10 lines)

**File**: `src/dashboard/ui/src/hooks/useVisualizationData.ts`

**Change**: Add `usage` as a 4th metric in health score:

```typescript
// Current: overall = freshness * 0.4 + coverage * 0.35 + connectivity * 0.25
// New:     overall = freshness * 0.30 + coverage * 0.30 + connectivity * 0.20 + usage * 0.20

// usage = memories_with_access / total_memories
```

**Risk**: Changes the health score number for all users. The current formula is documented. Old weights must be updated in the OverviewTab MetricCards too.

### Phase F: MemoryTable Column (1 file, ~15 lines)

**File**: `src/dashboard/ui/src/components/MemoryTable.tsx`

**Change**: Add "Uses" column showing `access_count` with color coding:
- 0 = red pill ("Never")
- 1-5 = default
- 5+ = green pill

---

## 5. Files Changed Summary

| File | Phase | Type of Change |
|------|-------|---------------|
| `scripts/update_dashboard_data.py` | A | Add 1 line: `last_accessed` field |
| `src/dashboard/ui/src/types.ts` | B | Add 2 fields to interface |
| `src/dashboard/ui/src/hooks/useVisualizationData.ts` | C, E | New hook + health formula update |
| `src/dashboard/ui/src/components/OverviewTab.tsx` | D | New "Usage Intelligence" row |
| `src/dashboard/ui/src/components/MemoryTable.tsx` | F | New "Uses" column |

**Total**: 5 files, ~170 lines of new/modified code.

---

## 6. Data Reality Check

Before building UI, we need to verify what the actual `access_count` values are across the 121 memories. If they're all 0 (possible if golden_cleanup.py or some reset zeroed them), then:

- The Usage Intelligence panel would show "0% retrieval" — technically correct but unhelpful for demo
- We should **validate the data first** with a quick audit script before building UI

**Proposed validation** (run before any frontend work):

```bash
python3 -c "
import chromadb
c = chromadb.PersistentClient('~/.elefante/data/chroma_db')
col = c.get_or_create_collection('memories')
data = col.get(include=['metadatas'])
counts = [m.get('access_count', 0) for m in data['metadatas']]
print(f'Total memories: {len(counts)}')
print(f'Never accessed (0): {sum(1 for c in counts if c == 0)}')
print(f'Accessed 1+: {sum(1 for c in counts if c > 0)}')
print(f'Max access_count: {max(counts) if counts else 0}')
print(f'Avg access_count: {sum(counts)/len(counts):.1f}' if counts else 'N/A')
"
```

---

## 7. Success Criteria

| # | Criterion | Measurable |
|---|-----------|------------|
| 1 | OverviewTab shows "Usage Intelligence" section | Visual — new row visible |
| 2 | "Never retrieved" count is displayed with actual number | Number matches ChromaDB data |
| 3 | "Most retrieved" top 5 list shows memory titles + counts | Sorted correctly |
| 4 | Health score includes usage metric (20% weight) | Formula updated, MetricCards show 4 cards |
| 5 | MemoryTable has "Uses" column with access_count | Sortable, color-coded |
| 6 | `npm run build` passes with no errors | CI-checkable |
| 7 | Snapshot includes `last_accessed` field | Verifiable in JSON |

---

## 8. What This Does NOT Do (Deferred)

| Feature | Why Deferred | Target Version |
|---------|-------------|----------------|
| Query logging ("what triggered this retrieval") | Requires changes to MCP tool response format | v2.3 |
| "Effectiveness" scoring (did the agent use it well?) | Requires agent feedback loop — not available in MCP protocol | v3.0 |
| Write operations (archive unused memories) | Separate Agent 1 workstream | v2.2-Agent1 |
| Contradiction detection with semantic approach | Separate Agent 4 workstream | v2.3 |
| Cross-visualization interaction (click usage → filter table) | Separate Agent 2 workstream | v2.2-Agent2 |

---

## 9. Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| All access_counts are 0 | MEDIUM — golden cleanup may not have affected these, but memories are new | Run data audit FIRST (Section 6) |
| Health score change confuses users | LOW — dashboard is in development, no production users | Document weight change in CHANGELOG |
| Snapshot size increase | NEGLIGIBLE — 1 new field per node | No mitigation needed |
| `last_accessed` values are all identical (default=utcnow at creation) | MEDIUM — if memories were bulk-imported, all have same timestamp | Display "No usage data yet" instead of misleading dates |

---

## 10. Implementation Order

```
1. Run data audit (Section 6) → determine if access_count data exists
2. Phase A: Fix snapshot pipeline (1 line)
3. Phase B: Update TypeScript types
4. Phase C: Build useUsageData hook
5. Phase D: Build Usage Intelligence row in OverviewTab
6. Phase E: Update health score formula + MetricCards
7. Phase F: Add Uses column to MemoryTable
8. Regenerate snapshot + rebuild frontend + verify
```

**Estimated scope**: 5 files, ~170 lines, 6 phases.

---

*This PRD must be approved before any code is written.*
