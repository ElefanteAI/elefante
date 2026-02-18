# Elefante Classification System Analysis

**Date**: 2026-02-18
**Status**: Critical Analysis
**Purpose**: Identify phantom/outdated systems and propose sustainable path forward

---

## Executive Summary

The Elefante codebase contains **FOUR overlapping classification systems** accumulated over multiple development iterations. This analysis identifies what is actively used, what is phantom/deprecated, and proposes a unified approach.

**Key Finding**: The user is correct—keyword-only classification is low quality. The current deterministic approaches cannot understand memory content. The ETL pattern (agent-driven classification) is the right direction but has been implemented as an optional layer rather than the core approach.

---

## Part 1: Current Classification Systems

### System 1: V3 Schema (classifier.py) — DETERMINISTIC

**File**: `src/core/classifier.py`

| Field | Values | Method |
|-------|--------|--------|
| `layer` | self, intent, world | Regex patterns |
| `sublayer` | identity, preference, constraint, rule, goal, anti-pattern, failure, method, fact | Regex patterns |
| `importance` | 1-10 | Content heuristics |

**Status**: ⚠️ PARTIALLY DEPRECATED
- Used for title generation (`generate_title()`)
- Used in refinery for namespace detection
- NOT stored in memory metadata
- **Phantom**: Values computed but discarded

### System 2: V4 Cognitive Schema (memory.py) — DETERMINISTIC

**File**: `src/models/memory.py`, `src/utils/curation.py`

| Field | Values | Method |
|-------|--------|--------|
| `memory_type` | 13 types (conversation, fact, insight, code, decision, task, note, preference, question, answer, hypothesis, observation) | Agent-provided at ingestion |
| `memory_class` | fact, directive, state | Agent-provided at ingestion |
| `domain` | work, personal, learning, project, reference, system | Agent-provided at ingestion |
| `category` | free-form string | Agent-provided at ingestion |
| `concepts` | 3-5 key terms | `extract_concepts()` - keyword frequency |
| `surfaces_when` | query patterns | `infer_surfaces_when()` - pattern matching |
| `authority_score` | 0.0-1.0 | `compute_authority_score()` - formula |
| `score` | 0-100 | Behavioral relevance (system-computed) |

**Status**: ✅ PRODUCTION
- Core schema fields
- Used in retrieval scoring
- Used in MCP tool schemas
- **Problem**: `concepts` and `surfaces_when` are keyword-based, low quality

### System 3: V5 Topology Schema (topology.py + etl.py) — AGENT-DRIVEN

**File**: `src/core/topology.py`, `src/core/etl.py`

| Field | Values | Method |
|-------|--------|--------|
| `ring` | core, domain, topic, leaf | Agent LLM via ETL |
| `knowledge_type` | law, principle, method, decision, insight, preference, fact | Agent LLM via ETL |
| `topic` | coding-standards, communication, workflow, agent-behavior, tools-environment, collaboration, general | Agent LLM via ETL |
| `summary` | one-line essence | Agent LLM via ETL |
| `processing_status` | raw, processing, processed, failed | ETL lifecycle |

**Status**: ⚠️ OPTIONAL LAYER
- Stored in `custom_metadata` (not core schema)
- Requires agent to call ETL tools
- Not enforced at ingestion
- **Problem**: Duplicates V4 dimensions with different values

### System 4: Decay Rates (memory.py) — LOOKUP TABLE

**File**: `src/models/memory.py`

```python
TYPE_DECAY_RATES = {
    "rule": 0.002,          # ~347 days
    "preference": 0.002,    # ~347 days
    "decision": 0.005,      # ~139 days
    "fact": 0.005,          # ~139 days
    ...
}
```

**Status**: ✅ PRODUCTION
- Maps `memory_type` to decay rate
- Core to Behavioral Relevance Model

---

## Part 2: Overlap Analysis

### Dimension Overlap Matrix

| Purpose | V3 (classifier.py) | V4 (memory.py) | V5 (topology.py) |
|---------|-------------------|----------------|------------------|
| **Type Classification** | layer/sublayer (9 combos) | memory_type (13 types) | knowledge_type (7 types) |
| **Subject Area** | implicit | domain (6) + category (free) | topic (7) |
| **Importance/Hierarchy** | importance (1-10) | score (0-100) | ring (4 levels) |
| **Decay Rate** | - | TYPE_DECAY_RATES | - |

### Conflict Examples

1. **memory_type vs knowledge_type**:
   - `memory_type="decision"` → `knowledge_type="decision"` (same)
   - `memory_type="fact"` → `knowledge_type="fact"` (same)
   - `memory_type="insight"` → `knowledge_type="insight"` (same)
   - `memory_type="preference"` → `knowledge_type="preference"` (same)
   - BUT: `memory_type="conversation"` → no V5 equivalent
   - BUT: `memory_type="code"` → no V5 equivalent
   - BUT: `knowledge_type="law"` → no V4 equivalent
   - BUT: `knowledge_type="principle"` → no V4 equivalent
   - BUT: `knowledge_type="method"` → no V4 equivalent

2. **domain vs topic**:
   - `domain="work"` ≠ `topic="workflow"` (different granularity)
   - `domain="project"` ≠ `topic="coding-standards"` (different purpose)
   - Both categorize subject area but with different ontologies

3. **importance vs score vs ring**:
   - `importance` (1-10): V3 heuristic, discarded
   - `score` (0-100): V4 behavioral relevance, system-computed
   - `ring` (core/domain/topic/leaf): V5 hierarchy, agent-assigned
   - Three different systems for "how important is this?"

---

## Part 3: What's Actually Used?

### Actively Used in Code

| Field | Used In | Purpose |
|-------|---------|---------|
| `memory_type` | orchestrator.py, vector_store.py, MCP tools, retrieval.py | Decay rate, filtering, display |
| `memory_class` | orchestrator.py | Contradiction handling |
| `domain` | retrieval.py, MCP tools | Cognitive scoring, filtering |
| `category` | vector_store.py, refinery.py | Filtering, namespace detection |
| `score` | orchestrator.py, retrieval.py | Behavioral relevance |
| `concepts` | retrieval.py, dashboard | Concept-overlap scoring |
| `ring` | dashboard | Topology visualization |
| `knowledge_type` | dashboard | Topology visualization |
| `topic` | dashboard | Topology visualization |

### Phantom/Deprecated

| Field | Status | Evidence |
|-------|--------|----------|
| `layer` | Phantom | Computed in classifier.py but not stored in MemoryMetadata |
| `sublayer` | Phantom | Computed in classifier.py but not stored in MemoryMetadata |
| `importance` | Phantom | Computed in classifier.py but V4 uses `score` instead |
| `processing_status` | Optional | Only used if agent calls ETL tools |

---

## Part 4: The Core Problem

### Why Keyword Classification Fails

The user's intuition is correct. Current deterministic approaches:

1. **`classify_memory()`** (V3): Regex patterns like `\b(NEVER|ALWAYS|MUST)\b` → misses context
2. **`extract_concepts()`** (V4): Word frequency + position → misses semantics
3. **`infer_surfaces_when()`** (V4): Pattern matching → misses intent
4. **`classify_topology()`** (V5): Keyword matching → misses meaning

**Example of Failure**:
```
Content: "The user prefers dark mode but sometimes uses light mode for presentations."

Keyword extraction: ['user', 'prefers', 'dark', 'mode', 'sometimes', 'uses', 'light', 'mode', 'presentations']
→ Redundant, misses the key insight

What agent would extract:
- Core preference: dark mode
- Exception: presentations → light mode
- Context: user has conditional preference
```

### Why ETL Pattern is Right Direction

The ETL pattern (`elefante-ETLProcess` → agent classifies → `elefante-ETLClassify`) correctly delegates understanding to the agent's LLM brain. But:

1. **It's optional**: Memories can exist without V5 fields
2. **It's disconnected**: V5 fields duplicate V4 dimensions
3. **It's not enforced**: No validation that classification happened
4. **It's late**: Classification happens after ingestion, not during

---

## Part 5: Proposed Solution

### Principle: One Classification System, Agent-Driven

**Core Insight**: Elefante is LLM-free by design. The agent has an LLM. Therefore, classification should be:
1. **Agent-driven** (not deterministic keywords)
2. **At ingestion** (not post-hoc ETL)
3. **Unified** (not multiple overlapping systems)

### Proposed Schema: Unified Classification

Replace V3/V4/V5 overlap with a single classification system:

```python
class MemoryClassification(BaseModel):
    """Single unified classification for a memory."""
    
    # WHAT is this? (nature)
    nature: str  # fact | preference | decision | insight | method | rule | conversation
    
    # WHERE does it belong? (context)  
    domain: str   # work | personal | project | learning | reference | system
    topic: str    # free-form, agent-assigned (e.g., "elefante", "python-async", "user-preferences")
    
    # HOW IMPORTANT is it? (hierarchy)
    ring: str     # core | domain | topic | leaf
    
    # WHEN should it surface? (triggers)
    surfaces_when: list[str]  # Agent-generated query patterns
    
    # WHAT is it about? (essence)
    summary: str   # One-line agent-generated summary
    concepts: list[str]  # 3-5 key concepts (agent-extracted)
```

### Key Changes

1. **Merge `memory_type` + `knowledge_type` → `nature`**:
   - 7 values: fact, preference, decision, insight, method, rule, conversation
   - Covers all use cases without overlap

2. **Keep `domain` from V4**:
   - 6 values: work, personal, project, learning, reference, system
   - Well-established, used in retrieval

3. **Free-form `topic`**:
   - Not limited to 7 predefined values
   - Agent assigns based on content understanding
   - Examples: "elefante-architecture", "python-async-patterns", "user-preferences"

4. **Keep `ring` from V5**:
   - 4 values: core, domain, topic, leaf
   - Clear hierarchy for dashboard

5. **Agent-generates `surfaces_when`, `summary`, `concepts`**:
   - Not keyword extraction
   - Agent understands content and generates meaningful values

### Migration Path

1. **Add new fields to MemoryMetadata** (don't remove old ones yet)
2. **Update MCP tool schema** to request agent classification at ingestion
3. **Backfill existing memories** using agent ETL
4. **Deprecate old fields** after validation
5. **Remove phantom code** (classifier.py layer/sublayer)

---

## Part 6: Implementation Considerations

### MCP Tool Change

Current `elefante-MemoryAdd`:
```json
{
  "content": "...",
  "memory_type": "fact",
  "memory_class": "fact",
  "domain": "work",
  "category": "general"
}
```

Proposed `elefante-MemoryAdd`:
```json
{
  "content": "...",
  "classification": {
    "nature": "fact",
    "domain": "work", 
    "topic": "elefante-architecture",
    "ring": "topic",
    "summary": "Elefante uses agent-driven classification",
    "concepts": ["elefante", "classification", "agent-driven"],
    "surfaces_when": ["how does elefante classify", "elefante classification"]
  }
}
```

### Backward Compatibility

- Old fields (`memory_type`, `memory_class`, `category`) remain readable
- New field `classification` is preferred
- Migration script maps old → new

### Decay Rate Mapping

```python
NATURE_DECAY_RATES = {
    "rule": 0.002,        # ~347 days
    "preference": 0.002,  # ~347 days
    "decision": 0.005,    # ~139 days
    "fact": 0.005,        # ~139 days
    "insight": 0.008,     # ~87 days
    "method": 0.008,      # ~87 days
    "conversation": 0.025, # ~28 days
}
```

---

## Part 7: Files to Modify

### Add/Modify

| File | Change |
|------|--------|
| `src/models/memory.py` | Add `MemoryClassification` model, integrate into `MemoryMetadata` |
| `src/mcp/server.py` | Update `elefante-MemoryAdd` schema to request classification |
| `src/core/orchestrator.py` | Use unified classification, remove V3 layer/sublayer calls |
| `src/core/retrieval.py` | Use `nature` instead of `memory_type` |
| `src/utils/curation.py` | Remove `extract_concepts()`, `infer_surfaces_when()` (agent does this now) |

### Deprecate/Remove

| File | Change |
|------|--------|
| `src/core/classifier.py` | Remove `classify_memory()`, `calculate_importance()` (phantom) |
| `src/core/topology.py` | Remove deterministic `classify_topology()` (agent does this now) |
| `src/core/etl.py` | Simplify to just backfill utility |

---

## Part 8: Open Questions

1. **Should `memory_class` (fact/directive/state) be preserved?**
   - It controls contradiction behavior
   - Could be merged into `nature` or kept separate

2. **Should `topic` be free-form or constrained?**
   - Free-form: More flexible, agent-driven
   - Constrained: Easier to filter, but limits expression

3. **How to handle existing memories?**
   - Backfill via agent ETL
   - Or keep old fields readable, new memories use new system

4. **What about the dashboard?**
   - Dashboard currently uses `ring`, `knowledge_type`, `topic`
   - Would need to adapt to `nature`, `ring`, `topic`

---

## Conclusion

The Elefante classification system has accumulated multiple overlapping approaches. The solution is not to add more logic on top, but to:

1. **Unify** into a single classification system
2. **Delegate to agent** for understanding-based classification
3. **Remove phantom code** that computes but doesn't persist
4. **Simplify** the dimension space (nature, domain, topic, ring)

The user's intuition is correct: keyword-only classification is low quality. The agent's LLM brain should be leveraged for classification, not bypassed with deterministic heuristics.
