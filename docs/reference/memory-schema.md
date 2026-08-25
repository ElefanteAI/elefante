# Memory Schema


This document is the normative specification for Elefante's memory metadata schema. It covers the V4 cognitive retrieval fields and V5 knowledge topology fields.

---

## V4: Cognitive Retrieval Fields

V4 added enrichment fields for concept retrieval, dashboard inspection, and
forward-compatible trigger metadata. The current retriever uses `concepts`,
but does not score `surfaces_when` or the stored `authority_score` field.

### New Metadata Fields

| Field             | Type       | Purpose                                        | Auto-populated |
| ----------------- | ---------- | ---------------------------------------------- | -------------- |
| `concepts`        | `string[]` | 3-5 key terms used by concept-overlap retrieval | Yes            |
| `surfaces_when`   | `string[]` | Stored trigger metadata for inspection and future proactive surfacing; not a current ranking signal | Yes |
| `authority_score` | `float`    | Stored compatibility/dashboard field; the current retriever derives authority from vitality and access count | Yes |

### Concept Extraction

**File**: `src/utils/curation.py` → `extract_concepts()`

Deterministic keyword extraction (no LLM):

- Removes stop words
- Boosts technical terms (python, docker, elefante, etc.)
- Weights by position (early words score higher)
- Returns top 5 concepts

```python
content = "Always use absolute paths in Elefante to avoid errors"
concepts = extract_concepts(content)
# → ['elefante', 'always', 'absolute', 'paths', 'avoid']
```

### Surfaces When

**File**: `src/utils/curation.py` → `infer_surfaces_when()`

Generates candidate query patterns for future proactive surfacing. The values
are persisted and shown in the dashboard, but are not a current ranking signal:

| Content Pattern           | Generated Triggers                            |
| ------------------------- | --------------------------------------------- |
| "how to", "why"           | Question patterns                             |
| "error", "fix", "bug"     | `{concept} error`, `{concept} problem`        |
| "always", "never", "must" | `{concept} best practice`, `how to {concept}` |
| "config", "setup"         | `{concept} setup`, `{concept} configuration`  |

### Authority Score

**File**: `src/utils/curation.py` → `compute_authority_score()`

Legacy enrichment score stored for compatibility and dashboard inspection:

```python
authority = (
    0.35 × (relevance_score / 100) +     # System-computed behavioral relevance
    0.25 × log(access_count) / log(50) +  # Usage frequency
    0.20 × exp(-0.007 × days_since_created) +  # Creation freshness
    0.20 × exp(-0.05 × days_since_accessed)    # Access recency
)
```

The current retrieval authority signal is computed at query time from stored
behavioral vitality and access count. See [`scoring.md`](scoring.md).

### Dashboard Edges

V4 adds **SHARES_CONCEPT** edges to the dashboard:

| Edge Type           | Meaning                                 |
| ------------------- | --------------------------------------- |
| `SHARES_CONCEPT`    | Two memories share at least one concept |
| `CO_TOPIC`          | Share same topic (existing)             |
| `CO_RING`           | Share same ring (existing)              |
| `CO_KNOWLEDGE_TYPE` | Share same knowledge type (existing)    |

---

## V5: Knowledge Topology

V5 adds a queryable knowledge topology so the dashboard can present a higher-level map (rings, topics, and types) without speculative metadata.

### Topology Rings

Rings define hierarchy depth:

| Ring | Meaning |
|------|---------|
| `core` | Identity and foundational principles/laws |
| `domain` | Broad areas of life/work/projects |
| `topic` | Subject clusters (coding standards, workflow, tools) |
| `leaf` | Individual memories (facts, preferences, decisions) |

### Knowledge Types

`law`, `principle`, `preference`, `method`, `fact`, `decision`, `insight`

### Topics

`coding-standards`, `communication`, `workflow`, `agent-behavior`, `tools-environment`, `collaboration`, `general`

### Relationship Types

| Type | Meaning |
|------|---------|
| `OWNED_BY` | Memory belongs to a domain entity |
| `BELONGS_TO` | Entity is part of a group/project |
| `DERIVES_FROM` | Knowledge derived from another source |
| `CONTRADICTS` | Two memories contradict each other |
| `SUPERSEDES` | Newer memory replaces older one |
| `REQUIRES` | One memory depends on another |
| `IMPLEMENTS` | Memory implements a specification |

---

## See Also

- [`scoring.md`](scoring.md) — Temporal decay and reinforcement system
- [`architecture.md`](architecture.md) — Triple-layer brain design
- [`tools.md`](tools.md) — API reference
