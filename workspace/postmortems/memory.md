# Memory System Postmortems

> **Domain:** Memory storage, retrieval, scoring, ETL, schema evolution.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md). Full pre-distillation narrative preserved verbatim in [`_archive/memory-full.md`](_archive/memory-full.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson.

---

<a id="issue-1"></a>

## Issue #1: Partial Memory Export [FIXED]

**Trigger:** User has 71 memories; export returns only 3-10.
**Root cause:** Default `min_similarity=0.5` filters memories below the threshold during export. Export is not a search-time question — it should not apply retrieval-time relevance filters.
**Solution:** Use `scripts/pipeline/export_memories.py`, which reads every
record from the configured vector-store adapter without a retrieval threshold.
**Lesson:** Retrieval thresholds belong on retrieval. Export must not silently discard data.

<a id="issue-2"></a>

## Issue #2: Wrong Data Store Queried [FIXED]

**Trigger:** Dashboard / report shows an entity count while the user expects a memory count. Same as dashboard #4.
**Root cause:** Code queried Kuzu entities when it needed records from the configured vector store.
**Solution:** Use the configured vector-store API for memory operations and the graph-store API for relationship operations.
**Lesson:** Vector records are memories; Kuzu nodes and edges represent entities and relationships. Verify the intended data source before debugging the data flow.

**Structured-search recurrence (BUG-073, 2026-09-03):** The search plan held
filters that the graph path discarded; it also queried `m.memory_type` although
that metadata lives in JSON or the authoritative vector record. Filtering an
oversampled first page still falsely omitted later matches. The correction
hydrates each record, applies its complete metadata contract, and reads stable
bounded graph pages until the requested qualifying count or end. A regression
places the sole matching record eleventh with a requested limit of one. Scope,
tags, date, score and related-entity tests verify meaning, not just nonempty output.
The legacy Chroma wrapper also distinguishes an explicit zero threshold from
an absent setting and filters before list pagination. Its nearest-neighbor
search still uses a bounded candidate window; fresh customers use SQLite.

<a id="issue-3"></a>

## Issue #3: Memory Not Used for Decision Making [DOCUMENTED, behavioral]

**Trigger:** Agent retrieves memory ("Project Hydro uses gRPC") then makes architectural decision contradicting it.
**Root cause:** Same root failure class as ai-behavior #4 — retrieval ≠ application. Reading memories without enforcing compliance becomes performative.
**Solution:** Layer 4 Memory Compliance Verification — list retrieved memory IDs, identify applicable rules, state how response follows each, refuse if action violates memory.
**Lesson:** Retrieved memory must be APPLIED, not just acknowledged. (Cross-bug with ai-behavior #4.)

<a id="issue-4"></a>

## Issue #4: Temporal Decay Implementation Failure [FIXED]

**Trigger:** Agent claims temporal decay shipped; tests reveal merge-conflict markers, missing `aiosqlite` dependency, invalid enum values from LLM output.
**Root cause:** Premature completion claims (cross-bug with ai-behavior #2). "Implemented" used without verification.
**Solution:** Mandatory 4-phase verification before "done": syntax (no merge markers, `py_compile`), dependencies (imports), functionality (execute), real data (test with user's actual memories).
**Lesson:** Temporal decay or any scoring formula change must round-trip through the actual function in `src/`, not just docs. (Five Gates Gate 4 — Numeric Verification.)

<a id="issue-5"></a>

## Issue #5: Legacy ChromaDB Memory Schema Mismatch [DOCUMENTED]

**Trigger:** Code accesses `memory.metadata.score` directly; ChromaDB stores all 40+ fields flat in `metadata` dict.
**Root cause:** Same as database #6 — storage format ≠ domain model. Direct field access is fragile across versions.
**Solution:** Keep translation inside the backend adapter. Current callers use
Memory objects; the legacy ChromaDB adapter reconstructs them through
`VectorStore._reconstruct_memory()`.
**Lesson:** Translate between storage format and domain objects via model helpers. (Cross-bug with database #6.)

<a id="issue-6"></a>

## Issue #6: V3 Layer Metadata Not Persisting [HISTORICAL — V3 fields removed]

**Trigger:** Classifier returns correct `layer`/`sublayer`; ChromaDB shows `null` after write/read cycle.
**Root cause:** Three-layer write/read mismatch — `add_memory()` didn't include `layer`/`sublayer` in metadata dict; `_reconstruct_memory()` didn't read them back; long-running MCP server cached old code so migration tool reported success but used unfixed bytecode.
**Solution:** Added explicit `layer`/`sublayer` fields to `add_memory()` and `_reconstruct_memory()`; built standalone migration script bypassing MCP cache.
**Lesson:** When a field doesn't persist, check BOTH write AND read paths AND server import cache. Long-running servers cache imports — restart after code changes. **V3 fields no longer exist; the methodology rule survives.** (Cross-bug with dashboard #6.)

<a id="issue-7"></a>

## Issue #7: `elefante-Memory(action="search")` Response Bloat [FIXED]

**Trigger:** A single memory-search response could exceed 10K tokens of overhead — full memory objects with all 40+ fields, raw embeddings, and internal IDs.
**Root cause:** `_handle_search_memories` returned every `SearchResult` with full memory object, no field projection. Most fields are decision-irrelevant for retrieval-time use.
**Solution:** Token-budgeted projection returns only the fields needed for
retrieval. `elefante-Memory(action="search", list_all=true)` provides compact
inspection; the read-only export script is the supported full-corpus analysis
path. `signal_ratio` was added to `TOKEN_STATS`.
**Lesson:** Default to minimal projection at retrieval boundaries. Full payloads on demand, not by default. Signal-per-token is a hard constraint, not aesthetic.

<a id="issue-8"></a>

## Issue #8: Low Similarity Scores for Exact Matches [FIXED]

**Trigger:** Topic-relevant memories return similarity 0.37-0.39 (barely above default `min_similarity=0.3`); expected 0.7+.
**Root cause:** `score_candidate` in `src/core/retrieval.py` had broken composite weighting — vector similarity was normalized incorrectly relative to other signals (concept overlap, co-activation, authority, temporal). Vector signal got drowned by zero-valued auxiliary signals.
**Solution:** Smoothed vector baseline + signal independence — each signal scores in [0,1] independently and the composite respects that floor; vector similarity is never penalized below its raw value.
**Lesson:** Composite scoring must respect each signal's independent contribution. A signal with weight=0.35 should not be dragged to 0.05 by zero-valued companions. (Cross-bug with #11, #12.)

<a id="issue-9"></a>

## Issue #9: No Actionable Integration in Search Results [DOCUMENTED]

**Trigger:** Search results show what memories exist but don't tell the agent how to *use* them in the next response.
**Root cause:** A memory search returns evidence, not proof that the caller will apply it. Knowing "this memory is relevant" is not the same as using it correctly.
**Solution:** Provide an explicit answer-context selection map on search and an
opt-in `RELEVANT_CONTEXT` block for workflow pilots. Automatic delivery is now
default-off and requires the three local flags documented in
`docs/reference/tools.md`; this is not a released effectiveness claim.
**Lesson:** A search tool that returns raw memories assumes the agent will apply
them. Delivery must be bounded, governed, measurable, and immediately
reversible rather than always active. (Cross-bug with ai-behavior #6.)

<a id="issue-10"></a>

## Issue #10: Memory Add Silent IGNORE — Opaque Test-Memory Guard [BUG-011, FIXED, guarded]

**Trigger:** `elefante-Memory(action="add")` returns "Memory filtered by Intelligence Pipeline" with no rejection reason. User can't fix what they can't see.
**Root cause:** Test-memory guard in `src/core/orchestrator.py::add_memory()` rejected submissions matching test patterns (`tag="test"`, `e2e`, `hybrid_test_*`, content prefixes) but returned a generic IGNORE response without naming the matched condition. Heuristic also too broad — blocked legitimate tags.
**Solution:** Guard now returns `rejection_reason` field naming the exact matched condition (e.g., `"tag 'test' present"`) so caller can route the failure. Heuristic narrowed to exact-match on critical patterns only.
**Lesson:** Silent rejections are debugging landmines. Every guard must name its condition in the response so the next agent can fix the cause, not the symptom. (Cross-bug with installation #12 — installer seed collision.)

<a id="issue-11"></a>

## Issue #11: Domain Signal Value-Space Disjunction [BUG-016, FIXED v2.7.0]

**Trigger:** Scoring's domain signal contributes 15% of composite weight but never produces 1.0 — only 0.5 (neutral) or 0.0 (penalty). Domain actively *degrades* ranking vs. pure vector.
**Root cause:** `analyze_query()` infers domain values `None` / `"work"` / `"personal"` / `"project:elefante"` while memories default to `DomainType.REFERENCE`. The two value spaces never intersected. 15% of scoring weight was mathematically dysfunctional.
**Solution:** Removed the domain signal. Reweighted composite: vector 0.40, concept 0.30, co-activation 0.15, authority 0.10, temporal 0.05.
**Lesson:** A signal is dysfunctional if its value spaces never intersect. Verify each signal's range against real query/memory pairs before shipping. Empirical validation > spec.

<a id="issue-12"></a>

## Issue #12: Unconditional Spec Override Dominates All Queries [BUG-017, FIXED v2.7.0]

**Trigger:** Three different real queries all return the same top 4 specification memories. Non-spec memories mathematically cannot outrank specs.
**Root cause:** `+0.30` boost applied to all `specification`/`directive` memories regardless of query intent. Specs always won.
**Solution:** Intent-gated spec override — boost applied only when query intent is `developer-process` or `system-rule`. For factual / conversational / preference queries, specs compete on merit.
**Lesson:** A boost without intent gating becomes a default. Override should fire only when the query asks for what the boosted type provides. (Cross-bug with #11 — empirical validation.)

**Recall recurrence (BUG-047, 2026-09-03):** A real explanation request selected
the product purpose and an unrelated staffing rule. Strong vector similarity,
a specification label and shared topic words had stood in for answer evidence.
Question focus now distinguishes a mechanism request from a saved property;
leading presentation instructions are not topic matches. Independent review then
exposed the opposite error: a property cue vetoed text that genuinely described
the mechanism. The exception requires strong body evidence plus substantive
question terms absent from the saved cue; separate success criteria cannot supply
those terms. Fail-first regressions preserve both errors, two property-only
negatives and the success-criteria boundary. Cached-model coverage retains the
original corpus and adds independent cases without rewriting user memories or
changing similarity thresholds. Publication remains a separate gate in
[`PLANNING.md §2.7`](../PLANNING.md#27-whole-product-acceptance-checklist-current-gate).
**Prevention:** Test both unrelated same-topic retrieval and valid content beyond
its saved example question. A green count is not a general relevance guarantee.

<a id="issue-13"></a>

## Issue #13: Co-Activation Cold-Start [BUG-018, FIXED v2.7.0]

**Trigger:** First query of every session returns 0.0 co-activation score. Co-activation never contributes on session start.
**Root cause:** `_session_retrieval_history` was an in-memory list reset to `[]` on every server restart. Kuzu `CO_ACTIVATED` edges existed but the read path needed retrieval IDs that were lost on restart.
**Solution:** Persisted session retrieval history to disk (`~/.elefante/data/session_history.json`), restored on init. Read path now reconstructs from persisted IDs.
**Lesson:** State that should persist across restarts must persist to disk, not memory. Co-activation is a multi-session signal; treating it as in-process state is a category error.

**Current contract note (2026-08-08):** This historical repair is superseded by
BUG-048 for normal operation. Retrieval IDs are no longer treated as use
evidence. The development `record_use` event is observational and does not
populate ranking history or co-activation input.

<a id="issue-14"></a>

## Issue #14: ChromaDB query() with where filter fails [BUG-022, FIXED v2.9.0]

**Trigger:** `collection.query(where=...)` raises `InternalError: Error finding id` on ChromaDB 1.3.5 when a legacy collection has 400+ memories. `elefante-Memory(action="add", memory_type="preference")` fails.
**Root cause:** ChromaDB 1.3.5 has a bug in indexed `where` filter on large collections. Reproducer: any preference memory triggers a where-filtered duplicate check that fails silently in small collections, surfaces in large ones.
**Solution:** Workaround — `collection.get(where=...)` (non-query path) instead of `collection.query(where=...)` for the duplicate check. Pin ChromaDB version until upstream fix.
**Lesson:** Library bugs surface at scale. Test with production-size data before claiming fix. Workaround paths are cheaper than version pins when upstream is slow.

<a id="issue-15"></a>

## Issue #15: Multi-Instance Write Origin Tracking [GAP-025, CLOSED FOR CURRENT INSTALLED STORE]

**Trigger:** Two concurrent IDEs (e.g. Hermes + VS Code) writing memory: no `source.*` tuple distinguishes which instance wrote which memory. Stdio-per-client transport makes Kuzu single-writer contract violation possible. Blocks session-intelligence client attribution.
**Root cause:** Memories had no `source.tool`, `source.instance_id`, or `source.cwd`. Stdio MCP transport is per-client by design, so concurrent IDEs could spawn database-owning processes and fight for Kuzu's single-writer lock.
**Solution:** A loopback Streamable HTTP daemon is the singleton database owner; stdio bridges forward provenance headers; `(:Entity)-[:WRITTEN_BY]->(:Source)` is written with each memory; and `backfill_memory_provenance.py` provides an idempotent, dry-run-first legacy migration. VS Code, Bob, and Antigravity emit bridge configuration. User-modified configuration is preserved by manifest-driven uninstall.
**Acceptance:** Two concurrent bridge clients produce distinct `source.instance_id` values with zero Kuzu lock contention. Proof: `pytest tests/test_mcp_daemon.py -m slow -q`. On 2026-08-28 the explicitly authorized installed-store migration ran only after daemon shutdown and a verified backup; it added five Memory entities and five source links, a repeat dry-run reported zero pending work, and final customer doctor returned ready with zero diagnostics. Migration closure is store-specific, so every other existing installation must run the same backup-bound operator procedure independently.
**Lesson:** A multi-writer contract on a single-writer database is a category error. Push concurrency to the layer above the database (daemon), not into the database's locking primitives.

<a id="issue-16"></a>

## Issue #16: Memory Governance Had No Authority Boundary [BUG-049, FIXED in development]

**Trigger:** A workflow-managed call could assert permanent or user-locked policy, later automation could change that protected record, refinery cleanup could archive it, and normal delete permanently removed data.
**Root cause:** Storage metadata described retention and injection preferences, but mutation authority and forgetting semantics were not enforced at the MCP and maintenance boundaries.
**Solution:** Require an explicit invocation mode, reserve protected policy for user-directed calls, reject workflow changes to protected records, exclude protected memories from automated archival, and make archive the default delete behavior. Permanent deletion now requires explicit user-directed confirmation and a second confirmation for protected memory.
**Lesson:** Retention, retrieval, injection, and deletion are separate decisions. Automation may operate inside user policy; it may not manufacture or silently weaken user authority.

<a id="issue-17"></a>

## Issue #17: Correction Completion Was Not Verified Across Product Surfaces [BUG-059, FIXED locally]

**Trigger:** A conflict-resolution write could return success before the authoritative records, Home snapshot, and scoped Recall agreed. An adapter that mutated one record and then returned false could also be reported as a no-change failure even though the store had changed.
**Root cause:** The correction path owned the two-record mutation but not the product-level postconditions. Snapshot publication used a normal file write, Recall was not part of completion, and the adapter return value was trusted without authoritative readback.
**Solution:** Add an operation-specific Verified Resolve boundary. The dry-run plan binds exact scope and record hashes. Apply performs at most one semantic write, reads both records back, atomically replaces a private generation-tagged snapshot, and runs a disposable scoped Recall question that must select the winner and exclude the loser. Any failed postcondition restores the exact two-record preimage and verifies the restore; an incomplete restore returns `UNSAFE`. Home receives only a short-lived, origin-bound Resolve capability and a one-use plan ticket. Receipts contain bounded identifiers, hashes, checks, and error codes but no memory content, reason, question, project name, or path.
**Guard:** `pytest tests/test_verified_resolve.py tests/test_home_control.py tests/test_atomic_json.py tests/test_conflict_resolution.py tests/test_dashboard_serializer.py -q`.
**Lesson:** A semantic write is not product completion. Declare the customer-visible postconditions, read back authoritative state, publish derived views atomically, verify the consuming path, and label incomplete compensation unsafe.

<a id="issue-18"></a>

## Issue #18: Project Isolation State Could Fail Open or Drift Across Surfaces [BUG-060, FIXED locally]

**Trigger:** Project identity was optional metadata rather than a product-owned registry. When registry or snapshot state was absent, different surfaces could infer compatibility independently; paired Home writes could leave the dashboard behind the registry; and isolated test installations still touched the account-global write lock.
**Root cause:** Elefante had no single durable authority for project identity and no independent record that strict isolation had been chosen. The derived Home projection was treated as best effort, and lock placement followed the account default instead of the configured data installation.
**Solution:** Add a private versioned Project Registry with stable opaque IDs and deterministic deepest-root mapping. Persist strict intent in a separate mode-0600 marker written before the strict registry transition; a missing, corrupt, conflicting, or downgraded state now fails closed. Resolve project context before opening stores, stamp every new memory with the resolved ID/root/scope, and force Search and Recall through that same scope. Publish the registry, intent marker, and Home snapshot as one checked operation with exact byte-and-mode rollback. Preserve unavailable or invalid projection state instead of fabricating compatibility, and derive the write-lock directory from the configured data installation.
**Guard:** `pytest tests/test_atomic_json.py tests/test_write_lock_isolation.py tests/test_project_registry.py tests/test_project_scoping.py tests/test_home_control.py tests/test_dashboard_serializer.py tests/test_dashboard_snapshot_verifier.py tests/test_install_setup.py tests/test_mcp_daemon.py -m "not integration and not slow" -q`; `npm run build` in `src/dashboard/ui`.
**Lesson:** Fail-closed intent must survive loss of its primary state. Every projection must preserve unknown or invalid status, coupled control files require one rollback boundary, and test isolation includes locks as well as data.

**Configured-root recurrence, 2026-09-03:** A real isolated dashboard launch
still loaded account-default directives and exposure history. No browser
mutations ran; both real files subsequently matched their verified backup hashes.
Directives (including the singleton), explicit-use history and attachment
ingestion now resolve the active configured data directory. Two fail-first
configuration tests cover YAML and environment selection across separate roots;
the attachment test verifies bytes under the configured root and absence under
the old default. All three pass. Isolation must include auxiliary state, not
only databases and locks.

<a id="issue-19"></a>

## Issue #19: Customer Correction Had Multiple Bypass Paths [BUG-061, FIXED locally]

**Trigger:** Edit, replacement, conflict repair, archive, and deletion were exposed through different low-level verbs. A caller could change content or lifecycle state without proving graph consistency, Home refresh, or future Recall, while Home itself could not complete the ordinary correction journey.
**Root cause:** Storage mutations were treated as the feature. No single customer-owned Correct boundary defined authority, project scope, preimages, postconditions, compensation, receipts, or the dependency between irreversible deletion and recovery.
**Solution:** Add a shared verified correction service for Edit, Replace, Archive, Restore, and advanced permanent deletion, retaining Verified Resolve for explicit conflict authority. Bind exact record, graph, relationship, content, and scope hashes; perform one semantic write; read back SQLite and Kuzu; atomically publish Home; prove scoped Recall; and restore exact preimages when any postcondition fails. Edit and Replace replace only deterministic concept links and preserve explicit relationships. Permanent deletion requires a second confirmation and an exact live workflow-managed backup, removes the selected memory, graph projection, safe orphan source, and unshared attachments, proves Home and Recall absence, then destroys the temporary backup; any failure restores it. Make `elefante-Memory(action="correct")` the primary repair path, fail legacy content/lifecycle mutation into it before stores open, and expose only named Home plan/apply endpoints with content-free one-use tickets.
**Follow-up recurrence:** The backend could plan verified permanent deletion for an archived superseded record, but Home hid every correction action because it treated all non-manual inactive states as unmanageable. Keep Restore limited to manually archived, non-superseded records while exposing the verified permanent-deletion plan for every represented inactive record; the plan remains authoritative and may still block unsafe work.
**Guard:** `pytest tests/test_verified_correction.py tests/test_verified_recovery.py tests/test_verified_resolve.py tests/test_home_control.py tests/test_mcp_daemon.py tests/test_dashboard_serializer.py tests/test_dashboard_ui.py -q`; `npm run build` in `src/dashboard/ui`; rendered permanent-delete acceptance remains a release gate.
**Lesson:** A product correction is a verified lifecycle, not a database verb. One customer path must own authority, all promised postconditions, compensation, and the boundary that deliberately blocks irreversible work.

<a id="issue-20"></a>

## Issue #20: Verified Remember Used Two Creation Clocks [BUG-063, FIXED locally]

**Trigger:** An isolated Elefante-builds-Elefante run used the real SQLite vector store and Kuzu graph. Verified Remember wrote both records, then failed `authoritative_store_and_graph` and removed the new memory through its verified rollback.
**Root cause:** `MemoryOrchestrator.add_memory` let the graph `Entity` generate its own `created_at` instead of projecting the memory's canonical timestamp. The verifier correctly hashes persisted graph fields, so fake-store tests that copied the memory timestamp passed while the real integration could not.
**Solution:** Project `memory.metadata.created_at` into the graph entity and add a real SQLite/Kuzu regression that compares the persisted entity with the verifier's expected projection. Keep `updated_at` outside the authoritative graph hash because the current Kuzu entity schema does not persist it.
**Guard:** `pytest tests/test_verified_remember.py -q`; the isolated dogfood run additionally requires all four Remember postconditions and a scoped Recall selection.
**Lesson:** A verifier must be exercised against the real persistence adapters. Fake stores may prove compensation logic while silently normalizing away serialization, clock, or schema differences at the product boundary.

<a id="issue-21"></a>

## Issue #21: Remember Collected but Discarded the Future Recall Question [BUG-065, FIXED locally]

**Trigger:** In Home, the customer selected Preference, entered `User likes answers in simple terms and concisely (STAC). User usually refers this as "STAC"`, and supplied `what is the conclusion, after all this work, explain me STAC` as the likely future question. The write reached the stores but semantic Recall did not select it, so Verified Remember rolled it back and Home reduced the failure to a generic related-knowledge message.
**Root cause:** The future question was treated as a disposable acceptance input rather than part of the memory's durable retrieval contract. No model or adapter field persisted it, no exact-cue retrieval route existed, and the UI normalized a specific failed Recall postcondition into an unrelated conflict-shaped error.
**Solution:** Add a canonical, bounded `recall_cues` metadata field and persist it through every configured vector adapter and Home snapshot. Remember binds the customer's question to the new memory; Edit and Replace bind it to the resulting current record; Restore appends it without duplication. An exact complete normalized cue may surface only when both registered project and workspace are explicit and the memory still passes all normal scope, lifecycle, trust, source, conflict, and privacy gates. Failed Remember removes the attempted record and says plainly that Recall could not be proved and nothing was saved.
**Guard:** `pytest tests/test_verified_remember.py tests/test_verified_correction.py tests/test_proactive_surfacing.py tests/test_dashboard_serializer.py tests/test_dashboard_ui.py -q`; exact STAC browser acceptance proves write, persisted cue, and scoped Recall.
**Lesson:** If the product asks how knowledge will be requested later, that answer is part of the durable retrieval contract. Acceptance inputs must not disappear between write and future use.

<a id="issue-22"></a>

## Issue #22: Remember Could Not Safely Preserve an Explicit Conflict [BUG-067, FIXED locally]

**Trigger:** Home remembered `The disposable billing banner must be green.` and then `The disposable billing banner must not be green.` The second assertion was classified as a duplicate. After forcing Keep both, the two records lacked one bilateral conflict projection and Verified Remember treated safe Recall withholding as a failed write.
**Root cause:** The conservative proposition parser did not recognize `must` as an explicit assertion/negation form. Similarity classification ran without contradiction precedence, the add path could not receive known conflict IDs, and the Remember verifier assumed every successful write must be selected by Recall even when unresolved contradiction should block both sides.
**Solution:** Parse explicit `must`/`must not` propositions, give contradiction precedence over near-duplicate similarity, allow only the typed verified path to create explicit conflict IDs, and write bilateral store and graph conflict projections with compensating restoration of the peer. Keep both now succeeds only when authoritative conflict projection is complete and scoped Recall withholds both records while reporting the conflict. Verified Resolve then requires explicit winner authority, supersedes the loser, and proves only the winner is recalled. A later live recurrence also removed similarity-only false positives: non-duplicate, non-conflict candidates require at least two shared substantive concepts after project-name and generic memory terms are excluded.
**Guard:** `pytest tests/test_conflict_detection.py tests/test_verified_remember.py tests/test_verified_resolve.py -q`; isolated browser acceptance covers an unrelated same-project direct save, Keep both, visible At risk peers, Resolve, and winner-only Recall.
**Lesson:** Conflict is a safe delivery state, not a failed retrieval. Completion must verify the intended abstention until authority resolves the contradiction.

---

## Cross-bug pattern (extracted to `../lessons.md`)

1. **Retrieval thresholds belong on retrieval, not export** — Issue #1.
2. **Configured vector records are memories; Kuzu is relationships** — Issues #2, dashboard #4. Verify data source first.
3. **Retrieved memory must be APPLIED, not just acknowledged** — Issue #3, ai-behavior #4.
4. **Translate between storage and domain via model helpers** — Issues #5, database #6.
5. **Default to minimal projection at retrieval boundaries; full payloads on demand** — Issue #7.
6. **Composite scoring must respect each signal's independent contribution** — Issues #8, #11, #12.
7. **Silent rejections are debugging landmines — every guard names its condition** — Issues #10, installation #12.
8. **Empirical validation > spec when value spaces are involved** — Issues #11, #12.
9. **State that persists across restarts must persist to disk** — Issue #13.
10. **Library bugs surface at scale — test with production-size data** — Issue #14.
11. **Push concurrency to the layer above the database** — Issue #15 (GAP-025, v2.11.0 closure).
12. **Automation cannot grant itself user authority** — Issue #16.
13. **Customer correction needs one verified path; legacy verbs must not bypass it** — Issue #19.
13. **A semantic write is not completion until authoritative state and every promised customer surface agree** — Issue #17.
14. **Fail-closed intent must survive loss of its primary state, projections must preserve uncertainty, and isolated data must use isolated locks** — Issue #18.
15. **Verify cross-store identity against the real adapters; fake stores can hide clock and serialization drift** — Issue #20.
16. **Persist the customer's likely future question when the product uses it as a retrieval promise** — Issue #21.
17. **Treat conflict-safe abstention as the correct postcondition until explicit authority resolves the pair** — Issue #22.

Distill any new repeating rule into `../lessons.md`.
