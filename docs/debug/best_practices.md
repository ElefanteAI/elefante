# Debug Best Practices

> **Purpose:** Distilled reusable debugging rules for Elefante contributors
> **Companion Docs:** [README.md](README.md) and [dev-developer-agent.md](dev-developer-agent.md)
> **Status:** Live feedback-loop ledger
> **Applies to**: v2.5.4+

---

## Role In The Feedback Loop

This file is the compression layer between one-off bug post-mortems and the day-to-day developer protocol.

1. [README.md](README.md) routes the agent to the right BUG row and verifier.
2. The relevant `ops-*-compendium.md` records the full incident narrative.
3. This file keeps the reusable decision edge that should survive beyond one incident.
4. [dev-developer-agent.md](dev-developer-agent.md) turns that edge into active workflow behavior.
5. Maintained tests and verifiers guard the rule so it does not decay back into prose.

Use this file for transferable patterns. Do not duplicate the compendiums here.

---

## Design Rules For This File

Each entry should carry just enough context to be usable during the next debugging pass:

- **Trigger:** when the rule applies
- **Rule:** what to do
- **Why:** the failure pattern the rule prevents
- **Proof:** the compendium entry, test, verifier, or source guard that makes the rule real
- **Avoid:** the overfit or misleading behavior that should not be repeated

If a lesson needs a long narrative to make sense, the narrative belongs in the compendium and this file should only keep the distilled edge plus the link back.

### Promotion Filter

Promote a lesson into this file only if at least one of these is true:

1. The lesson changes the default debugging workflow.
2. The lesson spans multiple live surfaces such as source, docs, tests, runtime messages, or memory.
3. The lesson is now guarded by a maintained verifier or test.
4. The same mistake is likely to recur in a different bug if the rule stays implicit.

Keep a lesson out of this file if it is only a one-off workaround, a narrow environment quirk, or a narrative that still needs the full post-mortem to be understandable.

---

## Current Best Practices

### Entry Routing Must Appear At First Contact

- **Trigger:** Any debugging task that begins from an MCP tool response or terminal failure.
- **Rule:** Put the exact routing path in the first successful response and the first failing response, not only in passive docs.
- **Why:** Agents skip documentation that is merely available. They follow instructions that are visible at the point of action.
- **Proof:** [ops-ai-behavior-compendium.md Issue #6](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure), [../../scripts/verify/verify_e2e_tests.py](../../scripts/verify/verify_e2e_tests.py), and [../../tests/test_autonomous_coactivation.py](../../tests/test_autonomous_coactivation.py).
- **Avoid:** Generic “check the docs” hints with no exact entry path.

### Prefer Maintained Proof Over Scratch Reproduction

- **Trigger:** You need to reproduce, verify, or narrow a failure.
- **Rule:** Check [../../tests/README.md](../../tests/README.md) and [../../scripts/verify/](../../scripts/verify/) before creating ad hoc repro scripts.
- **Why:** Maintained proof compounds knowledge. Scratch reproducers fragment it and create parallel truth.
- **Proof:** [dev-developer-agent.md](dev-developer-agent.md) now embeds this routing as part of the development loop.
- **Avoid:** Creating a `tmp/` reproducer before checking the maintained test and verifier inventory.

### Fix The Whole Live Surface, Not Only The Hurt File

- **Trigger:** The issue touches behavior that crosses source, docs, tests, runtime messages, or stored memory.
- **Rule:** Scan and update every live surface that participates in the behavior.
- **Why:** Partial alignment creates false closure. The file that surfaced the bug is often not the only place the bug lives.
- **Proof:** [ops-ai-behavior-compendium.md Issue #7](ops-ai-behavior-compendium.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads), [../../tests/test_developer_routing.py](../../tests/test_developer_routing.py), and the linked active docs.
- **Avoid:** Declaring completion because one source file is correct while docs, runtime guidance, or live memory still point somewhere stale.

### Source-Derived Guards Beat Static Documentation Claims

- **Trigger:** A doc claims a tool count, schema field, path, response key, or other enumerated contract detail.
- **Rule:** Derive the claim from source where possible and guard it with a maintained test.
- **Why:** Static prose drifts quietly. Source-derived assertions fail loudly.
- **Proof:** [ops-ai-behavior-compendium.md Issue #7](ops-ai-behavior-compendium.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads) and [../../tests/test_developer_routing.py](../../tests/test_developer_routing.py).
- **Avoid:** Trusting a human-maintained count or path list without a source-backed guard.

### Graph And Session Tools Must Target The Actual Schema

- **Trigger:** You are changing graph/session tool queries, relationship creation, or result parsing against Kuzu-backed entities.
- **Rule:** Check the exact node and relation-table schema before composing Cypher or reading returned fields.
- **Why:** `CREATED_IN` and `WORKS_ON` do not share `RELATES_TO`'s `strength` property, and synthetic session metadata may live in JSON `props` rather than guaranteed top-level columns.
- **Proof:** [ops-database-compendium.md Issue #8](ops-database-compendium.md#issue-8-graph-and-session-schema-contract-drift) and [../../tests/test_memory_persistence.py](../../tests/test_memory_persistence.py).
- **Avoid:** Assuming every relation table has the same properties or every session field exists as a top-level `Entity` column.

### Maintained Verifiers Must Follow The Live Contract

- **Trigger:** You are extending or debugging a maintained harness, shipped verifier, or release-proof script.
- **Rule:** Verify runtime paths, payload sizes, and side-effect locations from source and real runs before encoding assertions in the harness.
- **Why:** A verifier that assumes the wrong path or transport limit creates false regressions and wastes debugging cycles on healthy product code.
- **Proof:** [ops-ai-behavior-compendium.md Issue #8](ops-ai-behavior-compendium.md#issue-8-self-protocol-verifier-drift--runtime-path-and-payload-assumptions), [../../scripts/verify/verify_e2e_tests.py](../../scripts/verify/verify_e2e_tests.py), and [../../tests/test_developer_routing.py](../../tests/test_developer_routing.py).
- **Avoid:** Hard-coding convenience paths like raw temp data dirs or relying on default stream limits when live MCP responses can exceed them.

### The Verifier Must Prove The Actual Failure Mode

- **Trigger:** A bug is marked fixed but the only verifier is a broad health check, smoke test, or adjacent workflow.
- **Rule:** Choose or build a verifier that exercises the exact contract that failed.
- **Why:** Nearby health can stay green while the original regression silently returns.
- **Proof:** BUG-003 was still using a generic health check after the real fix was a launch/open contract: readiness wait before browser open, forced restart on refresh, and frontend retry/backoff. Guarded in [../../tests/test_dashboard_serializer.py](../../tests/test_dashboard_serializer.py).
- **Avoid:** Treating a passing baseline health script as proof of a first-launch, refresh, or race-condition fix.

### Cold Start Counts As Real Product Behavior

- **Trigger:** You are validating live MCP behavior, startup, restart, or first-use flows.
- **Rule:** Treat isolated temporary HOME and data directories as real product conditions, not artificial edge cases.
- **Why:** Fresh users and fresh IDE sessions hit cold start. Warm local state hides latency and initialization defects.
- **Proof:** [ops-ai-behavior-compendium.md Issue #6](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure), [ops-ai-behavior-compendium.md Issue #9](ops-ai-behavior-compendium.md#issue-9-self-protocol-cold-start-timeout--request_timeout_seconds-too-tight-for-cpu-only-embedding-init), and [../../scripts/verify/verify_e2e_tests.py](../../scripts/verify/verify_e2e_tests.py).
- **Avoid:** Sizing timeouts and confidence only around a warmed-up development shell.

### Verifier Timeout Constants Must Cover The Slowest Supported Target

- **Trigger:** A maintained harness uses a hardcoded timeout constant for MCP subprocess communication.
- **Rule:** Size `REQUEST_TIMEOUT_SECONDS` (or equivalent) for CPU-only cold start on the slowest supported platform, not for a warm GPU development machine. Make the constant overridable via environment variable if platform variance is wide.
- **Why:** Embedding model cold-start (`sentence-transformers` + `thenlper/gte-base` on CPU) can add 8+ seconds to the first tool call in an isolated temp environment. Combined with multiple assertions in a single phase, a tight timeout produces a deterministic failure that masquerades as a product defect.
- **Proof:** BUG-010 initial symptom. [ops-ai-behavior-compendium.md Issue #9](ops-ai-behavior-compendium.md#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio).
- **Avoid:** Hard-coding a timeout that passes on the development machine but fails on a clean CI or user install. Catch-all exception handlers that hide the timeout source.

### Heavy Imports Must Run Before The Event Loop, Not In Worker Threads

- **Trigger:** A heavy C-extension import (torch, sentence-transformers) must execute at runtime inside an MCP server subprocess with piped stdio.
- **Rule:** Pre-load the module in the `__main__` block before `asyncio.run()`. Never defer a heavy import to `asyncio.to_thread()` or any threaded executor running under an anyio-managed event loop with piped stdio.
- **Why:** `from sentence_transformers import SentenceTransformer` (which triggers `import torch`) deadlocks when executed in a worker thread under anyio 4.x + Python 3.11 + Windows ProactorEventLoop with piped stdin/stdout. The same import completes in ~3s when run synchronously before the event loop starts.
- **Proof:** BUG-010 — traced via 6 raw `sys.stderr.write` probes to confirm the import line is the exact deadlock point. Pre-loading in `server.py __main__` before `asyncio.run(main())` resolved the deadlock. Self-protocol: 45/45 PASS. [ops-ai-behavior-compendium.md Issue #9](ops-ai-behavior-compendium.md#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio).
- **Avoid:** Wrapping heavy imports in `asyncio.to_thread()` as a "non-blocking" fix — this moves the deadlock to the thread instead of eliminating it. Confusing "slow" (fixable by timeout increase) with "hung" (requires lifecycle change).

### Differentiate Slow From Hung Before Choosing A Fix

- **Trigger:** A subprocess operation times out and you're considering increasing the timeout.
- **Rule:** If doubling the timeout (90→180s) still fails, the operation is hung, not slow. Stop tuning timeouts and investigate the deadlock mechanism. Use raw `sys.stderr.write` + `flush` probes (not structured logging) to trace execution through threaded/async boundaries.
- **Why:** Timeout increases fix latency. Deadlocks require lifecycle changes (moving operations to a different phase) or eliminating the threading that causes the lock contention.
- **Proof:** BUG-010 — three debugging cycles wasted on timeout increases and asyncio.to_thread wrapping before raw probes revealed the import deadlocks indefinitely in a thread. [ops-ai-behavior-compendium.md Issue #9](ops-ai-behavior-compendium.md#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio).
- **Avoid:** Incrementally increasing timeouts hoping the operation "just needs more time." Relying on structured logging (which may buffer or drop messages) for probe-level diagnostics in threaded/async contexts.

### MCP Tool Rejections Must Include The Specific Reason

- **Trigger:** An MCP tool handler returns a non-error response that silently drops or ignores the caller's input.
- **Rule:** Always include a `rejection_reason` field that names the exact condition that triggered the rejection. The calling agent must be able to correct and retry without guessing.
- **Why:** Opaque rejections like `"Memory filtered by Intelligence Pipeline"` are indistinguishable from bugs. Agents cannot introspect server-side logs, so the MCP response is the only diagnostic channel.
- **Proof:** BUG-011 — MemoryAdd with tag `"test"` returned `status: ignored` with no indication which of 9 heuristic conditions fired. The same guard silently blocked the installer's seed passcode, producing a false-positive "Successfully injected" claim. [ops-memory-compendium.md Issue #10](ops-memory-compendium.md#issue-10-memoryadd-silent-ignore--opaque-test-memory-guard-rejection).
- **Avoid:** Generic rejection messages. Silent `None` returns from internal functions that get translated into success-shaped MCP responses.

### Instruction Delivery Scope Must Match The Broadest Usage Scope

- **Trigger:** An agent has access to an MCP server but never calls it, even when the context clearly warrants it.
- **Rule:** Behavioral instructions (search-first rules, tool contracts, engagement objectives) must be delivered at the broadest available scope — not the narrowest that works in one demo. For VS Code Copilot: `settings.json` user-level `codeGeneration.instructions` is system-scoped; `.github/copilot-instructions.md` is workspace-scoped only.
- **Why:** A workspace-scoped instructions file is invisible the moment the user opens a parent folder, a sibling project, or any subfolder as the workspace root. The cold-start trigger gap silently returns with no visible indication.
- **Proof:** BUG-012 — working from `BOB/` workspace, agent answered "what is the code?" by reading README directly, never calling `elefante-MemorySearch`, despite Elefante being registered and running. [ops-ai-behavior-compendium.md Issue #10](ops-ai-behavior-compendium.md#issue-10-elefante-cold-start-trigger-gap--instructions-file-is-workspace-scoped-not-system-scoped).
- **Avoid:** Conflating MCP registration scope with instruction delivery scope — they are orthogonal systems. A fix that works in the demo scenario but fails silently in adjacent ones is worse than a documented gap.

### Whole-System Claims Require A Whole-System Verifier

- **Trigger:** You need to answer "is Elefante actually running?" or make a release-level claim about the live MCP surface.
- **Rule:** Run the isolated self-protocol after targeted regressions. Narrow pytest passes are necessary but they do not prove end-to-end liveness by themselves.
- **Why:** Regression tests prove slices. The self-protocol proves that the real MCP server boots, exposes the expected tool/prompt surface, mutates isolated state correctly, survives restart, and cleans up after itself.
- **Proof:** [self-elefante-protocol.md](self-elefante-protocol.md) and [../../scripts/verify/verify_e2e_tests.py](../../scripts/verify/verify_e2e_tests.py).
- **Avoid:** Treating a green unit/regression matrix as proof that the live MCP server is operational end-to-end.

### Response-Contract Changes Are Public Surface Changes

- **Trigger:** The MCP server starts promising a new always-injected field or new behavioral contract.
- **Rule:** Treat the change as release-significant. Update CHANGELOG and versioning accordingly.
- **Why:** External agents and tests bind to the response contract, not to internal implementation intent.
- **Proof:** BUG-006 closed as v2.4.0 because the MCP response contract changed, not just an internal helper.
- **Avoid:** Hiding externally visible protocol shifts inside an unversioned “internal fix.”

### Verify The Live Contract Before Trusting Historical Explanations

- **Trigger:** A bug report, recovery script, or legacy doc explains storage shape, lock behavior, or path layout.
- **Rule:** Reconfirm the current runtime contract from source and a fresh initialization before declaring the historical explanation true.
- **Why:** Runtime behavior changes faster than old post-mortems decay. The most dangerous stale docs are the ones that still sound plausible.
- **Proof:** BUG-002 required source checks plus fresh `GraphStore` initialization to prove that `kuzu_db` now materializes as a file path and that recovery should route through transaction-scoped `write.lock`, not an older internal-lock story. Guarded by [../../tests/test_memory_persistence.py](../../tests/test_memory_persistence.py).
- **Avoid:** Treating filesystem shape or old lock instructions as corruption proof without revalidating the active contract.

### A Write-Only Export Is Not a Backup

- **Trigger:** A script exports data to a human-readable format (JSON, CSV, YAML).
- **Rule:** Every export format must either (a) have a documented import counterpart, or (b) be explicitly labeled "read-only analysis output — not a backup" at the top of the script and in the relevant README.
- **Why:** Users will treat any exportable format as a backup. If no import path exists, the export creates false confidence and a data-loss trap.
- **Proof:** GAP-013 — `export_memories.py --format json` produced a JSON file with all memory content and metadata. No `import_memories.py` existed. Embeddings were not included (ChromaDB stores them explicitly from `thenlper/gte-base`; the export's `collection.get()` call omits them). A user who exported, factory reset, then tried to restore from JSON would lose their brain. The binary zip backup (`backup_elefante_data.py`) is the only real restore path — but it is not surfaced in the install flow. See [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md#issue-11-json-export-is-not-a-backup--missing-import-path-and-embeddings).
- **Avoid:** Shipping an export script without a companion import script and without labeling the export as read-only.

---

## Update Protocol

After a significant debugging session:

1. Update the relevant `ops-*-compendium.md` with the full post-mortem.
2. Add or revise the BUG row in [README.md](README.md).
3. Add or revise a rule here only if the lesson survives the Promotion Filter above.
4. Update [dev-developer-agent.md](dev-developer-agent.md) if the workflow itself changed.
5. Guard the rule in a maintained test or verifier when possible.

If a rule becomes structural, move it into source, tool schemas, directives, or the agent constitution and leave only the distilled lesson here.

---

## Recent Examples

- **BUG-006:** The reusable lesson was not “tool responses were missing a field.” The reusable lesson was “entry routing must be visible at first contact.” See [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure).
- **BUG-007:** The reusable lesson was not “a few docs were stale.” The reusable lesson was “fix the whole live surface, then guard it from source.” See [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads).
- **BUG-002:** The reusable lesson was not “Kuzu was locked again.” The reusable lesson was “verify the live contract before trusting the old explanation.” See [ops-database-compendium.md](ops-database-compendium.md#issue-2-database-lock-persistence).
- **BUG-008:** The reusable lesson was not “GraphConnect broke once.” The reusable lesson was “graph and session tools must target the actual schema.” See [ops-database-compendium.md](ops-database-compendium.md#issue-8-graph-and-session-schema-contract-drift).
- **BUG-009:** The reusable lesson was not “the self-protocol flaked.” The reusable lesson was “maintained verifiers must follow the live contract.” See [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md#issue-8-self-protocol-verifier-drift--runtime-path-and-payload-assumptions).
- **BUG-003:** The reusable lesson was not “dashboard health was good.” The reusable lesson was “the verifier must prove the actual failure mode.” See [ops-dashboard-compendium.md](ops-dashboard-compendium.md#issue-8-persistent-blank-dashboard-on-first-launch).