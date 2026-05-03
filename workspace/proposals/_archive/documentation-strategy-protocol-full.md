# documentation-strategy-protocol.md — Absorbed (content map, original lost)

> **Status:** ARCHIVED (semantic recovery only). The original 450-LOC PRD was deleted 2026-05-02 by the agent-architect during curation pass 1, before this session adopted the "we don't cut, we document" rule. The file was never committed to git (post-`e603475`), so no verbatim recovery is possible. **This violated the Memory Janitor mandate and is recorded here as the canonical absorption map.**

## What the document was

A meta-process PRD authored 2026-04-19. It proposed a strict protocol a new agent could follow to build, audit, and evolve a documentation strategy that preserves context relevance, minimizes noise, and remains explicit about unknowns. Status was DRAFT — isolated working file, never adopted as authority. The Documentation Skill section authored into `docs/elefante-orchestrator-agent.md` during the BUG-026 mitigation (2026-05-02) and then merged into `agents/orchestrator.md` during Phase B of the agentic restructure absorbed the substantive rules.

## Where the content went (absorption map)

| Section in original | Absorbed into |
|---------------------|---------------|
| Problem statement (audience-cost leakage, durable rules in giant prompts, debugging lessons trapped in conversation, agent protocols mixed with human prose, implied authority, migration drift) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § (preamble) |
| Four basic questions (audience / loading model / authority / evidence) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Pre-write checklist (Q1–Q7) |
| Audience axis (end-user agent / developer agent / debugger / human contributor) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Closed Surface Map (consumer column) |
| Loading model taxonomy (browse-first / route-first / trigger-first / proof-first) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Pre-write checklist Q3 |
| Authority declaration rules | [`agents/orchestrator.md`](../../../agents/orchestrator.md) frontmatter `AUTHORITY:` field convention |
| Closed Surface Map proposal (one canonical home per event) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Closed Surface Map (full table) |
| Forbidden patterns (date-stamped, version-stamped, generic dump filenames) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Forbidden Patterns |
| Pre-write checklist (7 questions before any doc edit) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Pre-write checklist |
| Required routing (every doc edit, in order) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Required routing |
| New-File Test (7 conditions all required) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § New-file test |
| Failure conditions (7 violations) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Failure conditions |
| Lifecycle (CAPTURE → CLASSIFY → PRIORITIZE → SPECIFY → EXECUTE → VERIFY → DISTILL → CLOSE) | [`agents/orchestrator.md`](../../../agents/orchestrator.md) Documentation Skill § Lifecycle |
| Audit/evolve protocol (cross-bug edge promotion to lessons.md) | [`workspace/lessons.md`](../../lessons.md) header (Promotion Filter) |

## Lesson learned (added to `../../lessons.md`)

**Never delete an uncommitted file.** Commit first, then delete with a record — git history becomes the archive. The "delete with a record" rule is not satisfied by a `### Removed` CHANGELOG line if the underlying content is unrecoverable.

## Journal entry (process trace)

| Date | Event |
|------|-------|
| 2026-04-19 | File authored as `docs/planning/prd-documentation-strategy-protocol.md` |
| 2026-05-02 | Substantive rules absorbed into `docs/elefante-orchestrator-agent.md` Documentation Skill section (BUG-026 mitigation) |
| 2026-05-02 | Moved to `workspace/proposals/documentation-strategy-protocol.md` during the agentic restructure |
| 2026-05-02 | Deleted via `rm` (curation pass 1) — `### Removed` CHANGELOG entry authored, content not preserved |
| 2026-05-02 | User directive "WE DONT CUT INFORMATION IT GETS DOCUMENTED" — this stub authored as the absorption map |

The original text is not recoverable. The semantic content above is the documented absorption record.
