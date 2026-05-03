# PRD: Retrieval Effectiveness

> Status: DRAFT · Owner: planning · Supersedes the prior `spec-usage-intelligence.md`

## Why

Basic usage tracking is already shipped. `access_count` and `last_accessed` exist in [src/models/memory.py](../../src/models/memory.py), are updated on every retrieval in [src/core/orchestrator.py](../../src/core/orchestrator.py), persisted to ChromaDB, hydrated by [scripts/pipeline/update_dashboard_data.py](../../scripts/pipeline/update_dashboard_data.py), and surfaced in the dashboard.

Counting retrievals does not answer the only question Law 4 cares about: **did the injected memory raise the probability of a correct answer?** Without that signal, the system cannot tell a load-bearing memory from a frequently-surfaced distraction.

## Goal

Per-memory retrieval provenance and helpfulness, so the brain can demote noise instead of just decaying it.

## Non-Goals

- No new vector store, no new graph store, no new MCP tool surface beyond what is required.
- No LLM-based judging of usefulness. Heuristic + agent-acknowledged signal only.
- No real-time streaming. Snapshot pipeline remains the dashboard contract.

## What Must Exist

1. **Per-retrieval log entry**, written when a memory is returned in a `MemorySearch` or auto-injection result. Fields: `memory_id`, `query`, `mode`, `rank`, `score`, `session_id`, `timestamp`. Bounded ring buffer per memory (e.g., last 20).
2. **Helpfulness signal**, attached when a memory is referenced again or reinforced inside the same session. Reuse existing co-activation as the cheapest proxy; do not invent a new score.
3. **Dead-weight surfacing**: memories with high retrieval count and zero co-activation reinforcement are flagged in the snapshot.
4. **Gap surfacing**: queries that returned nothing are logged at the system level (not per-memory) so the user can see what the brain failed to answer.

## Out Of Scope

- Cross-session attribution.
- Importing logs from external IDEs.
- Any UI work beyond exposing the new fields in the existing snapshot consumers.

## Acceptance

- A memory's detail view can answer: which queries surfaced me, how often did surfacing lead to reuse, when did I last actually help.
- Snapshot exposes a "dead weight" list and a "answered nothing" list.
- No regression in retrieval latency beyond the cost of one append per returned memory.
