# Elefante Development Roadmap

**Current Version**: v1.6.3  
**Last Updated**: 2025-12-30

---

## v1.6.4 PLANNING: Cognitive Hub Dashboard

**Vision**: Transform dashboard from static snapshot viewer into dynamic "Cognitive Hub" with AI-powered insights, temporal awareness, and configurable views.

### Core Pillars

| Pillar | Goal |
|--------|------|
| **Simplicity** | Clean UI, minimal clutter, immediate understanding |
| **Smarts** | AI-driven queries, pattern detection, summaries |
| **Configurability** | Custom views, filters, export options |
| **Impact** | Surface trends, health metrics, actionable insights |

### Feature Matrix

| Feature | Priority | Description |
|---------|----------|-------------|
| Multi-View Layouts | HIGH | Force/hierarchy/timeline graph modes |
| Semantic Search Bar | HIGH | In-dashboard search with instant filtering |
| AI Summaries | HIGH | "Top 3 intent rules", "Rising tasks this week" |
| Temporal Filters | MEDIUM | "Since last week", "Most accessed" |
| Health Metrics | MEDIUM | Duplicate detection, staleness alerts |
| Node Editing | LOW | Preview edits via MCP (with confirmation) |
| Export | LOW | JSON/PNG snapshots |

### Data Enhancements Required

| Field | Storage | Purpose |
|-------|---------|---------|
| `last_accessed` | ChromaDB metadata | Temporal queries, usage ranking |
| `access_count` | ChromaDB metadata | Hot memory detection |
| `confidence` | ChromaDB metadata (0-1) | Reliability weighting |
| `version` | ChromaDB metadata | Change history |
| `edge_weight` | Kuzu property | Usage-based relationship strength |

### AI Agent Workflow (MCP-Driven)

1. **Analyze**: `elefanteGraphQuery` + `elefanteMemorySearch` to map data
2. **Design**: Generate schemas/prototypes via prompts
3. **Implement**: Batch upsert via `elefanteGraphConnect`, build features
4. **Test**: `elefanteSystemStatusGet` for health, `elefanteDashboardOpen` for validation

---

## v1.6.3 SHIPPED (2025-12-30)

**Neural Web Visualization** - Dashboard graph transformed from rigid "Solar System" to organic "Neural Web".

| Feature | Status | Impact |
|---------|--------|--------|
| Linear node sizing |  DONE | Balanced sizes (max 25px vs. 48px) |
| Neural physics |  DONE | Nodes float organically, no ring locks |
| Recency pulse |  DONE | White ring for very recent memories |
| Status borders |  DONE | Green=processed, amber=pending |
| Ring guides disabled |  DONE | Cleaner brain visualization |

---

##  v1.1.0 SHIPPED (2025-12-26)

**Transaction-Scoped Locking** - Fixed multi-IDE deadlock issue where session-based locks blocked access for 12+ days.

| Feature | Status | Impact |
|---------|--------|--------|
| Transaction-scoped locking |  DONE | Per-operation locks (ms) instead of per-session (hours) |
| Stale lock auto-expiry |  DONE | Locks > 30 seconds auto-cleared |
| Dead PID detection |  DONE | Orphaned locks from crashed processes cleared |
| Backward compatibility |  DONE | `enable()`/`disable()` remain safe; semantics evolved after v1.1.0 |

---

##  CRITICAL: Production Testing Findings (2025-12-10)

**Real-world testing revealed fundamental design flaws that MUST be addressed before v1.2.0:**

| Issue | Severity | Impact |
|-------|----------|--------|
| **Response Bloat** | CRITICAL | `elefanteMemorySearch` returns ~500 tokens/memory (90% nulls) - wastes context window |
| **Low Similarity Scores** | HIGH | Exact topic matches score 0.37-0.39 (should be 0.7+) - retrieval broken |
| **No Action Guidance** | HIGH | Raw JSON dump with no summary - agent can't use results effectively |

**Source**: See `docs/debug/memory-compendium.md` Issues #7, #8, #9

**Priority**: These MUST be fixed before any new feature work.

---

## Current State (v1.6.2)

###  Implemented Features
- **Transaction-Scoped Locking** (v1.1.0) - Per-operation locks with auto-expiry
- **Cognitive Memory Model** - Agent-managed enrichment (agent supplies intent/entities/relationships)
- **Temporal Decay** - Memories decay over time, reinforced on access
- **Dual Storage** - ChromaDB (vectors) + Kuzu (graph)
- **MCP Server** - 18 tools for IDE integration (+ 2 prompts)
- **Dashboard** - React/Vite visualization (functional but needs UX work)

###  Recently Added
- **Cognitive Retrieval (V4/V5)** - Composite scoring and retrieval explanations
- **Agent ETL Classification (V5 topology)** - Raw → classified via agent tools

###  Partial Implementation
- **Memory Schema V2** - Schema defined, but 3-level taxonomy (domain/category) defaults only
  - `domain` always defaults to `REFERENCE`
  - `category` always defaults to `general`
  - LLM does NOT auto-classify these fields

---

## Next Phase (TBD)

### Priority 1: Auto-Classification (HIGH)
**Goal**: Agent automatically detects domain/category and passes them into Elefante (Elefante remains LLM-free).

#### 1. Enhanced Agent Extraction
**Goal**: Deeper semantic understanding of memories

**Tasks**:
- [ ] Implement advanced `analyze_memory` function
  - Extract complex relationships (not just entities)
  - Identify temporal patterns (before/after, cause/effect)
  - Detect contradictions with existing memories
  - Extract implicit knowledge (assumptions, implications)

**Technical Approach**:
- Improve agent prompts/workflow for deeper analysis
- Add multi-pass extraction (entities -> relationships -> implications)
- Implement confidence scoring for extracted information

#### 2. Agent Enrichment Contract (No internal LLM)
**Goal**: Make the agent-to-Elefante contract explicit and stable.

**Tasks**:
- [ ] Document the minimal agent-supplied fields that improve storage quality (e.g., `metadata.title`, `metadata.layer`, `metadata.sublayer`, `metadata.domain`, `metadata.category`, `entities`, `relationships`).
- [ ] Ensure Elefante accepts/round-trips these fields deterministically.
- [ ] Keep Elefante runtime free of LLM provider calls; enrichment belongs in the calling agent.

---

### Priority 2: Smart UPDATE (MEDIUM)
**Goal**: Merge new info with existing memories instead of duplicating

**Tasks**:
- [ ] Implement UPDATE action in orchestrator (currently only ADD/IGNORE work)
- [ ] Merge metadata when similarity > 0.85
- [ ] Track version history

**Files to Modify**:
- `src/core/orchestrator.py` - Implement UPDATE branch
- `src/models/memory.py` - Add version tracking

---

### Priority 3: Dashboard UX (MEDIUM)
**Goal**: Make visualization useful, not just "bag of dots"

**Current Problems**:
- No meaningful color coding
- Labels are "salad" at scale
- Connections feel arbitrary

**Tasks**:
- [ ] Implement semantic zoom (hide labels at low zoom)
- [ ] Color by memory type or domain
- [ ] Show only high-importance nodes by default
- [ ] Internal iteration v32: Add a dashboard **Ribbon** (top toolbar)
  - Refresh snapshot + show snapshot source/timestamp
  - Toggles: hide test artifacts, show signal hubs (topic/ring/knowledge_type)

**Files to Modify**:
- `src/dashboard/ui/src/components/GraphCanvas.tsx`

---

## Future Phases

### v1.2.0 - Smart Relationships
- Automatic relationship inference (if A->B and B->C, suggest A->C)
- Knowledge clustering
- Contradiction detection

### v1.3.0 - Multi-Modal
- Image memory support
- Audio transcription integration

---

## Historical Reference

Previous roadmap content archived at: `docs/archive/historical/task-roadmap-completed.md`

---

**Last Updated**: 2025-12-30  
**Status**: Active Development  
**Current Release**: v1.6.3

---

For roadmap and vision, see [`docs/planning/vision.md`](vision.md)