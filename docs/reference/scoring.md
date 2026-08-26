# Memory Scoring and Lifecycle

This reference separates four concepts that must not be conflated:

- **Vitality** estimates how active a memory is over time.
- **Retrieval relevance** ranks candidates for one query.
- **Trust** comes from type, provenance, lifecycle, and user policy.
- **Utility** requires evidence that memory improved an accepted task outcome.

Neither vitality nor retrieval relevance is supplied by the agent. Retrieval,
repeated exposure, or lower token use alone does not prove utility.

## Behavioral vitality

The canonical implementation is `Memory.calculate_relevance_score()` in
[`src/models/memory.py`](../../src/models/memory.py).

```text
effective_decay_rate = decay_rate / (1 + reinforcement_factor * ln(access_count + 1))
vitality = exp(-effective_decay_rate * days_since_created) * exp(-0.005 * days_since_access)
```

The result is bounded to `[0, 1]` and stored as an integer score from 0 to 100.
Access history slows age-based decay; it cannot inflate the score above 100.

| Memory type | Daily decay rate | Approximate half-life |
|---|---:|---:|
| preference | `0.002` | 347 days |
| decision | `0.005` | 139 days |
| fact | `0.005` | 139 days |
| insight | `0.008` | 87 days |
| note | `0.015` | 46 days |
| conversation | `0.025` | 28 days |
| specification | `0.000` | no type decay |
| directive | `0.000` | no type decay |

Specifications and directives still receive the freshness factor, so zero type
decay does not make them mathematically immutable or guarantee that they rank
first. Ordinary retrieval is read-only and does not yet update access history
or create co-activation. The development
`record_use` path writes a reversible observational event; it does not mutate
ranking; no runtime reinforcement is authorized by retrieval or delivery.

## Cognitive retrieval

The canonical implementation is `CognitiveRetriever` in
[`src/core/retrieval.py`](../../src/core/retrieval.py).

| Signal | Weight | Meaning |
|---|---:|---|
| vector similarity | `0.35` | semantic similarity between query and memory |
| concept overlap | `0.30` | overlap between query and memory concepts |
| co-activation | `0.15` | prior authorized co-retrieval evidence |
| authority | `0.10` | stored vitality plus access history |
| temporal | `0.10` | creation and access freshness |

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
erase a strong semantic match. Positive co-activation is added after that
floor. Specifications and directives receive a gated `+0.30` boost only when
query analysis identifies system intent.

`surfaces_when` is stored enrichment metadata for inspection and possible
future proactive surfacing. It is not a current ranking signal.

## Dashboard score

The dashboard uses a separate display score implemented by
`src/utils/dashboard_serializer.py`:

```text
dashboard_score = 0.50 * vitality
                + 0.25 * memory_type_weight
                + 0.25 * engagement
```

Do not compare this display score directly with retrieval relevance.

## Reinforcement and configuration boundary

The memory model defaults `reinforcement_factor` to `0.25`. Configuration also
exposes `default_reinforcement_factor: 0.1`, but that setting is not wired into
normal memory creation. Callers must not claim that the configurable default
controls runtime reinforcement.

## Consolidation and lifecycle

Deterministic consolidation is implemented by `MemoryRefinery` in
[`src/core/refinery.py`](../../src/core/refinery.py) and exposed through:

```text
elefante-Memory(action="consolidate")
```

The default is a dry run. With `force=true`, it canonicalizes duplicate groups
and recoverably archives non-winning duplicates. It does not call an LLM and
does not automatically delete memories based on age or vitality.

The development governance extension applies scope, trigger, retention, and
user-authority gates before Task Intelligence ranking. Protected memories are
not silently archived. Those fields are not part of the published v2.12.3
customer contract until released.

## Verification

```bash
pytest tests/test_scoring.py tests/test_autonomous_coactivation.py tests/test_refinery.py -q
```

These tests cover bounded vitality, type-specific decay, reinforcement,
multi-signal ranking, intent-gated authority, co-activation, and deterministic
consolidation. Task Intelligence evaluation remains unreleased; retrieval
activity must not be presented as task-outcome evidence.

## Related documentation

- [Memory schema](memory-schema.md)
- [MCP tools](tools.md)
- [Architecture](architecture.md)
- [Archived superseded scoring reference](_archive/scoring-full.md)
