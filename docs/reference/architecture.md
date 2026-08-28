# Elefante Architecture

> **Release:** v2.13.0 · **Status:** released product contract

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

The released search path also supports bounded literal-trigger delivery. When a
caller supplies `surface_context` (or the query
itself is used as context), one read-only scan considers only memories with
`injection_policy=triggered`, requires a case-insensitive literal match, and
adds at most three results. Scope, lifecycle, source-trust, conflict, and
privacy gates still apply; the pass does not update access history or graph
state. If a workspace filter is supplied, it also uses the shared current-source
digest check on a deep copy and skips stale records. It is an explicit delivery
hint, not automatic host interception or a second semantic retriever.

The governed answer-context compiler also reports a bounded warning when a
candidate with a stored conflict relationship or contradictory status is
withheld. It never selects either side automatically, and the warning omits
internal memory IDs; the customer Recall text carries the same warning without
expanding its minimal payload.

The scoring details and known exposure-versus-utility limitation are in
[`scoring.md`](scoring.md). Retrieval ranks likely relevance; it does not prove
that a memory improved the downstream task.

## Response behavior

- Every normal non-Recall tool response includes heuristic `TOKEN_STATS`.
- `elefante-Recall` intentionally returns a minimal customer payload and keeps
  its token accounting internal. Its shared selector admits at most 12
  candidates, three memories, and 450 heuristic context tokens; the complete
  pretty Unicode response is capped at 1,000 heuristic tokens and fails closed
  instead of truncating evidence.
- Normal memory, graph, context, session, ETL, and task operations also receive
  entrypoint/pitfall blocks and active directives.
- The default customer profile does not inject automatic tool-response context.
  Recall and the context prompt provide explicit bounded answer delivery.
- System, dashboard, and directive-management tools use a minimal management
  response.

See [`token-intelligence.md`](token-intelligence.md) and
[`tools.md`](tools.md).

## Trust and recovery boundaries

- Dashboard APIs read a redacted snapshot rather than opening live stores.
- Browser actions cannot regenerate that snapshot.
- Backup/restore is checksummed, dry-run-first, and preserves replaced data.
- JSON export is a portable, additive vector-memory migration source: the
  importer regenerates embeddings with the configured local model, preserves
  memory IDs/metadata, rejects collisions, and does not restore graph topology.
  CSV remains analysis-only. Neither human-readable format replaces a full
  binary backup.
- Host configuration is ownership-tracked; user-managed or modified entries
  are preserved.
- Migration of an existing legacy store is explicit, stopped-runtime,
  backup-gated support work.

## Optional v2.13 local surfaces

- **Conflict repair:** a deterministic detector classifies only explicit
  same-proposition polarity or value contradictions. Ambiguous language
  abstains. `elefante-Memory(action="resolve")` is dry-run-first, keeps both
  records recoverable, and requires a user-selected winner when authority does
  not identify one.
- **Host event ingress:** `/events/surface` accepts bounded, privacy-scrubbed
  file, terminal-error, and conversation envelopes, runs the same read-only
  governed selector, and does not persist the event body. Hosts must opt in and
  send the event; Elefante does not silently intercept activity.
- **Session Distiller:** foreground `--watch` mode processes changed supported
  session files serially and stores nothing unless `--store` is supplied.
- **Session Intelligence:** a separate consent-gated SQLite ledger accepts
  typed provider-actual or estimated usage metadata through its CLI or
  `/events/usage`. It supports dated rate cards, outcome records, Signal Cards,
  aggregate training hypotheses, retention, export, and deletion. Prompts,
  transcripts, responses, hidden reasoning, and credentials are invalid input.
- **Team Sync:** signed, exact-scope local bundles export only an explicit
  memory-ID allowlist. Imports are additive, dry-run-first, conflict-withholding,
  and backup-gated for non-empty stores. Elefante provides no cloud transport.
- **Media attachments:** bounded local image, audio, and video files live in a
  private content-addressed store with integrity metadata and text descriptions.
  Elefante performs no OCR, transcription, model analysis, or network upload.

## Developer-only boundary

The default-off Task Intelligence tool, causal evaluation ledger, benchmark,
and automatic tool-response context pilot are developer surfaces. They have not
established representative multi-task outcome lift and are not part of the
17-tool customer profile. Automatic age-based forgetting, a background
Distiller service, cloud Team Sync transport, and vendor certification of host
adapters are also not shipped claims.

## Source authorities

- `src/core/orchestrator.py` — memory lifecycle and dual-store coordination
- `src/core/sqlite_vector_store.py` — released vector backend
- `src/core/graph_store.py` — Kuzu boundary
- `src/core/retrieval.py` — five-signal ranking
- `src/mcp/daemon.py` and `src/mcp/stdio_bridge.py` — customer topology
- `src/mcp/server.py` — MCP schemas, dispatch, and response contract
- `scripts/setup/` — installer and host integration behavior
