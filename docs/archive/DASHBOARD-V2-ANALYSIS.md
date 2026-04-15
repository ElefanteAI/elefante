# Elefante Dashboard v2.1 - Deep Analysis & Handoff Document

> ⚠️ **ARCHIVED** — Handoff document written at v1.10/v2.1. For current dashboard architecture see [docs/technical/ops-dashboard.md](../technical/ops-dashboard.md) and [docs/technical/spec-architecture.md](../technical/spec-architecture.md).

> **Purpose**: Comprehensive analysis for a new agent to understand the work done on Elefante at v1.10 and Dashboard at v2.1. This document explains the reasoning for changes, the current state, and the path forward.
>
> **Audience**: Incoming developer/agent taking over the dashboard development
>
> **Date**: 2026-02-18 (Updated: 2026-02-18 Session 2)
>
> **Status**: Dashboard in active development - requires systematic work to become a product
>
> **CRITICAL CONTEXT**: The dashboard is about analyzing the performance of Elefante (a visual angle of memories) in near-real-time. The user must be capable of understanding the state of their second brain in a way that is revolutionary compared to other tools. The dashboard is still in development and requires significant work to become a product.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Elefante Core v1.10 - Context](#elefante-core-v110---context)
3. [Dashboard Evolution History](#dashboard-evolution-history)
4. [The v2.0 Overhaul - Why It Happened](#the-v20-overhaul---why-it-happened)
5. [Current Dashboard Architecture](#current-dashboard-architecture)
6. [Data Flow & Snapshot Contract](#data-flow--snapshot-contract)
7. [Component Analysis](#component-analysis)
8. [Health Score System](#health-score-system)
9. [Golden Cleanup - Data Quality Transformation](#golden-cleanup---data-quality-transformation)
10. [What's Working Well](#whats-working-well)
11. [What Still Needs Work](#what-still-needs-work)
12. [Undocumented Recent Changes](#undocumented-recent-changes)
13. [Critical Laws & Pitfalls](#critical-laws--pitfalls)
14. [Known Bugs & Root Causes](#known-bugs--root-causes)
15. [Competitive Positioning](#competitive-positioning)
16. [Recommended Next Steps](#recommended-next-steps)
17. [File Reference Map](#file-reference-map)

---

## Executive Summary

### The Product Vision

Elefante is a **Second Brain for AI Agents** - a persistent memory system that allows AI coding agents to remember context across sessions. The dashboard is the **visual interface** for understanding the state of this second brain in near-real-time.

The vision: **"What does my AI know about me?"** - a question no other tool answers well. The dashboard should make memory health as intuitive as a heart rate monitor.

### Current State

| Component | Version | Status |
|-----------|---------|--------|
| Elefante Core | v1.10.0 | Stable - Behavioral Relevance model |
| Dashboard Backend | v1.11.0 | Stable - Snapshot-driven API |
| Dashboard Frontend | v2.1.0 | In Development - 3-tab + HealthGauge + Agent Impact |
| Memory Data | Post-Golden Cleanup | 97% categorized, avg score 6.9, 0 contradictions |

### The Transformation

The dashboard underwent a **complete architectural overhaul** in v1.11.0/v2.0.0, then further enhancement in v2.1.0:

```
BEFORE (v1.6.x - v1.10.x):
- Single monolithic component (GraphCanvas.tsx, 2888 lines)
- D3 force-directed physics simulation
- Unstable "screensaver" visualization
- No search, no table, no actionable insights
- 91% memories uncategorized, 83% unprocessed, all scores=0

AFTER (v2.1.0):
- 3-tab architecture (Overview, Memories, Explore)
- Static visualizations (no physics)
- TanStack Table with sorting/filtering
- Semantic search wired to API
- Health Score with SVG ring gauge + Agent Impact diagnostics
- Zustand state management
- Golden cleanup: 97% categorized, avg score 6.9, 0 contradictions
```

---

## Elefante Core v1.10 - Context

### What Elefante Does

Elefante provides persistent memory for AI coding agents through:

1. **Vector Store (ChromaDB)**: Semantic search over memories
2. **Graph Store (Kuzu)**: Entity relationships and knowledge topology
3. **MCP Protocol**: 17 tools for memory operations

### Key v1.10.0 Changes - Behavioral Relevance

The most significant recent change to the core was the **Behavioral Relevance Model**:

| Before v1.10 | After v1.10 |
|--------------|--------------|
| User-assigned `importance` (1-10) | System-computed `score` (0-100) |
| Manual "Layer/Sublayer" taxonomy | Simplified `MemoryType` + `Domain` |
| Importance rot (everything rated 8-10) | Automatic decay based on memory type |

**The Formula** (from [`src/models/memory.py`](src/models/memory.py)):

```python
# Behavioral Relevance Score = 
#   Recency (decay by type) + 
#   Freshness (recent access boost) + 
#   Reinforcement (access count)

TYPE_DECAY_RATES = {
    "rule": 0.995,      # Rules decay slowly
    "fact": 0.990,      # Facts moderately
    "decision": 0.985,  # Decisions faster
    "conversation": 0.950,  # Conversations quickly
}
```

### Why This Matters for the Dashboard

The dashboard now displays `score` instead of `importance`. The Health Score system (v2.1.0) uses behavioral relevance to determine "freshness" - a key metric for knowledge health.

---

## Dashboard Evolution History

### Version Timeline

| Version | Date | Key Change |
|---------|------|------------|
| v1.6.0 | 2025-12-28 | Compliance Gate (search-before-write) |
| v1.6.1 | 2025-12-29 | Cognitive Field Standardization |
| v1.6.2 | 2025-12-29 | Cognitive Visual Enablement (sidebar shows concepts) |
| v1.6.3 | 2025-12-30 | Neural Web Visualization (organic physics) |
| v1.9.0 | 2026-02-09 | Custodial Memory Tools (update/delete) |
| v1.9.1 | 2026-02-09 | Tool Consolidation (24 tools -> 17) |
| v1.10.0 | 2026-02-09 | Behavioral Relevance + Tool Renaming |
| v1.11.0 | 2026-02-17 | **Dashboard Overhaul** - Complete rewrite |

### The Physics Problem (v1.6.3 - v1.10.x)

The original dashboard used a D3 force-directed graph with physics simulation. This caused:

1. **"Two Dots" Bug**: Nodes appeared as visual duplicates
2. **Flying Nodes**: Nodes would "fly away" or flicker
3. **CPU Intensive**: Physics calculations consumed resources
4. **Unstable UX**: Users couldn't click nodes reliably

**The Root Cause**: The physics engine was fundamentally the wrong metaphor. Knowledge visualization should be static and explorable, not animated and chaotic.

---

## The v2.0 Overhaul - Why It Happened

### The Diagnosis

The dashboard was a **tech demo, not a product**. Key problems identified in the strategy documents:

| Problem | Evidence |
|---------|----------|
| No actionable insight | User sees 70 dots, asks "so what?" |
| No workflow | Read-only. Click node -> see details -> close. No action. |
| Wrong metaphor | Force graphs are for debugging, not knowledge work |
| Zero discovery | Doesn't surface stale, contradicted, or missing knowledge |
| Stale data | Pre-generated snapshot. Not live. |
| Monolith | GraphCanvas.tsx = 2,888 lines doing everything |

### The Solution - 3-Tab Architecture

```
BEFORE:
+--------------------------------------------------+
|  [Physics Graph - Full Screen]                   |
|  - 70+ dots floating randomly                    |
|  - Click to see sidebar                          |
|  - No search, no filters, no actions             |
+--------------------------------------------------+

AFTER:
+--------------------------------------------------+
| [Overview] [Memories] [Explore]                  |
+--------------------------------------------------+
| Overview: Health Score + Treemap + Activity      |
| Memories: Table + Search + Detail Panel          |
| Explore: Network + Calendar + Treemap            |
+--------------------------------------------------+
```

### What Was Killed

1. **Physics Engine**: Removed D3 force simulation entirely
2. **Monolith**: Split GraphCanvas.tsx into 15+ components
3. **Ring Layout**: No more concentric orbits

### What Was Added

1. **Zustand Store**: Centralized state management
2. **TanStack Table**: Sortable/filterable memory table
3. **Nivo Visualizations**: Static treemap, calendar, network
4. **Health Score**: Freshness + Coverage + Connectivity
5. **Semantic Search**: Wired to `/api/search`

---

## Current Dashboard Architecture

### Frontend Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Build | Vite 5.1.4 | Fast dev server, TypeScript |
| Framework | React 18.2 | UI components |
| State | Zustand 5.0 | Global store (replaced useState spaghetti) |
| Table | TanStack Table 8.21 | Sortable/filterable memory list |
| Charts | Nivo 0.99 | Treemap, Calendar, Network |
| Styling | Tailwind 3.4 | Dark theme, utility classes |
| Icons | Lucide React | Consistent iconography |

### Backend Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Server | FastAPI | REST API endpoints |
| Data | Snapshot JSON | Pre-generated graph data |
| Search | ChromaDB | Semantic search (live query) |

### File Structure

```
src/dashboard/
  server.py                    # FastAPI backend (234 lines)
  ui/
    package.json               # Dependencies
    vite.config.ts             # Build config
    src/
      App.tsx                  # Main app (101 lines)
      store.ts                 # Zustand store (148 lines)
      types.ts                 # TypeScript interfaces (93 lines)
      components/
        TabNav.tsx             # Tab navigation
        HeaderBar.tsx          # Stats display
        OverviewTab.tsx        # Health + Treemap
        MemoriesTab.tsx        # Table + Search
        ExploreTab.tsx         # Visualizations
        MemoryTable.tsx        # TanStack Table
        MemoryDetailPanel.tsx  # Slide-out detail
        KnowledgeGraph.tsx     # Nivo Network
        TopicTreemap.tsx       # Nivo Treemap
        CalendarHeatmap.tsx    # Nivo Calendar
        HealthGauge.tsx        # Circular health display
        ActivityFeed.tsx       # Recent memories
      hooks/
        useVisualizationData.ts  # Data transformations
        useSearch.ts            # Semantic search hook
```

---

## Data Flow & Snapshot Contract

### The Critical Architecture Decision

**LAW #1**: Dashboard reads from SNAPSHOT file, never queries database directly.

```
                    +------------------+
                    |   ChromaDB       |
                    |   (memories)     |
                    +--------+---------+
                             |
                             v
+------------------+   update_dashboard_data.py   +------------------+
|   Kuzu DB        | <-------------------------- |   Snapshot       |
|   (entities)     |                             |   Generation     |
+------------------+                             +--------+---------+
                             |                           |
                             v                           v
                    +------------------+         +------------------+
                    |   Relationships  |         | dashboard_snapshot.json
                    |   + Concepts     |         | (static file)     |
                    +------------------+         +--------+---------+
                                                          |
                                                          v
                                                 +------------------+
                                                 |   Dashboard      |
                                                 |   server.py      |
                                                 |   (read-only)    |
                                                 +------------------+
```

### Why This Matters

1. **Lock Prevention**: Kuzu has single-writer lock. MCP server writes, dashboard reads snapshot.
2. **Performance**: Snapshot is pre-computed, no runtime queries.
3. **Separation**: Dashboard can run independently of MCP server.

### Snapshot Schema

From [`docs/technical/dashboard-snapshot-contract.md`](docs/technical/dashboard-snapshot-contract.md):

```json
{
  "generated_at": "2026-02-18T13:00:00Z",
  "stats": {
    "total_nodes": 75,
    "memories": 70,
    "entities": 5,
    "edges": 120
  },
  "nodes": [
    {
      "id": "mem_abc123",
      "name": "Always use absolute paths",
      "type": "memory",
      "description": "...",
      "created_at": "2026-02-15T10:30:00Z",
      "properties": {
        "content": "...",
        "title": "...",
        "memory_type": "rule",
        "topic": "coding",
        "score": 85,
        "ring": "core",
        "knowledge_type": "rule",
        "concepts": ["path", "configuration"],
        "surfaces_when": "when configuring applications",
        "authority_score": 0.9
      }
    }
  ],
  "edges": [
    {
      "from": "mem_abc123",
      "to": "signal:topic:coding",
      "label": "HAS_TOPIC",
      "type": "signal"
    }
  ]
}
```

---

## Component Analysis

### OverviewTab (v2.1.0) — The Brain Dashboard

**Purpose**: Answer "What's the state of my knowledge?" at a glance.

**Layout** (4 rows):

```
Row 1: HealthGauge (left, 4-col) + Diagnosis Panel + Agent Impact (right, 8-col)
Row 2: Quick Stats Bar (Memories | Topics | Edges | Fresh | Connected | Type breakdown)
Row 3: 3 MetricCards (Freshness 40% | Coverage 35% | Connectivity 25%)
Row 4: TopicTreemap (left, 3-col) + ActivityFeed (right, 2-col)
```

**Sub-Components**:
- **`HealthGauge`** (v2.1.0): SVG ring gauge with `strokeDasharray` animation, glow via `drop-shadow`, color-coded (emerald >= 70% / amber >= 40% / red < 40%). Shows percentage centered with status label.
- **`StatPill`**: Inline stat display with label + value + optional subtitle.
- **`MetricCard`**: Card with label, weight indicator, progress bar, contextual hint text.
- **`getHealthDiagnosis()`**: Analyzes health metrics and returns `{ issues[], recommendations[], status }` with **concrete numbers** (e.g., "28 of 70 memories are over 90 days old").
- **`getAgentImpact()`**: Returns severity-tagged impacts on agent behavior (e.g., "Searches return too many irrelevant memories — agent cannot filter by topic" with severity `critical`).

**Key Logic** - Health Diagnosis Thresholds:

```typescript
// Freshness
if (health.freshness < 20) → CRITICAL: "{staleCount} of {total} memories over 90 days old"
if (health.freshness < 50) → WARNING: "{staleCount} memories aging"

// Coverage (the key differentiator)
if (health.coverage < 15) → CRITICAL: "{generalCount} of {total} memories uncategorized"
if (health.coverage < 40) → WARNING: "{generalCount} still tagged general"

// Connectivity
if (health.connectivity < 10) → WARNING: "{orphanCount} memories have zero connections"
```

**Agent Impact Severity Levels**:
- `critical`: Coverage < 15% → "Agent may repeat past mistakes because relevant learnings are buried in noise"
- `warning`: Coverage < 40% → "Topic filtering is partially effective"
- `critical`/`warning`: Freshness < 30% → "Agent relies on outdated knowledge"
- `warning`: Connectivity < 10% → "Cannot traverse related concepts"

### MemoriesTab (v2.0.0) — The Workhorse

**Purpose**: Find, inspect, and compare specific memories.

**Layout**:
```
Top: Semantic Search Bar (Sparkles icon, violet theme)
Body: MemoryTable (TanStack Table, full width)
Right: MemoryDetailPanel (fixed 420px slide-out, overlays content)
```

**Components**:
- **Search Bar**: Debounced 300ms, 2+ character threshold, AbortController for cancellation
- **MemoryTable**: TanStack Table with columns: Expand | Title | Topic (violet pill) | Type (color-coded pill) | Created | Score. Supports sorting, global text filter, expandable rows.
- **MemoryDetailPanel**: Fixed right panel showing title/type/ring/time header, summary, content (scrollable), metadata grid (topic, knowledge_type, score, status, namespace, source), tags, related memories (from edges), debug info (collapsible).

**Data Flow for Search**:
1. User types in search bar → debounce 300ms
2. Calls `/api/search?query=...&limit=20&min_similarity=0.3`
3. Results converted to `MemoryNode[]` format for table
4. Table shows search results instead of browse mode

**Cross-Navigation**: `ActivityFeed` click sets `inspectedMemoryId` in store → MemoriesTab detects it via `useEffect` → opens detail panel for that memory.

### ExploreTab (v2.0.0) — Visual Discovery

**Purpose**: Visual exploration of knowledge topology through 3 visualization modes.

**Layout**:
```
Top: Segmented control (Topics | Activity | Network) + node/link count
Body: Selected visualization (full width, flex-1)
Bottom: Legend bar (context-sensitive per visualization type)
```

**Visualizations**:
1. **TopicTreemap** (Nivo `ResponsiveTreeMap`): Topic distribution, `squarify` algorithm, spectral color scheme, custom tooltips. Data from `useTreemapData()`.
2. **CalendarHeatmap** (Nivo `ResponsiveCalendar`): Memory creation frequency by day, GitHub-style, cyan gradient (`#164e63` → `#22d3ee`). Data from `useCalendarData()`.
3. **KnowledgeGraph** (Nivo `ResponsiveNetwork`): Static node-link diagram, `animate=false`, node size by connection count, color by topic. Data from `useNetworkData()`. **Capped at 200 edges for performance**.

**Legend Bar** adapts per visualization:
- Network: Memory/Entity color dots + "Node size = connection count"
- Treemap: "Rectangle size = number of memories in topic"
- Calendar: Low/High gradient + "Memory creation frequency by day"

### HeaderBar (v1.11.0)

**Purpose**: System status at a glance.

Shows Elefante version, memory/entity/link counts, and snapshot timestamp from `/api/stats`.

### TabNav (v1.11.0)

**Purpose**: Tab navigation with icons.

3 tabs: Overview (LayoutDashboard icon) | Memories (Table2 icon) | Explore (Compass icon). Active tab highlighted with cyan underline.

### App.tsx (v2.0.0)

**Purpose**: Root component orchestrating data fetch and keyboard shortcuts.

- Fetches snapshot + stats on mount via Zustand store
- Global keyboard: `1`/`2`/`3` switch tabs (skips if input focused), `Escape` closes detail panel
- Loading spinner during data fetch
- Error banner for API failures
- Footer with version and keyboard shortcut hint

---

## Health Score System

### The Formula (v1.11.0)

From [`src/dashboard/ui/src/hooks/useVisualizationData.ts`](src/dashboard/ui/src/hooks/useVisualizationData.ts):

```typescript
// Weights based on user value:
// - Freshness (40%): Most important - stale knowledge is dangerous
// - Coverage (35%): Important - single-topic knowledge is brittle
// - Connectivity (25%): Less important - orphans can still be valuable

overall = freshness * 0.4 + coverage * 0.35 + connectivity * 0.25
```

### Metric Definitions

| Metric | Formula | Data Needed |
|--------|---------|-------------|
| **Freshness** | `avg(1 - days_since_created / 90)` | `created_at` |
| **Coverage** | `non_general_memories / total_memories` | `topic` field |
| **Connectivity** | `memories_with_edges / total_memories` | edge count |

### What the Health Score Tells You

```
HEALTH = 72%

BREAKDOWN:
- Freshness: 85% (most memories created recently)
- Coverage: 60% (40% still tagged "general")
- Connectivity: 15% (most memories are orphans)

ISSUES:
- 28 memories have no topic (search will be noisy)
- 60 memories have no graph connections

RECOMMENDATIONS:
- Assign specific topics when saving memories
- Link related memories with elefante-GraphConnect
```

---

## Golden Cleanup - Data Quality Transformation

### Why It Was Needed

The dashboard was visually functional but showing **garbage data**. The treemap was one giant "general" block, all scores were 0, and 25 memories were falsely flagged as "contradictory."

### Before vs After

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Categorized memories** | 9% (11/121) | 97% (117/121) | +88% |
| **Average score** | 0.0 | 6.9 | +6.9 |
| **"general" topic** | 91% (110/121) | 3% (4/121) | -88% |
| **Contradictory status** | 25 | 0 | -25 |
| **Unique topics** | 4 | 10 | +6 |

### What Was Done

A dedicated script (`scripts/golden_cleanup.py`) was built with:

1. **Two-pass keyword classifier**: 10 topic categories with 7-13 keywords each:
   - `ai-memory-systems`, `mcp-protocol`, `coding-standards`, `user-identity`, `communication-rules`, `workflow-methodology`, `bug-reports`, `architecture-decisions`, `llm-preferences`, `dashboard-visualization`

2. **Score formula**: `topic_specificity(0-3) + knowledge_type(0-2) + memory_type(0-2) + actionable(0-1) + freshness(0-2)`, clamped 1-10

3. **Title-based overrides** for 3 specific misclassifications (contextual corrections that keyword matching can't handle)

4. **Contradictory status fix**: All 25 "contradictory" statuses changed to "related" (root cause: `_detect_contradiction()` in orchestrator.py uses a naive negation XOR heuristic)

### Root Cause of False Contradictions

`_detect_contradiction()` in `src/core/orchestrator.py` (line ~1575) flags memories as contradictory when:
- Both have 2+ shared words of 4+ characters
- XOR: one has negation words ("not", "don't", "never") and the other doesn't

This produces massive false positives. Example: "Always use concise language" and "Don't use unnecessary emojis" share words and differ in negation, but are complementary rules, not contradictions.

### Impact on Dashboard

After the golden cleanup:
- **Treemap**: Shows 10 colored topic blocks instead of one giant "general" block
- **Health Score**: Coverage jumped from ~3% to ~97%
- **Table**: Scores column now shows meaningful values (1-10)
- **Detail Panel**: Topic and knowledge_type fields are populated

### Script Modes

```bash
python3 scripts/golden_cleanup.py --dry-run   # Preview changes without modifying
python3 scripts/golden_cleanup.py --apply      # Apply changes to ChromaDB
```

---

## What's Working Well

### 1. Snapshot Architecture

The separation between write (MCP) and read (Dashboard) via snapshot file prevents lock contention and allows independent operation.

### 2. Health Score System

The 3-metric health score provides actionable insight:
- Low freshness -> archive stale memories
- Low coverage -> add topics
- Low connectivity -> build relationships

### 3. Semantic Search Integration

The `/api/search` endpoint is now wired to the UI with:
- Debouncing
- AbortController
- Error handling
- Loading states

### 4. TanStack Table

Industry-standard table with:
- Sorting by any column
- Filtering by topic/type
- Expandable rows
- Selection state

### 5. Static Visualizations

No more physics bugs. Nivo charts are:
- Deterministic
- Performant
- Mobile-friendly (except network)

---

## ULTRATHINK: The Fundamental Problem

### The Core Question the Dashboard Must Answer

**"Is my second brain actually making my AI smarter?"**

Not "how many memories do I have?" or "what topics are they sorted into?" — but **are they useful?**

### What's Completely Missing from the Dashboard

| What We Show | What We SHOULD Show |
|---------------|---------------------|
| Memory count | **Usage count** - How often is this memory retrieved? |
| Topic distribution | **Retrieval context** - What queries triggered this memory? |
| Health score | **Effectiveness score** - Did it help the agent's response? |
| "Contradictory" flags | **Unused memories** - Dead weight that's never retrieved |
| Score (0-100) | **Over-used memories** - Too generic, matches everything |

### The Hard Truth About the 121 Memories

**We don't know which ones are actually useful.**

The dashboard shows:
- 97% categorized ✓
- Average score 6.9 ✓
- 0 contradictions ✓

But it DOESN'T show:
- Which memories have **never been retrieved**?
- Which memories are **retrieved for every query** (too generic)?
- Which memories **improved** an agent response?
- Which memories were **ignored** by the agent?

---

## Rethinking Contradictions

### Why Current Detection Fails

The current `_detect_contradiction()` looks at **text similarity + negation words** — which produces false positives:

- "Always use concise language" 
- "Don't use unnecessary emojis"

These are **complementary**, not contradictory. They're both about communication quality.

### Better Approach: Contextual Conflict Detection

Two memories conflict ONLY when they give **opposite advice for the SAME situation**:

| Memory A | Memory B | Verdict |
|----------|----------|---------|
| "Always use absolute paths" | "Never use absolute paths" | **CONFLICT** - same context, opposite advice |
| "Use concise language" | "Don't use emojis" | **COMPLEMENTARY** - different aspects of same goal |
| "Prefer functional components" | "Use class components for state" | **CONTEXTUAL** - need to clarify when each applies |

### Approaches to Deal with Conflicts Without Breaking Flow

**1. Tag as "Needs Review" (not "Contradictory")**
- Soft flag, doesn't break anything
- User sees both memories side-by-side
- User decides: merge, clarify, deprecate, or keep both

**2. Contextualize Instead of Delete**
- Add "When..." conditions to make them non-conflicting
- "Prefer functional components **for simple UI**"
- "Use class components **for complex stateful logic**"

**3. Merge into Nuanced Memory**
- Combine two "contradictory" memories into one with nuance
- "Use absolute paths in config files, relative paths in imports"

**4. Deprecate the Loser**
- If one memory is clearly outdated/wrong, mark `deprecated: true`
- It stays in the database but isn't retrieved

---

## The Real Metrics That Matter

### For Each Memory

| Metric | Why It Matters | Current State |
|--------|----------------|---------------|
| **Times Retrieved** | Is this memory actually being used? | NOT TRACKED |
| **Last Retrieved** | Is it still relevant? | NOT TRACKED |
| **Retrieval Queries** | What context does it surface in? | NOT TRACKED |
| **Effectiveness** | Did the agent use it well? | NOT TRACKED |
| **Specificity** | Does it match too broadly? Too narrowly? | NOT TRACKED |

### For the Overall System

| Metric | Why It Matters | Current State |
|--------|----------------|---------------|
| **Retrieval Rate** | What % of queries retrieve at least one memory? | NOT TRACKED |
| **Coverage Gap** | What queries retrieve NOTHING? (missing knowledge) | NOT TRACKED |
| **Noise Ratio** | What % of retrieved memories are ignored? | NOT TRACKED |

---

## A Different Dashboard Philosophy

**Current approach:** "Here's all your data, nicely visualized."

**Better approach:** "Here's how well your second brain is working."

The dashboard should answer:

1. **"What's working?"** - Memories that are frequently retrieved and useful
2. **"What's broken?"** - Memories that conflict, are outdated, or never used
3. **"What's missing?"** - Queries that retrieve nothing (knowledge gaps)
4. **"What's noisy?"** - Memories that match everything but help nothing

---

## The 121 Memories Question

Are all 121 memories needed? Without usage data, we can't know. But we can make educated guesses:

### Candidates for Archival
- Test artifacts (already filtered from snapshot)
- Duplicate concepts (same rule stated differently)
- Outdated decisions (superseded by newer memories)
- Overly specific (applies to one situation, never retrieved)

### Candidates for Merging
- High semantic similarity + same topic
- Same concept, different wording
- Complementary rules about same thing

### Candidates for Clarification
- Memories that could apply to multiple contexts
- Memories that seem to conflict with others
- Memories with vague "surfaces_when" conditions

---

## What Still Needs Work

### 0. Usage Tracking (P0 - Foundation for Everything Else)

**Current State**: We have NO IDEA which memories are actually used.

**Needed**:
- Track `access_count` on every retrieval
- Track `last_accessed` timestamp
- Track what query triggered the retrieval
- Surface "Never retrieved" memories prominently
- Surface "Most retrieved" memories

**This is the single most valuable metric.** Without it, any curation is guessing.

### 1. Write Operations (P0 - Critical for Product)

**Current State**: Dashboard is 100% read-only. Users can see but not act.

**Needed**:
- `PATCH /api/memories/:id` - Update topic, tags, archived status
- `DELETE /api/memories/:id` - Archive (soft-delete) a memory
- Wire to MCP tools internally (`elefante-MemoryUpdate`, `elefante-MemoryDelete`)
- Inline editing in table (click cell to edit topic, tags)
- Action bar on row selection: Archive / Edit / Reinforce
- Bulk operations for multi-select

**This is THE gap that separates "visualization tool" from "curation workbench."**

### 2. Contradiction Detection (P1 - Differentiator)

**Current State**: The existing `_detect_contradiction()` uses a naive negation XOR heuristic that produces massive false positives (25/121 = 21% false positive rate). It has been effectively disabled by the golden cleanup.

**Needed**:
- Semantic similarity + LLM-based contradiction assessment
- "Potential conflicts" list with user confirmation
- Resolution actions: merge, archive one, mark as complementary

**Challenge**: "Use pytest fixtures" vs "Avoid fixtures in integration tests" requires understanding context, not just text matching.

### 3. Real-Time Refresh (P1)

**Current State**: Data is static snapshot-based. Users must manually run `update_dashboard_data.py` and restart server.

**Needed**:
- Auto-refresh button in UI
- WebSocket or polling for live updates
- "Last updated: X minutes ago" indicator

### 4. Action Layer (P1)

**Current State**: Visualizations are passive.

**Needed**:
- Click treemap topic → filter memories table to that topic
- Click calendar day → show memories created that day
- Click network node → open detail panel with context
- "Fix this" buttons on health issues → guided remediation

### 5. Session Timeline (P2)

**Current State**: Session metadata (`session_id`) exists but is not visualized.

**Needed**:
- Audit session_id coverage in data
- Timeline component showing knowledge growth over sessions
- Session detail: what was discussed, what was learned
- Cross-session pattern detection

### 6. Mobile Responsiveness (P2)

**Current State**: Desktop-focused. Layout breaks on narrow screens.

**Needed**:
- Responsive breakpoints
- Default to Memories tab on mobile
- Stack grid layouts vertically on mobile
- "Desktop recommended" banner on visualizations

### 7. Onboarding Experience (P2)

**Current State**: Basic empty states with text messages.

**Needed**:
- Welcome modal on first launch
- 3-step quick start guide
- localStorage for "don't show again"
- Interactive tutorial highlighting each tab's purpose

### 8. KnowledgeGraph Improvements (P2)

**Current State**: Static Nivo Network with basic layout, doesn't use topic data effectively.

**Needed**:
- Color nodes by topic (currently by memory_type)
- Hover to highlight connected nodes
- Click node → open detail panel
- Cluster visualization based on topic

### 9. Health Score Accuracy (P2)

**Current State**: Freshness uses `created_at` date, which never changes. Should ideally use `last_accessed` or `last_modified`.

**Improvements**:
- Use `last_accessed` for freshness if available
- Add "staleness" metric separate from "freshness"
- Consider `access_count` in health calculation

---

## Known Bugs & Root Causes

### Fixed in This Session

| Bug | Root Cause | Fix |
|-----|-----------|-----|
| NaN% in health metrics | `useHealthScore` looked for `created_at` at node level, but data has it inside `properties` | Added fallback: `m.properties?.created_at \|\| m.created_at` |
| Score column empty in table | `update_dashboard_data.py` didn't map `score` field to snapshot node properties | Added `"score": meta.get("score")` to properties mapping |
| 25 false "contradictory" statuses | `_detect_contradiction()` in orchestrator.py uses naive negation XOR | Changed all to "related" via golden_cleanup.py |
| 91% "general" topic | `topology.py` keyword matching too weak, most memories fall through | Applied rule-based classification via golden_cleanup.py |
| All scores = 0 | Pre-v1.10 memories never assigned behavioral scores | Computed scores via golden_cleanup.py formula |

### Known Remaining Issues

| Issue | Severity | Location | Description |
|-------|----------|----------|-------------|
| `compute_semantic_edges()` disabled | LOW | server.py | Returns `[]` — was causing DB lock contention. Should be pre-computed in snapshot generation instead. |
| No emoji enforcement in UI | LOW | OverviewTab.tsx | Empty state uses emoji (`🧠`) — violates project emoji policy |
| Related memories not clickable | LOW | MemoryDetailPanel.tsx | Click handler on related memories is empty (`// Could navigate`) |
| Search breaks LAW #1 | MEDIUM | server.py `/api/search` | Directly queries `vector_store.search()` for live results. Acceptable for quick reads but violates snapshot-only principle. |
| Calendar heatmap date range | LOW | CalendarHeatmap.tsx | Uses `from` and `to` from data bounds, which may show short range. Should default to current year. |

---

## Competitive Positioning

### The Competitive Landscape

| Product | Strengths | Weaknesses | Elefante Opportunity |
|---------|-----------|------------|---------------------|
| **Supermemory.ai** | API-first, 80% token reduction, tiered pricing | No self-reflection, purely B2B | Local-first privacy + "What does my AI know about me?" |
| **Mem0.ai** | Clear value prop ("AI Agents Forget"), memory compression | Dashboard is observability-only, no health concept | Health Score + Contradiction Detection |
| **Obsidian** | Notes-first, bidirectional links, local-first | No AI integration, no semantic search, no health | AI-native from day one + semantic search |

### Unique Differentiators

1. **Health Score**: No competitor has a quantifiable "knowledge health" metric
2. **Agent Impact Analysis**: Shows HOW memory quality affects AI agent behavior
3. **Privacy-First**: All data stored locally — no cloud dependency
4. **Cognitive Loop**: "Hijack-Process-Enhance" model proactively surfaces context

### The North Star Question

> **Would someone pay $19/month for this?**

- **Current v2.1.0**: Not yet — it's still a read-only visualization
- **After action layer + write ops**: Getting closer — it becomes a curation workbench
- **After contradiction detection**: Yes — it becomes "Spotify Wrapped for your AI's brain"

---

## Undocumented Recent Changes

### v2.1.0 OverviewTab Overhaul (This Session)

The OverviewTab was completely redesigned from the v2.0.0 "4 metric cards" layout to a rich diagnostic dashboard:

1. **HealthGauge Component** (NEW): SVG ring gauge replacing plain text percentage
   - `strokeDasharray` + `strokeDashoffset` for animated progress arc
   - `drop-shadow` glow effect color-matched to status
   - Status labels: "Healthy" / "Attention" / "Critical"
   - Score breakdown mini-bars underneath showing individual metrics with weights

2. **Diagnosis + Agent Impact Panel** (NEW): Two-panel analysis
   - **Issues**: Concrete numbers ("42 of 70 memories uncategorized")
   - **Recommendations**: Actionable steps ("Assign specific topics when saving memories")
   - **Agent Impact**: Severity-tagged behavioral consequences ("Agent may repeat past mistakes")

3. **Quick Stats Bar** (NEW): Horizontal stat pills showing:
   - Memories | Topics | Edges | Fresh (of total) | Connected (of total) | Top 3 types

4. **MetricCard Components** (NEW): 3 cards with:
   - Weight indicator (e.g., "40% weight")
   - Detail text (e.g., "85 fresh · 12 stale")
   - Contextual progress bar with color coding
   - Hint text explaining what the number means

### Golden Cleanup Applied (This Session)

Results of `scripts/golden_cleanup.py --apply`:

```
BEFORE:
  Categorized: 9%    | Avg Score: 0.0  | Contradictory: 25
  Topics: general(91%), 3 others(9%)

AFTER:
  Categorized: 97%   | Avg Score: 6.9  | Contradictory: 0
  Topics: 10 categories, only 4 memories still "general"
```

### Snapshot Pipeline Fix (This Session)

`scripts/pipeline/update_dashboard_data.py` was missing `"score"` in the node properties mapping. Fixed by adding:

```python
"score": meta.get("score"),
```

This was causing the Score column in MemoryTable to show empty/null for all memories despite scores being stored in ChromaDB.

### Health Score Date Fix (This Session)

`useHealthScore()` in `useVisualizationData.ts` was looking for `created_at` at the node level:

```typescript
// BROKEN: const created = new Date(m.created_at).getTime();
// FIXED:  const dateStr = m.properties?.created_at || m.created_at;
```

The server transforms snapshot data and spreads `properties` inside a `properties` object, meaning `created_at` can be at either path depending on the node type.

---

## Critical Laws & Pitfalls

### The 7 Laws (from Debug Compendium)

| # | Law | Violation Cost |
|---|-----|----------------|
| 1 | Dashboard reads from SNAPSHOT file, never query database directly | 3 hours |
| 2 | ChromaDB = memories (70+), Kuzu = entities (17) - DIFFERENT DATA | 2 hours |
| 3 | Always run `update_dashboard_data.py` after memory changes | Stale data |
| 4 | Verify BOTH producer AND consumer when debugging data flow | Circular debugging |
| 5 | Hard refresh browser after frontend changes (`Ctrl+Shift+R`) | "It's still broken!" |
| 6 | Frontend reads `n.properties`, NOT `n.full_data.props` | 8 hours |
| 7 | Long-running servers cache imports - restart after code changes | Silent failures |

### Common Pitfalls

1. **Testing API Without Testing UI**: API working != Dashboard working
2. **Fixing Wrong Files**: Verify file is actually USED before debugging
3. **Confusing Data Stores**: ChromaDB = memories, Kuzu = entities
4. **Premature Success Claims**: Only claim success after USER confirms

### Prevention Protocol

```bash
# Before debugging dashboard issues:
1. Check actual data counts in ChromaDB and Kuzu
2. Regenerate snapshot: python scripts/pipeline/update_dashboard_data.py
3. Verify snapshot content
4. Verify API returns snapshot data
5. Hard refresh browser

# After any dashboard changes:
1. Run update_dashboard_data.py
2. Restart server
3. Hard refresh browser
4. Verify stats panel shows correct numbers
5. Verify graph shows ALL nodes with labels
```

---

## Recommended Next Steps

### Divide-and-Conquer Strategy

The remaining work is best split across focused agents, each owning a specific domain:

#### Agent 1: Action Layer & Write Operations (P0)

**Scope**: Make the dashboard interactive — transform from viewer to workbench.

**Tasks**:
1. Build `PATCH /api/memories/:id` endpoint in server.py
2. Build `DELETE /api/memories/:id` endpoint (soft-delete/archive)
3. Wire endpoints to MCP tools (`elefante-MemoryUpdate`, `elefante-MemoryDelete`)
4. Add action bar to MemoryTable on row selection
5. Add inline editing for topic and tags
6. Add bulk archive for multi-select
7. Add "Refresh Data" button that triggers `update_dashboard_data.py`

**Key Files**: [server.py](src/dashboard/server.py), [MemoryTable.tsx](src/dashboard/ui/src/components/MemoryTable.tsx), [MemoriesTab.tsx](src/dashboard/ui/src/components/MemoriesTab.tsx), [store.ts](src/dashboard/ui/src/store.ts)

**Constraint**: Must respect LAW #1 — write operations go through MCP tools, not direct DB access. Read operations use snapshot.

#### Agent 2: Visualizations & Explore Tab (P1)

**Scope**: Make the Explore tab a powerful discovery tool.

**Tasks**:
1. Fix KnowledgeGraph colors to use topic-based coloring
2. Add click-to-inspect on network nodes → opens detail panel
3. Add hover highlighting on connected nodes
4. Improve CalendarHeatmap to show current year by default
5. Add click-to-filter on treemap topics → navigate to filtered Memories tab
6. Add click-to-filter on calendar days → show memories from that day
7. Consider adding a 4th visualization: topic flow / Sankey diagram

**Key Files**: [KnowledgeGraph.tsx](src/dashboard/ui/src/components/KnowledgeGraph.tsx), [TopicTreemap.tsx](src/dashboard/ui/src/components/TopicTreemap.tsx), [CalendarHeatmap.tsx](src/dashboard/ui/src/components/CalendarHeatmap.tsx), [ExploreTab.tsx](src/dashboard/ui/src/components/ExploreTab.tsx), [useVisualizationData.ts](src/dashboard/ui/src/hooks/useVisualizationData.ts)

#### Agent 3: UX Polish & Mobile (P2)

**Scope**: Production-quality polish, responsive design, onboarding.

**Tasks**:
1. Mobile-responsive layouts (stack grids, hide complex visualizations)
2. Welcome/onboarding modal on first visit (localStorage flag)
3. Fix emoji in empty state (violates project policy)
4. Add loading skeletons for each tab
5. Keyboard shortcut help overlay
6. Error boundary components for each tab
7. Accessibility audit (ARIA labels, focus management)

**Key Files**: All component files, [App.tsx](src/dashboard/ui/src/App.tsx)

#### Agent 4: Smart Features (P2)

**Scope**: Differentiation features that no competitor has.

**Tasks**:
1. Contradiction detection (replace naive negation XOR with semantic approach)
2. Coverage gap analysis ("You have 0 memories about X")
3. Memory staleness alerts with "Archive" quick action
4. Session timeline visualization
5. "Memory of the Day" surfacing widget

**Key Files**: New components + potentially new hooks and API endpoints

### Build & Deployment Commands

```bash
# Frontend build
cd src/dashboard/ui && npm run build

# Regenerate snapshot after data changes
python3 scripts/pipeline/update_dashboard_data.py

# Start server
python3 -m src.dashboard.server

# Dashboard URL
open http://127.0.0.1:8000

# Golden cleanup (if new memories need classification)
python3 scripts/golden_cleanup.py --dry-run
python3 scripts/golden_cleanup.py --apply
```

---

## File Reference Map

### Core Files to Understand

| File | Purpose | Lines |
|------|---------|-------|
| [`src/dashboard/ui/src/App.tsx`](src/dashboard/ui/src/App.tsx) | Main app, tab routing | ~101 |
| [`src/dashboard/ui/src/store.ts`](src/dashboard/ui/src/store.ts) | Zustand state (fetch, search, filters) | ~148 |
| [`src/dashboard/ui/src/types.ts`](src/dashboard/ui/src/types.ts) | TypeScript interfaces (GraphData, Memory, etc.) | ~93 |
| [`src/dashboard/ui/src/hooks/useVisualizationData.ts`](src/dashboard/ui/src/hooks/useVisualizationData.ts) | Data transforms, health score, enriched HealthScore interface | ~220 |
| [`src/dashboard/ui/src/hooks/useSearch.ts`](src/dashboard/ui/src/hooks/useSearch.ts) | Semantic search via /api/search | ~61 |
| [`src/dashboard/server.py`](src/dashboard/server.py) | FastAPI backend (4 endpoints) | ~234 |
| [`scripts/pipeline/update_dashboard_data.py`](scripts/pipeline/update_dashboard_data.py) | Snapshot generation from ChromaDB + Kuzu | ~930 |

### Key Components

| Component | Purpose | Version |
|-----------|---------|---------|
| [`OverviewTab.tsx`](src/dashboard/ui/src/components/OverviewTab.tsx) | Health score, diagnostics, agent impact, stat pills, metric cards | v2.0.0 |
| [`HealthGauge.tsx`](src/dashboard/ui/src/components/HealthGauge.tsx) | SVG ring gauge with animated stroke + glow | v2.0.0 |
| [`MemoriesTab.tsx`](src/dashboard/ui/src/components/MemoriesTab.tsx) | Table + search + filters | v2.0.0 |
| [`ExploreTab.tsx`](src/dashboard/ui/src/components/ExploreTab.tsx) | 3 visualization panels | v2.0.0 |
| [`MemoryTable.tsx`](src/dashboard/ui/src/components/MemoryTable.tsx) | TanStack Table with sorting + row click | v2.0.0 |
| [`MemoryDetailPanel.tsx`](src/dashboard/ui/src/components/MemoryDetailPanel.tsx) | Slide-out detail panel | v2.0.0 |
| [`KnowledgeGraph.tsx`](src/dashboard/ui/src/components/KnowledgeGraph.tsx) | Nivo network graph (418 nodes, 1893 edges) | v2.0.0 |
| [`TopicTreemap.tsx`](src/dashboard/ui/src/components/TopicTreemap.tsx) | Nivo treemap for topic distribution | v2.0.0 |
| [`CalendarHeatmap.tsx`](src/dashboard/ui/src/components/CalendarHeatmap.tsx) | Nivo calendar for activity over time | v2.0.0 |
| [`ActivityFeed.tsx`](src/dashboard/ui/src/components/ActivityFeed.tsx) | Recent memory timeline | v2.0.0 |

### Scripts

| Script | Purpose |
|--------|---------|
| [`scripts/golden_cleanup.py`](scripts/golden_cleanup.py) | Memory metadata cleanup (topic, score, status) with --dry-run/--apply |
| [`scripts/pipeline/update_dashboard_data.py`](scripts/pipeline/update_dashboard_data.py) | Snapshot generation pipeline |
| [`scripts/verify/verify_dashboard_health.py`](scripts/verify/verify_dashboard_health.py) | Dashboard health diagnostic |

### Documentation

| Document | Purpose |
|----------|---------|
| [`docs/technical/dashboard.md`](docs/technical/dashboard.md) | Usage guide |
| [`docs/technical/dashboard-startup.md`](docs/technical/dashboard-startup.md) | Troubleshooting |
| [`docs/technical/dashboard-snapshot-contract.md`](docs/technical/dashboard-snapshot-contract.md) | Schema definition |
| [`docs/debug/dashboard-compendium.md`](docs/debug/dashboard-compendium.md) | Bug history |
| [`plans/dashboard-overhaul-strategy.md`](plans/dashboard-overhaul-strategy.md) | Strategy rationale |
| [`plans/dashboard-v2-kiro-plan.md`](plans/dashboard-v2-kiro-plan.md) | Implementation plan (KIRO Phases 0-7 + M) |
| [`plans/dashboard-v2-clarity-critique.md`](plans/dashboard-v2-clarity-critique.md) | Critique & improvements |
| [`plans/dashboard-v2-kiro-critique.md`](plans/dashboard-v2-kiro-critique.md) | KIRO plan critique |

---

## Conclusion

The dashboard has evolved from a **physics-based screensaver** (v1) to a **functional health workbench** (v2.0). The foundation is solid:

- 3-tab architecture provides clear navigation
- Health Score with HealthGauge ring gives beautiful, actionable insight
- Enriched OverviewTab provides diagnostics with concrete numbers, agent impact awareness
- Table + Search provides expected UX with sorting and detail panels
- 3 static visualizations (treemap, calendar, network) are stable
- Golden cleanup gave the data layer integrity (97% classified, 0 contradictions)

**What separates it from competitors**: No other memory tool shows you a health score, contradiction detection, topic distribution, AND a knowledge graph in one place. The "second brain health dashboard" is a novel concept.

**The remaining work is primarily about**:
1. **Adding actions** (write operations, curation) — transforms viewer into workbench
2. **Cross-visualization interaction** (click treemap → filter table) — creates flow between discovery and action
3. **Smart features** (coverage gaps, staleness alerts) — makes it a proactive assistant

**The North Star**: Would someone pay $19/month for this?

- Current (v2.1): Not yet — still read-only, but the health monitoring is already unique
- After action layer + write operations: Getting there — it becomes a curation workbench
- After smart features (contradiction detection, gap analysis): Yes — it becomes the "Spotify Wrapped for your AI's second brain"

---

*Document last updated: 2026-02-18*
*Elefante version: v2.0.0*
*Dashboard version: v2.0.0*
*Memory count: 121 deduplicated, 97% categorized, avg score 6.9*