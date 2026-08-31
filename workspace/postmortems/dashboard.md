# Dashboard Postmortems

> **Domain:** Dashboard, visualization, snapshot pipeline.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson.
> **Historical note:** Some entries reference V3 concepts (`layer`, `sublayer`, `classifier.py`, importance 1-10) that have since been removed. The lessons survive; the referenced fields don't.

---

<a id="issue-1"></a>

## Issue #1: Kuzu Database Compatibility [FIXED]

**Trigger:** `RuntimeError: Database path cannot be a directory` on first dashboard launch after Kuzu 0.11.x upgrade.
**Root cause:** Same as database/installation #3 — Kuzu 0.11.x stopped tolerating pre-existing `kuzu_db/` directory. `config.py` was eagerly creating it.
**Solution:** Removed `KUZU_DIR.mkdir(exist_ok=True)` from `config.py`. Added `_parse_buffer_size()` for `'512MB'` → bytes conversion in `graph_store.py`.
**Lesson:** Version upgrades can break database formats. Always check changelogs.

<a id="issue-2"></a>

## Issue #2: Stats Display Showing Zero [FIXED]

**Trigger:** Dashboard shows "0 MEMORIES" despite 17 memories in store.
**Root cause:** Frontend reading the wrong API response field. API returned `{vector_store: {total_memories: 17}}`; frontend read `stats.total_memories` (undefined).
**Solution:** `App.tsx` line 36 reads `stats.vector_store.total_memories`.
**Lesson:** API working ≠ Dashboard working. Test the COMPLETE user experience — API in isolation passes while UI is broken.

<a id="issue-3"></a>

## Issue #3: Memory Labels Missing [FIXED]

**Trigger:** Green dots with no labels — user can't identify memories without hovering.
**Root cause:** Canvas only rendered labels on hover. Technical implementation worked; UX was broken.
**Solution:** `GraphCanvas.tsx` displays truncated labels (first 3 words) below each node by default; full description in tooltip on hover.
**Lesson:** Technical correctness ≠ user satisfaction. Ask "what does the user NEED to see?" before declaring a feature done.

<a id="issue-4"></a>

## Issue #4: Dashboard Shows 11 Instead of 71 [FIXED]

**Trigger:** The vector store had 71 memories but the dashboard showed an unrelated graph-node count.
**Root cause:** `update_dashboard_data.py` queried Kuzu entities instead of the configured vector store's memory records. Time was also spent debugging unused `graph_service.py` code.
**Solution:** The snapshot pipeline now reads memories through the configured vector-store path and relationships through Kuzu.
**Lesson:** Vector records are memories; Kuzu carries entities and relationships. Verify the data source and that the inspected code is actually used before debugging the data flow.

<a id="issue-5"></a>

## Issue #5: API Bypassed Snapshot File [FIXED]

**Trigger:** After Issue #4 fix, snapshot has 71 nodes but `/api/graph` still returns 17.
**Root cause:** `server.py /api/graph` endpoint queried Kuzu directly instead of reading the snapshot file. Producer was fixed; consumer still bypassed it.
**Solution:** Endpoint reads `dashboard_snapshot.json` only — no live Kuzu query in the request path.
**Lesson:** Fix BOTH producer AND consumer when debugging data flow. Trace data path end-to-end; never assume one fix propagates.

<a id="issue-6"></a>

## Issue #6: V3 Metadata Display — 6-Layer Bug Chain [FIXED, historical]

**Trigger:** All nodes show "FACT • General" / "5/10" importance despite varied V3 classification in DB.
**Root cause:** Six bugs hidden behind each other. (1) `classifier.py` only had 5 regex patterns → 90% defaulted to `world/fact`. (2) `VectorStore.add_memory()` missing `layer`/`sublayer` in metadata dict — never saved. (3) `_reconstruct_memory()` missing same fields — even if saved, never read back. (4) MCP server cached old code (12h running) — migration tool reported success but used unfixed code. (5) `GraphCanvas.tsx` colors read `n.full_data.props` instead of `n.properties`. (6) Same path mismatch in sidebar code.
**Solution:** Six sequential fixes — expanded classifier patterns; added `layer`/`sublayer` to add and reconstruct paths; standalone migration script bypassing MCP cache; fixed both color and sidebar property paths.
**Lesson:** Data flows through 8 layers (Classifier → add_memory → ChromaDB → reconstruct → Snapshot → API → Frontend → Sidebar). Verify at EACH layer, not just endpoints. When fixing property paths, grep for ALL occurrences. Long-running servers cache imports — restart after code changes. **V3 fields no longer exist; the methodology rule survives.**

<a id="issue-7"></a>

## Issue #7: Phantom Dashboard — Daemon Thread Vaporized on MCP Exit [FIXED]

**Trigger:** Agent reports "Dashboard opened at http://localhost:8000". User sees blank screen or `ERR_CONNECTION_REFUSED`.
**Root cause:** Dashboard launched via `serve_dashboard_in_thread(port=port)` as a daemon thread. MCP clients (like Agent Zero) often spin up `src.mcp.server` for a single tool call and close stdio when done. Daemon threads die instantly with the parent process — the dashboard vaporized as soon as the MCP transient process exited.
**Solution:** `_start_dashboard_and_open()` launches dashboard as detached background subprocess: `subprocess.Popen([sys.executable, "-m", "src.dashboard.server"], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)`.
**Lesson:** Never bind long-living HTTP servers to daemon threads inside a transient/stateless worker process. Always detach into a true subprocess.

<a id="issue-8"></a>

## Issue #8: Persistent Blank Dashboard on First Launch [BUG-003, FIXED, guarded]

**Trigger:** `elefante-DashboardOpen(refresh=true)` — agent reports correct counts, browser shows blank white page, server is running.
**Root cause:** Two compounding bugs. (a) **Race:** `subprocess.Popen` returned before Uvicorn bound to port 8000. `webbrowser.open()` fired immediately; first request got error; React rendered blank root permanently. (b) **Stale server on refresh:** when `refresh=true`, snapshot was updated on disk but the long-running server process was NOT restarted. `is_running` check found the old server alive, skipped Popen, served stale data.
**Solution:** (1) `_wait_for_ready(max_wait=5.0)` polls `/health` before opening browser. (2) `force_restart=True` (set when `refresh=true`) kills existing server (`lsof -ti :8000 | xargs kill`) before reopening.
**Guard:** `tests/test_dashboard_serializer.py -k "dashboard"` verifies readiness wait + force-restart + frontend retry/backoff.
**Lesson:** Never open the browser before the server is ready. When refreshing data, restart the server — a stale process cannot serve a new snapshot without restart.

<a id="issue-9"></a>

## Issue #9: All Dashboard Scores Stuck at 100 [BUG-004, FIXED structurally]

**Trigger:** Almost all dashboard memory scores show 100. Average 94.6. Real computed scores should range 54-94 with avg ~75.
**Root cause:** **Three independent code paths built dashboard nodes with different scoring logic.** (1) MCP server `_refresh_dashboard_snapshot()` read `mem.metadata.score` (stale stored value, set at creation, only updated on retrieval — most memories never retrieved → stays 100 forever). (2) Standalone `update_dashboard_data.py` had a correct `_compute_live_score()` but as a local duplicate. (3) Dashboard API just served whatever wrote the snapshot last.
**Solution:** Single source of truth — `src/utils/dashboard_serializer.py` exports `compute_live_score(mem)`, `compute_live_score_from_raw(meta)`, and `memory_to_dashboard_node(mem)`. MCP server and standalone script both import from this module; ~50 LOC of inline serialization deleted from `server.py`. Verified: 0 memories at score 100, avg 75.3, min 54, max 94.
**Guard:** `pytest tests/test_dashboard_serializer.py -v`.
**Lesson:** Never trust stored scores. Scores are derived values — always compute them live from behavioral signals. Enforce this architecturally via a single shared serializer; documentation and rules are not enough when three code paths can drift.

<a id="issue-10"></a>

## Issue #10: Dashboard Private Data Exposure [BUG-028, FIXED, guarded]

**Trigger:** Dashboard API endpoints return memory content, metadata, and graph data while the server bound `0.0.0.0` and accepted wildcard CORS; Docker published port 8000 on every host interface.
**Root cause:** Local development defaults were treated as deployment defaults without an explicit privacy boundary.
**Solution:** Default to `127.0.0.1`, allow only explicit local CORS origins, constrain request bounds, and publish Docker Compose to `127.0.0.1:8000`. Any reverse-proxy deployment must configure its origin allowlist and authentication explicitly.
**Guard:** `pytest tests/test_dashboard_serializer.py -k "loopback or cors" -v`.
**Lesson:** A dashboard that can return private memories is a private service by default, not a public API with optional hardening.

<a id="issue-11"></a>

## Issue #11: Dashboard Live-Store and Browser-Mutation Bypass [BUG-031, FIXED, guarded]

**Trigger:** The dashboard was documented as a read-only snapshot viewer, but `/api/graph` hydrated values from ChromaDB, `/api/search` performed live semantic retrieval, and `/api/refresh` spawned the snapshot pipeline from a browser POST.
**Root cause:** The snapshot boundary was applied to the main graph response but not to adjacent convenience features. The resulting process could contend with the singleton daemon and gave a browser surface unnecessary mutation authority.
**Solution:** All dashboard reads now use only `dashboard_snapshot.json`; search is explicitly lexical over its redacted content. The browser refresh route was removed and its control now reloads the current snapshot. Regeneration remains an explicit MCP `DashboardOpen(refresh=true)` or operator CLI action.
**Guard:** `tests/test_dashboard_serializer.py` executes snapshot graph/search/stats responses and verifies no live-store import or browser refresh route remains; production UI build passes.
**Lesson:** A read-only inspection boundary applies to every convenience endpoint, not only the primary page load. Browser UI should never gain database authority merely to make refresh convenient.

<a id="issue-12"></a>

## Issue #12: Orphaned/Stale Dashboard Process from Trashed Directory [BUG-033, FIXED, guarded]

**Trigger:** Browser requests to `http://127.0.0.1:8000/api/graph` returned `HTTP 500 Internal Server Error` even though the active workspace data snapshot was valid and test suite passed.
**Root cause:** A stale Python dashboard process (PID 7219) spawned from a previously trashed repository path (`/Users/jay/.Trash/elefante`) remained listening on port 8000. When browser or curl requests hit port 8000, the stale process handled them against its missing/trashed dependencies rather than reading the active workspace's configuration and snapshot.
**Solution:** Terminated the stale process (`kill -9 7219`), regenerated the data snapshot (`python scripts/pipeline/update_dashboard_data.py`), and launched the active workspace server (`.venv/bin/python -m src.dashboard.server`). Hardened `src/dashboard/server.py` node property formatting against `None` values and added process CWD verification checks.
**Guard:** `pytest tests/test_dashboard_serializer.py -k "null_name or graph" -v`.
**Lesson:** When diagnosing port binding issues or HTTP 500 errors, verify the running process's CWD (`lsof -p <PID> | grep cwd`) to ensure port ownership belongs to the active workspace rather than an orphaned daemon from a trashed or moved folder.

<a id="issue-13"></a>

## Issue #13: Dashboard Header Emblem Was Clipped [BUG-034, FIXED, guarded]

**Trigger:** The live header showed a copper block-like fragment instead of the complete Elefante symbol.
**Root cause:** The exported mask asset contained only the left portion of the elephant. Source-shape review was mistaken for final-size composition review.
**Solution:** Replaced it with the complete elephant-and-network crop from the repository's canonical logo, corrected the network-only hover clip, and locked the PNG dimensions and digest in the dashboard regression test.
**Guard:** `pytest tests/test_dashboard_serializer.py -k "brand_assets" -v`, dashboard production build, and live-header inspection.
**Lesson:** Brand-asset acceptance happens in the final rendered composition. Inspect the actual pixels at shipping size; source provenance alone does not prove an export is complete.

<a id="issue-14"></a>

## Issue #14: Home Graph Hydration Assumed One Kuzu Row Shape [BUG-064, FIXED locally]

**Trigger:** The real Elefante-on-Elefante Home refresh logged `'dict' object has no attribute 'id'`. The snapshot still contained derived topic connections, so the Connections surface could look healthy while real Kuzu entities and labels were absent.
**Root cause:** Both snapshot producers assumed that `RETURN n` yielded a model object and that `LABEL(r)` appeared under the literal key `label(r)`. The installed Kuzu driver returns entity mappings and a generated label key; the broad live-refresh exception converted that contract drift into a silent partial snapshot.
**Solution:** Normalize Kuzu entities and relationship labels through shared serializer helpers used by both snapshot producers. Preserve only visible entity properties, accept the supported driver result shapes, and emit graph edges only when both normalized endpoints exist.
**Guard:** `pytest tests/test_dashboard_serializer.py tests/test_verified_remember.py -q`; an isolated current-driver query must hydrate without the mapping-attribute error.
**Lesson:** A populated visualization is not proof that every authoritative source was projected. Exercise driver-native row shapes and reject partial graph output that can be masked by derived edges.

---

## Cross-bug pattern (extracted to `../lessons.md`)

1. **API working ≠ UI working** — test the complete user experience. Issues #2, #4, #5.
2. **Verify data source before debugging data flow** — wrong store assumption wastes hours. Issue #4.
3. **Fix BOTH producer AND consumer in any data pipeline** — partial fixes drift. Issues #5, #9.
4. **Long-running servers cache imports** — restart after code changes; migration tools may report success while using stale bytecode. Issue #6.
5. **Single source of truth for derived values** — three code paths producing the "same output" eventually drift. Issue #9.
6. **Detach long-lived servers into subprocesses, never daemon threads** — daemon threads die with their transient parent. Issue #7.
7. **Exercise driver-native result shapes, not only friendly fakes** — partial graph hydration can hide behind derived visualization data. Issue #14.

Distill any new repeating rule into `../lessons.md`.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/dashboard-full.md`](_archive/dashboard-full.md).

This file (`dashboard.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
