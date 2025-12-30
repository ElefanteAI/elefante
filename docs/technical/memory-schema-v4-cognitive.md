# V4 Cognitive Retrieval Schema

**Status**: IMPLEMENTED  
**Date**: 2025-12-27  
**Supersedes**: V3 taxonomy (layer/sublayer still valid, this adds retrieval intelligence)

---

## Overview

V4 adds **cognitive retrieval fields** to make memories discoverable not just by content similarity, but by:
- **Shared concepts** (keywords)
- **Query patterns** (when should this surface?)
- **Authority** (importance × usage × freshness)
- **Relationships** (supports/contradicts other memories)

---

## New Metadata Fields

| Field | Type | Purpose | Auto-populated |
|-------|------|---------|----------------|
| `concepts` | `string[]` | 3-5 key terms extracted from content |  Yes |
| `surfaces_when` | `string[]` | Query patterns that should trigger this memory |  Yes |
| `authority_score` | `float` | Composite score (0-1) for ranking |  Yes |
| `co_activated_with` | `uuid[]` | Memories often retrieved together |  Runtime |
| `contradicts` | `uuid[]` | Memories with opposing information |  Runtime |
| `supports` | `uuid[]` | Memories that reinforce this one |  Runtime |

---

## Concept Extraction

**File**: `src/utils/curation.py` → `extract_concepts()`

Deterministic keyword extraction (no LLM):
- Removes stop words
- Boosts technical terms (python, docker, elefante, etc.)
- Weights by position (early words score higher)
- Returns top 5 concepts

**Example**:
```python
content = "Always use absolute paths in Elefante to avoid errors"
concepts = extract_concepts(content)
# → ['elefante', 'always', 'absolute', 'paths', 'avoid']
```

---

## Surfaces When

**File**: `src/utils/curation.py` → `infer_surfaces_when()`

Generates query patterns that should surface this memory:

| Content Pattern | Generated Triggers |
|-----------------|-------------------|
| "how to", "why" | Question patterns |
| "error", "fix", "bug" | `{concept} error`, `{concept} problem` |
| "always", "never", "must" | `{concept} best practice`, `how to {concept}` |
| "config", "setup" | `{concept} setup`, `{concept} configuration` |

**Example**:
```python
surfaces_when = infer_surfaces_when(content, concepts)
# → ['elefante error', 'elefante problem', 'elefante best practice', ...]
```

---

## Authority Score

**File**: `src/utils/curation.py` → `compute_authority_score()`

Composite score for retrieval ranking:

```python
authority = (
    0.35 × (importance / 10) +        # User-assigned importance
    0.25 × log(access_count) / log(50) +  # Usage frequency
    0.20 × exp(-0.007 × days_since_created) +  # Creation freshness
    0.20 × exp(-0.05 × days_since_accessed)    # Access recency
)
```

---

## Dashboard Edges

V4 adds **SHARES_CONCEPT** edges to the dashboard:

| Edge Type | Meaning |
|-----------|---------|
| `SHARES_CONCEPT` | Two memories share at least one concept |
| `CO_TOPIC` | Share same topic (existing) |
| `CO_RING` | Share same ring (existing) |
| `CO_KNOWLEDGE_TYPE` | Share same knowledge type (existing) |

---

## Cognitive Retriever

**File**: `src/core/retrieval.py`

Multi-signal scoring for search:

```python
composite_score = (
    0.30 × vector_similarity +    # Semantic match
    0.20 × concept_overlap +      # Shared keywords
    0.15 × domain_match +         # Same project/context
    0.15 × co_activation +        # Often retrieved together
    0.10 × authority_score +      # Importance/usage
    0.10 × temporal_relevance     # Freshness
)
```

### Memory Constellation

Search returns structured results, not flat lists:

```json
{
  "primary": {"id": "...", "score": 0.87, "role": "direct_answer"},
  "supporting": [{"id": "...", "role": "context"}],
  "contradicting": [{"id": "...", "role": "exception"}],
  "synthesis": "Primary: X | Supported by: Y | Note: Conflicting info in Z"
}
```

---

## Ingestion Pipeline

When `add_memory()` is called:

1. **Extract concepts** → `extract_concepts(content)`
2. **Infer triggers** → `infer_surfaces_when(content, concepts)`
3. **Compute authority** → `compute_authority_score(...)`
4. **Store in ChromaDB** → All fields in metadata
5. **Create graph edges** → Entity + relationships

---

## Migration

**Script**: `scripts/migrate_v4_cognitive.py`

Backfills existing memories with V4 fields:

```bash
python scripts/migrate_v4_cognitive.py
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/models/memory.py` | Added 6 new fields to `MemoryMetadata` |
| `src/utils/curation.py` | Added `extract_concepts()`, `infer_surfaces_when()`, `compute_authority_score()` |
| `src/core/retrieval.py` | New file: `CognitiveRetriever`, `MemoryConstellation` |
| `src/core/orchestrator.py` | Auto-populate V4 fields on add |
| `scripts/update_dashboard_data.py` | Added SHARES_CONCEPT edges |
| `scripts/migrate_v4_cognitive.py` | New migration script |

---

## Example

```python
# Adding a memory
await orchestrator.add_memory(
    content="When debugging path errors, use absolute paths",
    memory_type="decision",
    importance=8
)

# Result:
# title: "intent.rule: When debugging path errors..."
# concepts: ['debugging', 'path', 'errors', 'absolute', 'paths']
# surfaces_when: ['debugging error', 'path error', 'debugging best practice', ...]
# authority_score: 0.724
```
