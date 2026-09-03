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
| [`session-intelligence.md`](session-intelligence.md) | RETAINED DESIGN RECORD — the opt-in metadata-only product surface shipped in v2.13.0; current contracts live in token, architecture, dashboard, and operator docs | Current behavior is documented in `docs/reference/token-intelligence.md` and related shipped references |
| [`session-intelligence-activation.md`](session-intelligence-activation.md) | LOCALLY ACTIVATED — SI-1–SI-5 pass within recorded boundaries; exact candidate `4b17c63` is installed and recording real MCP events. No public release or task-value claim | Existing token/architecture references and HTML dashboard guide own behavior; this PRD records the bounded local rollout and remaining coverage limits |
| [`retrieval-effectiveness.md`](retrieval-effectiveness.md) | NORTH STAR — one bounded causal-repair experiment; the first evidenced failed stage chooses the implementation; representative lift and customer promotion remain gated | `docs/reference/task-intelligence.md` when shipped |
| [`memory-identity.md`](memory-identity.md) | DEFERRED DESIGN REFERENCE — no schema work unless a bounded experiment proves state/scope ambiguity causes task failure and read-only resolution improves it | `docs/reference/memory-identity.md` when shipped |
| [`four-action-product-lifecycle.md`](four-action-product-lifecycle.md) | APPROVED / LOCAL PRODUCT LOOP IMPLEMENTED — product defaults, complete six-scenario exact-package execution, and release evidence remain gated | Product and operating references when the exact artifact is accepted and shipped |
| [`integrations/agent-zero.md`](integrations/agent-zero.md) | Integration target draft | `docs/reference/integrations/agent-zero.md` if shipped |
| [`tool-consolidation.md`](tool-consolidation.md) | EXPLORING — unversioned 17 → smaller-surface hypothesis; no approval or implementation | `docs/reference/tools.md` only if later proved and shipped |

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
