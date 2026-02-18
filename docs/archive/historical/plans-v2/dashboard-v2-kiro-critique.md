# Dashboard v2.0.0 KIRO Plan — ULTRATHINK Critique

## Executive Summary

The KIRO plan is **85% correct** and **executable**. This critique identifies the 15% that's wrong, missing, or risky — with specific fixes.

---

## WHAT THE PLAN GETS RIGHT

| Aspect | Verdict | Evidence |
|--------|---------|----------|
| Phase M (Migration First) | ✅ BRILLIANT | Dashboard is only as good as its data. 91% "general" = garbage in, garbage out. |
| Zustand over Context | ✅ CORRECT | Store has 15+ state slices + actions. Context would be a mess. My earlier critique was wrong. |
| 3 visualizations, not 6 | ✅ CORRECT | Scope control. Ship faster. |
| Delete GraphCanvas.tsx entirely | ✅ CORRECT | 2888 lines is untangleable. Rewrite is faster. |
| TanStack Table | ✅ CORRECT | Industry standard. Good choice. |
| Nivo for charts | ✅ CORRECT | Has all 3 chart types. Dark theme support. |
| No React Router | ✅ CORRECT | 3 tabs don't need URL routing. YAGNI. |

---

## CRITIQUE 1: Phase Order Is Wrong

**Claim:** "Phase M can run in parallel with Phases 0-3."

**Problem:** 
- Phase 3 (Table + Search) displays memories
- If M runs in parallel, table shows 121 garbage entries
- After M.7 (regenerate snapshot), data suddenly becomes 40-50 clean entries
- User sees confusing state transition

**Fix:** Phase M runs FIRST. Sequential. Not parallel.

```
CORRECT ORDER:
Phase M  →  Migration (3-4 hours) → CLEAN DATA
Phase 0  →  Dependencies (15 min)
Phase 1  →  Store + hooks (1-2 hours)
Phase 2  →  Tab shell (1-2 hours)
Phase 3  →  Table + search (3-4 hours) → SHOWS CLEAN DATA
...
```

**Why:** Building a dashboard on garbage data hides bugs. You can't test topic filtering when 91% is "general". You can't test knowledge_type badges when 93% is "fact".

---

## CRITIQUE 2: Migration Script Is Too Aggressive

**Claim:** "Delete ~64 neural-register memories."

**Problem:** Some neural-register content is actually valuable:
- "LAW #1: Reserved Word Prohibition" — useful Kuzu knowledge
- "Database Lock Monitoring" — operational knowledge
- The filter "tags contain neural-register AND content starts with SOURCE: docs/debug/" might catch useful content

**Fix:** ARCHIVE, don't DELETE.

```python
# Instead of:
chroma_collection.delete(ids=[...])

# Do:
for memory in to_remove:
    memory.metadata['archived'] = True
    memory.metadata['archive_reason'] = 'neural-register-doc'
    # Move to separate collection or mark invisible
```

**Recovery path:** If we accidentally archive useful knowledge, we can unarchive. Delete is irreversible.

---

## CRITIQUE 3: No Error Boundaries

**Claim:** (Not mentioned)

**Problem:** If a visualization crashes, the whole app crashes. Nivo can throw on malformed data. TanStack Table can throw on bad props.

**Fix:** Wrap each major component:

```typescript
// src/components/ErrorBoundary.tsx
import { Component } from 'react';

export class ErrorBoundary extends Component<
  { fallback: React.ReactNode; children: React.ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false };
  
  static getDerivedStateFromError() {
    return { hasError: true };
  }
  
  render() {
    if (this.state.hasError) {
      return this.props.fallback;
    }
    return this.props.children;
  }
}

// Usage in App.tsx:
<ErrorBoundary fallback={<div className="p-4 text-red-400">Visualization failed to load</div>}>
  <TopicTreemap />
</ErrorBoundary>
```

**Where to add:**
- Around each visualization (Treemap, Calendar, Network)
- Around MemoryTable
- Around MemoryDetailPanel

---

## CRITIQUE 4: No Loading States Specified

**Claim:** "Show loading spinner during search."

**Problem:** Missing loading states for:
1. Initial data fetch (snapshot, stats) — user sees blank screen
2. Tab switching (if we add lazy loading later)
3. Visualization rendering (large datasets)

**Fix:** Add skeleton states:

```typescript
// In OverviewTab.tsx:
if (isLoading) {
  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {[1,2,3,4].map(i => (
          <div key={i} className="bg-slate-800/60 rounded-xl p-6 animate-pulse">
            <div className="h-4 bg-slate-700 rounded w-20 mb-2" />
            <div className="h-8 bg-slate-700 rounded w-16" />
          </div>
        ))}
      </div>
      <div className="h-64 bg-slate-800/60 rounded-xl animate-pulse" />
    </div>
  );
}
```

---

## CRITIQUE 5: No Testing Strategy

**Claim:** (Not mentioned)

**Problem:** v2.0.0 rewrite with no tests = regression risk. How do we know the health score formula is correct? How do we know topic classification works?

**Fix:** Add minimal test coverage:

```typescript
// src/__tests__/useVisualizationData.test.ts
import { renderHook } from '@testing-library/react';
import { useHealthScore, useTreemapData } from '@/hooks/useVisualizationData';

describe('useHealthScore', () => {
  it('returns 0 for empty snapshot', () => {
    // Mock empty snapshot
    const result = useHealthScore();
    expect(result.overall).toBe(0);
  });
  
  it('calculates freshness correctly', () => {
    // Mock snapshot with recent memories
    // Assert freshness > 80
  });
});
```

**Minimum tests:**
- Health score calculation
- Topic classification rules
- Knowledge type classification rules
- Store actions (select, filter, etc.)

**Effort:** 2-3 hours. Worth it for confidence.

---

## CRITIQUE 6: No Rollback Plan

**Claim:** "Back up ChromaDB before running."

**Problem:** What if:
- Backup is corrupted?
- Migration partially succeeds (deletes 30 memories, then crashes)?
- User wants to undo after seeing results?

**Fix:** Add rollback command:

```python
# In migrate_v2_memory_cleanup.py:

def rollback(backup_path: str):
    """Restore ChromaDB from backup."""
    current_path = get_chroma_path()
    shutil.rmtree(current_path)
    shutil.copytree(backup_path, current_path)
    print(f"Rolled back to {backup_path}")

# CLI:
# python3 scripts/migrate_v2_memory_cleanup.py --rollback ~/.elefante/data/chromadb_backup_pre_v2
```

**Also:** Save a manifest of all changes:

```json
// migration_manifest.json
{
  "timestamp": "2026-02-17T02:00:00Z",
  "deleted_ids": ["id1", "id2", ...],
  "modified_ids": ["id3", "id4", ...],
  "before_counts": {"total": 121, "general": 110, ...},
  "after_counts": {"total": 45, "general": 8, ...}
}
```

---

## CRITIQUE 7: Timeline Is Optimistic

**Claim:** "14-19 hours of focused execution."

**Problem:**

| Task | Claimed | Realistic | Reason |
|------|---------|-----------|--------|
| Phase 1.1 (types) | 30 min | 2 hours | Extracting types from 2888 lines is tedious |
| Phase 3.1 (table) | 3 hours | 5 hours | TanStack Table learning curve + styling |
| Phase M (migration) | 3-4 hours | 6 hours | Edge cases, testing, rollback |
| Phase 4 (treemap) | 2 hours | 3 hours | Nivo treemap quirks |
| Testing | 0 hours | 3 hours | Not mentioned but necessary |

**Realistic total:** 25-30 hours.

**Mitigation:** Ship incrementally. Each phase is a checkpoint. Don't aim for perfect in one pass.

---

## CRITIQUE 8: Action Layer Still Missing

**Claim:** (Not mentioned in KIRO plan)

**Problem:** My earlier critique identified this. The KIRO plan doesn't address it. The dashboard is still READ-ONLY.

**Fix:** Add to Phase 3.5 (new phase):

```typescript
// In MemoryTable.tsx, add action column:
{
  id: 'actions',
  header: '',
  cell: ({ row }) => (
    <div className="flex gap-1">
      <button onClick={() => archiveMemory(row.original.id)} title="Archive">
        <Archive size={14} />
      </button>
      <button onClick={() => editMemory(row.original.id)} title="Edit">
        <Edit size={14} />
      </button>
    </div>
  ),
}
```

**Wire to API:** Phase 7 (deferred) becomes Phase 3.5 (required for v2.0.0).

**Why:** A read-only dashboard is a museum. Users need to curate. "Archive" is the minimum action.

---

## CRITIQUE 9: Mobile Still Not Addressed

**Claim:** (Not mentioned)

**Problem:** Treemap on mobile is unreadable. Table is the only mobile-friendly view.

**Fix:** Add mobile detection + default to Memories tab:

```typescript
// In App.tsx:
const isMobile = window.innerWidth < 768;

useEffect(() => {
  if (isMobile) {
    setActiveTab('memories'); // Default to table on mobile
  }
}, []);
```

**Also:** Add "Desktop recommended" banner on Explore tab for mobile users.

---

## CRITIQUE 10: Health Score Weights Are Arbitrary

**Claim:**
```typescript
const overall = Math.round(freshness * 0.4 + coverage * 0.35 + connectivity * 0.25);
```

**Problem:** Why 40/35/25? Why not 33/33/33? These weights have no justification.

**Fix:** Document the reasoning:

```typescript
/**
 * Health Score Formula (v2.0.0)
 * 
 * Weights are based on user value:
 * - Freshness (40%): Most important — stale knowledge is dangerous
 * - Coverage (35%): Important — single-topic knowledge is brittle
 * - Connectivity (25%): Less important — orphans can still be valuable
 * 
 * These weights are TUNABLE. Future versions may adjust based on user feedback.
 */
```

**Also:** Add a "Learn more" tooltip on the health score that explains the formula.

---

## REVISED EXECUTION ORDER

```
Phase M    →  Migration (6 hours) → BACKUP + ARCHIVE + CLEAN DATA
Phase 0    →  Dependencies (15 min)
Phase 1    →  Store + hooks + TESTS (3 hours)
Phase 2    →  Tab shell + error boundaries (2 hours)
Phase 3    →  Table + search (5 hours)
Phase 3.5  →  Action buttons + archive API (3 hours) ← NEW
Phase 4    →  Overview treemap + feed (3 hours)
Phase 5    →  Explore visualizations (3 hours)
Phase 6    →  Cleanup + mobile detection (2 hours)
Phase 7    →  Polish + empty states + loading states (2 hours)
```

**Total:** 29 hours (realistic)

---

## FINAL VERDICT

| Question | Answer |
|----------|--------|
| Is the plan executable? | YES, with fixes |
| Is the order correct? | NO — Migration should be FIRST, not parallel |
| Is the scope correct? | MOSTLY — missing action layer, mobile |
| Is the timeline realistic? | NO — 25-30 hours, not 14-19 |
| Is it shippable? | YES, after fixes |

**Key insight:** The plan is 85% correct. The 15% missing is:
1. Migration FIRST (not parallel)
2. Archive (not delete)
3. Error boundaries
4. Loading states
5. Tests
6. Rollback plan
7. Action layer
8. Mobile detection
9. Realistic timeline

**Recommendation:** Apply these fixes, then execute. The plan is solid after fixes.
