# AI Behavior Postmortems

> **Domain:** Agent protocol failures, self-analysis, methodology drift.
> **Cross-refs:** BUG/GAP rows + verification commands live in [`../ISSUES.md`](../ISSUES.md). Reusable cross-bug rules live in [`../lessons.md`](../lessons.md).
> **Format per entry:** Trigger / Root cause / Solution / Lesson. Full narrative preserved verbatim in [`_archive/ai-behavior-full.md`](_archive/ai-behavior-full.md).

---

<a id="issue-1"></a>

## Issue #1: Analysis-Action Gap [DOCUMENTED, behavioral]

**Trigger:** Agent analyzes a task perfectly, states intentions clearly, then never executes — uses future/conditional tense ("should", "will", "needs to") in place of action.
**Root cause:** Three distinct behavioral gaps — Knowledge (no info), Application (info but not used), Execution (knows what to do but doesn't). Analysis feels like progress; stating intent feels like commitment; action requires more effort.
**Solution:** Forced-execution protocol — present-tense action verbs only. STATE → DO → VERIFY in the same response, with proof of result. No conditional/future tense for actions you control.
**Lesson:** Analysis without action is entertainment.

<a id="issue-2"></a>

## Issue #2: Premature Completion Claims [DOCUMENTED, behavioral]

**Trigger:** Agent claims "done" / "ready" / "complete" / "implemented" without verification. User tests, finds merge markers, missing deps, or broken behavior.
**Root cause:** Completion-trigger words used without proof. Writing code feels like completion; testing feels like a separate step. Time pressure favors quick claims.
**Solution:** Verification protocol — every completion-trigger word requires evidence: `grep "<<<<<<< HEAD"`, `py_compile`, import test, execution test, real-data test. Claim "done" only after all five pass.
**Lesson:** "It should work" ≠ "It works." Only verification output counts.

<a id="issue-3"></a>

## Issue #3: Code-Mode MCP Limitation [HISTORICAL]

**Trigger:** Roo-Cline `code` mode cannot access MCP tools; agent creates Python workaround scripts instead.
**Root cause:** Mode-based tool restrictions in Roo. `code` / `architect` / `ask` modes have no MCP; only `jaime` mode does.
**Solution:** Switch mode before MCP operations. Workaround scripts cause Kuzu lock contention.
**Lesson:** Mode-specific. VS Code Copilot and Claude Code expose MCP in all modes; this issue is platform-specific to Roo. Retained for multi-agent reference.

<a id="issue-4"></a>

## Issue #4: Knowledge Not Applied [DOCUMENTED, behavioral]

**Trigger:** Memory exists with score 100 ("NEVER delete files, move to ARCHIVE"). Agent retrieves it, states compliance, then deletes anyway.
**Root cause:** Reading ≠ applying. Easy to retrieve and ignore. No enforcement mechanism. Speed prioritized over compliance.
**Solution:** Layer 4 — Memory Compliance Verification. Before each response: list retrieved memory IDs, identify applicable rules, state HOW the response follows each rule, check for conflicts. If action violates memory, do not proceed.
**Lesson:** Retrieved memory must be APPLIED, not just acknowledged. Acknowledgement is the failure mode, not the success mode.

<a id="issue-5"></a>

## Issue #5: Environment Assumption Failures [DOCUMENTED]

**Trigger:** Agent claims "dashboard fully operational"; user sees "0 memories" because of cached frontend.
**Root cause:** AI test environment (Puppeteer, fresh state, no cache) ≠ user environment (Chrome, existing data, network delays, cached JS/CSS).
**Solution:** Verify in user-equivalent conditions: hard refresh, cache cleared, existing data, post-restart. Always ask the user what they see (exact output) before claiming success.
**Lesson:** "It works for me" is not proof; account for caching and user-specific state.

<a id="issue-6"></a>

## Issue #6: Passive Protocol Enforcement Failure [FIXED v2.4+, guarded]

**Trigger:** Elefante has comprehensive protocols (Inception Memory, Tool Descriptions, Documentation), but agents skip them and re-discover failures the docs already documented (e.g., 15+ install attempts when the answer was in `docs/how-to/install.md`).
**Root cause:** ALL enforcement was PASSIVE — agent must choose to engage. Inception Memory must be searched. Tool Descriptions must be read. Documentation must be opened. None forced compliance.
**Solution:** Inject `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` on normal product-operation success and error paths. Minimal system/dashboard/directive-management responses deliberately avoid recursive policy blocks. `scripts/verify/verify_e2e_tests.py` proves first-success and first-error product responses inject the sequence.
**Lesson:** If exact routing is not injected on the operational paths where agents act or fail, agents will skip the protocol at the moment they need it most. Active injection is stronger than passive prose, but its scope must be documented exactly.

<a id="issue-7"></a>

## Issue #7: Developer Documentation Drift — Stale Paths, Versions, and Runtime Claims [FIXED AGAIN, guarded]

**Trigger:** Active guidance routed to deleted files and later recurred as stale release versions, ChromaDB-default claims, legacy MCP names, obsolete scoring formulas, broken relative links, and release-candidate language after v2.12.2 publication.
**Root cause:** Mutable facts were copied into many prose surfaces without source-derived guards. Historical evidence was also mixed into current instructions without a clear historical boundary.
**Solution:** Reconciled active user, developer, agent, proposal, example, and embedded MCP documentation against current source and the published release; separated historical records from current operational guidance; added release-version, active-link, MCP-surface, and scoring-contract regressions in `tests/test_developer_routing.py`.
**Lesson:** A documentation bug is not solved by editing the page where it was noticed. Current claims must derive from code or a single release authority, historical facts must be labeled, and executable links/contracts need automated guards.

<a id="issue-8"></a>

## Issue #8: Self-Protocol Verifier Drift — Path & Payload Assumptions [FIXED, guarded]

**Trigger:** `verify_e2e_tests.py --with-dashboard-open` reports `[FAIL]` while live MCP surface is healthy. Two cascading failures: dashboard snapshot path, then large-payload stream limit.
**Root cause:** Verifier encoded convenience assumptions instead of following live runtime behavior. (a) Checked only `temp_data_dir/dashboard_snapshot.json`, but `src.mcp.server` writes through `HOME`-derived `DATA_DIR`. (b) Used asyncio's default subprocess stream limit, too small for `elefante-ContextGet` payloads.
**Solution:** Stream limit raised to 1 MiB (`STREAM_LIMIT_BYTES = 1024 * 1024`). Snapshot path lookup now tries both `temp_home/.elefante/data/` and `temp_data_dir/`. Guarded by `TestSelfProtocolContract` tests.
**Lesson:** A maintained verifier is part of the product confidence surface; if it assumes the wrong runtime path or payload shape, it becomes a false bug generator.

<a id="issue-9"></a>

## Issue #9: Self-Protocol Cold-Start Deadlock [FIXED, guarded — Windows/Py3.11/CPU only]

**Trigger:** `verify_e2e_tests.py` hangs at Phase 3 with `TimeoutError`. Trace shows `from sentence_transformers import SentenceTransformer` never returns inside `asyncio.to_thread()`.
**Root cause:** The torch import deadlocks specifically when running in (a) a worker thread under (b) a piped-stdio MCP subprocess under (c) an anyio-managed event loop on Windows + Python 3.11. Likely a GIL/DLL-loader interaction with ProactorEventLoop's I/O completion ports. Direct in-process import works fine.
**Solution:** Pre-load the embedding model in `src/mcp/server.py` `__main__` block BEFORE `asyncio.run(main())`. Adds ~8-10s startup; makes runtime `_load_model()` a no-op. Approach #1 (longer timeout) and Approach #2 (move to a different thread) both failed — only Approach #3 (move to a different process-lifecycle phase) worked.
**Lesson:** When a blocking operation deadlocks in a thread under an event loop, moving it to a different thread doesn't help. Move it to a different PHASE of the process lifecycle — before the event loop starts. **Differentiate "slow" from "hung":** if a 180s timeout doesn't help, it's a deadlock, not latency.

<a id="issue-10"></a>

## Issue #10: Elefante Cold-Start Trigger Gap [FIXED partial — runtime global, host behavior varies]

**Trigger:** Agent answers Elefante-relevant questions from training data or local files without calling `elefante-Memory(action="search")`, even though the server is available.
**Root cause:** Three layers. (1) **Instruction delivery is workspace-scoped:** VS Code Copilot loads `copilot-instructions.md` only from the active workspace root's `.github/`. When the user opens a parent or sibling folder, the file is invisible. (2) **Cold-start bootstrap gap:** server-side directives only inject AFTER the first Elefante tool call — there is no delivery path before that first call. (3) **Orthogonal to MCP registration scope** — fixing where the server is declared does not fix where the instructions live.
**Solution:** v2.12.2 provides one account-level runtime and connects detected compatible hosts to it. Host-specific instruction delivery remains separate from registration and must be tested in each actual client; unimplemented surfaces remain Planned.
**Lesson:** A global memory runtime makes information available, but it cannot force every host to choose retrieval. Registration, instruction delivery, retrieval policy, and measured task use are separate contracts.

<a id="issue-11"></a>

## Issue #11: JSON Export Is Not a Backup [FIXED, guarded — portable import]

**Trigger:** User runs `export_memories.py --format json`, factory-resets, finds no script to re-import. Brain is gone.
**Root cause:** Three layers. (1) `export_memories.py` was built for offline analysis, not migration; no `import_memories.py` was ever written. (2) Embeddings excluded — the export calls `collection.get(include=["metadatas", "documents"])` but Elefante stores embeddings explicitly via `thenlper/gte-base`. (3) ChromaDB has no named embedding function in Elefante's collection — using its default (`all-MiniLM-L6-v2`) on upsert silently corrupts semantic search.
**Solution:** The checksummed binary backup/restore path remains the full recovery contract. `scripts/pipeline/import_memories.py` now provides a dry-run-first, additive JSON migration path: it validates every record, preserves memory IDs and metadata, regenerates embeddings through the configured local model, rejects existing IDs, requires `--confirm-stopped STOPPED` for apply plus a verified binary backup for non-empty targets, and rolls back partial writes. The analysis export does not contain graph topology, so JSON migration is not a full backup and CSV remains analysis-only.
**Lesson:** A write-only export is not a backup. Every export format needs a documented import path or must be explicitly labeled read-only. Never infer "exportable = restorable."

<a id="issue-12"></a>

## Issue #12: DOC_SYNC Protocol Bypass [MITIGATED, guard partial — parent class BUG-006]

**Trigger:** Direct-repo file-edit agent skips Loop Step 1 (`workspace/ISSUES.md` Known Issues check) at the moment of action, even with the constitution loaded into context. Reproduces BUG-006 in a new surface (file-edit) where the shipped MCP-response injection cannot fire.
**Root cause:** BUG-006's fix injects `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` into every MCP tool response — bound to `src/mcp/server.py`. **Direct-repo agents make file-edit decisions without ever calling Elefante MCP**, so no MCP response fires the injection. The orchestrator constitution is loaded once at session start and expected to be re-engaged voluntarily — exactly the passive-protocol failure class BUG-006 documented.
**Same-session recurrences observed (2026-05-02):** (1) authored §0.7 inside version-stamped filename without flagging the pattern; (2) ran an audit without re-reading 4 unedited READMEs; (3) authored Forbidden Patterns enumerating `HANDOFF-YYYY-MM-DD.md`, then left existing handoff files alive in `docs/planning/` for hours.
**Solution adopted (passive):** Documentation Skill section in `agents/orchestrator.md` (Closed Surface Map, Forbidden Patterns, Pre-write checklist, Required routing, New-File test, Failure conditions, Lifecycle).
**Solution adopted (active, filename subset):** `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents` fails CI on `HANDOFF-*`, `spec-v[0-9]*-*`, `NOTES*`, `scratch*`, `todo*`, `ideas-new*`, `CURRENT_STATE*`, `IDEA-[0-9]*`, `session-summary*` under `docs/`, `agents/`, `workspace/`.
**Active candidates pending (broader surface):** (a) pre-edit hook requiring `BUG-NNN | new` classification before any Edit/Write call; (b) maintained transcript-scanning verifier.
**Lesson:** An agent constitution loaded once at session start is a passive protocol. Every doc edit starts at Known Issues. No exceptions. Active guards beat prose at the moment of action.

<a id="issue-13"></a>

## Issue #13: Task Intelligence Judge Encoded Hidden Implementation Shape [BUG-044, MITIGATED, guarded]

**Trigger:** Source-grounded v2 retrieval reached relevant repair files and reduced one pilot's token/time cost, but both conditions failed an implementation-coupled hidden test. Eight valid black-box canaries now replace that judge class. Controlled results still do not show repeatable correctness lift: two tasks tied at 3/3, one harder pair failed in both conditions, and the only 0/3 to 2/3 restore signal exceeded the latency gate and came from one task cluster.
**Root cause:** The first judge required undisclosed patch shape. The repaired experiment then exposed separate failures: retrieval hit-rate is only navigation, delivery does not prove use, a broad memory directive may not supply the task-specific facts needed for execution, and the runner falsely encoded unmeasured retries/corrections as zero. Long workspace paths and inherited agent configuration also caused zero-token infrastructure failures that could be mistaken for task failures.
**Solution:** Preserve historical outcomes as diagnostic-only; bind behavioral canaries to exact base/known-good refs and fixture digests; self-test every eligible judge at both refs; isolate evaluator configuration; keep baseline-only screening independent from Task Brief construction; abort non-measurable CLI invocations; use short temp workspaces; represent unmeasured data as unknown; record judge, retrieval, selection, delivery, execution, and acceptance metadata; block invalid-judge execution by default; and block promotion until enough independently reviewed black-box tasks show causal outcome improvement.
**Lesson:** A valid judge, relevant retrieval, memory selection, memory delivery, agent use, correct execution, and acceptance are distinct gates. Do not promote on a proxy, a single favorable run, or a memory that was merely present.

<a id="issue-14"></a>

## Issue #14: Search Ranking Was Mistaken for Answer Context [BUG-045, FIXED AGAIN, guarded]

**Trigger:** `elefante-context` initially injected the raw top five search hits, and normal search told the agent that every result was authoritative. On 2026-08-14, a live replacement-task screen exposed a recurrence: Recall supplied unrelated SDD/developer-etiquette constraints for three real GitHub product questions instead of abstaining. A live positive control then caught the first repair rejecting the canonical mission on a paraphrased question. On 2026-08-15, the independently requested task `use Elefante to improve Elefante` exposed a narrower recurrence: generic Developer Etiquette was selected when `Elefante` was the only distinct matched term.
**Root cause:** Retrieval and answer delivery were initially treated as one operation. The first v2 guard counted an intrinsic evidence role (`constraint`, `decision`, `failure`, or `safeguard`) as both independent relevance and a question-specific action anchor; one live false positive matched only 3 of 28 task terms (10.7%) but passed because it was classified as a constraint. Replacing that error with one absolute lexical threshold overfit the negative case and discarded an explicitly user-enforced governing directive. The remaining short-query path still treated one of three distinct terms as both a direct answer and a role-text anchor; repeating the product name raised its apparent coverage without adding task evidence.
**Solution:** Keep broad search for exploration and one fail-closed answer selector for delivery. Text-only evidence for a multi-term question now requires at least two distinct matched terms before it can become a direct answer or ordinary role-text anchor. One-term factual questions remain eligible, and explicit path, graph, mandatory-governance, or semantically strong user-locked scoped-directive anchors retain their separate bounded paths. Broad search remains inspectable, while always-inject policy remains governed separately.
**Lesson:** A retrieved role or project identity is not proof of task applicability, but explicit user governance is also not ordinary ranking metadata. Test false-positive abstention, genuine one-term facts, and the intended user-enforced decision path together.

<a id="issue-15"></a>

## Issue #15: Retrieval Exposure Was Mistaken for Memory Use [BUG-046, FIXED in development, guarded]

**Trigger:** Ordinary MCP search and automatic context delivery appended retrieved IDs to session history, persisted co-activation, and incremented access metadata through the normal orchestrator path. Repeated exposure could therefore change future ranking without evidence that an agent used the memory or that the task improved.
**Root cause:** Candidate discovery, delivery, declared use, and task outcome were collapsed into one behavioral feedback signal. This contaminated both memory lifecycle behavior and Task Intelligence evaluation.
**Solution:** Search now defaults to non-reinforcing and the MCP search/automatic context paths explicitly disable access mutation. Legacy exposure history is discarded rather than reused as use evidence. The development-only `record_use` boundary accepts only active IDs delivered by the same live Task Intelligence trace and writes a reversible event to a separate metadata ledger. It does not change access history, co-activation, or ranking.
**Lesson:** Retrieval is exposure; declared use is a separate event; neither is proof of task utility. Evaluation must attribute improvement to observable outcomes, not search frequency.

<a id="issue-16"></a>

## Issue #16: Task Intelligence Stopped at Retrieval [BUG-048, INFRASTRUCTURE FIXED, effectiveness open]

**Trigger:** The Task Brief compiler could select evidence and the evaluator could score historical repairs, but no production invocation tied a host task to delivery, declared use, outcome, inspection, retraction, and the exact durable memory being tested.
**Root cause:** Offline evaluation, runtime delivery, and learning signals were separate partial systems. A retrieved memory could look persuasive without proof that it was the reviewed record, reached the agent, stayed within budget, or changed an observable outcome.
**Solution:** Add one default-off Task Intelligence MCP surface with independent pilot delivery, a session-bound metadata-only ledger, idempotent use/outcome events, retraction, and no ranking mutation. Bind a sealed export of a real durable memory to an independently reviewed black-box base/fix canary; preflight now proves exact selection, deterministic rendering, hard budget, no hidden-answer leakage, and zero model calls before evaluation spend.
**Lesson:** A production intelligence loop needs provenance from invocation through outcome. Deterministic preflight proves the pipe; only controlled paired outcomes can prove lift.

<a id="issue-17"></a>

## Issue #17: Evaluation Lost Causal Truth Between Retrieval and Judge [BUG-049, FIXED, guarded]

**Trigger:** A real-memory treatment received the right modules and changed only the public doctor CLI, yet failed because the judge used an undisclosed `~/.bob` convention. Earlier diagnostics also discarded failed workspaces, could reuse filenames after task changes, and let repeated implementation chunks crowd out validation evidence.
**Root cause:** The evaluator treated candidate rank, task identity, preserved failure evidence, and judge validity as separate conveniences instead of one immutable causal contract. A nearby symbol or hidden environment convention could therefore dominate the verdict.
**Solution:** Preserve failed workspaces by default; bind schema-v3 outcomes to the complete task contract; keep broad source candidates but reserve declared-context chunks, diverse ownership files, and later stages; classify tests as safeguards; expose selected source paths in preflight; and require every judge convention to exist in the frozen task or base. The corrected canary still fails on base and passes on the known fix, and the preserved treatment patch passes it without another model run.
**Lesson:** Before spending another run, prove that the brief contains the target, ownership chain, and safeguard, and that the judge tests only disclosed behavior. A verdict without those properties is evaluator evidence, not product evidence.

<a id="issue-18"></a>

## Issue #18: Runtime Delivery Skipped Current-Source Validation [BUG-050, FIXED, guarded]

**Trigger:** A digest-stale user-locked memory was blocked by the explicit Task Brief but delivered by normal search context, the context prompt, and opt-in tool-response context.
**Root cause:** Runtime paths shared the ranking compiler but not the service step that cloned candidates and compared source-file digests. Selector parity was mistaken for full delivery-pipeline parity.
**Solution:** Centralize candidate cloning and source annotation in `TaskBriefService.prepare_candidates`; route all answer-delivery paths through one server boundary before compilation; regress every public delivery path with the same digest-mismatch case.
**Lesson:** A governed selector is only as safe as its complete preprocessing chain. Runtime and evaluation must share validation, selection, and budget boundaries—not only ranking code.

<a id="issue-19"></a>

## Issue #19: Installed Memory Was Available but a Normal Question Did Not Recall It [BUG-051, FIXED, guarded]

**Trigger:** A clean Codex session answered `UNKNOWN` even though Elefante was globally installed and the requested durable fact existed. An explicit Recall then requested approval; after approval was removed, selection still rejected the direct fact and successful output wasted context on internal wrappers.
**Root cause:** Four contracts were incorrectly treated as one: host registration, retrieval routing, safe tool authorization, and answer selection. The selector also reused an implementation-actionability threshold for factual questions, while the generic response decorator ignored Recall's narrow customer purpose.
**Solution:** Keep registration separate, add one manifest-owned reversible global Codex routing block, declare Recall read-only/idempotent/non-destructive/closed-world, allow a strong `direct_answer` to bypass only the implementation-actionability threshold, and return a seven-field Recall payload without internal wrappers. Rebuild and install the exact customer archive, then prove the journey in an empty directory with Codex JSON events.
**Lesson:** Availability is not use. A customer memory path is complete only when the host routes a normal question, invokes safely, selects answer-bearing evidence, and returns less context than it saves.

<a id="issue-20"></a>

## Issue #20: Relevant Memory Did Not Supply the Decisive Task Evidence [GAP-053, OPEN]

**Trigger:** Task 032's sealed installation-contract memory was retrieved, selected, and delivered in every treatment, yet treatment accepted 0/3. The two completed source-only controls also failed.
**Root cause:** Semantic relevance was mistaken for decision value. The memory described global runtime architecture and host coverage, but the black-box task required a real public `elefante-Recall` MCP surface; all five preserved patches changed routing or installer files and omitted that API.
**Solution:** Reject task 032's tested memory component and preserve its `STOP`. Before another model run, require a different task whose prior memory contributes one specific decision-relevant fact absent from the source-only Brief, then prove that difference in deterministic preflight. The evaluator now compares source-only and memory Briefs directly and stops redundant controls after a bound treatment 0/3.
**Lesson:** A memory should be selected because it changes the next task action, not because it is topically related. Retrieval, selection, and delivery are healthy only when the evidence portfolio contains the missing decision input.

<a id="issue-21"></a>

## Issue #21: Recall-Only Workflow Had No Durable Decision Supply [GAP-054, FIXED in development]

**Trigger:** After Task 032 stopped, a model-free search for a different eligible memory-task pair returned `no_match`. The live customer store contained five records: one synthetic passcode, two unverified related specifications, and two contradictory records; it did not contain Elefante's user-declared canonical mission.
**Root cause:** The installed Codex guidance actively routed prior-context questions through Recall but had no active rule for an explicit user request to remember something across sessions. It also treated a successful write as sufficient even though governance can make a stored record ineligible; availability, capture, deliverability, and outcome had been collapsed into “memory exists.”
**Solution:** Extend the manifest-owned reversible Codex block and customer entrypoint with one narrow capture contract: only an explicit cross-session remember request or canonical/non-negotiable declaration triggers search-first add/update; the mutation is `user_directed`; user locks and permanent retention require explicit protection; ordinary conversation and secrets are excluded. Scope must be an exact identifier rather than prose, triggered delivery must name future-question phrases, and one likely future question must pass Recall after the write.
**Proof:** The live store initially had five unrelated or unsuitable records and the complete candidate-selection question returned `no_match`. Pilot memory `0b27fa62-d459-4029-a390-391305ab555d` was then stored. Raw retrieval ranked it first, but the first Recall rejected its descriptive scope and supplied a loose developer specification; after the same record's scope was corrected to literal `elefante`, Recall supplied only the canonical mission. This proves capture and deliverability, not a better task outcome.
**Lesson:** Recall cannot improve a later task when the workflow never captured the decision, and `stored` does not mean `deliverable`. Safe capture is an explicit, closed-loop causal stage; it is not automatic conversation harvesting and it is not evidence of task lift.

<a id="issue-22"></a>

## Issue #22: Evaluator Separated Task Value From Overall Token Cost [GAP-055, FIXED in development]

**Trigger:** The product objective was restated as intelligence per overall token, but the paired report measured acceptance and retries as effectiveness while using input-token growth only as a secondary cost ceiling; output tokens were omitted from the gate.
**Root cause:** Outcome quality and token cost were evaluated in separate gates instead of one paired value measure. This could recognize correctness lift without showing its overall-token efficiency and could not recognize equal accepted value delivered with reliably fewer total tokens.
**Solution:** Define the current observable value proxy as one unit for a black-box accepted outcome and zero for failure; define total tokens as input, including cached input, plus output. Report accepted outcomes per million tokens and a task-clustered difference from complete pairs, while separately reporting all observed spend so early-stop work is not hidden. The gate requires at least one treatment acceptance, no acceptance-count regression, and a 95% lower bound above zero; historical consumed evidence remains non-promotable.
**Lesson:** Measure accepted value and complete cost together. Cheap failure is zero intelligence, and raw ratios across unrelated task mixes are not comparable evidence.

<a id="issue-23"></a>

## Issue #23: Declarative Triggers Had No Delivery Path [GAP-056, FIXED in development]

**Trigger:** `trigger` and `surfaces_when` metadata could describe when a memory should matter, but no runtime path examined an explicit file, terminal-error, or conversation context. A caller had to guess a semantic query and could miss an exact opt-in reminder.
**Root cause:** The schema hint was passive. Adding automatic host interception would cross the local memory authority boundary and introducing another semantic retriever would duplicate the existing search contract, so no bounded delivery surface had been wired.
**Solution:** Extend the existing `elefante-Memory(action="search")` path with optional `surface_context`. It performs one bounded read-only scan, considers only `injection_policy="triggered"` memories, requires a case-insensitive literal phrase from `trigger` or `surfaces_when`, returns at most three matches with an explicit trigger explanation, and preserves lifecycle, scope, source-trust, conflict, and privacy gates. If a workspace filter is supplied, it uses the shared current-source digest check on a deep copy and skips stale records. It never updates access or graph state. The shared answer-context compiler reports a bounded warning when a relevant candidate has a stored conflict relationship or contradictory status; it withholds the candidate, selects neither side, and omits internal IDs from the warning and Recall text. The 2026-08-28 closure then added typed file, terminal-error, and conversation envelopes for every manifest host family, secret scrubbing and hard bounds, and a loopback `/events/surface` adapter that feeds the same read-only selector without persisting the event. Conservative semantic detection and dry-run-first reversible `Memory(resolve)` repair close the related contradiction path without allowing an arbitrary automatic winner.
**Proof:** `tests/test_proactive_surfacing.py` covers policy/literal requirements, context separate from the semantic query, scope/trust/lifecycle/conflict/privacy gates, stale-source rejection, result bounds, Task Brief delivery, and read-only behavior. `tests/test_host_event_adapters.py` and `tests/test_host_event_endpoint.py` cover host normalization, privacy, bounds, and daemon integration. `tests/test_conflict_detection.py` and `tests/test_conflict_resolution.py` cover abstention, equivalent consolidation, explicit winner authority, protected records, rollback, and scope separation. `tests/test_mcp_daemon.py` covers answer-context and opt-in warning delivery without selecting or exposing the conflicted memory. The published v2.12.3 surface remains unchanged.
**Lesson:** A declarative trigger is not a shipped behavior. Make proactive delivery explicit, opt-in, literal, bounded, and read-only before considering host automation or outcome claims.

---

## Cross-bug pattern (extracted to `../lessons.md`)

The recurring rules from these 23 issues:

1. **STATE → DO → VERIFY in the same response** — analysis without action is entertainment. Issues #1, #4.
2. **Trigger words require proof** — "done" / "ready" / "fixed" must include verification output. Issue #2.
3. **Active injection beats passive prose** — passive protocols are skipped at the moment they're needed most. Issues #6, #12.
4. **Source + memory + verification must agree** — fix in one layer is not a fix. Issues #7, #8.
5. **Differentiate "slow" from "hung"** — timeouts cannot fix deadlocks. Issue #9.
6. **Broadest scope for behavioral instructions** — system-level injection, not workspace-level file presence. Issue #10.
7. **Every export needs a documented import** — exportable ≠ restorable. Issue #11.
8. **Judge observable outcomes, not hidden patch shape** — an invalid acceptance test can erase real improvement or reward overfitting. Issue #13.
9. **Separate discovery from answer delivery** — broad retrieval can find useful material, but only a bounded, question-specific evidence set belongs in an answer. Issue #14.
10. **Separate exposure from use** — retrieval and delivery cannot reinforce memory or co-activation before a caller explicitly acknowledges use. Issue #15.
11. **Prove the whole evidence path** — bind invocation, selected memory, delivery, declared use, and outcome before attributing benefit. Issue #16.
12. **Bind and preserve evaluation truth** — task, judge, evidence portfolio, failed workspace, and verdict must remain one inspectable contract. Issue #17.
13. **Share the complete delivery pipeline** — preprocessing, source validation, selection, and budgets must be identical across runtime paths. Issue #18.
14. **Prove the normal-question journey** — registration, routing, authorization, selection, and payload economy are separate gates. Issue #19.
15. **Select for decision value, not topical similarity** — a relevant memory that cannot change the next action is context cost, not Task Intelligence. Issue #20.
16. **Capture and verify before depending on Recall** — explicit user-directed durable decisions need a governed write plus one future-question delivery check before a later task can depend on them. Issue #21.
17. **Measure accepted value against complete token cost** — input-only savings and cheap failures cannot establish intelligence per overall token. Issue #22.
18. **Treat declarative triggers as opt-in delivery gates** — a stored trigger is not permission for broad automatic injection; require explicit context, literal matching, bounded output, and the same governance/privacy gates as normal delivery. Issue #23.

Distill any new repeating rule into `../lessons.md`. Postmortems hold the bug-specific narrative; `lessons.md` holds the cross-bug edge.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/ai-behavior-full.md`](_archive/ai-behavior-full.md).

This file (`ai-behavior.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
