# Memory Identity Proposal

> Status: DRAFT · Audience: Elefante developers · Contract authority: none

## Question

How should Elefante give a logical memory a stable identity before duplicate
cleanup runs?

## Problem

Memory identity is currently enforced by inference, not by the stored schema.
`src/core/refinery.py` infers a `namespace` and `canonical_key` during cleanup
and collapses duplicates by that pair. Neither field is a released
`MemoryMetadata` contract, so downstream code cannot rely on it.

## Proposed Contract

- `namespace: str` — coarse partition such as `prod`, `test`, or `quarantine`;
  default `prod`.
- `canonical_key: Optional[str]` — stable identity inside a namespace, set once
  at write time when inferable.

At most one active memory would exist for a `(namespace, canonical_key)` pair.
Active means neither deprecated nor archived.

## Proposed Behavior

1. A memory write computes `canonical_key` once.
2. If an active memory already owns the same key, the write updates that memory
   or is classified as redundant.
3. Refinery enforces the invariant instead of creating identity.
4. Exports and dashboard snapshots expose the two fields directly.

## Out of Scope

- Rewriting historical memories.
- Cross-namespace merging.
- User-facing namespace management.

## Acceptance Before Promotion

- The two fields are implemented in the schema.
- Existing data has an explicit, reversible population strategy.
- Two writes with the same canonical key produce only one active memory.
- The released contract is documented under `docs/reference/` only after those
  behaviors ship and pass regression coverage.
