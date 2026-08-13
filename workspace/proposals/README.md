# `workspace/proposals/` — Active designs and retained design records

Draft PRDs and partially implemented designs live here. A shipped proposal may
remain only when its rationale is still needed by developer tests or evaluation
fixtures; it must be marked **RETAINED DESIGN RECORD**, excluded from active
planning/retrieval, and defer to the released `docs/` contract.

## What lives here

| File | Status | Promotes to |
|------|--------|-------------|
| [`installer-procedure.md`](installer-procedure.md) | RETAINED DESIGN RECORD — pre-release rationale; not current product guidance | Current behavior is documented in `docs/how-to/install.md` |
| [`ide-integration-surface.md`](ide-integration-surface.md) | PARTIALLY IMPLEMENTED — shared runtime and compatible adapters shipped; additional certification is Upcoming | Released integration behavior is documented in `docs/how-to/configure-ide.md` |
| [`session-intelligence.md`](session-intelligence.md) | DRAFT — broader local telemetry remains downstream; it must reuse the existing Task Intelligence ledger rather than duplicate it | `docs/reference/session-intelligence.md` when shipped |
| [`retrieval-effectiveness.md`](retrieval-effectiveness.md) | NORTH STAR — one bounded causal-repair experiment; the first evidenced failed stage chooses the implementation; representative lift and customer promotion remain gated | `docs/reference/task-intelligence.md` when shipped |
| [`memory-identity.md`](memory-identity.md) | DEFERRED DESIGN REFERENCE — no schema work unless a bounded experiment proves state/scope ambiguity causes task failure and read-only resolution improves it | `docs/reference/memory-identity.md` when shipped |
| [`integrations/agent-zero.md`](integrations/agent-zero.md) | Integration target draft | `docs/reference/integrations/agent-zero.md` if shipped |
| [`tool-consolidation.md`](tool-consolidation.md) | EXPLORING — unversioned 16 → smaller-surface hypothesis; no approval or implementation | `docs/reference/tools.md` only if later proved and shipped |

## Lifecycle

A proposal here is **design intent**, not a released contract. Status is a frontmatter field, not a folder. When a proposal ships:

1. Author the canonical `docs/reference/<name>.md` from the proposal body.
2. Update CHANGELOG `### Added` referencing both the new spec and the deleted draft.
3. Delete the proposal with a `### Removed` record, unless a maintained
   developer test or evaluation still needs its design rationale. In that
   exceptional case, mark it retained and remove it from active retrieval.

## Authority

A proposal here has **no contract authority**. The shipped spec in `docs/reference/` is the contract; this folder is intent.

## Boundaries

- **Not a released-product authority.** Once shipped, `docs/` and source own
  the contract. A retained record exists only for historical rationale.
- **Not for ideas** — those live in [`../PLANNING.md §4.1 Backlog`](../PLANNING.md).
- **Not for rejected proposals** — rejections move to [`../decisions/ADR-NNNN-rejected-*.md`](../decisions/) when the ADR backlog is migrated.
