# Memory Scoring and Lifecycle

This reference describes the behavior implemented in the current source. It
separates four concepts that must not be conflated:

- **Vitality** estimates how active a memory is over time.
- **Retrieval relevance** ranks candidates for a query.
- **Trust** is supplied by memory type, provenance, lifecycle, and user policy.
- **Utility** means evidence that the memory improved a task outcome. Retrieval
  or repeated exposure alone does not prove utility.

## Temporal vitality

`MemoryMetadata.calculate_relevance_score()` returns vitality in the range
`0.0–1.0`:

```text
effective_decay_rate = decay_rate / (1 + 0.25 * ln(access_count + 1))
recency_factor       = exp(-effective_decay_rate * days_since_created)
freshness_factor     = exp(-0.005 * days_since_last_access)
vitality             = recency_factor * freshness_factor
```

The default type decay rates are:

| Memory type | Daily type decay |
|---|---:|
| `preference` | 0.002 |
| `decision`, `fact` | 0.005 |
| `insight` | 0.008 |
| `note` | 0.015 |
| `conversation` | 0.025 |
| `specification`, `directive` | 0.000 |

Specifications and directives have zero **type** decay, but the freshness
factor still lowers their vitality when they have not been accessed. They are
therefore not mathematically immutable or guaranteed to rank first.

Access slows type decay logarithmically. Retrieval is now read-only: a search or
automatic context delivery does not increment access or create co-activation.
The development `record_use` path writes a reversible declared-use event to the
Task Intelligence ledger. It does not yet update access history,
co-activation, or ranking. That separation prevents observational pilot data
from silently changing retrieval before causal benefit is established.

## Retrieval ranking

Fresh SQLite searches use semantic similarity plus vitality when temporal
scoring is enabled:

```text
initial_score = 0.70 * semantic_similarity + 0.30 * vitality
```

The orchestrator then computes the cognitive score:

```text
score = 0.35 * vector
      + 0.30 * concept
      + 0.15 * coactivation
      + 0.10 * authority
      + 0.10 * temporal
```

The vector component has a `0.70` floor before weighting. A `+0.30`
specification/directive boost applies only when the analyzed query has system
intent. These five signals rank likely relevance; they do not establish that a
result caused a better task outcome.

Development-only literal-trigger results are marked separately from this
five-signal score. They require an explicit `surface_context` match on a memory
with `injection_policy="triggered"`, use a bounded explicit-trigger score for
delivery, and do not update access history or graph state.

## Dashboard score

The dashboard uses a separate display score:

```text
dashboard_score = 0.50 * vitality
                + 0.25 * memory_type_weight
                + 0.25 * engagement
```

Do not compare this score directly with a retrieval score. They answer
different questions.

## Reinforcement and configuration boundary

The memory model currently defaults `reinforcement_factor` to `0.25`. The
configuration model also exposes `default_reinforcement_factor: 0.1`, but that
setting is not wired into normal memory creation. Until that implementation gap
is closed, documentation and callers must not claim the configurable default
controls runtime reinforcement. The current Task Intelligence ledger is an
observational boundary only; no runtime reinforcement is authorized from its
declared-use or outcome events.

## Lifecycle behavior

Elefante does **not** automatically archive memories merely because they are
old or have a low score. The current refinery can canonicalize duplicates,
merge redundant memories, and archive the redundant records recoverably. A
general age-based consolidation job, configurable consolidation threshold, and
automatic resurrection are not implemented.

Future memory governance is specified separately in the developer proposal. A
user-enforced memory may require retention or delivery; managed memories may
become dormant or archived. Governance is applied before task-specific ranking.
The development branch now enforces the first bounded contract: scope and
trigger gates run before ranking, locked `always` memories are reserved, and
protected memories are not silently archived by the refinery. These fields are
not presented as part of the published v2.12.3 client until released.

## Verification

- `tests/test_scoring.py` verifies score arithmetic and key ranking behavior.
- `tests/test_autonomous_coactivation.py` verifies multi-signal behavior.
- `tests/test_refinery.py` verifies current duplicate/refinery behavior.
- Task Intelligence evaluation and governance remain unshipped developer work;
  retrieval activity must not be presented as task-outcome evidence.

## Related documentation

- [`architecture.md`](architecture.md) — system architecture
- [`memory-schema.md`](memory-schema.md) — memory data model
- [`tools.md`](tools.md) — MCP surface
