# Spec: Memory Identity

> Status: DRAFT · Scope: storage contract · Authority: technical

## Problem

Memory identity is enforced by inference, not by schema. [src/core/refinery.py](../../src/core/refinery.py) infers a `namespace` and a `canonical_key` for every memory at cleanup time and collapses duplicates by `(namespace, canonical_key)`. Neither field exists on [`MemoryMetadata`](../../src/models/memory.py). That means:

- The same logical memory can be re-derived to different keys across runs.
- New writes cannot deduplicate against existing identity at insert time, only at sweep time.
- Downstream code (dashboard, exports, MCP tool responses) cannot rely on identity being stable.

## Contract

`MemoryMetadata` must carry two first-class, immutable-after-set fields:

- `namespace: str` — coarse partition (e.g. `prod`, `test`, `quarantine`). Default `prod`.
- `canonical_key: Optional[str]` — stable identity within a namespace. Set at write time when inferable, never rewritten by cleanup.

Uniqueness invariant: at most one **active** memory per `(namespace, canonical_key)`. Active means not `deprecated` and not `archived`.

## Required Behavior

1. `elefante-Memory(action="add")` computes `canonical_key` once at write. If a non-deprecated memory exists with the same key, the new write either updates that record or is marked `REDUNDANT` against it. No silent duplicate.
2. `Refinery` no longer infers identity. It only enforces the invariant. If two active memories share a key, it deprecates the lower-authority one.
3. Exports and dashboard snapshots include `namespace` and `canonical_key` as top-level fields, not as `custom_metadata`.

## Out Of Scope

- Renaming or rewriting historical memories.
- Cross-namespace identity merging.
- User-facing namespace management UI.

## Acceptance

- Schema has the two fields; migrations populate them from current refinery inference.
- Refinery’s collapse pass becomes a guard, not a generator.
- A test asserts that two `elefante-Memory(action="add")` calls with the same canonical_key produce one active memory, not two.
