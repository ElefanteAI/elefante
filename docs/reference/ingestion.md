# Memory Ingestion Contract

This page documents the released `MemoryOrchestrator.add_memory()` behavior in
v2.12.3. Elefante is LLM-free: the caller decides what is worth storing and may
provide classification metadata; Elefante validates, enriches, persists, and
links the record deterministically.

## Input

`elefante-Memory(action="add")` accepts content, memory type, tags, optional
entities and metadata, plus `force_new`. Governance metadata can opt a memory
into ranked, literal-triggered, or user-locked always delivery. A successful
write requires a memory search earlier in the same MCP session; that compliance
gate is enforced by the server before the orchestrator runs.

The write path does not rewrite the caller's content or remove conversational
language. Store one durable idea per memory when practical. If the agent should
discard an item before storage, it may send `metadata.action="IGNORE"`.

## Write sequence

1. **Validate and guard.** Content must satisfy the memory model. Test-like
   records are rejected unless `ELEFANTE_ALLOW_TEST_MEMORIES=1` is set.
2. **Create identity.** A supplied title is retained; otherwise Elefante creates
   a deterministic title. Without `force_new`, an existing record with the same
   title and near-identical content is reinforced instead of duplicated. A
   title collision with different content receives a short hash suffix.
3. **Check related knowledge.** Preference reassertions may merge into a close
   existing preference. Other close semantic matches can mark the new record as
   related, redundant, or contradictory. In the active development checkout,
   contradiction classification uses a narrow deterministic parser for explicit
   propositions and abstains on ambiguous language; it is still heuristic, not
   proof that one statement is correct.
4. **Enrich metadata.** Elefante creates or normalizes a summary, concepts,
   `surfaces_when`, source provenance, authority input, and the type-specific
   decay rate. New records start with `access_count=1` because creation counts
   as the first use, and `processing_status="raw"`.
5. **Persist and link.** The complete record and embedding are written to the
   configured vector store. Kuzu receives the memory node, source provenance,
   supplied entity links, concept links, and any detected relationship to an
   existing memory.

## Deduplication boundaries

The immediate write path uses title equality, near-text comparison, semantic
similarity, and a preference-specific merge. `force_new=true` bypasses those
checks and should be rare.

Namespace and canonical-key grouping are separate consolidation behavior.
`elefante-Memory(action="consolidate")` infers or honors those values and marks
duplicate groups; ingestion does not promise a universal Subject-Aspect-
Qualifier key or automatic supersession.

## Agent-assisted ETL

Every new record is usable immediately. The optional ETL pair improves its
retrieval metadata without calling an internal model:

1. `elefante-ETLProcess` returns raw records to the connected agent and marks
   them `processing`.
2. The agent analyzes the content.
3. `elefante-ETLClassify` writes a summary, concepts, and `surfaces_when`, then
   marks the record `processed`.

`ring`, `topic`, and `knowledge_type` are not fields in the released memory or
ETL contract.

## Retrieval and reinforcement

Search uses the stored semantic and graph signals described in
[`scoring.md`](scoring.md). Retrieval and automatic context delivery are
read-only: they do not increment access metadata or create co-activation.
The development search path also accepts explicit `surface_context` for
case-insensitive literal matching against `trigger` and `surfaces_when`; only
`injection_policy="triggered"` memories can surface this way, and the result is
bounded and subject to lifecycle, scope, trust, conflict, and privacy gates.
The development `elefante-Memory(action="record_use")` path records a reversible,
trace-bound acknowledgement for delivered IDs in a separate metadata ledger.
That is declared use, not verified task utility; it does not change ranking or
co-activation and is not an ingestion step.

The active development checkout also provides an opt-in foreground Distiller
watch mode (`distill --watch`). It enumerates all session files, detects new or
changed metadata, processes one session at a time, and isolates per-session
errors. It is not a daemon and it does not persist insights unless `--store` is
explicitly supplied.

## Lifecycle limits

Type decay and freshness can lower ranking. Elefante does not currently archive
ordinary memories automatically because they are old. The governance fields and
triggered-surfacing path are development extensions and are not part of the
published v2.12.3 client contract until a release explicitly includes them.

## Source authority

- Write behavior: `src/core/orchestrator.py`
- Memory fields and decay rates: `src/models/memory.py`
- Optional ETL: `src/core/etl.py`
- Consolidation: `src/core/refinery.py`
- MCP gate and schemas: `src/mcp/server.py`
