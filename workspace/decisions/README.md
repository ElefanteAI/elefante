# `workspace/decisions/` — Architecture Decision Records (ADRs)

> Currently empty. ADRs migrate here from existing scattered homes in a follow-on phase.

## Format

`ADR-NNNN-short-name.md`. Sequential, immutable, append-only. Sections: **Status / Context / Decision / Consequences**.

| Field | Rule |
|-------|------|
| Filename | `ADR-NNNN-short-name.md`. Sequential `NNNN` (zero-padded), never date-stamped, never reused. |
| Status | `proposed` → `accepted` → `superseded by ADR-MMMM` (status field, never deleted) |
| Context | Why this decision had to be made; the situation, constraint, or pressure that forced it |
| Decision | What was chosen; concrete and unambiguous |
| Consequences | What follows from the decision (good and bad); what becomes easier; what becomes harder; what new costs are accepted |

Source pattern: Michael Nygard, *Documenting Architecture Decisions* (2011). Industry-standard for agentic doc surfaces in 2025-2026.

## Migration plan

ADRs to be authored from existing scattered homes:

| Source | Future ADR |
|--------|------------|
| `workspace/PLANNING.md §2.5` X1 (3-tool facade rejected) | `ADR-0001-rejected-3-tool-facade.md` |
| `workspace/PLANNING.md §2.5` X2 (storage tiers rejected) | `ADR-0002-rejected-storage-tiers.md` |
| `workspace/PLANNING.md §2.5` X3 (scoring profiles rejected) | `ADR-0003-rejected-scoring-profiles.md` |
| `workspace/PLANNING.md §2.5` X4 (confidence-on-writes rejected) | `ADR-0004-rejected-confidence-field.md` |
| `workspace/PLANNING.md §2.5` X5 (write modes rejected) | `ADR-0005-rejected-write-modes.md` |
| `workspace/PLANNING.md §2.5` X6 (Hermes profile rejected) | `ADR-0006-rejected-hermes-profile.md` |
| BUG-016 (domain signal removal) — `ops-memory-compendium.md` Issue #11 | `ADR-0007-removed-domain-signal.md` |
| BUG-017 (intent-gated spec override) — `ops-memory-compendium.md` Issue #12 | `ADR-0008-intent-gated-spec-override.md` |
| BUG-018 (co-activation persistence) — `ops-memory-compendium.md` Issue #13 | `ADR-0009-co-activation-persistence.md` |
| BUG-026 (DOC_SYNC protocol bypass) parent class + active guard adoption | `ADR-0010-doc-sync-active-guard.md` |
| Killed dated-handoff pattern (this session) | `ADR-0011-no-date-stamped-filenames.md` |
| Killed version-stamped spec filename pattern (this session) | `ADR-0012-no-version-stamped-spec-filenames.md` |
| `workspace/lessons.md` distilled cross-bug rules | One ADR per rule (~10–15 ADRs) |

Migration is **not** in v2.10.0 contract scope; planned as part of v2.10.x or v2.11.0 follow-on work.

## Authority

When an ADR is authored, it becomes the source-of-truth for that decision. Existing homes (`workspace/PLANNING.md §2.5`, `best_practices.md`, compendium "Lesson" sections) get replaced with cross-references to the new ADR, not duplicates.

When an ADR is superseded, mark its `Status:` as `superseded by ADR-MMMM` and add a forward-link. Never delete; never edit the body of an accepted ADR (immutable). New decisions get new ADRs.

## Why ADRs (not "spec-*.md" or "decisions in compendium prose")

| Property | spec-*.md | compendium prose | ADR |
|----------|-----------|------------------|-----|
| Sequential immutable ID | ❌ | ❌ | ✓ |
| Status field for lifecycle | partial | ❌ | ✓ |
| Industry-standard format | ❌ | ❌ | ✓ |
| Programmatic queryable | ❌ | ❌ | ✓ (with frontmatter) |
| Append-only / immutable | varies | varies | ✓ (by definition) |
| Captures Consequences | sometimes | sometimes | required |

ADRs solve the "where do design decisions live?" question that currently has no canonical home in Elefante.
