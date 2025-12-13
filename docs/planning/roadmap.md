# Elefante Development Roadmap

**Current Version**: v1.0.1  
**Last Updated**: 2025-12-13

---

##  CRITICAL: Production Testing Findings (2025-12-10)

**Real-world testing revealed fundamental design flaws that MUST be addressed before v1.1.0:**

| Issue | Severity | Impact |
|-------|----------|--------|
| **Response Bloat** | CRITICAL | `elefanteMemorySearch` returns ~500 tokens/memory (90% nulls) - wastes context window |
| **Low Similarity Scores** | HIGH | Exact topic matches score 0.37-0.39 (should be 0.7+) - retrieval broken |
| **No Action Guidance** | HIGH | Raw JSON dump with no summary - agent can't use results effectively |

**Source**: See `docs/debug/memory/memory-compendium.md` Issues #7, #8, #9

**Priority**: These MUST be fixed before any new feature work.

---

## Current State (v1.0.0)

###  Implemented Features
- **Cognitive Memory Model** - Agent-managed enrichment (agent supplies intent/entities/relationships)
- **Temporal Decay** - Memories decay over time, reinforced on access
- **Dual Storage** - ChromaDB (vectors) + Kuzu (graph)
- **MCP Server** - 15 tools for IDE integration
- **Dashboard** - React/Vite visualization (functional but needs UX work)

###  Partial Implementation
- **Memory Schema V2** - Schema defined, but 3-level taxonomy (domain/category) defaults only
  - `domain` always defaults to `REFERENCE`
  - `category` always defaults to `general`
  - LLM does NOT auto-classify these fields

---

## Next Phase: v1.1.0 - Complete Schema V2

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

**Last Updated**: 2025-12-03  
**Status**: Planning Phase  
**Target Release**: v1.2.0 (TBD)

---

For current development status, see [`docs/debug/general/task-roadmap.md`](docs/debug/general/task-roadmap.md)