# Changelog

All notable changes to Elefante will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.1.1] - 2026-02-19

### Summary

Dashboard field mapping fix — Categories no longer show as "General" and usage counts no longer show as "Never".

### The Problem Solved

Two field name mismatches between ChromaDB storage and dashboard presentation caused all memories to display with wrong metadata:

1. **All topics showed "General"**: The dashboard `topic` field was reading `meta.get("topic")` — a key that does not exist in ChromaDB. The actual field is `category`. This bug existed in two independent code paths: the snapshot builder (`scripts/update_dashboard_data.py`) and the live refresh path (`src/mcp/server.py` `_refresh_dashboard_snapshot()`).
2. **All usage counts showed "Never"**: The `/api/graph` endpoint served snapshot data that lacked `access_count` and `last_accessed` fields, defaulting to zero/null in the UI.

### The Solution

1. **Snapshot builder**: Changed `meta.get("topic")` to `meta.get("category")` in `scripts/update_dashboard_data.py`.
2. **Live refresh path**: Changed `cm.get("topic")` to `mem.metadata.category` in `src/mcp/server.py` `_refresh_dashboard_snapshot()`.
3. **API hydration fallback**: Added server-side hydration in `src/dashboard/server.py` `get_graph()` that fetches live `access_count`, `last_accessed`, and `last_modified` from the vector store when the snapshot lacks them.

### Changes

- **FIX**: `scripts/update_dashboard_data.py` — Read `category` instead of nonexistent `topic` from ChromaDB metadata for dashboard topic derivation.
- **FIX**: `src/mcp/server.py` `_refresh_dashboard_snapshot()` — Read `mem.metadata.category` instead of `cm.get("topic")` for live refresh topic assignment.
- **FIX**: `src/dashboard/server.py` `get_graph()` — Added usage hydration fallback that populates `access_count`, `last_accessed`, `last_modified` from live vector store when snapshot properties lack them.
- **REMOVED**: Deprecated `importance`, `layer`, `sublayer` fields from snapshot builder (removed in schema v4).

---

## [2.1.0] - 2026-02-19

### Summary

Directive System + Behavioral Bootstrap — Always-active behavioral constraints separated from memories, `copilot-instructions.md` formally integrated into the installation process, and the three-key Tool Response Contract documented as first-class architecture.

### The Problem Solved

1. **Behavioral Rules Depended on Retrieval**: Critical rules like "never claim success without user approval" were stored as memories with `surfaces_when` triggers. Keyword-based retrieval is fragile — you cannot enumerate every possible phrasing of a rule that should never be forgotten.
2. **`copilot-instructions.md` Was an Afterthought**: The installer never validated or referenced it. Section 6.1 of installation docs listed it as a "Next Step" rather than a core installation component.
3. **Tool Response Contract Was Undocumented**: The three injected keys (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, `RELEVANT_CONTEXT`) existed in the server code but were only mentioned in internal planning docs — not in any agent-facing or user-facing documentation.

### The Solution

1. **Directive System**: A new `DirectiveStore` class (`src/core/directive_store.py`) stores behavioral constraints in `~/.elefante/data/directives.json`. Directives are injected into every MCP tool response unconditionally — no search, no similarity scores, no keyword matching. They cannot be outcompeted by memories.
2. **Three Directive Tools**: `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove`.
3. **Installation Bootstrap Validation**: `scripts/install.py` Step 4a now validates `copilot-instructions.md` exists. The installer warns with an explicit error if it is missing, explaining the behavioral consequence.
4. **Tool Response Contract Documented**: Both `copilot-instructions.md` and `docs/technical/installation.md` now formally document all three injected keys as a first-class agent-facing contract.

### Changes

- **NEW**: `src/core/directive_store.py` — `DirectiveStore` + `Directive` classes. JSON-backed persistent storage at `~/.elefante/data/directives.json`. Module-level singleton `get_directive_store()`.
- **MODIFIED**: `src/mcp/server.py` — Added `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove` tools. Added `_inject_directives()` and `_handle_directive_*` methods. Updated `_CONTEXT_SKIP_TOOLS`.
- **MODIFIED**: `scripts/install.py` — Added `verify_copilot_instructions()` function and Step 4a to installer flow.
- **MODIFIED**: `.github/copilot-instructions.md` — Added "Tool Response Contract" section documenting all three injected response keys with their sources, scope, and behavioral rules.
- **MODIFIED**: `docs/technical/installation.md` — Replaced "Next Steps / Section 6.1" with "Behavioral Instruction Architecture": Layer 1 (Bootstrap), Tool Response Contract (three keys), Layer 2 (Directives), Layer 3 (Memories), and installation-to-runtime mapping table.
- **MODIFIED**: `docs/technical/usage.md` — Added `elefante-DirectiveAdd`, `elefante-DirectiveList`, `elefante-DirectiveRemove` documentation under new "Directives" section.
- **IMPACT**:
  - **Tool count**: 17 → 20.
  - `copilot-instructions.md` is now validated by the installer (Step 4a) — missing file produces a clear warning.
  - Behavioral rules that must never be forgotten are separated from the memory system entirely.
  - Three-key Tool Response Contract is documented in both the bootstrap file and the installation guide.

---

## [2.0.0] - 2026-02-18

### Summary

Unified V2 Release — Cohesive product vision across MCP, Intelligence Engine, and Dashboard. Memory curation (19 → 13 high-signal memories), dashboard overhaul with functional Explore tab, and version consolidation eliminating the version multiverse.

### The Problem Solved

1. **Version Multiverse**: Components declared different versions (1.10.0, 1.11.0, 2.1.0, 2.3.0) creating confusion about what "Elefante version" meant.
2. **Memory Noise**: 6 of 19 memories were duplicates, generic checklists, or unimplemented design concepts that diluted retrieval quality.
3. **Broken Explore Tab**: The Nivo Network graph was non-functional — wrong data format, missing dependencies, and no useful visualization.
4. **Dashboard as Screensaver**: The dashboard showed data but didn't help users understand their knowledge system's health or find insights.

### The Solution

1. **Single Version (2.0.0)**: Every file — Python package, config, server, docs, dashboard components — now declares v2.0.0. Historical references in code comments are preserved but all "current version" indicators are unified.
2. **Memory Curation**: Deleted 6 noise memories (duplicates of Operating Laws, generic checklists, unimplemented v5 concepts, overly-niche debugging notes). 13 high-signal memories remain.
3. **Explore Tab Rewrite**:
   - **Topics**: Card grid showing memory distribution by topic (replaced broken Nivo Treemap).
   - **Insights**: Score distribution, type breakdown, topic breakdown, and top memories panel (replaced non-functional calendar heatmap).
   - **Graph**: Pure SVG hub-spoke knowledge graph grouped by topic with hover highlighting (replaced broken Nivo Network).
4. **Dashboard as Product**: Overview tab with health score ring gauge, diagnostic panels, agent impact metrics. Memories tab with semantic search and TanStack Table. Explore tab with three functional sub-views.

### Changes

- **MODIFIED**: `src/__init__.py`, `setup.py`, `config.yaml`, `src/mcp/server.py` — Version 2.0.0.
- **MODIFIED**: `src/dashboard/ui/src/components/ExploreTab.tsx` — 3 sub-views: Topics, Insights, Graph.
- **MODIFIED**: `src/dashboard/ui/src/components/CalendarHeatmap.tsx` — Rewritten as Memory Insights panel (score distribution, type/topic breakdown, top memories).
- **MODIFIED**: `src/dashboard/ui/src/components/KnowledgeGraph.tsx` — Rewritten as pure SVG hub-spoke graph (no Nivo dependency). ResizeObserver for responsive sizing.
- **MODIFIED**: `src/dashboard/ui/src/components/TopicTreemap.tsx` — Rewritten as card grid layout.
- **MODIFIED**: `src/dashboard/ui/src/components/OverviewTab.tsx` — Health gauge + diagnosis + agent impact + stat pills + metric cards.
- **MODIFIED**: `src/dashboard/ui/src/components/HealthGauge.tsx` — SVG ring gauge with animated score.
- **MODIFIED**: All dashboard component version comments unified to v2.0.0.
- **MODIFIED**: All documentation files — version references updated to 2.0.0.
- **DELETED**: 6 noise memories from ChromaDB (IDs: 9ae31791, a3db42e5, cc9ca4f3, 247d89cc, 58bdc18c, 1290ec67).
- **IMPACT**:
  - **Breaking Change**: Version jump from 1.11.0 to 2.0.0 reflects product maturity milestone.
  - **Memory Quality**: Retrieval precision improved by removing noise (31% fewer memories, 100% signal).
  - **Dashboard**: All 3 tabs and all Explore sub-views are functional with zero external visualization dependencies (no D3, no Nivo).

---

## [1.11.0] - 2026-02-17

### Summary

Dashboard Overhaul — Complete rewrite of the dashboard from a physics-based "screensaver" to a functional "knowledge workbench" with tabbed navigation, sortable memory table, and static visualizations.

### The Problem Solved

1. **Physics Instability**: The D3 force-directed graph was unstable, causing nodes to "fly away," flicker, or appear as visual duplicates ("two dots" artifact).
2. **Poor Usability**: The dashboard was a visual novelty with no practical utility for memory management.
3. **No Search**: Users could not find specific memories without visually scanning the graph.

### The Solution

1. **Removed Physics Engine**: Eliminated the unstable D3 force simulation entirely. All visualizations are now static.
2. **3-Tab Architecture**:
   - **Overview**: Health score (freshness, coverage, connectivity) + topic treemap.
   - **Memories**: Sortable/filterable table with semantic search integration.
   - **Explore**: Static knowledge graph using Nivo Network.
3. **Zustand State Management**: Centralized state with derived data selectors.
4. **TanStack Table**: Full-featured table with sorting, filtering, and expandable rows.

### Changes

- **NEW**: `src/dashboard/ui/src/types.ts` - TypeScript interfaces for all data structures.
- **NEW**: `src/dashboard/ui/src/store.ts` - Zustand store with 15+ state slices.
- **NEW**: `src/dashboard/ui/src/hooks/useVisualizationData.ts` - Data transformation hooks.
- **NEW**: `src/dashboard/ui/src/hooks/useSearch.ts` - Semantic search hook with abort controller.
- **NEW**: `src/dashboard/ui/src/components/TabNav.tsx` - Tab navigation component.
- **NEW**: `src/dashboard/ui/src/components/HeaderBar.tsx` - Header with stats display.
- **NEW**: `src/dashboard/ui/src/components/OverviewTab.tsx` - Health score + treemap.
- **NEW**: `src/dashboard/ui/src/components/MemoriesTab.tsx` - Memory list with search.
- **NEW**: `src/dashboard/ui/src/components/MemoryTable.tsx` - TanStack Table implementation.
- **NEW**: `src/dashboard/ui/src/components/ExploreTab.tsx` - Knowledge graph tab.
- **NEW**: `src/dashboard/ui/src/components/TopicTreemap.tsx` - Nivo Treemap visualization.
- **NEW**: `src/dashboard/ui/src/components/KnowledgeGraph.tsx` - Nivo Network visualization.
- **MODIFIED**: `src/dashboard/ui/src/App.tsx` - Complete rewrite with tabbed layout.
- **MODIFIED**: `src/dashboard/ui/package.json` - Added dependencies (zustand, @tanstack/react-table, @nivo/*).
- **MODIFIED**: `src/dashboard/ui/vite.config.ts` - Added @ path alias.
- **IMPACT**:
  - **Breaking Change**: Old GraphCanvas.tsx is no longer used (kept for reference).
  - **Performance**: Static visualizations eliminate CPU-intensive physics calculations.
  - **Usability**: Users can now search, sort, and filter memories efficiently.

---

## [1.10.0] - 2026-02-09

### Summary

Behavioral Relevance & Simplified Naming — Importance scores are now system-computed based on usage, not user assignment. All tools renamed to `elefante-PascalCase` for consistency.

### The Problem Solved

1. **Importance Rot**: Users rated everything as "important" (8-10), and old decisions stayed "critical" forever even as they became obsolete.
2. **Cognitive Load**: "Layer/Sublayer" taxonomy was jargon-heavy and confusing.
3. **Naming Inconsistency**: Tool names like `elefanteMemoryAdd` were hard to read and inconsistent with standard MCP practices.

### The Solution

1. **Behavioral Relevance Model**: Removed all user-assigned importance. The system now computes a score (0-100) automatically based on:
   - **Recency**: Exponential decay based on memory type (Rules decay slowly, conversations quickly).
   - **Freshness**: Recently accessed memories get a boost.
   - **Reinforcement**: Frequently accessed memories grow stronger.
2. **Simplified Classification**: Removed `Layer` (self/world/intent) and `Sublayer`. Now using only `MemoryType` (fact, decision, etc.) and `Domain`.
3. **New Naming Convention**: All 17 tools now follow the `elefante-ToolName` format (e.g., `elefante-MemorySearch`, `elefante-GraphConnect`).

### Changes

- **MODIFIED**: `src/models/memory.py`
  - Removed `importance`, `layer`, `sublayer` fields from `MemoryMetadata`.
  - Added `score` (system-computed) and `TYPE_DECAY_RATES`.
  - Implemented `calculate_relevance_score()` using the new formula.
- **MODIFIED**: `src/mcp/server.py`
  - Renamed ALL 17 tools to `elefante-X` convention.
  - Updated dispatch logic and handlers for the new naming.
  - Removed `importance`/`layer`/`sublayer` from `elefante-MemoryAdd` schema.
- **MODIFIED**: `README.md`
  - Complete rewrite to explain Behavioral Relevance and document new tool names.
- **IMPACT**:
  - **Breaking Change**: Old tool names (`elefanteMemoryAdd`) will no longer work. Client configuration must be updated.
  - **Data Compatibility**: v1.10.0 starts fresh (or requires migration of old importance values to score).

---

## [1.9.1] - 2026-02-09

### Summary

Tool Consolidation — 24 tools reduced to 17 with zero feature loss. Every tool earns its seat.

### The Problem Solved

24 MCP tools caused decision fatigue for LLMs (~6,000 tokens of schema per message), maintenance burden (each tool = registration + dispatch + handler + docs), and redundancy (3 graph tools did what 1 already did).

### The Solution

**KILLED (3 tools → 0):**
- `elefanteGraphEntityCreate` — redundant, `GraphConnect` already creates entities
- `elefanteGraphRelationshipCreate` — redundant, `GraphConnect` already creates relationships  
- `elefanteMemoryMigrateToV3` — one-time admin job, moved to scripts/

**MERGED (5 tools → 2):**
- `elefanteSystemEnable` + `elefanteSystemDisable` → **`elefanteSystem`** with `action: "enable" | "disable"`
- `elefanteMemoryListAll` → absorbed into **`elefanteMemorySearch`** with `list_all: true`
- `elefanteTaskDecompose` → absorbed into **`elefanteTaskCreate`** with optional `subtasks: [...]`
- `elefanteETLStatus` → absorbed into **`elefanteETLProcess`** with `include_stats: true`

### Changes

- **MODIFIED**: `src/mcp/server.py`
  - Removed 3 tool registrations, removed 3 dispatch branches
  - Merged 5 tools into 2 via new parameters
  - Updated `_CONTEXT_SKIP_TOOLS`, `GATED_TOOLS`, pitfall injection
  - `_handle_task_create` now handles inline subtask creation
  - `_handle_etl_process` now returns stats when requested
  - `_handle_search_memories` delegates to `_handle_list_all_memories` when `list_all=true`
  - Version bumped to v1.9.1
- **MODIFIED**: `README.md` — tool table consolidated, version bumped
- **UNCHANGED**: All handler implementations preserved (no backend changes)

### Impact

- **Context window**: ~2,000 fewer tokens per message (7 fewer tool schemas)
- **LLM decision quality**: Fewer choices = better picks
- **Backward compatibility**: Old tool names removed — MCP clients must update

---

## [1.9.0] - 2026-02-09

### Summary

Custodial Memory Tools — Elefante gains the ability to amend and forget memories, closing the gap between stored schema fields and runtime operations.

### The Problem Solved

Elefante stored `deprecated`, `archived`, `supersedes_id`, and `superseded_by_id` fields in its schema, but had **zero runtime tools** to use them. The vector store backend (`update_memory`, `delete_memory`) existed but was not exposed as MCP tools. Agents could only create memories — never correct, deprecate, or delete them. This violated the "Amendment" and "Forgetting" custodial duties described in Weaviate's "Limit in the Loop" framework.

### The Solution

1. **`elefanteMemoryUpdate`** — Amend any memory's content (triggers re-embedding), importance, tags, deprecated/archived status, or supersession chain. When `supersedes_id` is set, the old memory automatically gets `superseded_by_id` back-linked.
2. **`elefanteMemoryDelete`** — Permanently remove a memory with a reason (audit trail). Requires prior `elefanteMemorySearch` (compliance gated).
3. **Search-time filtering** — `elefanteMemorySearch` now excludes `deprecated=true` and `archived=true` memories from results, reporting the excluded count separately.

### Changes

- **MODIFIED**: `src/mcp/server.py`
  - Added `elefanteMemoryUpdate` + `elefanteMemoryDelete` tool registrations with full inputSchema
  - Added both to `GATED_TOOLS` compliance gate set (24 → 26 total tool registrations)
  - Added dispatch routing for both tools
  - Added `_handle_update_memory()` and `_handle_delete_memory()` async handlers
  - Modified search handler to filter deprecated/archived memories with `excluded_deprecated` count in response
- **UNCHANGED**: `src/core/vector_store.py` — backend methods already existed, now surfaced via MCP

### Project Cleanup (same release)

- Removed 5 identical duplicate scripts from `scripts/archive/historical/`
- Archived 2 old memory exports, 3 stale data files, and `install.log` to `data/archive/`
- Moved misplaced `test_end_to_end.py` from `scripts/` to `tests/`
- Archived completed `compliance_gate_plan.md` from `planning/` to `docs/archive/historical/`
- Removed empty `planning/` directory

---

## [1.6.3] - 2025-12-30

### Summary

Neural Web Visualization - Dashboard graph transformed from rigid "Solar System" to organic "Neural Web" layout.

### The Problem Solved

v1.6.2's ring-based layout forced memories into concentric orbits. The exponential node sizing (`r = 8 + importance^2 * 0.4`) made high-importance nodes overwhelmingly large. The result was visually cluttered and didn't represent how a "second brain" thinks.

### The Solution

1. **Linear Sizing**: Changed formula to `r = 10 + importance * 1.5` (max 25px vs. 48px)
2. **Neural Physics**: Removed ring gravity and core locking - nodes float organically based on connections
3. **Status Indicators**: Added visual borders for processing status (emerald=processed, amber=pending)
4. **Recency Pulse**: White pulsing ring for very recent memories (heat > 0.9)
5. **Cleaned Render**: Disabled ring guide backgrounds for cleaner brain visualization

### Changes

- **MODIFIED**: `src/dashboard/ui/src/components/GraphCanvas.tsx`
  - Node radius: Linear scaling replaces power law
  - Physics: Core nodes no longer locked (`fx`/`fy` removed)
  - Ring gravity: Disabled (commented out)
  - Ring guides: Disabled (commented out)
  - Added: Recency pulse ring (white, animated)
  - Added: Processing status border (green/amber dashed)

### Visual Impact

Before: Rigid orbits, giant nodes, cluttered labels
After: Organic clusters, balanced sizes, semantic grouping

---

## [1.6.2] - 2025-12-29

### Summary

Cognitive Visual Enablement - Dashboard now displays cognitive fields (concepts, surfaces_when, authority_score) in the memory inspector sidebar.

### The Problem Solved

v1.6.1 ensured cognitive fields are stored and reconstructed correctly, but users couldn't SEE them in the dashboard. The data existed in ChromaDB and the snapshot, but the UI didn't render it.

### The Solution

Updated `src/dashboard/ui/src/components/GraphCanvas.tsx` to display:
- **Concepts**: Clickable cyan chips showing extracted concepts (search on click)
- **Surfaces When**: Purple bullet list showing when memory surfaces
- **Authority Score**: Progress bar (0-1 scale) with color gradient

### Changes

- **MODIFIED**: `GraphCanvas.tsx` - Added Cognitive Fields section after Tags
- **NEW**: JSON array parser for ChromaDB-stored lists
- **NEW**: Visual design matching existing inspector aesthetic

### Visual Output

When clicking a memory node in the dashboard, the sidebar now shows:
```
Cognitive Fields                              v1.6.2
  Concepts: [elefante] [mcp] [law] [protocol]
  Surfaces When:
    • "when user asks about development rules"
    • "on etiquette or protocol questions"
  Authority Score: [=====-----] 0.850
```

---

## [1.6.1] - 2025-12-29

### Summary

Cognitive Field Standardization - Ensured `concepts`, `surfaces_when`, and `authority_score` persist correctly and are available for V4 Cognitive Retrieval scoring.

### The Problem Solved

V4 Cognitive Retrieval uses concept overlap (0.20 weight) for scoring, but:
- Concepts were sometimes stored in inconsistent formats (JSON, repr(), comma-separated)
- Some memories had missing or malformed cognitive fields
- Dashboard snapshot didn't include these fields

### The Solution

1. **Standardized Storage**: All cognitive fields stored as JSON strings in ChromaDB metadata
2. **Migration Script**: `scripts/migrate_cognitive_fields_v161.py` to fix existing memories
3. **Snapshot Update**: `scripts/update_dashboard_data.py` now includes cognitive fields

### Changes

- **NEW**: `scripts/migrate_cognitive_fields_v161.py` - Migrates all memories to v1.6.1 format
- **MODIFIED**: `scripts/update_dashboard_data.py` - Added concepts, surfaces_when, authority_score to node properties
- **MIGRATED**: 34 memories (9 updated, 25 already compliant)

---

## [1.6.0] - 2025-12-28

### Summary

Compliance Gate - Enforced search-before-write to ensure agents retrieve context before storing memories.

### The Problem Solved

Agents using Elefante MCP tools often skip memory retrieval entirely:
- Memories are stored without checking for duplicates
- Context is ignored because search is never called
- No mechanical enforcement existed - only "instructions" which agents drift from

### The Solution

**Server-Side Compliance Gate** in `src/mcp/server.py`:
- Session state tracks whether `elefanteMemorySearch` has been called
- Write operations (`elefanteMemoryAdd`, `elefanteGraphEntityCreate`, `elefanteGraphRelationshipCreate`, `elefanteGraphConnect`) are **BLOCKED** if no prior search
- Search handler sets `search_performed=True` and returns a compliance stamp
- Gate resets on session end

**Layered Defense** via `.github/copilot-instructions.md`:
- Injected into every GitHub Copilot request in this repository
- Documents the mandatory search-first protocol
- Defines the compliance stamp format

### Compliance Stamp Format

```
[ELEFANTE] Searched: Found {N} relevant memories
[ELEFANTE] Searched: No relevant memories found
```

### Changes

- **NEW**: `_compliance_state` dict in ElefanteMCPServer (`search_performed`, `search_count`, `search_timestamp`, `last_query`)
- **NEW**: `_check_compliance_gate()` method - returns error if search not performed
- **NEW**: `_reset_compliance_gate()` method - resets session state
- **MODIFIED**: `_handle_search_memories` - sets compliance flag and adds stamp to response
- **MODIFIED**: `_handle_add_memory` - gate check before write
- **MODIFIED**: `_handle_create_entity` - gate check before write
- **MODIFIED**: `_handle_create_relationship` - gate check before write  
- **MODIFIED**: `_handle_set_elefante_connection` - gate check before write
- **NEW**: `.github/copilot-instructions.md` - Copilot-injected protocol instructions

### Gated Tools

| Tool | Gate Enforced |
|------|---------------|
| `elefanteMemoryAdd` |  Yes |
| `elefanteGraphEntityCreate` |  Yes |
| `elefanteGraphRelationshipCreate` |  Yes |
| `elefanteGraphConnect` |  Yes |
| `elefanteMemorySearch` |  No (this unlocks the gate) |
| `elefanteContextGet` |  No (read-only) |
| `elefanteGraphQuery` |  No (read-only) |

### Error Response (Gate Blocked)

```json
{
  "success": false,
  "error": " COMPLIANCE GATE: Search required before write operations.",
  "gate_status": "BLOCKED",
  "action_required": "Call elefanteMemorySearch first to check for existing/related memories.",
  "reason": "This prevents duplicate memories and ensures you have full context before adding new knowledge."
}
```

---

## [1.5.0] - 2025-12-28

### Summary

V5 Cognitive Features - Retrieval Explanation, Memory Health, Conflict Detection, Proactive Surfacing.

### The Problem Solved

V4 returns cognitive scores but doesn't explain WHY. Users can't audit the system:
- Why did this memory rank higher than another?
- Which memories are stale or orphaned?
- Are any memories contradicting each other?
- What should surface proactively based on context?

### The Solution

4 new features via 2 consolidated components:

**CognitiveRetriever Extensions** (`src/core/retrieval.py`):
- `RetrievalExplanation` - Full breakdown of 6 signals with reasons
- `ProactiveSurfacer` - Suggests memories based on temporal/domain/concept triggers

**MemoryHealthAnalyzer** (`src/utils/curation.py`):
- `compute_health()` - 4 states:  healthy,  stale,  at_risk,  orphan
- `detect_potential_conflict()` - Flags same-domain memories with 60%+ concept overlap

### Property-Based Testing

8 properties verified with Hypothesis (700+ test iterations):
- P1: Explanation completeness (6 signals always present)
- P2: Explanation accuracy (matched concepts correct)
- P3: Health exhaustiveness (exactly 4 states)
- P4: Health determinism (same inputs → same output)
- P5: Conflict symmetry (conflict(a,b) ⇔ conflict(b,a))
- P6: Threshold monotonicity (higher threshold → fewer conflicts)
- P7: Trigger types (exactly 3: temporal, domain, recurring_concept)
- P8: Confidence bounds (always 0.0-1.0)

### Changes

- **NEW**: `RetrievalExplanation` dataclass in retrieval.py
- **NEW**: `ProactiveSuggestion` + `ProactiveSurfacer` in retrieval.py
- **NEW**: `HealthStatus`, `HealthReport`, `ConflictReport`, `MemoryHealthAnalyzer` in curation.py
- **MODIFIED**: `score_candidate()` now returns `(candidate, explanation)` tuple
- **MODIFIED**: Orchestrator attaches explanations to SearchResult
- **NEW**: tests/test_v5_explanation.py (7 tests)
- **NEW**: tests/test_v5_health.py (14 tests)
- **NEW**: tests/test_v5_proactive.py (14 tests)

---

## [1.4.0] - 2025-12-27

### Summary

V4 Cognitive Retrieval Engine - 6-signal composite scoring replaces raw vector similarity.

### The Problem Solved

Raw vector similarity alone is naive. A memory can be semantically similar but:
- Temporally stale (hasn't been accessed in months)
- Low authority (user never reinforced it)
- Disconnected (no graph relationships)

### The Solution

`CognitiveRetriever` in `src/core/retrieval.py` applies 6 weighted signals:

| Signal | Weight | Source |
|--------|--------|--------|
| Vector Similarity | 0.35 | ChromaDB cosine distance |
| Concept Match | 0.15 | Keyword/concept overlap |
| Domain Alignment | 0.10 | Domain field match |
| Coactivation | 0.15 | Graph relationship density |
| Authority | 0.15 | Reinforcement history |
| Temporal Recency | 0.10 | Decay-adjusted freshness |

### Verified Results

- Composite scores differ from vector scores by -0.32 to -0.45
- High-authority, recently-accessed memories rank higher
- Graph-connected memories get coactivation boost

### Changes

- **NEW**: `src/core/retrieval.py` - CognitiveRetriever class
- **MODIFIED**: `src/core/orchestrator.py` - Wired `_apply_cognitive_scoring()`
- **CLEANUP**: Archived 40+ one-off scripts to `scripts/archive/historical/`
- **CLEANUP**: Removed 26 old data exports from `data/`

---

## [1.3.0] - 2025-12-27

### Summary

Embedding model upgrade to `thenlper/gte-base` (768-dim) for improved semantic search quality.

### The Problem Solved

The previous embedding model (`all-MiniLM-L6-v2`, 384-dim) had lower semantic precision:
- Fuzzy queries often missed relevant memories
- Similar concepts had weak similarity scores
- Edge cases (version numbers, acronyms) performed poorly

### The Solution

Rigorous benchmarking of 10 embedding models (1485 queries) identified `thenlper/gte-base` as the optimal choice:

| Model | Dimensions | MRR | Hit@5 | Latency |
|-------|------------|-----|-------|---------|
| **thenlper/gte-base** | 768 | **0.337** | 49.8% | ~15ms |
| all-MiniLM-L6-v2 | 384 | 0.310 | 45.2% | ~8ms |
| BAAI/bge-base-en-v1.5 | 768 | 0.328 | 48.1% | ~14ms |

Live testing (35 queries, 24 memories) confirmed:
- **Global Avg Similarity: 0.803** (excellent)
- **Hit Rate: 100%** (all queries returned relevant results)
- **Fuzzy query handling**: "remember that thing about the database lock" → 0.845 similarity

### Changes

#### Configuration Updates
- **`config.yaml`**: `embedding_model: "thenlper/gte-base"`, `embedding_dimension: 768`
- **`src/utils/config.py`**: Updated `VectorStoreConfig` and `EmbeddingsConfig` defaults
- **`.env.example`**: Updated example value
- **`docs/technical/architecture.md`**: Model reference updated

#### Migration Script
- **`scripts/migrate_embeddings_gte_base.py`**: Re-embeds all memories with new model
  - Creates timestamped backup before migration
  - Batch processing with progress indication
  - Verification of count match

#### Documentation Fixes (Ghost Links)
During workspace audit, discovered v2 schema files were archived Dec 11 but documentation still linked to them:
- **`docs/README.md`**: v2 schema → v3/v4/v5 references
- **`docs/technical/README.md`**: Removed dead v2 links
- **`docs/debug/memory-neural-register.md`**: v2 → v3
- **`docs/technical/temporal-memory-decay.md`**: v2 → v3

#### Safeguards Added
- **`docs/pitfall-index.md`**: Added Documentation category with "archive without index update" pitfall
- **`docs/technical/developer-etiquette.md`**: Added LAW 6.5 (mandatory grep-before-archive rule)

#### Test Tooling
- **`scripts/test_embedding_battery.py`**: 35-query test battery across 8 categories
  - Identity, Preferences, Project, Technical, Decisions, Workflow, Fuzzy, Edge

### Migration

**BREAKING**: Existing ChromaDB databases have 384-dim embeddings incompatible with new 768-dim model.

To migrate:
```bash
PYTHONPATH=. .venv/bin/python scripts/migrate_embeddings_gte_base.py
```

The script:
1. Creates backup: `memories_backup_YYYYMMDD_HHMMSS`
2. Re-embeds all memories with `gte-base`
3. Verifies count match

To delete backup after verification:
```bash
python -c "import chromadb; c=chromadb.PersistentClient('~/.elefante/data/chroma'); c.delete_collection('memories_backup_...')"
```

---

## [1.2.0] - 2025-12-27

### Summary

Minor fixes and preparation work for schema/migration operations, plus embedding model benchmarking.

This release focused on reducing migration risk by validating candidate embedding models before shipping an embedding change.

### What Changed

- **Preparation for schema and migration flows** (stability work before larger changes)
- **Embedding model benchmarking** across multiple candidates using repeatable test queries
- **Decision milestone**: `thenlper/gte-base` (768-dim) selected as the best option to ship next

### Notes

- The embedding model upgrade itself is documented in **v1.3.0**.

---

## [Unreleased]

_No unreleased changes._

---

## [1.1.0] - 2025-12-26

### Summary

Transaction-scoped locking for true multi-IDE safety. Fixes the fundamental lock deadlock problem where stale locks from crashed/closed IDEs would block other instances indefinitely.

### The Problem Solved

v1.0.1 used **session-based locking**:
- `elefanteSystemEnable` acquired locks → held indefinitely
- `elefanteSystemDisable` released locks only on explicit call
- Crashed processes left stale locks forever (e.g., PID 4563 from Dec 14 blocking all access on Dec 26)
- Multiple IDEs could never interleave operations

### The Solution

v1.1.0 uses **transaction-scoped locking**:
- Each write operation acquires lock → does work → releases lock (milliseconds)
- Read operations are lock-free
- Stale locks auto-expire after 30 seconds
- Multiple IDEs can interleave operations safely

### Changes

#### Transaction-Scoped Locking (`src/utils/elefante_mode.py`)
- **NEW**: `TransactionLock` class - short-lived, auto-releasing locks
- **NEW**: `write_lock()` context manager for write operations
- **NEW**: `read_lock()` context manager (no-op - reads are lock-free)
- **NEW**: Stale lock detection (dead PID or timeout > 30s)
- **CHANGED**: `is_enabled` always returns `True` (no more enable/disable ceremony)
- **CHANGED**: `enable()`/`disable()` are now no-ops for backward compatibility
- **REMOVED**: Session-based lock files (`chroma.lock`, `kuzu.lock`)
- **ADDED**: Single `write.lock` file with PID/timestamp tracking

#### MCP Server Updates (`src/mcp/server.py`)
- **CHANGED**: Write operations wrapped in `write_lock()`:
  - `_handle_add_memory`
  - `_handle_create_entity`
  - `_handle_create_relationship`
  - `_handle_consolidate_memories`
  - `_handle_set_elefante_connection`
  - `_handle_etl_classify`
  - `_handle_migrate_memories_v3`
- **REMOVED**: Blocking mode check that returned "disabled" response
- **ADDED**: Graceful retry response when lock unavailable

### Migration

No migration needed. v1.1.0 is backward compatible:
- `elefanteSystemEnable` still works (now a no-op that returns success)
- `elefanteSystemDisable` still works (clears resources)
- All existing tool calls work unchanged

### Versioning Logic

Elefante follows [Semantic Versioning](https://semver.org/):
- **MAJOR** (x.0.0): Breaking changes requiring user action
- **MINOR** (1.x.0): New features, backward compatible
- **PATCH** (1.0.x): Bug fixes, documentation

This release is **1.1.0** (minor) because:
- New feature (transaction-scoped locking)
- Backward compatible (existing tools work unchanged)
- No user migration required

---

## [1.0.1] - 2025-12-11

### Summary

Critical update addressing protocol enforcement and multi-IDE safety.

### Changes

#### Auto-Inject Pitfalls (Protocol Enforcement)
- MCP Server now injects mandatory protocols (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`) directly into every tool response
- Context-Aware Warnings for `addMemory` (integrity), `searchMemories` (bias), and graph tools (consistency)
- Updated `ai-behavior-compendium.md` with Issue #6 (Passive Protocol Enforcement Failure)

#### ELEFANTE_MODE (Multi-IDE Safety)
- **Problem**: Multiple IDEs accessing same databases caused crashes/lock conflicts
- **Solution**: Server starts OFF by default, user must explicitly enable

##### New MCP Tools
- `elefanteSystemEnable` - Acquires exclusive locks, enables memory operations
- `elefanteSystemDisable` - Releases locks, cleans up, returns to OFF state
- `elefanteSystemStatusGet` - Shows current mode, lock status, holder info (and stats when enabled)

##### New Files
- `src/utils/elefante_mode.py` - Lock management singleton
- `config.yaml` -> `elefante_mode:` section added

##### Behavior
- When **OFF**: Memory tools return graceful "disabled" response with instructions
- When **ON**: Full functionality with exclusive database access
- Lock files stored in `~/.elefante/locks/` with PID/timestamp tracking
- Safe tools (`elefanteSystemEnable`, `elefanteSystemDisable`, `elefanteSystemStatusGet`, `elefanteDashboardOpen`) always available

##### Usage
```
User: "Enable Elefante"
Agent calls: elefanteSystemEnable -> Acquires locks -> Memory tools now work

User: "Disable Elefante" (before switching IDEs)
Agent calls: elefanteSystemDisable -> Releases locks -> Safe for other IDE
```

---

## [1.0.0] - 2025-12-05

### Summary
First stable production release with comprehensive documentation cleanup.

### Core Features
- **Triple-Layer Memory Architecture**
  - ChromaDB for semantic/vector search
  - Kuzu for knowledge graph relationships
  - Session context for conversation continuity

- **MCP Server with 15 Tools**
  - `addMemory` - Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY)
  - `searchMemories` - Hybrid search (semantic + structured + context)
  - `queryGraph` - Execute Cypher queries on knowledge graph
  - `getContext` - Retrieve comprehensive session context
  - `createEntity` - Create nodes in knowledge graph
  - `createRelationship` - Link entities with relationships
  - `getEpisodes` - Browse past sessions with summaries
  - `getSystemStatus` - Mode + lock info + (when enabled) system stats
  - `consolidateMemories` - Merge duplicates & resolve contradictions
  - `listAllMemories` - Export/inspect all memories
  - `getElefanteDashboard` - Launch visual Knowledge Garden UI (optionally refresh)
  - `setElefanteConnection` - Upsert entities + create relationships in one call
  - `migrateMemoriesV3` - Admin schema migration to V3

- **Cognitive Memory Model**
  - Agent-managed enrichment of emotions, intent, entities, relationships (no internal LLM calls)
  - Strategic insight generation
  - ADD/UPDATE/IGNORE action logic

- **Temporal Memory Decay**
  - Memories decay over time
  - Reinforced on access
  - Configurable decay rate

- **Visual Dashboard**
  - React/Vite frontend at http://127.0.0.1:8000
  - Force-directed graph visualization
  - Node inspector with full details

- **Automated Installation**
  - Pre-flight checks for common issues
  - Kuzu 0.11+ compatibility handling
  - IDE auto-configuration (VS Code, Cursor)

### Documentation
- Neural Register architecture (5 master registers)
- Domain compendiums for issue tracking
- Technical reference documentation
- Planning roadmaps

### Known Limitations
- Memory Schema V2 taxonomy (domain/category) requires manual input - auto-classification planned for v1.1.0
- Dashboard UX needs improvement - semantic zoom planned
- Smart UPDATE (merge) not yet implemented

---

## Pre-1.0 Development History

Development prior to v1.0.0 used inflated version numbers during rapid iteration.
These have been consolidated into this baseline release.

| Date | Internal Label | What Happened |
|------|----------------|---------------|
| 2025-11-27 | "v1.1.0" | Initial repository setup |
| 2025-12-02 | "v1.2.0" | User profile integration |
| 2025-12-04 | "v1.2.0" | Kuzu reserved word fix (`properties` -> `props`) |
| 2025-12-05 | "v1.3.0" | Documentation cleanup |
| 2025-12-06 | **v1.0.0** | Official baseline release |

---

## Migration Notes

### From Pre-1.0 Development
If upgrading from internal development versions:
1. Database schema changed (`properties` -> `props`)
2. Run `python scripts/init_databases.py` to reinitialize
3. Documentation restructured into `technical/`, `debug/`, `planning/`, `archive/`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.