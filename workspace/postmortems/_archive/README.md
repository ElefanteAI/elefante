# `workspace/postmortems/_archive/` — Full historical narratives

> **Frozen snapshot.** Each file here is the verbatim full narrative of a postmortem before the 2026-05-02 distillation. The active retrieval surface lives one level up at `workspace/postmortems/<domain>.md` (atomic Trigger / Root cause / Solution / Lesson chunks).

## What's here

| File | Source | Original LOC |
|------|--------|--------------|
| [`installation-full.md`](installation-full.md) | git HEAD `docs/debug/ops-installation-compendium.md` | 1,401 |
| [`ai-behavior-full.md`](ai-behavior-full.md) | git HEAD `docs/debug/ops-ai-behavior-compendium.md` | 985 |
| [`database-full.md`](database-full.md) | git HEAD `docs/debug/ops-database-compendium.md` | 572 |
| [`dashboard-full.md`](dashboard-full.md) | git HEAD `docs/debug/ops-dashboard-compendium.md` | 729 |

Total preserved: **3,687 LOC**.

## Why two surfaces (active vs archive)

**Active distilled** (`workspace/postmortems/<domain>.md`) is what Elefante surfaces during MemorySearch. Each closed BUG distills to ≤30 LOC of decision-bearing content (Trigger / Root cause / Solution / Lesson). High signal-per-token; cheap to retrieve; safe to embed and surface in agent context.

**Archive full** (this folder) is the historical record. Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, multi-paragraph Solution code blocks, Prevention Protocols, Quick Install References — all preserved verbatim. Open these files when:

- A distilled chunk is insufficient and you need the full debugging arc.
- You're investigating a methodology pattern that spans multiple bugs.
- A new BUG looks structurally similar to a closed one and you want the full prior context before classifying.

## Authority

The archive has **no contract authority** over current behavior. Two cases:

1. If a closed BUG re-opens and the distilled chunk is wrong, fix the distilled chunk first. The archive is frozen and may not reflect post-2026-05-02 understanding.
2. If a regression test that guards a BUG fails, the active surface (`../<domain>.md`) is the right home for the updated narrative — *not* the archive.

## Removal policy

This archive may be deleted entirely once:

1. The distilled surface has been live for ≥2 release cycles without rollback need.
2. No CHANGELOG `### Removed` or `### Changed` entries reference these paths.
3. Hermes / future agents have ingested and validated the distilled chunks at scale.

Until then, preserve.

## Note on memory.md

`workspace/postmortems/memory.md` (1,255 LOC) is **not yet distilled** as of 2026-05-02. It remains the full narrative; an `_archive/memory-full.md` will be authored when the distillation lands and the original is replaced. Until then, the live file is the only copy.
