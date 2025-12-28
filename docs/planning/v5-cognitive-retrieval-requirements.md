# V5 Cognitive Retrieval Requirements

**Status**: REQUIREMENTS (V4 VERIFIED)  
**Date**: 2025-12-27  
**Author**: Jaime + Agent  
**Priority**: P0 (Core Feature)

---

## Executive Summary

Transform Elefante from a **storage system** to a **cognitive retrieval system** that understands meaning, relationships, and context.

---

## Part A: V4 Implementation (VERIFIED ✅)

### A.1 Problem Solved
Memories were stored as raw text. Search only matched words. No understanding of meaning or connections.

### A.2 Delivered Features

| Feature | File | Status |
|---------|------|--------|
| Concept extraction | `src/utils/curation.py` | ✅ Verified |
| Query pattern inference | `src/utils/curation.py` | ✅ Verified |
| Authority scoring | `src/utils/curation.py` | ✅ Verified |
| Cognitive retriever | `src/core/retrieval.py` | ✅ Built (not wired to MCP) |
| Auto-populate on add | `src/core/orchestrator.py` | ✅ Verified |
| SHARES_CONCEPT edges | `scripts/update_dashboard_data.py` | ✅ Verified (24 edges) |
| Migration script | `scripts/migrate_v4_cognitive.py` | ✅ Done |
| Documentation | `docs/technical/memory-schema-v4-cognitive.md` | ✅ Done |

### A.3 New Metadata Fields

```python
# Added to MemoryMetadata in src/models/memory.py
concepts: List[str]           # 3-5 key terms extracted from content
surfaces_when: List[str]      # Query patterns that trigger this memory
authority_score: float        # importance × usage × freshness (0-1)
co_activated_with: List[UUID] # Memories often retrieved together
contradicts: List[UUID]       # Memories with opposing info
supports: List[UUID]          # Memories that reinforce this one
```

### A.4 Verified Results (2025-12-27)

| Metric | Value |
|--------|-------|
| Memories | 25 |
| With concepts | 25/25 (100%) |
| With surfaces_when | 25/25 (100%) |
| With authority_score | 25/25 (100%) |
| SHARES_CONCEPT edges | 24 |
| Total edges | 189 |

### A.5 V4 Debt: CognitiveRetriever Not Wired

**Issue**: `CognitiveRetriever` class exists but `elefanteMemorySearch` still uses raw ChromaDB.

**Impact**: Multi-signal scoring (concept overlap, authority, co-activation) not applied to search results.

**Fix**: Wire `CognitiveRetriever` to `orchestrator.search_memories()` in Phase 0.

---

## Part B: V5 Features (TO BE DEVELOPED)

### B.0 Feature 0: Wire CognitiveRetriever (V4 DEBT)

**Priority**: P0 (BLOCKING)  
**Complexity**: Low  
**Impact**: Critical

#### Requirement
The `CognitiveRetriever` engine must be connected to `elefanteMemorySearch`.

#### Current State
- `CognitiveRetriever` exists in `src/core/retrieval.py`
- `orchestrator.search_memories()` uses raw ChromaDB results
- Multi-signal scoring is computed but not applied

#### Target State
- Search uses `CognitiveRetriever.score_candidate()` for all results
- Results include composite scores from all signals
- Foundation ready for retrieval explanation

#### Files to Modify
- `src/core/orchestrator.py` - Integrate `CognitiveRetriever` into `_search_semantic()`

#### Acceptance Criteria
- [ ] Search results scored by CognitiveRetriever
- [ ] Composite score reflects concept/domain/authority/temporal signals

---

### B.1 Feature 1: Retrieval Explanation

**Priority**: P0  
**Complexity**: Low  
**Impact**: High

#### Requirement
Every search result must include WHY it was retrieved.

#### Specification
```json
{
  "memory_id": "abc-123",
  "score": 0.87,
  "explanation": {
    "vector_similarity": {"score": 0.30, "reason": "Semantic match"},
    "concept_overlap": {"score": 0.20, "matched": ["paths", "elefante"]},
    "domain_match": {"score": 0.15, "reason": "Same project"},
    "authority": {"score": 0.12, "reason": "High importance, frequently used"},
    "temporal": {"score": 0.10, "reason": "Accessed 2 days ago"}
  }
}
```

#### Files to Modify
- `src/core/retrieval.py` - Add explanation to `MemoryCandidate`
- `src/mcp/server.py` - Include explanation in search response

#### Acceptance Criteria
- [ ] Every search result includes breakdown of score components
- [ ] User can see which concepts matched
- [ ] Explanation is human-readable

---

### B.2 Feature 2: Memory Health Score

**Priority**: P0  
**Complexity**: Low  
**Impact**: High

#### Requirement
Every memory has a health indicator showing its current state.

#### Specification
```python
class HealthStatus(Enum):
    HEALTHY = "healthy"      # Recent, verified, frequently used
    STALE = "stale"          # Not accessed in 90+ days
    AT_RISK = "at_risk"      # Contradicted, unverified, or superseded
    ORPHAN = "orphan"        # No connections to other memories

def compute_health(memory) -> HealthStatus:
    if memory.superseded_by_id:
        return AT_RISK
    if memory.contradicts and not resolved:
        return AT_RISK
    if days_since_access > 90:
        return STALE
    if connection_count == 0:
        return ORPHAN
    return HEALTHY
```

#### Dashboard Integration
| Health | Icon | Color | Action |
|--------|------|-------|--------|
| Healthy | 🟢 | Green | None |
| Stale | 🟡 | Yellow | "Review this memory" |
| At Risk | 🔴 | Red | "Resolve conflict" |
| Orphan | ⚪ | Gray | "Connect or archive" |

#### Files to Modify
- `src/utils/curation.py` - Add `compute_health()`
- `scripts/update_dashboard_data.py` - Add health to node properties
- `src/dashboard/ui/src/components/GraphCanvas.tsx` - Render health indicator

#### Acceptance Criteria
- [ ] Every memory has a health status
- [ ] Dashboard shows health visually
- [ ] Unhealthy memories are actionable

---

### B.3 Feature 3: Potential Conflict Detection

**Priority**: P1  
**Complexity**: Medium  
**Impact**: High

#### Requirement
Automatically detect and flag **potential** conflicting memories for user confirmation.

#### Design Principle
Lexical pattern matching (always/never, do/don't) is brittle. Real contradictions are semantic.  
**Flag as "potential conflict" — let user confirm/dismiss. Never auto-assert.**

#### Specification
```python
def detect_potential_conflict(memory_a, memory_b) -> Optional[str]:
    """
    Returns conflict reason if potential conflict, None otherwise.
    
    Two memories MAY conflict if:
    1. High concept overlap (>60%)
    2. Same topic/domain
    3. Either: opposing patterns OR significantly different dates
    
    Returns reason string for user review, not boolean assertion.
    """
    
# Soft patterns (suggest, don't assert)
POTENTIAL_OPPOSING_PATTERNS = [
    ("always", "never"),
    ("do", "don't"),
    ("use", "avoid"),
    ("enable", "disable"),
    ("prefer", "avoid"),
]
```

#### Resolution Flow
1. System detects potential conflict
2. Adds to `potential_conflicts` field (not `contradicts`)
3. Dashboard shows "⚠️ Review conflict?" badge
4. User reviews and resolves: 
   - **Confirm conflict** → move to `contradicts`
   - **Dismiss** → remove flag
   - **Mark exception** → both valid in different contexts

#### Files to Modify
- `src/utils/curation.py` - Add `detect_potential_conflict()`
- `src/core/orchestrator.py` - Check on add, populate `potential_conflicts`
- `scripts/update_dashboard_data.py` - Add POTENTIAL_CONFLICT edges (dashed)
- Dashboard - Add conflict review UI

#### Acceptance Criteria
- [ ] High concept overlap memories flagged for review
- [ ] POTENTIAL_CONFLICT edges visible (distinct from confirmed)
- [ ] User can confirm, dismiss, or mark exception

---

### B.4 Feature 4: Proactive Memory Surfacing

**Priority**: P1  
**Complexity**: Medium  
**Impact**: Very High

#### Requirement
System suggests relevant memories without user searching.

#### Triggers
| Context | Action |
|---------|--------|
| File opened | Surface memories tagged with that file/project |
| Error in terminal | Surface memories matching error pattern |
| Conversation keyword | Surface memories with matching concepts |

#### Specification
```python
async def get_proactive_suggestions(
    context: dict,  # file_path, recent_errors, conversation
    limit: int = 3
) -> List[MemoryCandidate]:
    """
    Analyze context and return most relevant memories.
    Uses surfaces_when field for matching.
    """
```

#### MCP Tool
```json
{
  "name": "elefanteProactiveSuggestions",
  "description": "Get memory suggestions based on current context",
  "parameters": {
    "file_path": "string (optional)",
    "error_message": "string (optional)", 
    "conversation_snippet": "string (optional)"
  }
}
```

#### Files to Modify
- `src/core/retrieval.py` - Add `get_proactive_suggestions()`
- `src/mcp/server.py` - Add new MCP tool
- Agent prompt - Call tool proactively

#### Acceptance Criteria
- [ ] System can suggest memories without explicit search
- [ ] Suggestions based on `surfaces_when` patterns
- [ ] Agent receives suggestions in context

---

### B.5 Feature 5: Signal Hub Enrichment

**Priority**: P1  
**Complexity**: Low  
**Impact**: Medium

#### Requirement
Signal hubs (topic, ring, knowledge_type) have rich cognitive metadata.

#### Current State
```json
{
  "name": "topic: workflow",
  "description": "Contains 4 memories: Kiro Mode...",
  "properties": {
    "signal_type": "topic",
    "value": "workflow"
  }
}
```

#### Target State
```json
{
  "name": "topic: workflow",
  "description": "Contains 4 memories about how you work",
  "properties": {
    "signal_type": "topic",
    "value": "workflow",
    "cognitive_purpose": "How you approach and organize work",
    "retrieval_trigger": "When asked about process, methodology, or how to approach tasks",
    "memory_count": 4,
    "authority_weight": 0.72,
    "sample_concepts": ["spec-driven", "requirements", "process"],
    "health_summary": {"healthy": 3, "stale": 1, "at_risk": 0}
  }
}
```

#### Hub Definitions

**Rings:**
| Ring | Cognitive Purpose | Retrieval Trigger |
|------|-------------------|-------------------|
| `core` | Identity, beliefs, non-negotiables | Always consider |
| `domain` | Broad areas of life/work | When context matches |
| `topic` | Subject clusters | When topic mentioned |
| `leaf` | Individual facts/rules | Specific queries |

**Knowledge Types:**
| Type | Cognitive Purpose | Retrieval Trigger |
|------|-------------------|-------------------|
| `law` | Absolute rules, must follow | Always enforce |
| `principle` | Guiding beliefs | When making decisions |
| `preference` | Personal taste | When customizing |
| `method` | How to do things | When taking action |
| `fact` | Objective truth | When needing data |
| `decision` | Past choices | When facing similar choice |
| `insight` | Learned wisdom | When reflecting |

#### Files to Modify
- `scripts/update_dashboard_data.py` - Enrich hub properties
- `src/dashboard/ui/src/components/GraphCanvas.tsx` - Show rich tooltips

#### Acceptance Criteria
- [ ] Every hub has cognitive_purpose and retrieval_trigger
- [ ] authority_weight computed from connected memories
- [ ] sample_concepts extracted from connected memories
- [ ] health_summary shows cluster health

---

## Part C: Design Principles

### C.1 Knowledge Type Lifecycle

**Principle**: A fact is not "old" the same way a preference is "old."

Different knowledge types have different durability and should be managed accordingly:

| Knowledge Type | Durability | Rationale |
|----------------|------------|-----------|
| `law` | Most durable | Absolute rules that remain valid until explicitly superseded |
| `fact` | Durable | Objective truths that may become outdated over time |
| `method` | Moderate | Procedures that evolve as tools and practices change |
| `preference` | Least durable | Personal tastes that shift frequently |
| `decision` | Context-dependent | Past choices that may need revisiting as circumstances change |
| `insight` | Moderate | Learned wisdom that may deepen or be refined |

This principle affects retrieval priority, health scoring, and review prompts.  
**Implementation details (specific thresholds) to be determined in future phases.**

### C.2 No LLM Constraint

All classification must be deterministic. Keeps it fast, debuggable, and predictable.

### C.3 Soft Detection

Flag potential issues for user review rather than auto-asserting. The system suggests; the user confirms.

---

## Part D: Implementation Plan

### Phase 0: V4 Debt (Before V5)
1. **B.0 Wire CognitiveRetriever** — Foundation for all V5 features

### Phase 1: Low Complexity
2. B.1 Retrieval Explanation — Trivial once CognitiveRetriever wired
3. B.5 Signal Hub Enrichment — Build health_summary infrastructure
4. B.2 Memory Health Score — Uses hub infrastructure

### Phase 2: Medium Complexity  
5. B.3 Potential Conflict Detection — Soft detection, user confirmation
6. B.4 Proactive Memory Surfacing — Highest risk of unused, last

---

## Part E: Success Metrics

| Metric | Current | Target | Notes |
|--------|---------|--------|-------|
| V4 fields populated | 100% | 100% | ✅ Achieved |
| SHARES_CONCEPT edges | 24 | - | ✅ Achieved |
| Search uses multi-signal scoring | No | Yes | Phase 0 |
| Search includes explanation | No | Yes | Phase 1 |
| Potential conflicts flagged | 0 | All detected | Phase 2 |

---

## Part F: Technical Constraints

1. **No LLM calls** - All classification must be deterministic
2. **Backward compatible** - Existing memories must work
3. **Snapshot-first** - Dashboard reads from static JSON
4. **Single-writer** - Kuzu lock constraints remain
5. **Soft detection** - Flag for review, don't auto-assert conflicts

---

## Appendix: File Inventory

### V4 (Verified Working)
- `src/models/memory.py` - V4 fields in MemoryMetadata
- `src/utils/curation.py` - extract_concepts, infer_surfaces_when, compute_authority_score
- `src/core/retrieval.py` - CognitiveRetriever (built, NOT wired)
- `src/core/orchestrator.py` - Auto-populate V4 fields on add
- `scripts/update_dashboard_data.py` - SHARES_CONCEPT edges
- `scripts/migrate_v4_cognitive.py` - Migration script
- `docs/technical/memory-schema-v4-cognitive.md` - Documentation

### To Modify in V5
- `src/core/orchestrator.py` - Wire CognitiveRetriever (Phase 0)
- `src/mcp/server.py` - Include explanation in search response
- `src/dashboard/ui/src/components/GraphCanvas.tsx` - Health indicators, tooltips
- `scripts/update_dashboard_data.py` - Hub enrichment, health, conflict edges
