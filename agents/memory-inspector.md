---
PROTOCOL: memory-inspector
INVOKE: elefante-memory-inspector
PROTOCOL_VERSION: 2.12.2
LOAD_WHEN: User asks "what do I have stored", "show me my memories", export request, audit, dashboard navigation, "find a memory about X".
DIAGNOSTIC_QUESTION: "What memories exist that match this question, and what do they tell me about the system's state?"
AUTHORITY: This file owns memory inspection. Read-only. Any write operation routes to `agents/memory-janitor.md` instead.
---

# Memory Inspector Agent

> Read-only. This agent never mutates. If the task requires `elefante-Memory(action="add"|"update"|"delete")`, abort and load `agents/memory-janitor.md`.

## Inspection Routes

| Question | Tool / script |
| -------- | ------------- |
| "What's the most relevant memory for X?" | `elefante-Memory(action="search")` (semantic, k=5 default) |
| "Show me everything tagged Y" | `elefante-Memory(action="search")` with category filter |
| "What's connected to entity Z?" | `elefante-GraphQuery` for inbound + outbound edges |
| "What did I store recently?" | `elefante-Memory(action="search")` with temporal-recency boost; or dashboard table sorted by `created_at` |
| "Export everything for analysis" | `./.venv/bin/python scripts/pipeline/export_memories.py` (not a restorable backup) |
| "Inspect raw graph state" | `./.venv/bin/python scripts/privileged/inspect_memory_graph.py` (PRIVILEGED) |
| "Health snapshot" | `./.venv/bin/python scripts/verify/verify_health.py` + dashboard at `http://127.0.0.1:8000` |

## Search-First Discipline

Every inspection task starts with `elefante-Memory(action="search")`. Reasons:

1. The compliance gate logs the search; bypass is detectable.
2. Search exercises the same retrieval path the orchestrator uses, so issues surface where they will hurt.
3. Direct DB queries skip the 5-signal scoring and miss the answer the agent would actually see.

Drop to `inspect_memory_graph.py` only when a search returns 0 results AND the user expects results. That's a retrieval bug, not an inspection task — load `agents/orchestrator.md`.

## Export Protocol

`scripts/pipeline/export_memories.py` writes a JSON snapshot.

1. State the audit question first ("Who has access to my secrets?", "What did I learn about X last month?").
2. Run the export.
3. Read with `jq` or load into the dashboard table for filtering.
4. The export file is **sensitive** — it contains every stored memory. Do not share without redaction.

## Dashboard Inspection

Dashboard at `http://127.0.0.1:8000` is the human-readable surface:

- **Memory table** — sortable, filterable; quickest for "show me everything"
- **Topic distribution** — which categories dominate
- **Knowledge graph** — entity-level inspection
- **Health panels** — coverage, freshness, scoring distribution

If dashboard is blank or stale: load `agents/restarter.md` (likely a snapshot pipeline issue, not a memory issue).

## Closure

Inspection produces no artifacts. If the inspection revealed a real problem (duplicate memories, drift, schema corruption), hand off to `agents/memory-janitor.md` (cleanup) or `agents/orchestrator.md` (root-cause investigation). Never resolve in-flight from an inspection context.
