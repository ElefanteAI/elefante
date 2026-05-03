# `workspace/postmortems/` — Domain compendiums

Live development state. Postmortems for bugs grouped by domain. Migrated from `docs/debug/ops-*-compendium.md` on 2026-05-02 (state belongs in `workspace/`, not `docs/`).

## Files

| Domain | Compendium | Covers |
|--------|------------|--------|
| AI behavior | [`ai-behavior.md`](ai-behavior.md) | Agent skips search, fakes completion, ignores rules |
| Dashboard | [`dashboard.md`](dashboard.md) | Dashboard blank, stale, schema mismatch |
| Database | [`database.md`](database.md) | Kuzu / ChromaDB locks, corruption, races |
| Installation | [`installation.md`](installation.md) | Install fails, broken venv, IDE stale MCP |
| Memory | [`memory.md`](memory.md) | Scoring, export, schema drift, response bloat |

## Structure (Unified Post-Mortem)

Each postmortem follows: **Problem → Symptom → Root Cause → Solution → Lesson**.

After every significant debugging session, append a post-mortem entry to the matching compendium. Cross-bug lessons distill to [`../lessons.md`](../lessons.md).

## Trigger map

Routing entry lives in [`../../agents/orchestrator.md`](../../agents/orchestrator.md) Compendium Trigger Map. Open the matching file when its symptom appears.
