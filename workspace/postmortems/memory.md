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

<a id="issue-13"></a>

## Issue #13: Co-Activation Cold-Start [BUG-018, FIXED v2.7.0]

**Trigger:** First query of every session returns 0.0 co-activation score. Co-activation never contributes on session start.
**Root cause:** `_session_retrieval_history` was an in-memory list reset to `[]` on every server restart. Kuzu `CO_ACTIVATED` edges existed but the read path needed retrieval IDs that were lost on restart.
**Solution:** Persisted session retrieval history to disk (`~/.elefante/data/session_history.json`), restored on init. Read path now reconstructs from persisted IDs.
**Lesson:** State that should persist across restarts must persist to disk, not memory. Co-activation is a multi-session signal; treating it as in-process state is a category error.

**Current contract note (2026-08-08):** This historical repair is superseded by
BUG-046 for normal operation. Retrieval IDs are no longer treated as use
evidence. The development `record_use` event is observational and does not
populate ranking history or co-activation input.

<a id="issue-14"></a>

## Issue #14: ChromaDB query() with where filter fails [BUG-022, FIXED v2.9.0]

**Trigger:** `collection.query(where=...)` raises `InternalError: Error finding id` on ChromaDB 1.3.5 when a legacy collection has 400+ memories. `elefante-Memory(action="add", memory_type="preference")` fails.
**Root cause:** ChromaDB 1.3.5 has a bug in indexed `where` filter on large collections. Reproducer: any preference memory triggers a where-filtered duplicate check that fails silently in small collections, surfaces in large ones.
**Solution:** Workaround — `collection.get(where=...)` (non-query path) instead of `collection.query(where=...)` for the duplicate check. Pin ChromaDB version until upstream fix.
**Lesson:** Library bugs surface at scale. Test with production-size data before claiming fix. Workaround paths are cheaper than version pins when upstream is slow.

<a id="issue-15"></a>

## Issue #15: Multi-Instance Write Origin Tracking [GAP-025, IN PROGRESS]

**Trigger:** Two concurrent IDEs (e.g. Hermes + VS Code) writing memory: no `source.*` tuple distinguishes which instance wrote which memory. Stdio-per-client transport makes Kuzu single-writer contract violation possible. Blocks session-intelligence client attribution.
**Root cause:** Memories had no `source.tool`, `source.instance_id`, or `source.cwd`. Stdio MCP transport is per-client by design, so concurrent IDEs could spawn database-owning processes and fight for Kuzu's single-writer lock.
**Solution:** A loopback Streamable HTTP daemon is the singleton database owner; stdio bridges forward provenance headers; `(:Entity)-[:WRITTEN_BY]->(:Source)` is written with each memory; and `backfill_memory_provenance.py` provides an idempotent, dry-run-first legacy migration. VS Code, Bob, and Antigravity emit bridge configuration. User-modified configuration is preserved by manifest-driven uninstall.
**Acceptance:** Two concurrent bridge clients produce distinct `source.instance_id` values with zero Kuzu lock contention. Proof: `pytest tests/test_mcp_daemon.py -m slow -q`. Full closure still requires an authorized apply of pending legacy graph links and host-level install/reconnect/upgrade/uninstall certification.
**Lesson (provisional):** A multi-writer contract on a single-writer database is a category error. Push concurrency to the layer above the database (daemon), not into the database's locking primitives.

<a id="issue-16"></a>

## Issue #16: Memory Governance Had No Authority Boundary [BUG-047, FIXED in development]

**Trigger:** A workflow-managed call could assert permanent or user-locked policy, later automation could change that protected record, refinery cleanup could archive it, and normal delete permanently removed data.
**Root cause:** Storage metadata described retention and injection preferences, but mutation authority and forgetting semantics were not enforced at the MCP and maintenance boundaries.
**Solution:** Require an explicit invocation mode, reserve protected policy for user-directed calls, reject workflow changes to protected records, exclude protected memories from automated archival, and make archive the default delete behavior. Permanent deletion now requires explicit user-directed confirmation and a second confirmation for protected memory.
**Lesson:** Retention, retrieval, injection, and deletion are separate decisions. Automation may operate inside user policy; it may not manufacture or silently weaken user authority.

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

Distill any new repeating rule into `../lessons.md`.
