# surface-split.md — Absorbed (content map, original lost)

> **Status:** ARCHIVED (semantic recovery only). The original 583-LOC PRD was deleted 2026-05-02 by the agent-architect during curation pass 1, before this session adopted the "we don't cut, we document" rule. The file was never committed to git (post-`e603475`), so no verbatim recovery is possible. **This violated the Memory Janitor mandate and is recorded here as the canonical absorption map for what the document contained — the journal entry that documents the loss.**

## What the document was

A v2.10.0 surface-split PRD authored 2026-05-01/02. It proposed adding `docs/user/` + `docs/developer/` as audience-axis dispatch surfaces while leaving `docs/technical/`, `docs/debug/`, `docs/planning/` untouched as forwarding sources during v2.10.x. The 2026-05-02 restructure superseded its plan — instead of audience-folder boundaries, the codebase adopted **Diátaxis** (`docs/{reference,how-to,explanation}/`) plus tri-folder separation (`docs/`, `workspace/`, `agents/`).

## Where the content went (absorption map)

| Section in original | Absorbed into |
|---------------------|---------------|
| §0 Active release ledger (A-series, D-series, X-series, P-series, OB-series) | [`workspace/PLANNING.md §2`](../../PLANNING.md) |
| §0.5 ACCEPTED into v2.10.0 | [`workspace/PLANNING.md §2.3`](../../PLANNING.md) |
| §0.6 Rejected proposals (X1–X6 with re-open thresholds) | [`workspace/PLANNING.md §2.5`](../../PLANNING.md) |
| §0.6.2 Re-open thresholds for X-series | [`workspace/PLANNING.md §2.5`](../../PLANNING.md) (footer note) |
| §0.7 Resume Snapshot + Workspace blockers (OB1–OB8) | [`workspace/PLANNING.md §2.9, §2.10`](../../PLANNING.md) |
| §1 Three-Audience Surface map (User / Developer / Agent) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Closed Surface Map (event → canonical home) |
| §1.5 Swarm Law (≤100 LOC, trigger-first agents) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill + each `agents/<role>.md` frontmatter |
| §1.6 RESEARCH mode boundary | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Modes table + [`agents/researcher.md`](../../../agents/researcher.md) |
| §2 Closed Surface Map (event → canonical home) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Closed Surface Map (deduplicated, single home) |
| §2.2.1 Agent naming convention (kebab-case filename, `INVOKE: elefante-<role>` frontmatter) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) (constitution); each agent file's frontmatter |
| §2.4 Layered defense rationale (codename glossary, security vs friction) | [`agents/_glossary.md`](../../../agents/_glossary.md) |
| §3 Migration plan (commit buckets D, E, F, G) | Executed 2026-05-02; documented in `CHANGELOG.md [2.10.0]` `### Changed` (architectural restructure entry) |
| Bug-026 narrative (filename anti-patterns, recurrences #1/#2/#3) | [`workspace/postmortems/ai-behavior.md`](../../postmortems/ai-behavior.md) Issue #12 + [`workspace/postmortems/_archive/ai-behavior-full.md`](../../postmortems/_archive/ai-behavior-full.md) |
| Forbidden Patterns enumeration (HANDOFF-*, spec-vXX.YY.ZZ-*, NOTES, scratch, todo, ideas-new, CURRENT_STATE, IDEA-*, session-summary*) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Forbidden Patterns |

## Lesson learned (added to `../../lessons.md`)

**Never delete an uncommitted file.** Commit first, then delete with a record — git history becomes the archive. The "delete with a record" rule is not satisfied by a `### Removed` CHANGELOG line if the underlying content is unrecoverable.

## Journal entry (process trace)

| Date | Event |
|------|-------|
| 2026-05-01/02 | File authored as `docs/planning/spec-v2.10.0-surface-split.md` (version-stamped — BUG-026 recurrence #1) |
| 2026-05-02 | Renamed to `docs/planning/spec-surface-split.md` after BUG-026 recurrence flagged |
| 2026-05-02 | Moved to `workspace/proposals/surface-split.md` during the agentic restructure |
| 2026-05-02 | Deleted via `rm` (curation pass 1) — `### Removed` CHANGELOG entry authored, content not preserved |
| 2026-05-02 | User directive "WE DONT CUT INFORMATION IT GETS DOCUMENTED" — this stub authored as the absorption map |

The original text is not recoverable. The semantic content above is the documented absorption record.
