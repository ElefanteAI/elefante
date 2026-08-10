# Elefante Architecture

> **Release:** v2.12.2 · **Status:** released product contract

Elefante is a local persistent-memory service for AI agents. It stores semantic
memory and explicit relationships, exposes them through MCP, and keeps the
released customer runtime separate from the developer repository.

## Runtime topology

```text
MCP-capable host
  -> native loopback HTTP or storage-free stdio bridge
  -> one user-level daemon at 127.0.0.1:8765
  -> MemoryOrchestrator
       -> SQLite vector store (default)
       -> Kuzu graph store
       -> local directive store
```

- The customer installer places one stable account-level runtime and connects
  every detected compatible host to it.
- The daemon is loopback-only. Remote binding is rejected by default.
- The stdio bridge forwards MCP JSON-RPC and does not open databases.
- Direct `python -m src.mcp.server` remains a source/developer compatibility
  path, not the customer-global topology.
- Legacy ChromaDB stores are supported only when explicitly configured; normal
  fresh installations use SQLite.

## Storage responsibilities

### SQLite vectors

The default vector store persists the complete versioned Memory JSON plus an
explicit float32 embedding. Search uses deterministic exact cosine similarity
and can combine semantic similarity with temporal vitality.

### Kuzu graph

Kuzu stores memory/entity/session structure and explicit relationships.
Write operations are transaction-scoped. Query results are materialized while
the owning connection is valid, and normal tool cleanup releases graph
resources after the operation.

### Directives

Directives are stored in a dedicated local JSON store. They are not semantic
memories and do not compete in similarity ranking. Active directives are
attached to normal product-operation and error responses; management paths do
not recursively inject them.

## Write path

1. A host calls `elefante-Memory` with `action="add"`.
2. The Compliance Gate requires a prior memory search.
3. The orchestrator validates and deduplicates the candidate.
4. The configured embedding service creates a 768-dimensional
   `thenlper/gte-base` vector.
5. The complete memory record is written to the configured vector store.
6. Kuzu receives the corresponding memory node, entity relationships, and
   Source provenance when applicable.

Writes use transaction-scoped ownership. `elefante-System(action="enable")`
sets the logical mode and preloads the runtime; it is not a session-wide
exclusive database-lock contract.

## Retrieval path

1. The vector store finds semantic candidates.
2. Temporal vitality can influence the initial SQLite order.
3. The cognitive retriever combines vector, concept, co-activation, authority,
   and temporal signals.
4. Deprecated and archived memories are removed from normal results.
5. The result is returned with a compliance stamp and compact payload.

The scoring details and known exposure-versus-utility limitation are in
[`scoring.md`](scoring.md). Retrieval ranks likely relevance; it does not prove
that a memory improved the downstream task.

## Response behavior

- Every tool response includes heuristic `TOKEN_STATS`.
- Normal memory, graph, context, session, ETL, and task operations also receive
  entrypoint/pitfall blocks and active directives.
- `RELEVANT_CONTEXT` is supplementary and conditional. It is skipped for
  memory-heavy and management tools, requires a usable signal in the call, and
  is disabled unless all three development pilot flags documented in
  [`tools.md`](tools.md) are explicitly enabled.
- System, dashboard, and directive-management tools use a minimal management
  response.

See [`token-intelligence.md`](token-intelligence.md) and
[`tools.md`](tools.md).

## Trust and recovery boundaries

- Dashboard APIs read a redacted snapshot rather than opening live stores.
- Browser actions cannot regenerate that snapshot.
- Backup/restore is checksummed, dry-run-first, and preserves replaced data.
- JSON/CSV export is analysis-only, not a restorable backup.
- Host configuration is ownership-tracked; user-managed or modified entries
  are preserved.
- Migration of an existing legacy store is explicit, stopped-runtime,
  backup-gated support work.

## Development-only work

Task Intelligence evaluation, governed retention/injection fields, automatic
forgetting, expanded host certification, and proactive conflict surfacing are
not part of the v2.12.2 released architecture unless a later changelog and
reference document say otherwise.

## Source authorities

- `src/core/orchestrator.py` — memory lifecycle and dual-store coordination
- `src/core/sqlite_vector_store.py` — released vector backend
- `src/core/graph_store.py` — Kuzu boundary
- `src/core/retrieval.py` — five-signal ranking
- `src/mcp/daemon.py` and `src/mcp/stdio_bridge.py` — customer topology
- `src/mcp/server.py` — MCP schemas, dispatch, and response contract
- `scripts/setup/` — installer and host integration behavior
