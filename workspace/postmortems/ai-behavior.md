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

**Trigger:** Active guidance routed to deleted files and later recurred as stale release versions, ChromaDB-default claims, legacy MCP names, obsolete scoring formulas, broken relative links, release-candidate language, v2.12.2 protocol headers, pre-v2.13 proposal state, incomplete Memory action lists, duplicate BUG IDs, incorrect ledger counts, and a `restart_elefante.py --version` flag that first did nothing and then compared only the helper's own import rather than the restarted process.
**Root cause:** Mutable facts were copied into many prose surfaces without source-derived guards. Historical evidence was mixed into current instructions without a clear historical boundary, and the first CLI repair treated source consistency as runtime evidence.
**Solution:** Reconciled active user, developer, agent, proposal, example, embedded MCP, operational CLI, and issue-ledger documentation against current source and the published release; separated historical records from current operational guidance; and made the direct server author a private mode-0600 PID/version receipt that the restart helper verifies against the exact launched PID. Protocol-version, active-proposal, unique-ID/derived-count, release-version, active-link, MCP-surface, action-schema, process-identity, and scoring-contract regressions live in `tests/test_developer_routing.py`.
**Lesson:** A documentation bug is not solved by editing the page where it was noticed. Current claims must derive from code or a single release authority, historical facts must be labeled, executable links/contracts need automated guards, and a controller's own import cannot attest a child process.

<a id="issue-8"></a>

## Issue #8: Self-Protocol Verifier Drift — Path, Payload, and Platform Assumptions [FIXED AGAIN, guarded]

**Trigger:** `verify_e2e_tests.py --with-dashboard-open` reported `[FAIL]` while the live MCP surface was healthy. The original cascading failures were dashboard snapshot path and large-payload stream limit; the 2026-08-28 recurrence used `/usr/bin/true` as its browser stub despite documenting a Windows invocation and also risked presenting the direct-handler harness as customer-transport proof. The 2026-08-30 recurrence then used legacy update/delete actions without the Verified Correct lifecycle and did not create the strict registered project now required by customer Remember, Recall, and Task Intelligence. On 2026-09-01, identical default runs produced 49/52 and then 52/52: the failing run saw three of four fixture memories, one tagged graph edge, and two of three cleanup deletions.
**Root cause:** The verifier encoded convenience assumptions instead of following current product behavior. It checked one snapshot path, used asyncio's default subprocess stream limit, hard-coded a POSIX executable, and kept old mutation/scope shortcuts after the customer contract changed. Direct handler and shipped bridge/daemon topologies were not named as separate evidence layers. The repeatability recurrence exposed a product defect: preference reassertion fell back to any semantic candidate when no preference existed. A random UUID tag could contribute enough shared lexical terms for the preference fixture to reuse the graph decision ID; deleting the preference then removed the graph anchor and caused every later count mismatch.
**Solution:** Raise the stream limit to 1 MiB, check both isolated snapshot paths, build an isolated Python no-op browser command from the active interpreter, and document the direct-handler versus customer bridge/daemon proof boundary. The harness now creates one strict registered project, verifies project-scoped Remember with a durable Recall cue, performs Edit and permanent delete through `Memory(action="correct")`, and searches Task Intelligence using the canonical registered root. Preference reassertion now filters to actual preference memories, with regressions proving that cross-type matches remain distinct while preference-to-preference reinforcement still works. The harness also requires four unique fixture IDs before continuing. Guarded by `TestSelfProtocolContract`, platform-stub, strict-project, verified-correction, persistence, and process transport tests; three consecutive isolated runs completed 52/52 after the repair.
**Lesson:** A maintained verifier is part of the product confidence surface. It must evolve with the customer lifecycle, fail at the first broken identity invariant, and treat a green rerun after a red run as diagnosis evidence rather than repeatability proof.

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

## Issue #13: Release-Contract Truth Drift [BUG-044, FIXED guarded]

**Trigger:** A whole-product audit found v2.12.2 publicly released while active entrypoints and their tests still declared v2.12.1; the scoring reference documented retired formulas and nonexistent modules; dashboard and ETL copy promised semantics absent from their execution paths. The v2.13.0 Gauntlet recurrence then found a maintained v2.12.2 showcase baseline, shipped proposals described as unreleased, 16-tool active inventories, and trigger copy that still called proactive surfacing future behavior. The 2026-09-01 dashboard recurrence showed an inventory-selected memory as “shaping your next answer,” implied compatible agents carried records forward, and filled an incomplete relationship trail with unrelated high-score records even though Home had no query-specific Recall event for those claims.
**Root cause:** Release and feature-truth checks asserted hand-maintained literals instead of testing the current shipped contract. Passing CI therefore preserved the stale state rather than detecting it. The dashboard recurrence made the same category error at the presentation layer: a maintenance proxy was treated as evidence of task relevance and agent delivery.
**Solution:** Reconciled release and protocol entrypoints with the published tag, derived the showcase baseline from `src.__version__`, replaced scoring prose from source formulas, labeled dashboard search as snapshot-only, distinguished triggered delivery from general ranking, corrected shipped proposal status/tool counts and Distiller paths, and extended maintained regressions across all affected surfaces. The live HTML-guide recurrence added direct source-checkout subprocess coverage: dashboard scripts bootstrap the repository root, the pipeline parses `--help` before data access, and the generated showcase must pass the maintained strict verifier. The source dashboard now separates a maintenance-only Briefing from the project-scoped Recall Inspector, follows explicit graph edges only, labels Library/Review without grading truth or utility, supports No action, and regression-checks the removed inference copy.
**Lesson:** Contract tests must reject obsolete claims, not merely freeze yesterday's claim. Publication truth, source behavior, UI language, and reference documentation must agree.

**User-guide recurrence (2026-09-03):** The published documentation entry was a catalogue, and its dashboard link opened HTML source on GitHub. The detailed guide also conflated Home with Recall results, hidden with disabled project controls, and missing with observed provider usage. The correction makes the existing `docs/README.md` a workflow-first user guide, retains and clarifies the HTML reference, explains how to open it, and removes internal-plan/owner-specific wording. Source review and `test_user_guide_explains_the_workflow_before_technical_reference` plus `test_dashboard_user_guide_links_resolve_without_internal_plans` guard the entry flow, all six dashboard sections, local links and anchors. The frozen v2.15.0 tag is not rewritten; the authorized correction's publication state lives in `PLANNING.md §2.7`. Local HTML rendering was blocked by browser policy, so it is not claimed as visually verified.

**Demo and website-routing recurrence (2026-09-04):** The GitHub front door again
mixed first-use guidance with optional operator surfaces, while `examples/`
contained only agent-integration Markdown and no customer demo. The website had
a complete-looking guide but ended in three GitHub documentation exits, so the
customer journey and the technical source competed. The local repair preserves
all advanced and historical material, makes one real-memory loop the common
entry, adds explicit Use and Behavior evidence for every published capability,
and leaves one footer exit to exact source and deep technical reference. Core
routing and release tests pass 75 checks. The website candidate passes its
content contract, lint, 13 unit tests, production and compatibility builds,
21 route checks, 17 accessibility checks, and 13 visual checks. Fresh
desktop/phone and light/dark browser inspection found no clipping or hierarchy
defect. Core PR #36 published the GitHub documentation as `5407049`; website
PR #29 published the first-party guide and passed exact-live Vercel verification
as `8e87458`. The v2.15.2 release and installed runtime were not changed.

<a id="issue-14"></a>

## Issue #14: Task Intelligence Judge Encoded Hidden Implementation Shape [BUG-046, MITIGATED, guarded]

**Trigger:** Source-grounded v2 retrieval reached relevant repair files and reduced one pilot's token/time cost, but both conditions failed an implementation-coupled hidden test. Eight valid black-box canaries now replace that judge class. Controlled results still do not show repeatable correctness lift: two tasks tied at 3/3, one harder pair failed in both conditions, and the only 0/3 to 2/3 restore signal exceeded the latency gate and came from one task cluster.
**Root cause:** The first judge required undisclosed patch shape. The repaired experiment then exposed separate failures: retrieval hit-rate is only navigation, delivery does not prove use, a broad memory directive may not supply the task-specific facts needed for execution, and the runner falsely encoded unmeasured retries/corrections as zero. Long workspace paths and inherited agent configuration also caused zero-token infrastructure failures that could be mistaken for task failures.
**Solution:** Preserve historical outcomes as diagnostic-only; bind behavioral canaries to exact base/known-good refs and fixture digests; self-test every eligible judge at both refs; isolate evaluator configuration; keep baseline-only screening independent from Task Brief construction; abort non-measurable CLI invocations; use short temp workspaces; represent unmeasured data as unknown; record judge, retrieval, selection, delivery, execution, and acceptance metadata; block invalid-judge execution by default; and block promotion until enough independently reviewed black-box tasks show causal outcome improvement.
**Lesson:** A valid judge, relevant retrieval, memory selection, memory delivery, agent use, correct execution, and acceptance are distinct gates. Do not promote on a proxy, a single favorable run, or a memory that was merely present.

<a id="issue-15"></a>

## Issue #15: Search Ranking Was Mistaken for Answer Context [BUG-047, FIXED locally]

**Trigger:** `elefante-context` initially injected the raw top five search hits, and normal search told the agent that every result was authoritative. On 2026-08-14, a live replacement-task screen exposed a recurrence: Recall supplied unrelated SDD/developer-etiquette constraints for three real GitHub product questions instead of abstaining. A live positive control then caught the first repair rejecting the canonical mission on a paraphrased question. On 2026-08-15, the independently requested task `use Elefante to improve Elefante` exposed a narrower recurrence: generic Developer Etiquette was selected when `Elefante` was the only distinct matched term. On 2026-09-02, the exact question for archived fixture `VISIBLE-V2-9202` selected the unrelated canonical mission instead of returning `no_match`.
**Root cause:** Retrieval and answer delivery were initially treated as one operation. The first v2 guard counted an intrinsic evidence role (`constraint`, `decision`, `failure`, or `safeguard`) as both independent relevance and a question-specific action anchor; one live false positive matched only 3 of 28 task terms (10.7%) but passed because it was classified as a constraint. Replacing that error with one absolute lexical threshold overfit the negative case and discarded an explicitly user-enforced governing directive. The remaining short-query path still treated one of three distinct terms as both a direct answer and a role-text anchor; repeating the product name raised its apparent coverage without adding task evidence. The identifier recurrence then showed that high semantic similarity plus generic words such as `verification`, `code`, and `acceptance` could satisfy the same threshold while ignoring the query's distinguishing identifier.
**Solution:** Keep broad search for exploration and one fail-closed answer selector for delivery. Text-only evidence for a multi-term question requires at least two distinct matched terms before it can become a direct answer or ordinary role-text anchor. An identifier-bearing question additionally requires an identifier-bearing match on the ordinary text-only path. One-term factual questions remain eligible, and exact Recall cues, explicit path or graph evidence, mandatory governance, and semantically strong user-locked scoped directives retain their separate bounded paths. Broad search remains inspectable, while always-inject policy remains governed separately.
**Lesson:** A retrieved role, project identity, or shared workflow vocabulary is not proof of task applicability, but explicit user governance is also not ordinary ranking metadata. Test false-positive abstention, the distinguishing identifier, genuine one-term facts, and the intended user-enforced decision path together.

**2026-09-02 recurrence and candidate boundary:** The three curated customer
memories are present; this is not missing ingestion. `What is Elefante for?`
matches only `elefante` at the text gate, so the installed selector withholds
the purpose memory. Dropping question words alone would also admit the two
same-product distractors. An uncommitted candidate therefore compares the
complete question with existing scoped Recall cues using the already loaded
local model, without changing durable records or the ordinary lexical guard.
The candidate's bounds and limitations are recorded in
[`docs/reference/scoring.md`](../../docs/reference/scoring.md#recall-cue-candidate-not-accepted).

**Acceptance result:** An isolated real SQLite/Kuzu dashboard selected the
unchanged purpose body, preserved the dashboard and solo-operator results,
and abstained on the unrelated sourdough question. Review and settled empty
search also remained correct. The MCP self-protocol passed 52/52 checks.
The initial positive saved-question checks passed only 5/6. Adding the frozen
missing-fact controls gives **8/15 correct**: `Where are the backup batteries
kept?` misses the recorded hall-cabinet location, while six questions asking
for absent brands, quantities, prices or durations receive same-topic records.
These expected results remain failing tests, not rewritten fixtures or claimed
successful abstentions. The candidate is
**not accepted for commit or installation**. Existing live memories and the
installed runtime were not changed. This is functional evidence, not general
retrieval effectiveness or task-value lift.

The failed location question's measured cue cosine was `0.8730`, versus
`0.7017` for the unrelated herb-watering cue. Its `0.1714` margin clears the
candidate's separation guard but its score does not clear the `0.93` floor.
One universal absolute cue threshold has not been calibrated across question
types; a product-name success must not be presented as that calibration.

**Proof repair:** Two pre-existing MCP stale-source tests also failed on the
clean `9cbb3bb` baseline because their temporary workspace was unregistered.
Their fixtures now register and bind that workspace so the unchanged
assertions actually exercise stale-source blocking. All 24 targeted MCP
Recall/answer-context tests pass; the semantic acceptance failures remain.

**Root-cause follow-through:** The relevant battery body has raw cosine
`0.8722` but only one literal term overlap; the old guard rejects it. An
irrelevant dashboard-price question has raw cosine `0.8970` and two topic
words, so the old guard admits it without the cue candidate. Topic similarity
does not prove the requested fact exists. A model-free token-alignment probe
also missed an ordinary staffing question and was discarded, not installed.
Do not keep tuning example keywords or thresholds to call this solved.

A separate live Keep both failure came from splitting Recall's 450-token
answer budget into three stage quotas. Sharing that same bounded budget
admits both eligible records; its fail-first regression and isolated browser
Keep both, Edit, Replace, Archive/Restore, conflict Resolve and full backup
restore passed. Full restore reproduced all five record hashes after 5→4→5.
The browser also exposed a drawer blocking navigation and a reconnect banner
trapped below portal dialogs; their repairs were verified with real clicks.
Reconnect preserved the open correction draft and made no automatic write.
These repairs do not clear the 8/15 relevance blocker or authorize installing
the failed combined candidate.

**Further bounded investigation (2026-09-02, rejected):** Coverage now includes
27 fixed questions across ten everyday domains. The preserved lightweight
candidate passes 16/27; its original 15-case subset remains 8/15. These reused
cases are regressions, not an unseen holdout. No expectation or customer
memory was changed to manufacture a pass.

Offline MS MARCO MiniLM, SQuAD2 MiniLM, Qwen3 Reranker 0.6B, and Quora
DistilRoBERTa probes did not meet the selection contract. Qwen3.5-2B variants
also failed, including the actual staffing-constraint question; output-format
guards did not establish semantic correctness. The experimental model hooks
were removed, the preceding repairs restored, and 55 focused UI/Recall/embedding
guards passed. No candidate was committed or installed. The rejected prototype
and 5.9 GiB of downloaded test assets are recoverably isolated at
`/tmp/elefante-rejected-recall.PqRtxE`, outside the source and active model cache.
A larger-model experiment would change the product's resource footprint and
requires the user's decision; it is not an established repair. Do not repeat
these model/format probes or equate parser success with useful memory selection.

**Focused repair (2026-09-03):** No larger model was added. The shared compiler
now checks the explicit target of a saved question before accepting topic-only
text evidence. A location is not a time, a quantity is not a choice, and a named
property cannot be supplied solely by shared subject words. Matching targets
permit bounded lower-cosine paraphrases; closed alternatives also compare the
requested property separately from the subject. Unknown wording keeps the
existing conservative path, and open-ended guidance is not restricted to the
question form used when saving a constraint. Scope, privacy, source trust,
identifiers, conflicts and lifecycle checks remain independent.

The original 27 regression questions pass unchanged. Twelve added Elefante,
alternatives and vocabulary checks bring the real cached-model result to 39/39; the focused
dashboard/control/verified-operation/routing suite passes 441 checks and the
real isolated MCP self-protocol passes 52/52. These cases establish bounded
regression coverage, not universal language understanding or task-value lift.
Live browser checks verified the original purpose question, missing price,
two-memory Keep both delivery, Edit, Archive/Restore, verified backup and full
data restore, and reconnect with an unchanged draft. The full restore recovered
the archived record's version and lifecycle; an empty search showed zero rows
without the old detail. UI follow-through cleared stale search/review filters on
Recall inspection, closed old details when starting a new search, moved the
reconnect banner outside the shell's stacking context without covering the
header, and removed the second Recall dialog's unfounded abstention claim.
The existing HTML guide and scoring reference describe the actual behavior.
Local package installation requires the exact tested commit and a verified
data-preserving installer receipt; no push or public release belongs here.

**Natural-task recurrence, 2026-09-03:** The actual graph-repair question found
the existing verification memory but repeated words became mandatory anchors
and rejected it. Repetition now only disambiguates otherwise generic evidence;
independent direct answers and decision-bearing records keep their existing
coverage and relevance gates. A second, independent deployment case exercises
the same rule without Elefante vocabulary.

Negative tests and a live price/month question then exposed topic-only delivery
when a memory had no cue or its cue had unknown focus. Explicit named properties
must be represented in the body or supported by the existing cue path; quantity
questions need quantitative evidence or a matching cue. Scope, privacy,
identifiers, trust, conflicts and budgets are unchanged. Regressions include
uncued positive facts and numeric/word quantities, not merely abstention tests.
The focused Recall suites pass 116 tests, including the unchanged cached-model
cases and the real price/month reproduction. This is bounded functional proof,
not evidence of universal understanding or representative task-quality lift.

**First-use paraphrase recurrence, 2026-09-03:** A release rule passed its saved
question and a new “How do we…” question but failed “What checks are needed…”.
The grammar mistook a procedural noun for an absent factual property. Classify
procedural questions as methods; recognize single-noun subject questions without
an auxiliary so an unrecorded supplier is not returned from shared topic words.
Specification/directive metadata can establish that a record is a rule or
constraint, but cannot establish an unrelated requested fact. No embedding,
margin, scope, privacy or conflict threshold changed. Four of eight preregistered
release/import cases failed before the correction; all eight pass afterwards,
with the prior selection suite unchanged. Independent review caught plural
category handling; the full suite then caught an overbroad category exception.
A type label establishes only an unqualified rule/constraint category, not a
qualified property such as staffing constraints. The final 150 focused tests
(56 cached-model cases) preserve the failed cases and eight singular/plural
positive/negative checks. These consumed regressions are not a new holdout or
outcome-lift claim.

<a id="issue-16"></a>

## Issue #16: Retrieval Exposure Was Mistaken for Memory Use [BUG-048, FIXED in development, guarded]

**Trigger:** Ordinary MCP search and automatic context delivery appended retrieved IDs to session history, persisted co-activation, and incremented access metadata through the normal orchestrator path. Repeated exposure could therefore change future ranking without evidence that an agent used the memory or that the task improved.
**Root cause:** Candidate discovery, delivery, declared use, and task outcome were collapsed into one behavioral feedback signal. This contaminated both memory lifecycle behavior and Task Intelligence evaluation.
**Solution:** Search now defaults to non-reinforcing and the MCP search/automatic context paths explicitly disable access mutation. Legacy exposure history is discarded rather than reused as use evidence. The development-only `record_use` boundary accepts only active IDs delivered by the same live Task Intelligence trace and writes a reversible event to a separate metadata ledger. It does not change access history, co-activation, or ranking.
**Lesson:** Retrieval is exposure; declared use is a separate event; neither is proof of task utility. Evaluation must attribute improvement to observable outcomes, not search frequency.

<a id="issue-17"></a>

## Issue #17: Task Intelligence Stopped at Retrieval [BUG-050, INFRASTRUCTURE FIXED, effectiveness open]

**Trigger:** The Task Brief compiler could select evidence and the evaluator could score historical repairs, but no production invocation tied a host task to delivery, declared use, outcome, inspection, retraction, and the exact durable memory being tested.
**Root cause:** Offline evaluation, runtime delivery, and learning signals were separate partial systems. A retrieved memory could look persuasive without proof that it was the reviewed record, reached the agent, stayed within budget, or changed an observable outcome.
**Solution:** Add one default-off Task Intelligence MCP surface with independent pilot delivery, a session-bound metadata-only ledger, idempotent use/outcome events, retraction, and no ranking mutation. Bind a sealed export of a real durable memory to an independently reviewed black-box base/fix canary; preflight now proves exact selection, deterministic rendering, hard budget, no hidden-answer leakage, and zero model calls before evaluation spend.
**Lesson:** A production intelligence loop needs provenance from invocation through outcome. Deterministic preflight proves the pipe; only controlled paired outcomes can prove lift.

<a id="issue-18"></a>

## Issue #18: Evaluation Lost Causal Truth Between Retrieval and Judge [BUG-051, FIXED, guarded]

**Trigger:** A real-memory treatment received the right modules and changed only the public doctor CLI, yet failed because the judge used an undisclosed `~/.bob` convention. Earlier diagnostics also discarded failed workspaces, could reuse filenames after task changes, and let repeated implementation chunks crowd out validation evidence.
**Root cause:** The evaluator treated candidate rank, task identity, preserved failure evidence, and judge validity as separate conveniences instead of one immutable causal contract. A nearby symbol or hidden environment convention could therefore dominate the verdict.
**Solution:** Preserve failed workspaces by default; bind schema-v3 outcomes to the complete task contract; keep broad source candidates but reserve declared-context chunks, diverse ownership files, and later stages; classify tests as safeguards; expose selected source paths in preflight; and require every judge convention to exist in the frozen task or base. The corrected canary still fails on base and passes on the known fix, and the preserved treatment patch passes it without another model run.
**Lesson:** Before spending another run, prove that the brief contains the target, ownership chain, and safeguard, and that the judge tests only disclosed behavior. A verdict without those properties is evaluator evidence, not product evidence.

<a id="issue-19"></a>

## Issue #19: Runtime Delivery Skipped Current-Source Validation [BUG-052, FIXED, guarded]

**Trigger:** A digest-stale user-locked memory was blocked by the explicit Task Brief but delivered by normal search context, the context prompt, and opt-in tool-response context.
**Root cause:** Runtime paths shared the ranking compiler but not the service step that cloned candidates and compared source-file digests. Selector parity was mistaken for full delivery-pipeline parity.
**Solution:** Centralize candidate cloning and source annotation in `TaskBriefService.prepare_candidates`; route all answer-delivery paths through one server boundary before compilation; regress every public delivery path with the same digest-mismatch case.
**Lesson:** A governed selector is only as safe as its complete preprocessing chain. Runtime and evaluation must share validation, selection, and budget boundaries—not only ranking code.

<a id="issue-20"></a>

## Issue #20: Installed Memory Was Available but a Normal Question Did Not Recall It [BUG-053, FIXED, guarded]

**Trigger:** A clean Codex session answered `UNKNOWN` even though Elefante was globally installed and the requested durable fact existed. An explicit Recall then requested approval; after approval was removed, selection still rejected the direct fact and successful output wasted context on internal wrappers. The 2026-08-28 Gauntlet audit then showed that empty, overlong, missing, or wrong-type input could be rejected by MCP SDK schema validation as a raw protocol error, while packaged Antigravity and VS Code/Bob approval lists still omitted Recall and all three Directive tools from the 17-tool customer surface.
**Root cause:** Host registration, retrieval routing, safe tool authorization, answer selection, and wire-format failure handling were incorrectly treated as one contract. The selector reused an implementation-actionability threshold for factual questions, the generic response decorator ignored Recall's narrow customer purpose, and strict tool-schema validation could fail before Elefante's governed handler owned the response.
**Solution:** Keep registration separate, add one manifest-owned reversible global Codex routing block, declare Recall read-only/idempotent/non-destructive/closed-world, allow a strong `direct_answer` to bypass only the implementation-actionability threshold, and route success, abstention, operator-disabled, invalid-input, and retrieval-failure outcomes through the same bounded seven-field Recall payload. The public schema documents the input bound while the handler enforces it, preventing pre-handler protocol errors from replacing the product contract. Host-side approval metadata now derives from one source-checked exact customer inventory instead of duplicated stale lists. Rebuild and install the exact customer archive, then prove the journey in an empty directory with Codex JSON events.
**Lesson:** Availability is not use, and a documented terminal contract must survive invalid input. A customer memory path is complete only when the host routes a normal question, invokes safely, selects answer-bearing evidence, and returns a bounded product response on every terminal path.

<a id="issue-21"></a>

## Issue #21: Relevant Memory Did Not Supply the Decisive Task Evidence [GAP-053, OPEN]

**Trigger:** Task 032's sealed installation-contract memory was retrieved, selected, and delivered in every treatment, yet treatment accepted 0/3. The two completed source-only controls also failed.
**Root cause:** Semantic relevance was mistaken for decision value. The memory described global runtime architecture and host coverage, but the black-box task required a real public `elefante-Recall` MCP surface; all five preserved patches changed routing or installer files and omitted that API.
**Solution:** Reject task 032's tested memory component and preserve its `STOP`. Before another model run, require a different task whose prior memory contributes one specific decision-relevant fact absent from the source-only Brief, then prove that difference in deterministic preflight. The evaluator now compares source-only and memory Briefs directly and stops redundant controls after a bound treatment 0/3.
**Lesson:** A memory should be selected because it changes the next task action, not because it is topically related. Retrieval, selection, and delivery are healthy only when the evidence portfolio contains the missing decision input.

<a id="issue-22"></a>

## Issue #22: Recall-Only Workflow Had No Durable Decision Supply [GAP-054, FIXED in development]

**Trigger:** After Task 032 stopped, a model-free search for a different eligible memory-task pair returned `no_match`. The live customer store contained five records: one synthetic passcode, two unverified related specifications, and two contradictory records; it did not contain Elefante's user-declared canonical mission.
**Root cause:** The installed Codex guidance actively routed prior-context questions through Recall but had no active rule for an explicit user request to remember something across sessions. It also treated a successful write as sufficient even though governance can make a stored record ineligible; availability, capture, deliverability, and outcome had been collapsed into “memory exists.”
**Solution:** Extend the manifest-owned reversible Codex block and customer entrypoint with one narrow capture contract: only an explicit cross-session remember request or canonical/non-negotiable declaration triggers search-first add/update; the mutation is `user_directed`; user locks and permanent retention require explicit protection; ordinary conversation and secrets are excluded. Scope must be an exact identifier rather than prose, triggered delivery must name future-question phrases, and one likely future question must pass Recall after the write.
**Proof:** The live store initially had five unrelated or unsuitable records and the complete candidate-selection question returned `no_match`. Pilot memory `0b27fa62-d459-4029-a390-391305ab555d` was then stored. Raw retrieval ranked it first, but the first Recall rejected its descriptive scope and supplied a loose developer specification; after the same record's scope was corrected to literal `elefante`, Recall supplied only the canonical mission. This proves capture and deliverability, not a better task outcome.
**Lesson:** Recall cannot improve a later task when the workflow never captured the decision, and `stored` does not mean `deliverable`. Safe capture is an explicit, closed-loop causal stage; it is not automatic conversation harvesting and it is not evidence of task lift.

<a id="issue-23"></a>

## Issue #23: Evaluator Separated Task Value From Overall Token Cost [GAP-055, FIXED in development]

**Trigger:** The product objective was restated as intelligence per overall token, but the paired report measured acceptance and retries as effectiveness while using input-token growth only as a secondary cost ceiling; output tokens were omitted from the gate.
**Root cause:** Outcome quality and token cost were evaluated in separate gates instead of one paired value measure. This could recognize correctness lift without showing its overall-token efficiency and could not recognize equal accepted value delivered with reliably fewer total tokens.
**Solution:** Define the current observable value proxy as one unit for a black-box accepted outcome and zero for failure; define total tokens as input, including cached input, plus output. Report accepted outcomes per million tokens and a task-clustered difference from complete pairs, while separately reporting all observed spend so early-stop work is not hidden. The gate requires at least one treatment acceptance, no acceptance-count regression, and a 95% lower bound above zero; historical consumed evidence remains non-promotable.
**Lesson:** Measure accepted value and complete cost together. Cheap failure is zero intelligence, and raw ratios across unrelated task mixes are not comparable evidence.

<a id="issue-24"></a>

## Issue #24: Declarative Triggers Had No Delivery Path [GAP-056, FIXED in development]

**Trigger:** `trigger` and `surfaces_when` metadata could describe when a memory should matter, but no runtime path examined an explicit file, terminal-error, or conversation context. A caller had to guess a semantic query and could miss an exact opt-in reminder.
**Root cause:** The schema hint was passive. Adding automatic host interception would cross the local memory authority boundary and introducing another semantic retriever would duplicate the existing search contract, so no bounded delivery surface had been wired.
**Solution:** Extend the existing `elefante-Memory(action="search")` path with optional `surface_context`. It performs one bounded read-only scan, considers only `injection_policy="triggered"` memories, requires a case-insensitive literal phrase from `trigger` or `surfaces_when`, returns at most three matches with an explicit trigger explanation, and preserves lifecycle, scope, source-trust, conflict, and privacy gates. If a workspace filter is supplied, it uses the shared current-source digest check on a deep copy and skips stale records. It never updates access or graph state. The shared answer-context compiler reports a bounded warning when a relevant candidate has a stored conflict relationship or contradictory status; it withholds the candidate, selects neither side, and omits internal IDs from the warning and Recall text. The 2026-08-28 closure then added typed file, terminal-error, and conversation envelopes for every manifest host family, secret scrubbing and hard bounds, and a loopback `/events/surface` adapter that feeds the same read-only selector without persisting the event. Conservative semantic detection and dry-run-first reversible `Memory(resolve)` repair close the related contradiction path without allowing an arbitrary automatic winner.
**Proof:** `tests/test_proactive_surfacing.py` covers policy/literal requirements, context separate from the semantic query, scope/trust/lifecycle/conflict/privacy gates, stale-source rejection, result bounds, Task Brief delivery, and read-only behavior. `tests/test_host_event_adapters.py` and `tests/test_host_event_endpoint.py` cover host normalization, privacy, bounds, and daemon integration. `tests/test_conflict_detection.py` and `tests/test_conflict_resolution.py` cover abstention, equivalent consolidation, explicit winner authority, protected records, rollback, and scope separation. `tests/test_mcp_daemon.py` covers answer-context and opt-in warning delivery without selecting or exposing the conflicted memory. These capabilities later shipped in v2.13.0; the earlier v2.12.3 artifact remained unchanged.
**Lesson:** A declarative trigger is not a shipped behavior. Make proactive delivery explicit, opt-in, literal, bounded, and read-only before considering host automation or outcome claims.

<a id="issue-25"></a>

## Issue #25: Nested Graph and ETL Paths Bypassed Secret Scrubbing [BUG-056, FIXED LOCALLY, guarded]

**Trigger:** Adversarial MCP calls placed API-key and bearer-token patterns inside GraphConnect properties, legacy raw memory text, and ETLClassify enrichment. Graph and enrichment writes preserved those values, while ETLProcess returned a legacy secret directly to the agent.
**Root cause:** Privacy filtering was applied to common memory-write boundaries but not to complete nested request and response objects. GraphConnect trusted arbitrary `properties`; ETLProcess treated stored raw content as already safe; ETLClassify persisted agent-authored summary, concepts, and trigger metadata unchanged.
**Solution:** Scrub the complete GraphConnect request before any entity or relationship write, scrub the complete ETLProcess result before it leaves the server, and scrub every ETLClassify enrichment field before persistence. Return only redaction counts and detector types so clients can see that filtering occurred without receiving the secret.
**Guard:** `pytest tests/test_mcp_daemon.py -k "graph_connect_scrubs or etl_process_scrubs or etl_classify_scrubs" -q` proves response, persistence, nested-property, and metadata behavior with adversarial positive controls.
**Lesson:** Privacy is an end-to-end data-flow property. Every ingress, persistence, and egress boundary must scrub the complete nested payload, including old records and agent-authored metadata.

**Detector recurrence, 2026-09-03:** Traversing nested values removed the field
name needed to identify an unprefixed credential; the token expression also
missed hyphenated project/admin tokens. Explicit secret-field detection now
preserves key context, accepts common separator/CamelCase forms, and leaves
benign counters and public-key fields unchanged. Nested redaction-type counts
reconcile with the total, and a second scrub is idempotent. Thirteen added
synthetic regressions and seven existing MCP privacy-boundary tests pass.
This is bounded pattern detection, not a guarantee for every secret format;
users must still never submit credentials as memories.

**Scope recurrence, 2026-09-04 (v2.15.1 live acceptance):** The expanded `sk-`
pattern began inside ordinary words. `/work/task-intelligence-program` became
`/work/ta[REDACTED:OPENAI_KEY]` during read-side sanitization. Search found the
stored memories, but governed delivery rejected their changed workspace. The
stored six-memory and directive hashes were unchanged. Isolated tests had used
paths without the ambiguous prefix, so their passing results missed this
cross-boundary regression.

The v2.15.2 repair requires a token boundary before OpenAI/Anthropic prefixes;
it does not whitelist Elefante, a project path, or a question. Five new cases
failed before the repair and pass afterward, including Windows/POSIX paths,
ordinary prose, and the real privacy-to-scoped-Recall compilation path. Existing
secret-field checks plus 28 standalone-key/delimiter combinations remain
required. The new runtime test uses a disposable data root and also checks the
public Recall handler with a strict registry: the owning scope supplies the
memory and a different registered scope abstains.

**Prevention:** Test privacy false positives as well as secret removal, and
assert that benign governance/provenance identifiers survive the whole delivery
path unchanged. A green retrieval unit test or installer handshake does not
replace meaningful official-package Recall. The existing official v2.15.1 tag
must not be rewritten; publication and installed proof are tracked in §2.7 of
PLANNING.md.

**Released verification (2026-09-04):** v2.15.2 source `f04cd615` passes the
50 focused privacy/Recall cases and the 1,201-test local suite. The official
package's fresh bridge and visible dashboard supply the pre-existing purpose
memory and abstain for an absent revenue fact. Semantic-memory, directive and
consent hashes are unchanged. Exact receipts and publication links are in
[PLANNING §2.3](../PLANNING.md#23-current-release-state); the old tag and assets
remain intact.

<a id="issue-26"></a>

## Issue #26: Task Intelligence Used a Non-Canonical Project Root [BUG-066, FIXED LOCALLY, guarded]

**Trigger:** The strict-project self-protocol registered a macOS temporary workspace under its canonical `/private/var/...` path, while the caller supplied the equivalent `/var/...` spelling. Recall resolved the project, but Task Intelligence compared the raw strings and returned an empty/abstained brief.
**Root cause:** Task Intelligence accepted project and workspace fields as search filters without first passing them through the same strict Project Registry resolver used by Remember and Recall. Filesystem aliases therefore became false project boundaries on platforms that expose multiple names for one directory.
**Solution:** Resolve Task Intelligence through the shared registered-project boundary before store access, then search with the stable project ID and canonical registered root. Preserve bounded omission reasons so a genuine abstention remains inspectable. Add a regression using a symlinked/canonical temporary workspace and update the self-protocol to use the exact registered root.
**Guard:** `pytest tests/test_mcp_daemon.py tests/test_task_intelligence.py -k "task_intelligence and (project or workspace or canonical)" -q`; `python scripts/verify/verify_e2e_tests.py`.
**Lesson:** Project identity is a registry fact, not a caller-string equality test. Every memory consumer must resolve scope through the same canonical boundary before retrieval.

---

## Cross-bug pattern (extracted to `../lessons.md`)

The recurring rules from these 26 issues:

1. **STATE → DO → VERIFY in the same response** — analysis without action is entertainment. Issues #1, #4.
2. **Trigger words require proof** — "done" / "ready" / "fixed" must include verification output. Issue #2.
3. **Active injection beats passive prose** — passive protocols are skipped at the moment they're needed most. Issues #6, #12.
4. **Source + memory + verification must agree** — fix in one layer is not a fix. Issues #7, #8.
5. **Differentiate "slow" from "hung"** — timeouts cannot fix deadlocks. Issue #9.
6. **Broadest scope for behavioral instructions** — system-level injection, not workspace-level file presence. Issue #10.
7. **Every export needs a documented import** — exportable ≠ restorable. Issue #11.
8. **Guard current truth, not stale literals** — release, source, UI, and docs must agree. Issue #13.
9. **Judge observable outcomes, not hidden patch shape** — an invalid acceptance test can erase real improvement or reward overfitting. Issue #14.
10. **Separate discovery from answer delivery** — broad retrieval can find useful material, but only a bounded, question-specific evidence set belongs in an answer. Issue #15.
11. **Separate exposure from use** — retrieval and delivery cannot reinforce memory or co-activation before a caller explicitly acknowledges use. Issue #16.
12. **Prove the whole evidence path** — bind invocation, selected memory, delivery, declared use, and outcome before attributing benefit. Issue #17.
13. **Bind and preserve evaluation truth** — task, judge, evidence portfolio, failed workspace, and verdict must remain one inspectable contract. Issue #18.
14. **Share the complete delivery pipeline** — preprocessing, source validation, selection, and budgets must be identical across runtime paths. Issue #19.
15. **Prove the normal-question journey** — registration, routing, authorization, selection, and payload economy are separate gates. Issue #20.
16. **Select for decision value, not topical similarity** — a relevant memory that cannot change the next action is context cost, not Task Intelligence. Issue #21.
17. **Capture and verify before depending on Recall** — explicit user-directed durable decisions need a governed write plus one future-question delivery check before a later task can depend on them. Issue #22.
18. **Measure accepted value against complete token cost** — input-only savings and cheap failures cannot establish intelligence per overall token. Issue #23.
19. **Treat declarative triggers as opt-in delivery gates** — a stored trigger is not permission for broad automatic injection; require explicit context, literal matching, bounded output, and the same governance/privacy gates as normal delivery. Issue #24.
20. **Scrub complete data flows** — privacy guards must cover nested ingress, persistence, and egress, including legacy content and agent-authored enrichment. Issue #25.
21. **Resolve project scope once** — every consumer must use the same stable project ID and canonical registered root before retrieval. Issue #26.

Distill any new repeating rule into `../lessons.md`. Postmortems hold the bug-specific narrative; `lessons.md` holds the cross-bug edge.

---

## Full historical narrative

The pre-distillation full narrative — including Cognitive Failure Analysis sections, "Why This Took So Long" reflections, Methodology Failures tables, Prevention Protocols, code-block solutions in full, and original Symptom/Problem prose — is preserved verbatim at [`_archive/ai-behavior-full.md`](_archive/ai-behavior-full.md).

This file (`ai-behavior.md`) is the **active retrieval surface** — atomic Trigger/Root cause/Solution/Lesson chunks that Elefante surfaces at high signal-per-token. The archive is the **historical context surface** — open it when the distilled chunk is insufficient and you need the full debugging arc.

Distilled here = what Elefante surfaces. Archived next to it = what informed the distillation. Neither is lost.
