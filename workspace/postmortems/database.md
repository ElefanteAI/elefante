# Database Postmortems

> **Domain:** Kuzu graph database & ChromaDB vector store.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson.

---

## Issue #1: Reserved Word Collision [FIXED]

**Trigger:** Entity creation fails with `RuntimeError: Binder exception: Cannot find property properties for e.`
**Root cause:** Kuzu uses hybrid SQL/Cypher syntax. `properties` is valid as a column name in `CREATE NODE TABLE` (SQL) but is a reserved word in Cypher data operations. Schema creation succeeded; data inserts failed.
**Solution:** Renamed column `properties` → `props` in `src/core/graph_store.py` schema definition.
**Lesson:** Kuzu uses hybrid syntax. Test BOTH schema AND data operations against new column names — schema acceptance is not sufficient.

## Issue #2: Database Lock Persistence [FIXED, guarded]

**Trigger:** Second live process attempts to open Kuzu while another process owns the path. `RuntimeError: Kuzu database is locked by another process.`
**Root cause:** Kuzu access is single-owner across live processes. `read_only=True` does not enable cross-process sharing; it's for short-lived export/snapshot work. Old recovery guidance suggested deleting Kuzu's internal lockfile manually — wrong mental model.
**Solution:** (1) Dashboard reads on `dashboard_snapshot.json`, never live Kuzu. (2) Snapshot export runs in short-lived subprocess with `GraphStore(..., read_only=True)`. (3) Global `GraphStore` released after each MCP tool call so Kuzu ownership stays transaction-scoped. (4) On contention, stop the competing process or wait for the current transaction; do NOT delete Kuzu's internal lockfile as a default recovery step.
**Lesson:** Model Kuzu contention as short-lived process ownership, not as manual surgery on Kuzu's internal lockfile. `read_only=True` is for short-lived snapshot work, not a promise of live cross-process sharing.

## Issue #3: Database Path Format Change [FIXED]

**Trigger:** `RuntimeError: Database path cannot be a directory: ~/.elefante/data/kuzu_db`. Same as installation Issue #1 — Kuzu 0.11.x breaking change.
**Root cause:** Kuzu 0.11.x changed path semantics — database path cannot pre-exist as a directory. `config.py` was calling `KUZU_DIR.mkdir(exist_ok=True)` on import.
**Solution:** Removed eager `mkdir` from `config.py`. `src/core/graph_store.py` only creates the parent directory and removes legacy empty `kuzu_db/` directories before letting Kuzu materialize its own path (now a file under current contract).
**Lesson:** Kuzu owns the database path. Never infer the final on-disk shape from old versions.

## Issue #4: Legacy Path-Shape Diagnosis Drift [FIXED, guarded]

**Trigger:** Operators see `~/.elefante/data/kuzu_db` as a single file under current Kuzu contract; stale docs and destructive scripts treat that as corruption.
**Root cause:** Filesystem-shape assumptions drifted after the runtime contract changed in Issue #3. `kuzu_db` was historically a directory tree; new contract materializes it as a file. The stale "file = corruption" assumption spread across tests, docs, and debug tools.
**Solution:** (1) Guard the fresh path contract in maintained tests (`TestKuzuLockContract`). (2) Remove file-is-corruption logic from docs and destructive scripts. (3) Reset the Kuzu path only when init actually fails or data is known-bad.
**Lesson:** Never classify corruption from filesystem shape alone. Verify the current runtime contract from source and a fresh init first.

## Issue #5: Duplicate Entity Creation [DOCUMENTED, design limitation]

**Trigger:** Same logical entity ("User Approval Protocol") appears with multiple UUIDs across sessions.
**Root cause:** `entity_id = str(uuid.uuid4())` on every memory analysis — no existence check before creation. Each analysis spawns fresh entity rows.
**Solution (not yet implemented):** `find_entity_by_name(name, type)` lookup before insert; reuse existing ID if found. Requires fuzzy name matching for typos/variations.
**Lesson:** Entity deduplication requires fuzzy matching. Current impact is visualization-only — defer until usage demands it.

## Issue #6: ChromaDB Schema vs Memory Model [DOCUMENTED]

**Trigger:** ChromaDB queries returning unexpected types or missing fields.
**Root cause:** ChromaDB stores all 40+ memory fields flat in `metadata` dict; the Memory model expects typed direct attributes (`memory.score`, `memory.domain`). Direct `result["metadata"]["score"]` access is fragile across versions.
**Solution:** Always use `MemoryModel.from_chromadb_result(result)` translation helper. Never read metadata directly in callers.
**Lesson:** Always translate between storage format and domain objects via model helpers. Direct metadata access bypasses type coercion (strings → enums) and breaks on field renames.

## Issue #7: Async Shutdown Race / QueryResult Lifetime Leak [BUG-001, FIXED, guarded]

**Trigger:** Native SIGSEGV in `kuzu::main::QueryResult::~QueryResult()` or `kuzu::main::Database::~Database()` during MCP tool teardown.
**Root cause:** Three layers. (1) `src/core/graph_store.py` executed `self._conn.execute(...)` in `asyncio.to_thread(...)` but iterated the returned `QueryResult` on the event-loop thread — native lifetime escaped the worker thread. (2) `src/mcp/server.py` launched `record_coactivation(...)` via `asyncio.create_task(...)` then unconditionally called `close_graph_store()` in `finally` — background work could outlive close. (3) `GraphStore` had a thread-safety lock but never used it to serialize the shared `kuzu.Connection`.
**Solution:** Safe Kuzu boundary — `_execute_query_sync()` materializes rows inside the worker thread under `self._lock`; `close()` waits for `_active_operations` to drain before destroying the connection. Removed fire-and-forget co-activation writes; graph maintenance now stays inside the owning MCP tool lifecycle.
**Guards:** `tests/test_memory_persistence.py` includes a live MCP subprocess regression + static check that raw `self._conn.execute()` calls remain confined to `_initialize_schema()` and `_execute_query_sync()`. `scripts/verify/verify_e2e_tests.py` embeds the shutdown-race probe.
**Lesson:** Native database objects need a single owner. If you close Kuzu transaction-scoped, no Kuzu work may survive the tool call. Trace the full lifecycle (query start → background task → tool return → `finally` close), not the symptoms one by one.

## Issue #8: Graph and Session Schema Contract Drift [FIXED, guarded]

**Trigger:** `elefante-GraphConnect` fails creating `CREATED_IN` / `WORKS_ON` edges; `elefante-SessionsList` returns wrong shape.
**Root cause:** Both surfaces assumed every relation table and every session-shaped entity shared one generic schema. (1) `graph_store.py` reused `RELATES_TO`'s `strength` injection pattern for relations that don't define that property. (2) `server.py` queried sessions as `Entity` rows, then ordered by `s.last_active` (no such top-level field) and accessed properties as Python attributes instead of JSON in `props`.
**Solution:** Aligned both paths to the real schema — relation creation is whitelist-gated (`{"RELATES_TO"}` get `strength`, others don't); session listing orders by `created_at`, parses `props` JSON, falls back when `last_active` absent.
**Guards:** `TestGraphToolContract` creates real `CREATED_IN` and `WORKS_ON` edges + statically guards `SessionsList` query shape.
**Lesson:** Graph tools must target the concrete node and relation-table schema that exists, not a generic mental model. Code-review plausibility is not a substitute for live-surface verification.

## Issue #9: GraphQuery Write Boundary Bypass [BUG-029, FIXED, guarded]

**Trigger:** A client could send `CREATE`, `MERGE`, `SET`, or other mutations through `elefante-GraphQuery`, despite its retrieval-facing contract.
**Root cause:** Mutation filtering lived in the shared GraphStore method, which also powers trusted internal graph maintenance; its original keyword list was incomplete.
**Solution:** Keep GraphStore available to trusted internal operations and enforce a read-only Cypher validator at the external MCP GraphQuery boundary. Mutations use explicit `elefante-GraphConnect`.
**Guard:** `pytest tests/test_dashboard_serializer.py -k "graph_query_validator" -v`.
**Lesson:** Enforce capability policy at the client boundary; enforcing it in a shared internal primitive silently breaks legitimate maintenance work.

## Issue #10: Fresh Runner Test Required a Retired Chroma Directory [BUG-035, FIXED, guarded]

**Trigger:** PR #7 passed locally but failed on GitHub's clean runner because `~/.elefante/data/chroma` did not exist.
**Root cause:** A legacy path test asserted eager creation of `CHROMA_DIR`. SQLite is now the default, config creates the active vector directory while Kuzu owns its database path lazily, and the local machine's historical Chroma directory concealed the stale assertion.
**Solution:** Compare active vector and graph paths with the data root from the same configuration instance so test order cannot mix reloaded and module-default homes. Separately, run config loading in a subprocess with an isolated fresh home to prove the active SQLite directory is created without recreating retired Chroma state or pre-creating Kuzu.
**Guard:** `pytest tests/test_memory_persistence.py -k "config_paths_exist or fresh_home" -v`.
**Lesson:** Filesystem tests must include a clean-home proof. Persistent developer state can make obsolete path assumptions look valid indefinitely.

---

## Cross-bug pattern (extracted to `../lessons.md`)

1. **Read library changelogs before upgrading** — Issues #1, #3.
2. **Don't classify corruption from filesystem shape alone** — Issues #3, #4.
3. **Native objects need a single owner; cross-thread lifetimes are bugs** — Issue #7.
4. **Storage format ≠ domain model — always translate via helpers** — Issues #6, #8.
5. **Generic mental models of schemas hide concrete relation/property differences** — Issue #8.

Distill any new repeating rule into `../lessons.md`.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/database-full.md`](_archive/database-full.md).

This file (`database.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
