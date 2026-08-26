# Memory Vitality and Retrieval Scoring

Elefante uses two related scores for different purposes:

1. **Behavioral vitality** records how durable a memory remains over time.
2. **Cognitive retrieval** ranks candidates for one search query.

Neither score is supplied by the agent.

---

## Behavioral vitality

The canonical implementation is
`Memory.calculate_relevance_score()` in
[`src/models/memory.py`](../../src/models/memory.py).

```text
effective_decay_rate = decay_rate / (1 + reinforcement_factor * ln(access_count + 1))
vitality = exp(-effective_decay_rate * days_since_created) * exp(-0.005 * days_since_access)
```

The result is bounded to `[0, 1]` and stored as an integer score from 0 to 100.
Retrieval reinforcement slows the age-based decay rate; it does not multiply the
score above 100. A memory's last-access time also adds a gentle freshness
penalty.

### Decay rates by memory type

| Memory type | Daily decay rate | Approximate half-life |
| --- | ---: | ---: |
| preference | `0.002` | 347 days |
| decision | `0.005` | 139 days |
| fact | `0.005` | 139 days |
| insight | `0.008` | 87 days |
| note | `0.015` | 46 days |
| conversation | `0.025` | 28 days |
| specification | `0.0` | does not decay |
| directive | `0.0` | does not decay |

The default reinforcement factor is `0.25`. New memories begin at 100. Their
stored vitality is recomputed when a relevant retrieval records access.

---

## Cognitive retrieval

The canonical implementation is `CognitiveRetriever` in
[`src/core/retrieval.py`](../../src/core/retrieval.py).

| Signal | Weight | Meaning |
| --- | ---: | --- |
| vector similarity | `0.35` | semantic similarity between query and memory |
| concept overlap | `0.30` | overlap between extracted query and memory concepts |
| co-activation | `0.15` | prior co-retrieval with recent memories |
| authority | `0.10` | stored vitality plus access history |
| temporal | `0.10` | recent access and creation freshness |

The base score is:

```text
cognitive_without_coactivation =
    0.35 * vector_similarity
  + 0.30 * concept_overlap
  + 0.10 * authority
  + 0.10 * temporal

score = max(0.70 * vector_similarity, cognitive_without_coactivation)
score = min(1.0, score + 0.15 * coactivation)
```

The floor preserves at least 70% of the vector score so sparse metadata cannot
erase a strong semantic match. Positive co-activation is added after that floor
so the graph signal remains visible.

Specifications and directives receive a gated `+0.30` boost only when query
analysis identifies system intent such as a rule, requirement, architecture, or
compliance question. They do not receive that boost for unrelated searches.

`surfaces_when` is stored enrichment metadata for inspection and future
proactive surfacing. It is not a current ranking signal in this five-signal
retriever.

---

## Consolidation

Deterministic consolidation is implemented by `MemoryRefinery` in
[`src/core/refinery.py`](../../src/core/refinery.py) and exposed through:

```text
elefante-Memory(action="consolidate")
```

The default is a dry run. It plans canonical namespace/key updates and identifies
duplicate groups. Passing `force=true` applies those updates and marks
non-winning duplicates redundant, deprecated, archived, and superseded.
Consolidation does not call an LLM and does not automatically delete memories
based on a vitality threshold.

---

## Verification

```bash
pytest tests/test_scoring.py tests/test_autonomous_coactivation.py tests/test_refinery.py -q
```

These tests cover bounded vitality, type-specific decay, reinforcement,
multi-signal ranking, intent-gated authority, co-activation, and deterministic
consolidation.

---

## Related documentation

- [Memory schema](memory-schema.md)
- [MCP tools](tools.md)
- [Architecture](architecture.md)
- [Archived superseded scoring reference](_archive/scoring-full.md)
