# Elefante Memory Schema V5: Knowledge Topology

**Status**: DRAFT (Specification)

V5 adds a queryable knowledge topology over memories so the dashboard can present a higher-level map (rings, topics, and types) without writing speculative or marketing-only metadata.

This document is a normative spec for:

- Field names and allowed values
- Minimum semantics (what each field means)
- Relationship types used for topology edges

---

## Goals

- Organize knowledge into a small set of stable dimensions: ring, knowledge_type, topic.
- Keep the core system deterministic and LLM-free.
- Allow agent-managed enrichment (classification) to be persisted as metadata.
- Support snapshot-first dashboard rendering.

---

## Topology rings

Rings define hierarchy depth. Allowed values:

- `core`: identity and foundational principles/laws
- `domain`: broad areas of life/work/projects
- `topic`: subject clusters (coding standards, workflow, tools, etc.)
- `leaf`: individual memories (facts, preferences, decisions, methods, insights)

---

## Knowledge types

Allowed values:

- `law`
- `principle`
- `preference`
- `method`
- `fact`
- `decision`
- `insight`

---

## Topics

Allowed values:

- `coding-standards`
- `communication`
- `workflow`
- `agent-behavior`
- `tools-environment`
- `collaboration`
- `general`

---

## Relationship types

Topology uses explicit relationship types in the graph (when persisted) and may also mirror references in vector metadata.

| Edge Type | Direction | Meaning |
|-----------|-----------|---------|
| `OWNED_BY` | Memory → Owner | Every memory links to a single owner anchor |
| `BELONGS_TO` | Leaf → Topic/Domain | Hierarchical containment |
| `DERIVES_FROM` | Specific → General | A derived rule comes from a broader principle |
| `SUPPORTS` | Memory → Memory | Evidence or justification |
| `CONTRADICTS` | Memory  Memory | Conflict (requires resolution policy) |
| `SUPERSEDES` | New → Old | Versioning / replacement |
| `REQUIRES` | Memory → Memory | Dependency |
| `IMPLEMENTS` | Method → Principle | A process embodies a value |

---

## Metadata fields

V5 is implemented as additional metadata fields (typically inside `custom_metadata`) so it does not break legacy stores.

```python
{
    "ring": "core|domain|topic|leaf",
    "knowledge_type": "law|principle|preference|method|fact|decision|insight",
    "topic": "coding-standards|communication|workflow|agent-behavior|tools-environment|collaboration|general",
    "summary": "one-line essence",

    "owner_id": "owner-jay",

    # Optional, if storing hierarchy explicitly
    "parent_id": "uuid",
}
```

Constraints:

- `summary` MUST be a single line and intended for UI tooltips/cards.
- V5 fields MUST NOT contain unverified claims (no auto-generated analysis embedded in schema docs).

---

## Classification strategy

Classification may be:

- Agent-managed (the agent decides ring/type/topic and stores it), or
- Deterministic rules (pattern matching / keyword rules) as a fallback.

Core constraint: no internal LLM calls from Elefante runtime.

---

## Migration notes

Suggested migration (high-level):

1. Backfill missing topology fields (ring, knowledge_type, topic, summary) using deterministic rules.
2. Allow agent to refine/correct classifications over time.
3. Keep topology fields stable; do not churn values without a clear reason.
