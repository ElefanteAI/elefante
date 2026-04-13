# V4 Cognitive Retrieval Schema

**Status**: PRODUCTION  
**Date**: 2026-02-16

---

## Overview

V4 adds **cognitive retrieval fields** to make memories discoverable not just by content similarity, but by:

- **Shared concepts** (keywords)
- **Query patterns** (when should this surface?)
- **Authority** (relevance x usage x freshness)

---

## New Metadata Fields

| Field             | Type       | Purpose                                        | Auto-populated |
| ----------------- | ---------- | ---------------------------------------------- | -------------- |
| `concepts`        | `string[]` | 3-5 key terms extracted from content           | Yes            |
| `surfaces_when`   | `string[]` | Query patterns that should trigger this memory | Yes            |
| `authority_score` | `float`    | Composite score (0-1) for ranking              | Yes            |

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

| Content Pattern           | Generated Triggers                            |
| ------------------------- | --------------------------------------------- |
| "how to", "why"           | Question patterns                             |
| "error", "fix", "bug"     | `{concept} error`, `{concept} problem`        |
| "always", "never", "must" | `{concept} best practice`, `how to {concept}` |
| "config", "setup"         | `{concept} setup`, `{concept} configuration`  |

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
    0.35 × (relevance_score / 100) +     # System-computed behavioral relevance
    0.25 × log(access_count) / log(50) +  # Usage frequency
    0.20 × exp(-0.007 × days_since_created) +  # Creation freshness
    0.20 × exp(-0.05 × days_since_accessed)    # Access recency
)
```

---

## Dashboard Edges

V4 adds **SHARES_CONCEPT** edges to the dashboard:

| Edge Type           | Meaning                                 |
| ------------------- | --------------------------------------- |
| `SHARES_CONCEPT`    | Two memories share at least one concept |
| `CO_TOPIC`          | Share same topic (existing)             |
| `CO_RING`           | Share same ring (existing)              |
| `CO_KNOWLEDGE_TYPE` | Share same knowledge type (existing)    |

---

## Cognitive Retriever

**File**: `src/core/retrieval.py`

Multi-signal scoring for search (wired into `orchestrator.search_memories()`):

```python
composite_score = (
    0.30 × vector_similarity +    # Semantic match
    0.20 × concept_overlap +      # Shared keywords
    0.15 × domain_match +         # Same project/context
    0.15 × co_activation +        # Often retrieved together
    0.10 × authority_score +      # Authority/usage
    0.10 × temporal_relevance     # Freshness
)

# Smoothed Vector Baseline Limit (Issue #8 Fix)
# Prevents valid semantic matches from being mathematically suppressed by missing heuristics
vector_baseline = vector_similarity * 0.85
if composite_score < vector_baseline:
    composite_score = vector_baseline
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

## Files Modified

| File                               | Changes                                                                          |
| ---------------------------------- | -------------------------------------------------------------------------------- |
| `src/models/memory.py`             | Added 6 new fields to `MemoryMetadata`                                           |
| `src/utils/curation.py`            | Added `extract_concepts()`, `infer_surfaces_when()`, `compute_authority_score()` |
| `src/core/retrieval.py`            | `CognitiveRetriever` (wired in orchestrator)                                     |
| `src/core/orchestrator.py`         | Auto-populate V4 fields on add                                                   |
| `scripts/pipeline/update_dashboard_data.py` | Added SHARES_CONCEPT edges                                                       |

---

## Example

```python
# Adding a memory
await orchestrator.add_memory(
    content="When debugging path errors, use absolute paths",
    memory_type="decision"
)

# Result:
# title: "When debugging path errors..."
# concepts: ['debugging', 'path', 'errors', 'absolute', 'paths']
# surfaces_when: ['debugging error', 'path error', 'debugging best practice', ...]
# authority_score: 0.724
```
