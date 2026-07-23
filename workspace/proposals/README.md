# `workspace/proposals/` — Drafts (pre-spec)

Live development state. Draft PRDs and design proposals that have not yet earned a [`../../docs/reference/`](../../docs/reference/) home. Migrated from `docs/planning/spec-*.md` on 2026-05-02.

## What lives here

| File | Status | Promotes to |
|------|--------|-------------|
| [`installer-procedure.md`](installer-procedure.md) | DRAFT — Phase 1 only | `docs/reference/installer.md` when shipped |
| [`ide-integration-surface.md`](ide-integration-surface.md) | DRAFT (docs in v2.10.0; impl v2.11+) | `docs/reference/ide-integration.md` when shipped |
| [`session-intelligence.md`](session-intelligence.md) | DRAFT | `docs/reference/session-intelligence.md` when shipped |
| [`retrieval-effectiveness.md`](retrieval-effectiveness.md) | DRAFT (sketch only) | `docs/reference/retrieval-effectiveness.md` when shipped |
| [`integrations/agent-zero.md`](integrations/agent-zero.md) | Integration target draft | `docs/reference/integrations/agent-zero.md` if shipped |
| [`tool-consolidation.md`](tool-consolidation.md) | DRAFT — v3.0.0 atomic 16 → 6 domain-tool reduction; architecturally distinct from rejected X1 facade | `docs/reference/tools.md` (rewritten) when shipped |

## Lifecycle

A proposal here is a **draft**, not a contract. Status is a frontmatter field, not a folder. When a proposal ships:

1. Author the canonical `docs/reference/<name>.md` from the proposal body.
2. Update CHANGELOG `### Added` referencing both the new spec and the deleted draft.
3. Delete the proposal here with a `### Removed` record naming the resolution.

## Authority

A proposal here has **no contract authority**. The shipped spec in `docs/reference/` is the contract; this folder is intent.

## Boundaries

- **Not for accepted features.** Once accepted and shipped, the spec moves to `docs/reference/` and the proposal here is deleted.
- **Not for ideas** — those live in [`../PLANNING.md §4.1 Backlog`](../PLANNING.md).
- **Not for rejected proposals** — rejections move to [`../decisions/ADR-NNNN-rejected-*.md`](../decisions/) when the ADR backlog is migrated.
