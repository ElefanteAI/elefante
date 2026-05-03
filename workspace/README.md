# `workspace/` — Elefante Developer Workspace

> **For agents and humans BUILDING Elefante.** Not for agents/users *using* Elefante (those go to [`docs/`](../docs/) and `.github/copilot-instructions.md`).

## What lives here

| File | Purpose |
|------|---------|
| [`PLANNING.md`](PLANNING.md) | Single living plan. Vision, active release state, roadmap, features (backlog → in-design → shipped), aspect plans (optimization, ops, dev, UX), meta-process. **The canonical answer to "where are we?"** |
| [`decisions/ADR-NNNN-*.md`](decisions/) | Architecture Decision Records (sequential, immutable, append-only). Currently empty — migrating from `workspace/PLANNING.md §2.5` X-rejections + `workspace/lessons.md` distilled rules. |
| `manifests/agents.yaml` | Specialist agent roster (machine-readable). Currently planned; agents inventoried in `workspace/PLANNING.md §2.5` until migration. |
| `manifests/glossary.yaml` | Codename glossary (machine-readable). Currently in `agents/_glossary.md` markdown. |

## What does NOT live here

- **Client-facing reference, how-to, explanation** → [`docs/`](../docs/)
- **End-user agent constitution** → [`.github/copilot-instructions.md`](../.github/copilot-instructions.md)
- **Developer-mode constitution** → [`agents/orchestrator.md`](../agents/orchestrator.md) (constitution lives at top of docs/ for visibility; workspace/ is for state and plans, not authority)
- **Specialist agent protocols** → [`agents/`](../agents/)
- **Bug/GAP tracker** → [`workspace/ISSUES.md`](../workspace/ISSUES.md) (will move to `workspace/bugs/` in a future restructure phase)

## Current state of the workspace migration (2026-05-02)

This directory was created on 2026-05-02 in response to the user's diagnosis that mixing **client documentation** with **developer workspace material** in a single `docs/` folder produces unscoped sprawl. Migration is **partial**:

| Status | Content |
|--------|---------|
| Migrated | `PLANNING.md` (consolidated from `docs/explanation/vision.md` + `workspace/PLANNING.md §2.5` + `spec-ide-integration-surface.md §15` + 4 in-design PRDs as cross-references for now) |
| Migration in progress | Constitution + bug tracker + best practices + decisions stay in `docs/` until follow-on phases consolidate them |
| Not yet migrated | ADRs (planned next), specialist agent roster manifest, glossary manifest |

## Authority

When this directory's content conflicts with `docs/`:

- **State questions** ("what's the active release? what's blocked?") — `PLANNING.md` wins.
- **Decision history** ("why did we reject X?") — `decisions/ADR-NNNN-*.md` wins (when migrated).
- **Constitution / process rules** — `agents/orchestrator.md` wins.
- **Bug status** — `workspace/ISSUES.md` wins.

This will simplify as migration completes. See `PLANNING.md §2 Active Release § Migration State` for current step.
