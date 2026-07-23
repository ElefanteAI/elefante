# `workspace/` — Elefante Developer Workspace

> **For agents and humans BUILDING Elefante.** Not for agents/users *using* Elefante (those go to [`docs/`](../docs/) and `.github/copilot-instructions.md`).

## What lives here

| File | Purpose |
|------|---------|
| [`PLANNING.md`](PLANNING.md) | Single living plan. Vision, active release state, roadmap, features (backlog → in-design → shipped), aspect plans (optimization, ops, dev, UX), meta-process. **The canonical answer to "where are we?"** |
| [`decisions/ADR-NNNN-*.md`](decisions/) | Architecture Decision Records (sequential, immutable, append-only). Currently empty — migrating from `workspace/PLANNING.md §2.5` X-rejections + `workspace/lessons.md` distilled rules. |

## What does NOT live here

- **Client-facing reference, how-to, explanation** → [`docs/`](../docs/)
- **End-user agent constitution** → [`.github/copilot-instructions.md`](../.github/copilot-instructions.md)
- **Developer-mode constitution** → [`agents/orchestrator.md`](../agents/orchestrator.md); workspace is for state and plans, not authority
- **Specialist agent protocols** → [`agents/`](../agents/)
- **Bug/GAP tracker** → [`ISSUES.md`](ISSUES.md)

## Authority

When this directory's content conflicts with `docs/`:

- **State questions** ("what's the active release? what's blocked?") — `PLANNING.md` wins.
- **Decision history** ("why did we reject X?") — `decisions/ADR-NNNN-*.md` wins (when migrated).
- **Constitution / process rules** — `agents/orchestrator.md` wins.
- **Bug status** — `workspace/ISSUES.md` wins.

This will simplify as migration completes. See `PLANNING.md §2 Active Release § Migration State` for current step.
