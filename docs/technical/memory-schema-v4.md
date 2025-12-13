# Memory Schema V4 (Authoritative)

**Version**: 4.0.0
**Status**: PROPOSED (Specification)
**Supersedes**: `memory-schema-v3.md` (once implemented)

> **V4 goal**: Stop the "bag of dots" permanently.
>
> - One concept = one canonical key
> - One canonical key = one active memory per namespace
> - Duplicates become reinforcement or a version chain (supersedes)
> - Test/ephemeral data never pollutes production by default

---

## 1. What V3 Tried To Do (and where it breaks)

V3 correctly defined:

- A strict 3-layer taxonomy (`self` / `world` / `intent` + sublayers)
- Deduplication via a semantic title (SAQ) and a reinforcement path
- Temporal decay + reinforcement

But V3 left gaps that create the exact export problems we saw:

- **No enforced canonical identity** (titles exist, but duplicates still get stored)
- **No deterministic update rules** (when to reinforce vs supersede)
- **No quarantine for test memories** (tests write into the same dataset)

V4 makes those behaviors explicit and enforceable.

---

## 2. Core Concepts (V4 primitives)

### A. `canonical_key` (the identity of a concept)

A stable string identifier for "this exact concept".

- **Required** for every stored memory.
- **Derived deterministically** from content using SAQ rules (see §4).
- **Equivalent to V3 SAQ title**. In V4, SAQ is not just a label — it is the *key*.

Examples:

- `Self-Limit-Emojis`
- `Dev-Path-Absolute`
- `Server-Config-Binding`

### B. Namespace (production vs test vs ephemeral)

Every memory belongs to exactly one namespace.

Allowed values:

- `prod` (default)
- `test` (integration/E2E/verification writes)
- `ephemeral` (temporary diagnostics)

**Hard rule**: Default search/export must include only `prod` unless explicitly asked.

### C. One-active-per-key invariant

For each `(namespace, canonical_key)`, there can be **at most one ACTIVE** memory.

### D. Version chain (supersedes)

When content changes meaningfully for the same key, create a new version and link it:

- New memory: `supersedes_id = old.id`
- Old memory: `superseded_by_id = new.id`, `status = superseded` (and optionally `archived = true`)

This preserves history without duplicating active rules.

---

## 3. The V4 Record (minimal authoritative shape)

V4 defines the minimum fields required to make the system deterministic.
(Implementations may store more fields, but MUST preserve these semantics.)

```python
class MemoryV4:
    id: str  # uuid

    # Content
    content: str  # atomic, one concept
    content_hash: str  # stable hash of normalized content

    # Taxonomy (V3-compatible)
    layer: Literal['self', 'world', 'intent']
    sublayer: str

    # Canonicalization
    canonical_key: str  # SAQ key
    status: Literal['active', 'superseded', 'redundant', 'contradictory', 'archived']
    namespace: Literal['prod', 'test', 'ephemeral']

    # Versioning & relations
    supersedes_id: str | None
    superseded_by_id: str | None
    related_memory_ids: list[str]
    conflict_ids: list[str]

    # Lifecycle
    created_at: datetime
    last_modified: datetime
    access_count: int
    last_accessed: datetime

    # Provenance & retention
    source: Literal['user_input', 'agent', 'test_suite', 'import', 'system']
    expires_at: datetime | None  # TTL for test/ephemeral

    # Optional enrichment
    tags: list[str]
    entities: list[dict]  # agent-supplied
    relationships: list[dict]  # agent-supplied
    artifact_ref: dict | None  # pointer to a file/url/blob, if used
```

---

## 4. Deterministic Canonical Key (SAQ) Rules

### A. SAQ format

`{Subject}-{Aspect}-{Qualifier}`

Constraints:

- ASCII + `-` only (sanitize other chars)
- Max length 30 (truncate components deterministically)

### B. Deterministic generation rules (LLM-free)

V4 forbids internal LLM calls.

Canonical key generation MUST be deterministic, using:

1. Agent-supplied `title` / `canonical_key` (preferred)
2. Rule-based parser (regex/keyword map) with a fixed fallback:
   - If unsure: `World-Fact-General`

### C. Normalization

Before hashing/dedup:

- Trim whitespace, normalize line endings
- Collapse repeated spaces
- Normalize common synonyms if configured (optional)

---

## 5. Ingestion Semantics (the enforcement rules)

Given an incoming candidate memory `M`:

### Step 1: Assign namespace

- If `source == test_suite` OR tags include `test`/`e2e` OR content matches known test patterns → `namespace = test`
- If explicitly flagged diagnostic/temp → `namespace = ephemeral` and set `expires_at`
- Else → `namespace = prod`

### Step 2: Compute `(namespace, canonical_key, content_hash)`

### Step 3: Enforce the one-active-per-key invariant

Lookup the current ACTIVE memory `A` for `(namespace, canonical_key)`.

- If no `A` exists → store `M` as `active`.
- If `A.content_hash == M.content_hash` → **reinforce** `A` (increment access_count, update last_accessed/last_modified) and DO NOT create a new memory.
- If `A.content_hash != M.content_hash`:
  - If `M` is a clarification/update of the same concept → create `M` as new `active`, set supersedes links, mark `A` as `superseded`.
  - If `M` contradicts `A` → store `M` as `contradictory`, link `conflict_ids`, and require an explicit resolution policy (see §6).

---

## 6. Contradictions (resolution policy)

V4 treats contradictions as first-class.

Allowed resolution strategies (choose one per deployment):

- `manual`: store contradictory memory, block promotion to active until user resolves
- `latest_wins`: newest becomes active, previous becomes `superseded`, and add conflict links
- `source_priority`: prefer `user_input` over `import`, etc.

---

## 7. Export/Search Defaults (prevent pollution)

Defaults:

- Export and search MUST default to `namespace = prod`.
- Tools may allow `include_namespaces=[...]` but MUST be explicit.

Rationale:

- Test memories are necessary for verification, but must not contaminate the brain.

**Operational entry point**:

- Use `elefanteMemoryConsolidate` for deterministic cleanup (dry-run by default; apply with `force=true`).

---

## 8. Worked Example (from the current export)

### A. Duplicate rule: "No emojis"

Current export contains two different memories expressing the same rule.

Under V4:

- Both map to the same `canonical_key = Self-Limit-Emojis`.
- One becomes ACTIVE.
- The other becomes either:
  - reinforcement (if meaning is identical), or
  - a superseding version (if it clarifies scope), with a version chain.

### B. Test pollution: "Elefante E2E Test Memory …"

Under V4:

- These are automatically routed to `namespace=test` with an optional TTL.
- Default exports/searches do not include them.

---

## 9. Migration Notes (V3 → V4)

1. `custom_metadata.title` (V3 SAQ) → `canonical_key` (V4)
2. Reclassify namespaces:
   - Any memory with `category=test` or tags `test/e2e` → `namespace=test`
3. Collapse duplicates:
   - Group by `(namespace, canonical_key)`
   - Choose the best ACTIVE (highest importance, newest, or best quality)
   - Link the rest via supersedes or mark redundant/archived

---

## 10. Non-Goals

- V4 does not require perfect entity extraction.
- V4 does not require complex similarity thresholds.
- V4 prioritizes deterministic correctness over cleverness.
