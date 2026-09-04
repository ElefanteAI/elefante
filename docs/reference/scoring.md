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

<a id="recall-cue-candidate-not-accepted"></a>

## Recall selection: question focus and saved cues

Topic similarity is not proof of the fact requested. A small English
question-form check distinguishes explicit
targets such as location, time, quantity, and a named property. A known target
mismatch prevents the ordinary text/role path from supplying a same-topic
memory. Open-ended guidance, unrecognized wording, and explicitly represented
additional body properties retain the existing conservative path. Cues are not
an exhaustive whitelist of every use of a memory.
Different property names are uncertain rather than automatically incompatible:
they require the strong full-question cue match, not ordinary body overlap.
An explanatory question cannot select a different saved property using only a
shared subject or memory-type label. Independently strong body evidence can
still qualify: it must cover substantive terms from the question beyond those
in the saved cue. Task success criteria are not mechanism-answer evidence.
Procedural questions such as “Which checks should we perform?” are method
requests, not missing named facts. A simple subject question still asks for its
named property. Specification/directive metadata can establish an unqualified
rule or constraint category, not a specific kind of rule. All normal topic and
relevance checks still apply.
Leading presentation instructions such as “explain” do not count as topic matches.
Without a saved cue, an absent named property cannot be supplied merely by
matching its subject. Quantity requests require numeric or number-word evidence
unless a matching saved question establishes a separate path. Such evidence is
necessary, not sufficient: the other relevance and governance gates still apply.

Repeated question words help disambiguate generic context; they are not mandatory
answer tokens. A direct answer or decision-bearing record that meets the existing
text-coverage floor may pass without repeating those words. Independent relevance,
scope, trust, privacy, lifecycle, identifier and conflict checks are unchanged.

The bounded paraphrase path reuses the existing local embedding model over at
most 12 retrieved memories and 5 cues per memory. A matching explicit target
requires question cosine at least `0.85`; an unclassified target still requires
`0.93`. Both require a `0.03` lead over competing memories' cues. For closed
alternatives, the requested property is also compared with the alternatives
at `0.85`, without the shared subject words. Multiple cues on one memory count
as one candidate. This adds no corpus scan, index, durable write, model
download, external call, or dependency.

`recall_cue_similarity` and `recall_focus_similarity` are ephemeral evidence,
not body similarity or an exact `recall_cue_match`. Exact cues and explicit
governing/structural paths keep their bounded behavior. Scope, trust,
current-source, privacy, conflicts, lifecycle and query identifiers remain
independent gates. Weak, tied, unavailable or non-finite model evidence adds
no paraphrase match; unknown syntax is not certified understanding.

### Developer verification evidence

The repair passes 56 real cached-model selection regressions, including all
27 preceding cases, the unchanged Elefante memory bodies, missing-fact checks,
alternatives, different words for the same property, and independent body evidence
beyond a saved example question, procedural questions and simple subject
questions. These are bounded regression results,
not a general semantic-accuracy or task-value guarantee. Publication and the
exact installed build are separate from this source contract; see
[BUG-047](../../workspace/ISSUES.md).

Recall compiles one answer bundle, using the execution stage and its existing
450-token, three-memory cap. Splitting this small budget across planning,
execution and validation incorrectly dropped a second eligible memory even
when the whole bundle fit. The local repair shares the answer budget; Task
Intelligence's separate multi-stage allocation is unchanged. This budget fix
does not establish semantic relevance.

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

## Developer verification

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
