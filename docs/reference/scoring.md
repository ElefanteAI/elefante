# Memory Vitality and Retrieval Scoring

Elefante keeps four concepts separate:

1. **Behavioral vitality** estimates how durable a memory remains over time.
2. **Retrieval relevance** ranks candidates for one search query.
3. **Trust** comes from provenance, lifecycle, type, scope, and user policy.
4. **Utility** requires evidence that a memory improved a task outcome.

Neither score is supplied by the agent, and retrieval or repeated exposure alone
does not prove utility.

---

## Behavioral vitality

The canonical implementation is `Memory.calculate_relevance_score()` in
[`src/models/memory.py`](../../src/models/memory.py).

```text
effective_decay_rate = decay_rate / (1 + reinforcement_factor * ln(access_count + 1))
vitality = exp(-effective_decay_rate * days_since_created) * exp(-0.005 * days_since_access)
```

The result is bounded to `[0, 1]` and stored as an integer from 0 to 100.
Authorized access history slows age-based decay; it cannot raise vitality above
100. A memory's last-access time adds a gentle freshness penalty.

| Memory type | Daily decay rate | Approximate half-life |
|---|---:|---:|
| `preference` | `0.002` | 347 days |
| `decision`, `fact` | `0.005` | 139 days |
| `insight` | `0.008` | 87 days |
| `note` | `0.015` | 46 days |
| `conversation` | `0.025` | 28 days |
| `specification`, `directive` | `0.000` | no type decay |

Specifications and directives still receive the separate last-access freshness
factor. They are not mathematically immutable or guaranteed to rank first.

Normal MCP retrieval is read-only and does not yet update access history or
create co-activation. The default customer profile exposes no reinforcement
write; no runtime reinforcement is authorized. Developer declared-use events
remain a separate reversible ledger and do not change ranking.

## Cognitive retrieval

The canonical implementation is `CognitiveRetriever` in
[`src/core/retrieval.py`](../../src/core/retrieval.py).

| Signal | Weight | Meaning |
|---|---:|---|
| vector similarity | `0.35` | semantic similarity between query and memory |
| concept overlap | `0.30` | overlap between extracted query and memory concepts |
| co-activation | `0.15` | prior authorized co-use with recent memories |
| authority | `0.10` | behavioral vitality plus access history |
| temporal | `0.10` | recent creation and access freshness |

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
erase a strong semantic match. Positive co-activation is added afterward.
Specifications and directives receive a gated `+0.30` boost only when query
analysis identifies system intent such as a rule, architecture, requirement,
or compliance question.

Literal-trigger results are a separate path. They require an explicit file,
terminal-error, conversation, or query context that matches a memory with
`injection_policy="triggered"`. The path returns at most three governed matches
and does not update access history or graph state.

## Dashboard score

The dashboard uses a separate display score:

```text
dashboard_score = 0.50 * vitality
                + 0.25 * memory_type_weight
                + 0.25 * engagement
```

Do not compare dashboard score directly with retrieval score. They answer
different questions.

## Reinforcement and configuration boundary

The memory model defaults `reinforcement_factor` to `0.25`. The configuration
model also exposes `default_reinforcement_factor: 0.1`, but that setting is not
wired into normal memory creation. Callers must not claim that the configurable
default controls runtime reinforcement until that gap is closed.

## Consolidation and lifecycle

Deterministic consolidation is implemented by `MemoryRefinery` in
[`src/core/refinery.py`](../../src/core/refinery.py) and exposed through:

```text
elefante-Memory(action="consolidate")
```

The default is a dry run. Passing `force=true` applies canonical namespace/key
updates and recoverably archives non-winning duplicates as redundant and
superseded. Consolidation does not call an LLM and does not delete memories
merely because they are old or have low vitality.

Retention, scope, trigger, and user-lock governance run before task-specific
ranking. Protected memories are not silently archived. Automatic ephemeral
expiry and general age-based pruning are not implemented.

## Verification

```bash
pytest tests/test_scoring.py tests/test_autonomous_coactivation.py \
  tests/test_refinery.py tests/test_proactive_surfacing.py -q
```

These tests cover bounded vitality, type decay, reinforcement, multi-signal
ranking, intent-gated authority, co-activation, consolidation, and triggered
read-only delivery. Task Intelligence outcome evaluation is separate; retrieval
activity must not be presented as proof of task lift.

## Related documentation

- [Memory schema](memory-schema.md)
- [MCP tools](tools.md)
- [Architecture](architecture.md)
- [Archived superseded scoring reference](_archive/scoring-full.md)
