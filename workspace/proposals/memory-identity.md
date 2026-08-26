# Memory Identity Proposal

> Status: DEFERRED DESIGN REFERENCE
>
> Audience: Elefante developers
>
> Contract authority: none
>
> Parent: [`retrieval-effectiveness.md`](retrieval-effectiveness.md)

## Question

If evidence later proves that state/scope ambiguity prevents useful memory from
reaching a task, what minimum identity rules must a resolver preserve?

## Why this is deferred

Current evidence does not show that memory identity is the first causal failure
in Task Intelligence. Building persistent identity now would add schema,
migration, conflict, and rollback risk before demonstrating task benefit.

The parent North Star therefore uses a sealed, read-only evaluation overlay
first. No live memory, schema, or store changes are approved.

## Activation gate

Reopen this proposal only when all are true:

1. one new eligible memory-dependent task is frozen;
2. model-free stage tracing proves `SELECTION_MISS`;
3. the miss is caused by state/scope ambiguity, not ordinary relevance, budget,
   governance, delivery, agent application, or an invalid judge;
4. an evaluation-only resolver changes the intended selection deterministically;
5. the parent PRD's local causal gate passes without a trust regression.

Until then, persistent identity implementation is out of scope.

## Minimum principles if activated

- The existing memory UUID remains the immutable assertion identity.
- Only state-bearing memories need a state key.
- A state key identifies the proposition and scope:
  `project + subject + predicate + normalized scope`.
- Assertion role—governing, observed, or supporting—is metadata, not part of
  the state key. This keeps requirements and contradictory observations
  comparable.
- Different exact scopes may hold different governing values.
- Missing required scope returns `REQUIRES_SCOPE`; incompatible governing
  values at the same exact key return `UNRESOLVED_CONFLICT`.
- Similarity, recency, access count, and co-activation cannot settle authority
  or conflict.
- Reads never assign identity or mutate lifecycle, ranking, or history.
- User-protected retention and injection policy remains authoritative.

These are design constraints, not a storage contract.

## Still `UNKNOWN`

- scope dimensions and normalization;
- canonical subject, predicate, and value representation;
- indexed fields versus a transactional identity table;
- equivalent-value and collision behavior;
- handling of unauthorized conflicting writes;
- legacy backfill and migration;
- customer-visible inspection or correction surfaces.

Each item requires its own evidence, tests, backup, and rollback before schema
work. None is needed for the immediate experiment.

## Explicit non-goals now

- no schema migration;
- no uniqueness constraint;
- no automatic merge, supersession, archive, or deletion;
- no global "one truth" rule;
- no new MCP tool or customer claim.
