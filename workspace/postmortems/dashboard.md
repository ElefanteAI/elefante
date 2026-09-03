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

<a id="issue-15"></a>

## Issue #15: Direct Home Mistook Authorization Transport for Product Setup [BUG-069, FIXED + installed candidate]

**Trigger:** The customer typed `http://localhost:8000` for a healthy installed Elefante with one active project. Home showed `Setup required`, could not verify health, and instructed the customer to return to an agent and request a different secret URL.
**Root cause:** The UI equated “no capability fragment” with “product not set up.” `DashboardOpen` was the only path that minted a control capability and supplied daemon/project context, while the always-on daemon did not own the dashboard process. A security implementation detail therefore became the customer onboarding model.
**Solution:** Make port 8000 the stable loopback customer entry point. The daemon starts Home, the snapshot server advertises only the configured loopback daemon port, and the trusted local Home origin requests one bounded in-memory capability directly. Bind exactly one active project automatically; require an explicit choice when scope is ambiguous. Keep every named operation behind the existing expiry, request-limit, preview, confirmation, one-use ticket, exact-hash, verification, and rollback gates. Ship every installer-called verifier in the customer allowlist, and preserve the certified host executable path in the daemon service so shell health and Home health see the same environment. If the daemon is unavailable, preserve snapshot inspection and report `Needs attention` instead of fake setup work.
**Follow-up acceptance:** Exercising the HTML guide against an isolated live Home exposed stale post-restore client state. A verified restore now clears stale memory selection and awaits the refreshed snapshot before returning its receipt; the browser immediately shows the restored count and omits the post-backup marker without a page reload.
**Lesson:** Authentication transport is not onboarding. A local product URL must explain product state directly; IDEs and agents may provide context, but they cannot be required merely to enter the product. Preserve security at the action boundary, not by making the whole opening screen look broken. Runtime health is also environment-bound: a service is not ready merely because the same doctor passes from an interactive shell.

<a id="issue-16"></a>

## Issue #16: Dashboard Confused Capability, Evidence, and Product Workflow [BUG-070, FIXED locally]

**Trigger:** A first-time user saw a dominant attention state, unverified cards,
controls that did not produce receipts, and large narrative panels whose claims
were not bound to a real Recall event. Moving between local dashboard processes
was then explained as if it were a customer journey, while the actual Elefante
value remained unclear.

**Root cause:** Home used service/session readiness as its information
architecture. It treated missing operational evidence as product failure,
capability as readiness, and a heuristic inventory focus as task evidence. The
same developed ideas were repeated on Home instead of being owned by their
authoritative workspaces. Transport mechanics escaped into product language.

**Solution:** Lock one purpose—make governed memory useful for the next task—and
organize the dashboard around three operator jobs: Global understanding, Task
intelligence, and Continuity. Show snapshot facts and operation receipts as
different evidence classes. Keep overall inspection project-free; require a
project only for task-scoped Recall or durable changes. Claim Recall value only
inside an actual result receipt. Put review priority in Memory Intelligence,
stored vitality and explicit trails in Connections, and lifecycle proof in
Recover. Keep host, port, and launch origin invisible as product concepts.

**Follow-up recurrence:** Live use on 2026-09-02 proved that the dominant
`Review N direct signals` action changed workspaces but left Memory Intelligence
on Library; verified Remember refreshed the graph but not the header statistics;
and connected control, Session Intelligence, Connections, and package
maintenance still looked more capable than their evidence allowed. Route the
recommendation to the actual Review subview, refresh all represented snapshot
statistics after verified Remember, name control connectivity without claiming
operation completion, and label view-only or installer-owned surfaces directly.
Snapshot search also fell back to the browse list when it found zero matches.
Select search rows by search mode alone; an empty result must stay empty until
the query is cleared.

The subsequent live audit found two more evidence-presentation defects. Recover's
disconnected early return hid the expired-session error and falsely said no
recovery check had run. Keep the actual error visible there and offer an explicit
session reconnect, without replaying a mutation or relaxing expiry/confirmation
gates. Retrieval Explanation read content provenance (`source`) under the
Storage source label; read only `storage_backend`, with an honest missing-value
fallback. Shared authenticated requests now invalidate the same session state
on expiry or request exhaustion, never replaying an operation. Recall keeps
page-only question/result state across tab inspection, invalidates old results
on new input or snapshots, and clears it on a project change. A real expired
archive plan changed no data; the open memory drawer covered the reconnect
button, so that banner now renders above the drawer and below modal dialogs.
Regressions cover these paths; browser acceptance exercises real expired
sessions, changed Recall eligibility, and differing provenance/backend values.

**Graph recurrence, 2026-09-03:** Curating a small real memory set exposed a
branching-graph defect hidden by the earlier linear showcase. The renderer
placed arrows between consecutive sorted cards even when no edge joined them,
and could reverse a stored edge's direction. Cards now remain selectable without
implied adjacency; relationship rows render each actual source, label, and
target. A regression renders the real React component with branches, cycles,
parallel labels, reordered edges, and excluded semantic/dangling edges.
The installed 499×694 panel also exposed a 460-pixel graph inside a
226-pixel clipped parent, leaving only 34 pixels of its detail scroller visible.
The graph now fits its parent: one vertical scroll surface in narrow panels,
with the existing split scroll layout retained on wide screens.

**Guard:** Dashboard, snapshot, Home-control, daemon, and routing regressions;
the production UI build; and live deterministic-example acceptance across all
six workspaces, both themes, desktop, and 390×844.

**Lesson:** Capability is not readiness, invocation is not completion, and
transport is not product hierarchy. Stronger evidence usually requires fewer
authoritative panels, not more status cards. Preserve developed ideas by giving
each one a real evidence owner instead of duplicating it on Home.

---

## Cross-bug pattern (extracted to `../lessons.md`)

1. **API working ≠ UI working** — test the complete user experience. Issues #2, #4, #5.
2. **Verify data source before debugging data flow** — wrong store assumption wastes hours. Issue #4.
3. **Fix BOTH producer AND consumer in any data pipeline** — partial fixes drift. Issues #5, #9.
4. **Long-running servers cache imports** — restart after code changes; migration tools may report success while using stale bytecode. Issue #6.
5. **Single source of truth for derived values** — three code paths producing the "same output" eventually drift. Issue #9.
6. **Detach long-lived servers into subprocesses, never daemon threads** — daemon threads die with their transient parent. Issue #7.
7. **Exercise driver-native result shapes, not only friendly fakes** — partial graph hydration can hide behind derived visualization data. Issue #14.
8. **Authentication transport is not onboarding** — keep the stable local entry point independent of agents and enforce authority at named actions. Issue #15.
9. **Capability is not readiness; transport is not product hierarchy** — organize the dashboard by operator job and show a claim only where its authoritative evidence exists. Issue #16.

Distill any new repeating rule into `../lessons.md`.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/dashboard-full.md`](_archive/dashboard-full.md).

This file (`dashboard.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
