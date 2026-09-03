# Database Postmortems

> **Domain:** Kuzu graph database and the configured vector store (SQLite by
> default; legacy ChromaDB only when explicitly configured).
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson.

---

<a id="issue-1"></a>

## Issue #1: Reserved Word Collision [FIXED]

**Trigger:** Entity creation fails with `RuntimeError: Binder exception: Cannot find property properties for e.`
**Root cause:** Kuzu uses hybrid SQL/Cypher syntax. `properties` is valid as a column name in `CREATE NODE TABLE` (SQL) but is a reserved word in Cypher data operations. Schema creation succeeded; data inserts failed.
**Solution:** Renamed column `properties` → `props` in `src/core/graph_store.py` schema definition.
**Lesson:** Kuzu uses hybrid syntax. Test BOTH schema AND data operations against new column names — schema acceptance is not sufficient.

<a id="issue-2"></a>

## Issue #2: Database Lock Persistence [FIXED, guarded]

**Trigger:** Second live process attempts to open Kuzu while another process owns the path. `RuntimeError: Kuzu database is locked by another process.`
**Root cause:** Kuzu access is single-owner across live processes. `read_only=True` does not enable cross-process sharing; it's for short-lived export/snapshot work. Old recovery guidance suggested deleting Kuzu's internal lockfile manually — wrong mental model.
**Solution:** (1) Dashboard reads on `dashboard_snapshot.json`, never live Kuzu. (2) Snapshot export runs in short-lived subprocess with `GraphStore(..., read_only=True)`. (3) Global `GraphStore` released after each MCP tool call so Kuzu ownership stays transaction-scoped. (4) On contention, stop the competing process or wait for the current transaction; do NOT delete Kuzu's internal lockfile as a default recovery step.
**Lesson:** Model Kuzu contention as short-lived process ownership, not as manual surgery on Kuzu's internal lockfile. `read_only=True` is for short-lived snapshot work, not a promise of live cross-process sharing.

<a id="issue-3"></a>

## Issue #3: Database Path Format Change [FIXED]

**Trigger:** `RuntimeError: Database path cannot be a directory: ~/.elefante/data/kuzu_db`. Same as installation Issue #1 — Kuzu 0.11.x breaking change.
**Root cause:** Kuzu 0.11.x changed path semantics — database path cannot pre-exist as a directory. `config.py` was calling `KUZU_DIR.mkdir(exist_ok=True)` on import.
**Solution:** Removed eager `mkdir` from `config.py`. `src/core/graph_store.py` only creates the parent directory and removes legacy empty `kuzu_db/` directories before letting Kuzu materialize its own path (now a file under current contract).
**Lesson:** Kuzu owns the database path. Never infer the final on-disk shape from old versions.

<a id="issue-4"></a>

## Issue #4: Legacy Path-Shape Diagnosis Drift [FIXED, guarded]

**Trigger:** Operators see `~/.elefante/data/kuzu_db` as a single file under current Kuzu contract; stale docs and destructive scripts treat that as corruption.
**Root cause:** Filesystem-shape assumptions drifted after the runtime contract changed in Issue #3. `kuzu_db` was historically a directory tree; new contract materializes it as a file. The stale "file = corruption" assumption spread across tests, docs, and debug tools.
**Solution:** (1) Guard the fresh path contract in maintained tests (`TestKuzuLockContract`). (2) Remove file-is-corruption logic from docs and destructive scripts. (3) Reset the Kuzu path only when init actually fails or data is known-bad.
**Lesson:** Never classify corruption from filesystem shape alone. Verify the current runtime contract from source and a fresh init first.

<a id="issue-5"></a>

## Issue #5: Duplicate Entity Creation [DOCUMENTED, design limitation]

**Trigger:** Same logical entity ("User Approval Protocol") appears with multiple UUIDs across sessions.
**Root cause:** `entity_id = str(uuid.uuid4())` on every memory analysis — no existence check before creation. Each analysis spawns fresh entity rows.
**Solution (not yet implemented):** `find_entity_by_name(name, type)` lookup before insert; reuse existing ID if found. Requires fuzzy name matching for typos/variations.
**Lesson:** Entity deduplication requires fuzzy matching. Current impact is visualization-only — defer until usage demands it.

<a id="issue-6"></a>

## Issue #6: Legacy ChromaDB Schema vs Memory Model [DOCUMENTED]

**Trigger:** ChromaDB queries returning unexpected types or missing fields.
**Root cause:** ChromaDB stores all 40+ memory fields flat in `metadata` dict; the Memory model expects typed direct attributes (`memory.score`, `memory.domain`). Direct `result["metadata"]["score"]` access is fragile across versions.
**Solution:** Current callers use the configured store's Memory-returning API;
the legacy adapter reconstructs records through
`VectorStore._reconstruct_memory()`. Do not parse backend metadata in callers.
**Lesson:** Always translate between storage format and domain objects at the
adapter boundary. Direct metadata access bypasses type coercion and breaks on
field renames.

<a id="issue-7"></a>

## Issue #7: Async Shutdown Race / QueryResult Lifetime Leak [BUG-001, FIXED, guarded]

**Trigger:** Native SIGSEGV in `kuzu::main::QueryResult::~QueryResult()` or `kuzu::main::Database::~Database()` during MCP tool teardown.
**Root cause:** Three layers. (1) `src/core/graph_store.py` executed `self._conn.execute(...)` in `asyncio.to_thread(...)` but iterated the returned `QueryResult` on the event-loop thread — native lifetime escaped the worker thread. (2) `src/mcp/server.py` launched `record_coactivation(...)` via `asyncio.create_task(...)` then unconditionally called `close_graph_store()` in `finally` — background work could outlive close. (3) `GraphStore` had a thread-safety lock but never used it to serialize the shared `kuzu.Connection`.
**Solution:** Safe Kuzu boundary — `_execute_query_sync()` materializes rows inside the worker thread under `self._lock`; `close()` waits for `_active_operations` to drain before destroying the connection. Removed fire-and-forget co-activation writes; graph maintenance now stays inside the owning MCP tool lifecycle.
**Guards:** `tests/test_memory_persistence.py` includes a live MCP subprocess regression + static check that raw `self._conn.execute()` calls remain confined to `_initialize_schema()` and `_execute_query_sync()`. `scripts/verify/verify_e2e_tests.py` embeds the shutdown-race probe.
**Lesson:** Native database objects need a single owner. If you close Kuzu transaction-scoped, no Kuzu work may survive the tool call. Trace the full lifecycle (query start → background task → tool return → `finally` close), not the symptoms one by one.

<a id="issue-8"></a>

## Issue #8: Graph and Session Schema Contract Drift [PARTIAL, recurrence open]

**Trigger:** `elefante-GraphConnect` fails creating `CREATED_IN` / `WORKS_ON` edges; `elefante-SessionsList` returns wrong shape.
**Root cause:** Both surfaces assumed every relation table and every session-shaped entity shared one generic schema. (1) `graph_store.py` reused `RELATES_TO`'s `strength` injection pattern for relations that don't define that property. (2) `server.py` queried sessions as `Entity` rows, then ordered by `s.last_active` (no such top-level field) and accessed properties as Python attributes instead of JSON in `props`.
**Solution:** Aligned both paths to the real schema — relation creation is whitelist-gated (`{"RELATES_TO"}` get `strength`, others don't); session listing orders by `created_at`, parses `props` JSON, falls back when `last_active` absent.
**Guards:** `TestGraphToolContract` creates real `CREATED_IN` and `WORKS_ON` edges + statically guards `SessionsList` query shape.
**Open recurrence, source audit 2026-09-03:** The public enum is broader than
the named relationship-table mapping. For example, `GOVERNS` is accepted but
stored as `RELATES_TO`; returned edge properties are not persisted. Existing
UUID syntax is checked without proving that both graph rows exist. This audit
did not write unsupported relationships to customer data. The curated dashboard
example uses `DEPENDS_ON`, with both endpoints and all three stored edges read
back. Close this separate authoring gap only with real isolated type/property
round-trip and absent-endpoint tests; the dashboard-rendering repair does not
claim to fix it.
**Lesson:** Graph tools must target the concrete node and relation-table schema that exists, not a generic mental model. Code-review plausibility is not a substitute for live-surface verification.

<a id="issue-9"></a>

## Issue #9: GraphQuery Write Boundary Bypass [BUG-029, FIXED, guarded]

**Trigger:** A client could send `CREATE`, `MERGE`, `SET`, or other mutations through `elefante-GraphQuery`, despite its retrieval-facing contract.
**Root cause:** Mutation filtering lived in the shared GraphStore method, which also powers trusted internal graph maintenance; its original keyword list was incomplete.
**Solution:** Keep GraphStore available to trusted internal operations and enforce a read-only Cypher validator at the external MCP GraphQuery boundary. Mutations use explicit `elefante-GraphConnect`.
**Guard:** `pytest tests/test_dashboard_serializer.py -k "graph_query_validator" -v`.
**Lesson:** Enforce capability policy at the client boundary; enforcing it in a shared internal primitive silently breaks legitimate maintenance work.

<a id="issue-10"></a>

## Issue #10: Fresh Runner Test Required a Retired Chroma Directory [BUG-036, FIXED, guarded]

**Trigger:** PR #7 passed locally but failed on GitHub's clean runner because `~/.elefante/data/chroma` did not exist.
**Root cause:** A legacy path test asserted eager creation of `CHROMA_DIR`. SQLite is now the default, config creates the active vector directory while Kuzu owns its database path lazily, and the local machine's historical Chroma directory concealed the stale assertion.
**Solution:** Compare active vector and graph paths with the data root from the same configuration instance so test order cannot mix reloaded and module-default homes. Separately, run config loading in a subprocess with an isolated fresh home to prove the active SQLite directory is created without recreating retired Chroma state or pre-creating Kuzu.
**Guard:** `pytest tests/test_memory_persistence.py -k "config_paths_exist or fresh_home" -v`.
**Lesson:** Filesystem tests must include a clean-home proof. Persistent developer state can make obsolete path assumptions look valid indefinitely.

<a id="issue-11"></a>

## Issue #11: MCP Write Lock Ended Before Graph and Queue Mutations [BUG-057, FIXED LOCALLY, guarded]

**Trigger:** A Gauntlet event-order regression observed the transaction-scoped write lock exit before `GraphConnect` called entity creation. The same source shape existed in `ETLProcess`, whose raw-memory fetch marks rows as processing after its lock had already ended.
**Root cause:** The handlers used the lock as an admission check rather than as ownership of the complete mutating lifecycle. Acquiring and immediately leaving the context manager proved only that the store was momentarily available; it did not serialize the writes that followed.
**Solution:** Keep GraphConnect's lock through every entity and relationship write. Keep ETLProcess's lock through the queue-state transition and related stats read. Render optional system status only after the graph write lock is released so read-only reporting does not expand native database ownership.
**Guard:** `pytest tests/test_mcp_daemon.py -k "graph_connect_scrubs or etl_process_scrubs" -q` records context-manager entry, mutation, and exit order and fails if writes escape the lock again.
**Lesson:** A transaction lock must own the mutation, not merely precede it. Event-order tests are the shortest proof that context-manager scope matches the actual write lifecycle.

<a id="issue-12"></a>

## Issue #12: Kuzu-Only Reset Ignored Configuration and Claimed a Rebuild [BUG-058, FIXED LOCALLY, guarded]

**Trigger:** A Gauntlet regression supplied an isolated configuration and expected only its temporary graph path to move. The script ignored that configuration and moved the real default `~/.elefante/data/kuzu_db` instead, proving the destructive target bug. The exact timestamped backup was moved back immediately; daemon health and installed `doctor` then returned customer-ready with all configured hosts and 17 tools. No memory contents were inspected.
**Root cause:** The privileged script hard-coded `Path.home()/.elefante/data/kuzu_db` instead of resolving the running configuration. Its headers and active operator docs also claimed it rebuilt topology from a legacy Chroma store, but no reconstruction code existed. The initial regression failed to make its apply target safe before invoking the known-stale implementation. The first repair then treated configuration as authority for any external directory after only the generic `DELETE` confirmation.
**Solution:** Reuse the config-only storage resolver, show the exact configured graph target in dry-run, preserve the vector path, and move the graph into `<configured-data>/backups/kuzu_reset` only after privilege and confirmation gates. Reject filesystem-root, home, data-root, vector, and recovery ancestors. Any graph path outside the configured data root additionally requires `--confirm-path` to match the exact resolved dry-run target. State explicitly that next initialization is empty and no automatic rebuild occurs.
**Guard:** `pytest tests/test_backup_restore.py -k "kuzu_only_reset" -q` uses temporary custom graph paths, proves dry-run no-op, exact external-target confirmation, broad-directory rejection, apply recovery, vector preservation, and truthful output. The test cannot reach the user's default path because the implementation resolves its isolated config first.
**Lesson:** A destructive regression must isolate the target before exercising apply, even when the purpose is to prove that target resolution is broken. Configuration is target discovery, not sufficient destructive authority; broad and external paths need separate fail-closed validation.

<a id="issue-13"></a>

## Issue #13: Restore Integrity Check Mutated the Staged Manifest [BUG-068, FIXED LOCALLY, guarded]

**Trigger:** Home restored a verified backup whose SQLite database used WAL journal mode. Archive readback, staged manifest, SQLite, and Kuzu checks passed, but the active manifest immediately failed and Elefante rolled the exact previous data back.
**Root cause:** SQLite opened with `mode=ro` can still create `-wal` and `-shm` sidecars for a WAL-mode database. The staged manifest was compared before the integrity connection opened, so verification changed the tree after declaring it exact. The atomic switch then correctly exposed the extra files as `MANIFEST_MISMATCH`.
**Solution:** Open frozen staged SQLite files with `mode=ro&immutable=1`, which performs `PRAGMA quick_check` without creating sidecars. Compare the complete data manifest both before and after all SQLite/Kuzu integrity checks. Any validator side effect now fails while data is still staged, before the active directory switch. The existing safety backup and exact rollback remain unchanged.
**Guard:** `pytest tests/test_verified_recovery.py -q` includes a real WAL archive and an adversarial mutating integrity checker. Isolated Home acceptance additionally creates a post-backup marker, restores the earlier archive, confirms `Restore verified`, reloads 14 rather than 15 memories, proves the marker question returns no applicable memory, and proves the restored decision is recalled.
**Lesson:** Verification must be observational. Hash both sides of any validator that can touch a durable tree, especially before an atomic restore switch.

---

## Cross-bug pattern (extracted to `../lessons.md`)

1. **Read library changelogs before upgrading** — Issues #1, #3.
2. **Don't classify corruption from filesystem shape alone** — Issues #3, #4.
3. **Native objects need a single owner; cross-thread lifetimes are bugs** — Issue #7.
4. **Storage format ≠ domain model — always translate via helpers** — Issues #6, #8.
5. **Generic mental models of schemas hide concrete relation/property differences** — Issue #8.
6. **Lock scope must contain the write lifecycle** — entering a lock before a mutation is not protection if the context exits first. Issue #11.
7. **Isolate and validate destructive targets before apply** — never let a fail-first test inherit a real durable default; reject broad paths and require exact confirmation for external configured storage. Issue #12.
8. **Verification must not mutate the thing it verifies** — compare durable manifests before and after database checks, and fail before switching live data. Issue #13.

Distill any new repeating rule into `../lessons.md`.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/database-full.md`](_archive/database-full.md).

This file (`database.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
