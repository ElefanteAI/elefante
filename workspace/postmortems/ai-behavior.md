# AI Behavior Postmortems

> **Domain:** Agent protocol failures, self-analysis, methodology drift.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson. Full narrative preserved verbatim in [`_archive/ai-behavior-full.md`](_archive/ai-behavior-full.md).

---

## Issue #1: Analysis-Action Gap [DOCUMENTED, behavioral]

**Trigger:** Agent analyzes a task perfectly, states intentions clearly, then never executes — uses future/conditional tense ("should", "will", "needs to") in place of action.
**Root cause:** Three distinct behavioral gaps — Knowledge (no info), Application (info but not used), Execution (knows what to do but doesn't). Analysis feels like progress; stating intent feels like commitment; action requires more effort.
**Solution:** Forced-execution protocol — present-tense action verbs only. STATE → DO → VERIFY in the same response, with proof of result. No conditional/future tense for actions you control.
**Lesson:** Analysis without action is entertainment.

## Issue #2: Premature Completion Claims [DOCUMENTED, behavioral]

**Trigger:** Agent claims "done" / "ready" / "complete" / "implemented" without verification. User tests, finds merge markers, missing deps, or broken behavior.
**Root cause:** Completion-trigger words used without proof. Writing code feels like completion; testing feels like a separate step. Time pressure favors quick claims.
**Solution:** Verification protocol — every completion-trigger word requires evidence: `grep "<<<<<<< HEAD"`, `py_compile`, import test, execution test, real-data test. Claim "done" only after all five pass.
**Lesson:** "It should work" ≠ "It works." Only verification output counts.

## Issue #3: Code-Mode MCP Limitation [HISTORICAL]

**Trigger:** Roo-Cline `code` mode cannot access MCP tools; agent creates Python workaround scripts instead.
**Root cause:** Mode-based tool restrictions in Roo. `code` / `architect` / `ask` modes have no MCP; only `jaime` mode does.
**Solution:** Switch mode before MCP operations. Workaround scripts cause Kuzu lock contention.
**Lesson:** Mode-specific. VS Code Copilot and Claude Code expose MCP in all modes; this issue is platform-specific to Roo. Retained for multi-agent reference.

## Issue #4: Knowledge Not Applied [DOCUMENTED, behavioral]

**Trigger:** Memory exists with score 100 ("NEVER delete files, move to ARCHIVE"). Agent retrieves it, states compliance, then deletes anyway.
**Root cause:** Reading ≠ applying. Easy to retrieve and ignore. No enforcement mechanism. Speed prioritized over compliance.
**Solution:** Layer 4 — Memory Compliance Verification. Before each response: list retrieved memory IDs, identify applicable rules, state HOW the response follows each rule, check for conflicts. If action violates memory, do not proceed.
**Lesson:** Retrieved memory must be APPLIED, not just acknowledged. Acknowledgement is the failure mode, not the success mode.

## Issue #5: Environment Assumption Failures [DOCUMENTED]

**Trigger:** Agent claims "dashboard fully operational"; user sees "0 memories" because of cached frontend.
**Root cause:** AI test environment (Puppeteer, fresh state, no cache) ≠ user environment (Chrome, existing data, network delays, cached JS/CSS).
**Solution:** Verify in user-equivalent conditions: hard refresh, cache cleared, existing data, post-restart. Always ask the user what they see (exact output) before claiming success.
**Lesson:** "It works for me" is not proof; account for caching and user-specific state.

## Issue #6: Passive Protocol Enforcement Failure [FIXED v2.4+, guarded]

**Trigger:** Elefante has comprehensive protocols (Inception Memory, Tool Descriptions, Documentation), but agents skip them and re-discover failures the docs already documented (e.g., 15+ install attempts when the answer was in `docs/how-to/install.md`).
**Root cause:** ALL enforcement was PASSIVE — agent must choose to engage. Inception Memory must be searched. Tool Descriptions must be read. Documentation must be opened. None forced compliance.
**Solution:** Inject `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` into every MCP tool response, success AND failure paths. `src/mcp/server.py` adds it to both. Tool-contract directive in `src/core/directive_store.py` requires reading the entry sequence in addition to `MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, `RELEVANT_CONTEXT`. `scripts/verify/verify_e2e_tests.py` proves first-success and first-error responses both inject the sequence.
**Lesson:** If exact routing is not injected on both success AND failure paths, agents will skip the protocol at the moment they need it most. Active injection > passive prose. **This is the root failure class for repeat behavioral bugs.**

## Issue #7: Developer Routing Drift — Stale Paths in Active Guidance [FIXED, guarded]

**Trigger:** Agent guidance routes to deleted files (`docs/pitfall-index.md`, `docs/technical/sdd-development-protocol.md`); changelog reads framed as ritual instead of assumption-check.
**Root cause:** Drift in three layers at once — built-in directive text, human reference docs, and stored Elefante memories all cited retired paths.
**Solution:** Patched (1) `src/core/directive_store.py` routing, (2) `src/core/orchestrator.py` SDD seed and developer-etiquette baseline, (3) live source-of-truth files updated, (4) stored Elefante memories amended. Guarded by `tests/test_developer_routing.py`.
**Lesson:** A developer-process bug is not solved until source text, stored memory, and verification all agree on the same path.

## Issue #8: Self-Protocol Verifier Drift — Path & Payload Assumptions [FIXED, guarded]

**Trigger:** `verify_e2e_tests.py --with-dashboard-open` reports `[FAIL]` while live MCP surface is healthy. Two cascading failures: dashboard snapshot path, then large-payload stream limit.
**Root cause:** Verifier encoded convenience assumptions instead of following live runtime behavior. (a) Checked only `temp_data_dir/dashboard_snapshot.json`, but `src.mcp.server` writes through `HOME`-derived `DATA_DIR`. (b) Used asyncio's default subprocess stream limit, too small for `elefante-ContextGet` payloads.
**Solution:** Stream limit raised to 1 MiB (`STREAM_LIMIT_BYTES = 1024 * 1024`). Snapshot path lookup now tries both `temp_home/.elefante/data/` and `temp_data_dir/`. Guarded by `TestSelfProtocolContract` tests.
**Lesson:** A maintained verifier is part of the product confidence surface; if it assumes the wrong runtime path or payload shape, it becomes a false bug generator.

## Issue #9: Self-Protocol Cold-Start Deadlock [FIXED, guarded — Windows/Py3.11/CPU only]

**Trigger:** `verify_e2e_tests.py` hangs at Phase 3 with `TimeoutError`. Trace shows `from sentence_transformers import SentenceTransformer` never returns inside `asyncio.to_thread()`.
**Root cause:** The torch import deadlocks specifically when running in (a) a worker thread under (b) a piped-stdio MCP subprocess under (c) an anyio-managed event loop on Windows + Python 3.11. Likely a GIL/DLL-loader interaction with ProactorEventLoop's I/O completion ports. Direct in-process import works fine.
**Solution:** Pre-load the embedding model in `src/mcp/server.py` `__main__` block BEFORE `asyncio.run(main())`. Adds ~8-10s startup; makes runtime `_load_model()` a no-op. Approach #1 (longer timeout) and Approach #2 (move to a different thread) both failed — only Approach #3 (move to a different process-lifecycle phase) worked.
**Lesson:** When a blocking operation deadlocks in a thread under an event loop, moving it to a different thread doesn't help. Move it to a different PHASE of the process lifecycle — before the event loop starts. **Differentiate "slow" from "hung":** if a 180s timeout doesn't help, it's a deadlock, not latency.

## Issue #10: Elefante Cold-Start Trigger Gap [FIXED partial — VS Code Copilot only]

**Trigger:** Agent answers Elefante-relevant questions (preferences, past decisions) from training data or local file reads. No `elefante-MemorySearch` is called; no `[ELEFANTE] Searched:` stamp appears. Server is running and registered.
**Root cause:** Three layers. (1) **Instruction delivery is workspace-scoped:** VS Code Copilot loads `copilot-instructions.md` only from the active workspace root's `.github/`. When the user opens a parent or sibling folder, the file is invisible. (2) **Cold-start bootstrap gap:** server-side directives only inject AFTER the first Elefante tool call — there is no delivery path before that first call. (3) **Orthogonal to MCP registration scope** — fixing where the server is declared does not fix where the instructions live.
**Solution:** Two-layer fix. (1) **VS Code user-level** `settings.json` → `github.copilot.chat.codeGeneration.instructions` pointing to `elefante/.github/copilot-instructions.md`. Loads for every workspace, every subfolder, every session. (2) **BOB workspace fallback** `BOB/.github/copilot-instructions.md` as backup if user-settings injection is cleared. Cross-client fix (Cursor, Windsurf) requires client-specific bootstrap files — pending.
**Lesson:** Instruction delivery and MCP registration are separate systems at separate layers. The correct scope for behavioral instructions is the broadest available scope — not the narrowest that works in the demo scenario. System-level = `settings.json` user injection, not workspace-level file presence.

## Issue #11: JSON Export Is Not a Backup [DOCUMENTED — `import_memories.py` planned]

**Trigger:** User runs `export_memories.py --format json`, factory-resets, finds no script to re-import. Brain is gone.
**Root cause:** Three layers. (1) `export_memories.py` was built for offline analysis, not migration; no `import_memories.py` was ever written. (2) Embeddings excluded — the export calls `collection.get(include=["metadatas", "documents"])` but Elefante stores embeddings explicitly via `thenlper/gte-base`. (3) ChromaDB has no named embedding function in Elefante's collection — using its default (`all-MiniLM-L6-v2`) on upsert silently corrupts semantic search.
**Solution:** Phase 1 — surface backup/restore (`backup_elefante_data.py`) as the primary persistence path in README; mark JSON export as read-only analysis output. Phase 2 — build `scripts/pipeline/import_memories.py` that regenerates embeddings using `thenlper/gte-base` before `collection.upsert()`. Estimated ~120 LOC.
**Lesson:** A write-only export is not a backup. Every export format needs a documented import path or must be explicitly labeled read-only. Never infer "exportable = restorable."

## Issue #12: DOC_SYNC Protocol Bypass [MITIGATED, guard partial — parent class BUG-006]

**Trigger:** Direct-repo file-edit agent skips Loop Step 1 (`workspace/ISSUES.md` Known Issues check) at the moment of action, even with the constitution loaded into context. Reproduces BUG-006 in a new surface (file-edit) where the shipped MCP-response injection cannot fire.
**Root cause:** BUG-006's fix injects `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` into every MCP tool response — bound to `src/mcp/server.py`. **Direct-repo agents make file-edit decisions without ever calling Elefante MCP**, so no MCP response fires the injection. The orchestrator constitution is loaded once at session start and expected to be re-engaged voluntarily — exactly the passive-protocol failure class BUG-006 documented.
**Same-session recurrences observed (2026-05-02):** (1) authored §0.7 inside version-stamped filename without flagging the pattern; (2) ran an audit without re-reading 4 unedited READMEs; (3) authored Forbidden Patterns enumerating `HANDOFF-YYYY-MM-DD.md`, then left existing handoff files alive in `docs/planning/` for hours.
**Solution adopted (passive):** Documentation Skill section in `agents/orchestrator.md` (Closed Surface Map, Forbidden Patterns, Pre-write checklist, Required routing, New-File test, Failure conditions, Lifecycle).
**Solution adopted (active, filename subset):** `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents` fails CI on `HANDOFF-*`, `spec-v[0-9]*-*`, `NOTES*`, `scratch*`, `todo*`, `ideas-new*`, `CURRENT_STATE*`, `IDEA-[0-9]*`, `session-summary*` under `docs/`, `agents/`, `workspace/`.
**Active candidates pending (broader surface):** (a) pre-edit hook requiring `BUG-NNN | new` classification before any Edit/Write call; (b) maintained transcript-scanning verifier.
**Lesson:** An agent constitution loaded once at session start is a passive protocol. Every doc edit starts at Known Issues. No exceptions. Active guards beat prose at the moment of action.

---

## Cross-bug pattern (extracted to `../lessons.md`)

The recurring rules from these 12 issues:

1. **STATE → DO → VERIFY in the same response** — analysis without action is entertainment. Issues #1, #4.
2. **Trigger words require proof** — "done" / "ready" / "fixed" must include verification output. Issue #2.
3. **Active injection beats passive prose** — passive protocols are skipped at the moment they're needed most. Issues #6, #12.
4. **Source + memory + verification must agree** — fix in one layer is not a fix. Issues #7, #8.
5. **Differentiate "slow" from "hung"** — timeouts cannot fix deadlocks. Issue #9.
6. **Broadest scope for behavioral instructions** — system-level injection, not workspace-level file presence. Issue #10.
7. **Every export needs a documented import** — exportable ≠ restorable. Issue #11.

Distill any new repeating rule into `../lessons.md`. Postmortems hold the bug-specific narrative; `lessons.md` holds the cross-bug edge.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/ai-behavior-full.md`](_archive/ai-behavior-full.md).

This file (`ai-behavior.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
