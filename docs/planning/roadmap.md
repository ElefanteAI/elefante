# Elefante Development Roadmap

**Current Version**: v1.5.0  
**Last Updated**: 2025-12-28

---

##  v1.1.0 SHIPPED (2025-12-26)

**Transaction-Scoped Locking** - Fixed multi-IDE deadlock issue where session-based locks blocked access for 12+ days.

| Feature | Status | Impact |
|---------|--------|--------|
| Transaction-scoped locking | ✅ DONE | Per-operation locks (ms) instead of per-session (hours) |
| Stale lock auto-expiry | ✅ DONE | Locks > 30 seconds auto-cleared |
| Dead PID detection | ✅ DONE | Orphaned locks from crashed processes cleared |
| Backward compatibility | ✅ DONE | `enable()`/`disable()` remain safe; semantics evolved after v1.1.0 |

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

## Current State (v1.5.0)

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

**Last Updated**: 2025-12-28  
**Status**: Active Development  
**Current Release**: v1.6.0

---

For roadmap and vision, see [`docs/planning/vision.md`](vision.md)