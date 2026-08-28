# Debug Best Practices

> **Purpose:** Distilled reusable debugging rules for Elefante contributors
> **Companion Docs:** [ISSUES.md](ISSUES.md) and [`../agents/orchestrator.md`](../agents/orchestrator.md)
> **Status:** Live feedback-loop ledger

---

## Role In The Feedback Loop

This file is the compression layer between one-off bug post-mortems and the day-to-day developer protocol.

1. [ISSUES.md](ISSUES.md) routes the agent to the right BUG row and verifier.
2. The relevant `postmortems/<domain>.md` records the incident.
3. This file keeps the reusable decision edge that should survive beyond one incident.
4. [`../agents/orchestrator.md`](../agents/orchestrator.md) turns that edge into active workflow behavior.
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
- **Proof:** [postmortems/ai-behavior.md Issue #6](postmortems/ai-behavior.md#issue-6), [../scripts/verify/verify_e2e_tests.py](../scripts/verify/verify_e2e_tests.py), and [../tests/test_autonomous_coactivation.py](../tests/test_autonomous_coactivation.py).
- **Avoid:** Generic “check the docs” hints with no exact entry path.

### Prefer Maintained Proof Over Scratch Reproduction

- **Trigger:** You need to reproduce, verify, or narrow a failure.
- **Rule:** Check [../tests/README.md](../tests/README.md) and [../scripts/verify/](../scripts/verify/) before creating ad hoc repro scripts.
- **Why:** Maintained proof compounds knowledge. Scratch reproducers fragment it and create parallel truth.
- **Proof:** [`../agents/orchestrator.md`](../agents/orchestrator.md) now embeds this routing as part of the development loop.
- **Avoid:** Creating a `tmp/` reproducer before checking the maintained test and verifier inventory.

### Question-First Routing Maximizes Quality Per Token

- **Trigger:** You are about to open several files, run multiple scripts, or write a long progress update on an active debugging branch.
- **Rule:** State the concrete question first, choose the smallest maintained proof that can confirm or falsify it, and report only the delta after each result. Expand the search only when the narrow proof fails.
- **Why:** Clean development comes from short evidence paths. Broad repo tours, speculative parallel paths, and repeated summaries spend tokens without reducing uncertainty. Quality per token is the metric.
- **Proof:** [`../agents/orchestrator.md`](../agents/orchestrator.md) and [../tests/test_developer_routing.py](../tests/test_developer_routing.py).
- **Avoid:** Reading half the repo before naming the question, running both scratch scripts and maintained verifiers for the same uncertainty, or re-summarizing unchanged plans.

### Fix The Whole Live Surface, Not Only The Hurt File

- **Trigger:** The issue touches behavior that crosses source, docs, tests, runtime messages, or stored memory.
- **Rule:** Scan and update every live surface that participates in the behavior.
- **Why:** Partial alignment creates false closure. The file that surfaced the bug is often not the only place the bug lives.
- **Proof:** [postmortems/ai-behavior.md Issue #7](postmortems/ai-behavior.md#issue-7), [../tests/test_developer_routing.py](../tests/test_developer_routing.py), and the linked active docs.
- **Avoid:** Declaring completion because one source file is correct while docs, runtime guidance, or live memory still point somewhere stale.

### Source-Derived Guards Beat Static Documentation Claims

- **Trigger:** A doc claims a tool count, schema field, path, response key, or other enumerated contract detail.
- **Rule:** Derive the claim from source where possible and guard it with a maintained test.
- **Why:** Static prose drifts quietly. Source-derived assertions fail loudly.
- **Proof:** [postmortems/ai-behavior.md Issue #7](postmortems/ai-behavior.md#issue-7) and [../tests/test_developer_routing.py](../tests/test_developer_routing.py).
- **Avoid:** Trusting a human-maintained count or path list without a source-backed guard.

### Graph And Session Tools Must Target The Actual Schema

- **Trigger:** You are changing graph/session tool queries, relationship creation, or result parsing against Kuzu-backed entities.
- **Rule:** Check the exact node and relation-table schema before composing Cypher or reading returned fields.
- **Why:** `CREATED_IN` and `WORKS_ON` do not share `RELATES_TO`'s `strength` property, and synthetic session metadata may live in JSON `props` rather than guaranteed top-level columns.
- **Proof:** [postmortems/database.md Issue #8](postmortems/database.md#issue-8) and [../tests/test_memory_persistence.py](../tests/test_memory_persistence.py).
- **Avoid:** Assuming every relation table has the same properties or every session field exists as a top-level `Entity` column.

### Maintained Verifiers Must Follow The Live Contract

- **Trigger:** You are extending or debugging a maintained harness, shipped verifier, or release-proof script.
- **Rule:** Verify runtime paths, payload sizes, and side-effect locations from source and real runs before encoding assertions in the harness.
- **Why:** A verifier that assumes the wrong path or transport limit creates false regressions and wastes debugging cycles on healthy product code.
- **Proof:** [postmortems/ai-behavior.md Issue #8](postmortems/ai-behavior.md#issue-8), [../scripts/verify/verify_e2e_tests.py](../scripts/verify/verify_e2e_tests.py), and [../tests/test_developer_routing.py](../tests/test_developer_routing.py).
- **Avoid:** Hard-coding convenience paths like raw temp data dirs or relying on default stream limits when live MCP responses can exceed them.

### The Verifier Must Prove The Actual Failure Mode

- **Trigger:** A bug is marked fixed but the only verifier is a broad health check, smoke test, or adjacent workflow.
- **Rule:** Choose or build a verifier that exercises the exact contract that failed.
- **Why:** Nearby health can stay green while the original regression silently returns.
- **Proof:** BUG-003 was still using a generic health check after the real fix was a launch/open contract: readiness wait before browser open, forced restart on refresh, and frontend retry/backoff. Guarded in [../tests/test_dashboard_serializer.py](../tests/test_dashboard_serializer.py).
- **Avoid:** Treating a passing baseline health script as proof of a first-launch, refresh, or race-condition fix.

### Cold Start Counts As Real Product Behavior

- **Trigger:** You are validating live MCP behavior, startup, restart, or first-use flows.
- **Rule:** Treat isolated temporary HOME and data directories as real product conditions, not artificial edge cases.
- **Why:** Fresh users and fresh IDE sessions hit cold start. Warm local state hides latency and initialization defects.
- **Proof:** [postmortems/ai-behavior.md Issue #6](postmortems/ai-behavior.md#issue-6), [postmortems/ai-behavior.md Issue #9](postmortems/ai-behavior.md#issue-9), and [../scripts/verify/verify_e2e_tests.py](../scripts/verify/verify_e2e_tests.py).
- **Avoid:** Sizing timeouts and confidence only around a warmed-up development shell.

### Verifier Timeout Constants Must Cover The Slowest Supported Target

- **Trigger:** A maintained harness uses a hardcoded timeout constant for MCP subprocess communication.
- **Rule:** Size `REQUEST_TIMEOUT_SECONDS` (or equivalent) for CPU-only cold start on the slowest supported platform, not for a warm GPU development machine. Make the constant overridable via environment variable if platform variance is wide.
- **Why:** Embedding model cold-start (`sentence-transformers` + `thenlper/gte-base` on CPU) can add 8+ seconds to the first tool call in an isolated temp environment. Combined with multiple assertions in a single phase, a tight timeout produces a deterministic failure that masquerades as a product defect.
- **Proof:** BUG-010 initial symptom. [postmortems/ai-behavior.md Issue #9](postmortems/ai-behavior.md#issue-9).
- **Avoid:** Hard-coding a timeout that passes on the development machine but fails on a clean CI or user install. Catch-all exception handlers that hide the timeout source.

### Heavy Imports Must Run Before The Event Loop, Not In Worker Threads

- **Trigger:** A heavy C-extension import (torch, sentence-transformers) must execute at runtime inside an MCP server subprocess with piped stdio.
- **Rule:** Pre-load the module in the `__main__` block before `asyncio.run()`. Never defer a heavy import to `asyncio.to_thread()` or any threaded executor running under an anyio-managed event loop with piped stdio.
- **Why:** `from sentence_transformers import SentenceTransformer` (which triggers `import torch`) deadlocks when executed in a worker thread under anyio 4.x + Python 3.11 + Windows ProactorEventLoop with piped stdin/stdout. The same import completes in ~3s when run synchronously before the event loop starts.
- **Proof:** BUG-010 — traced via 6 raw `sys.stderr.write` probes to confirm the import line is the exact deadlock point. Pre-loading in `server.py __main__` before `asyncio.run(main())` resolved the deadlock. Self-protocol: 45/45 PASS. [postmortems/ai-behavior.md Issue #9](postmortems/ai-behavior.md#issue-9).
- **Avoid:** Wrapping heavy imports in `asyncio.to_thread()` as a "non-blocking" fix — this moves the deadlock to the thread instead of eliminating it. Confusing "slow" (fixable by timeout increase) with "hung" (requires lifecycle change).

### Differentiate Slow From Hung Before Choosing A Fix

- **Trigger:** A subprocess operation times out and you're considering increasing the timeout.
- **Rule:** If doubling the timeout (90→180s) still fails, the operation is hung, not slow. Stop tuning timeouts and investigate the deadlock mechanism. Use raw `sys.stderr.write` + `flush` probes (not structured logging) to trace execution through threaded/async boundaries.
- **Why:** Timeout increases fix latency. Deadlocks require lifecycle changes (moving operations to a different phase) or eliminating the threading that causes the lock contention.
- **Proof:** BUG-010 — three debugging cycles wasted on timeout increases and asyncio.to_thread wrapping before raw probes revealed the import deadlocks indefinitely in a thread. [postmortems/ai-behavior.md Issue #9](postmortems/ai-behavior.md#issue-9).
- **Avoid:** Incrementally increasing timeouts hoping the operation "just needs more time." Relying on structured logging (which may buffer or drop messages) for probe-level diagnostics in threaded/async contexts.

### MCP Tool Rejections Must Include The Specific Reason

- **Trigger:** An MCP tool handler returns a non-error response that silently drops or ignores the caller's input.
- **Rule:** Always include a `rejection_reason` field that names the exact condition that triggered the rejection. The calling agent must be able to correct and retry without guessing.
- **Why:** Opaque rejections like `"Memory filtered by Intelligence Pipeline"` are indistinguishable from bugs. Agents cannot introspect server-side logs, so the MCP response is the only diagnostic channel.
- **Proof:** BUG-011 — `elefante-Memory(action="add")` with tag `"test"`
  returned `status: ignored` with no indication which heuristic fired. The same
  guard silently blocked the installer's seed passcode, producing a
  false-positive "Successfully injected" claim. [postmortems/memory.md Issue
  #10](postmortems/memory.md#issue-10).
- **Avoid:** Generic rejection messages. Silent `None` returns from internal functions that get translated into success-shaped MCP responses.

### Instruction Delivery Scope Must Match The Broadest Usage Scope

- **Trigger:** An agent has access to an MCP server but never calls it, even when the context clearly warrants it.
- **Rule:** Behavioral instructions (search-first rules, tool contracts, engagement objectives) must be delivered at the broadest available scope — not the narrowest that works in one demo. For VS Code Copilot: `settings.json` user-level `codeGeneration.instructions` is system-scoped; `.github/copilot-instructions.md` is workspace-scoped only.
- **Why:** A workspace-scoped instructions file is invisible the moment the user opens a parent folder, a sibling project, or any subfolder as the workspace root. The cold-start trigger gap silently returns with no visible indication.
- **Proof:** BUG-012 — working outside the Elefante workspace, an agent answered from files without calling `elefante-Memory` with `action="search"`, despite Elefante being registered and running. [postmortems/ai-behavior.md Issue #10](postmortems/ai-behavior.md#issue-10).
- **Avoid:** Conflating MCP registration scope with instruction delivery scope — they are orthogonal systems. A fix that works in the demo scenario but fails silently in adjacent ones is worse than a documented gap.

### Whole-System Claims Require A Whole-System Verifier

- **Trigger:** You need to answer "is Elefante actually running?" or make a release-level claim about the live MCP surface.
- **Rule:** Run the isolated self-protocol after targeted regressions. Narrow pytest passes are necessary but they do not prove end-to-end liveness by themselves.
- **Why:** Regression tests prove slices. The self-protocol proves that the real MCP server boots, exposes the expected tool/prompt surface, mutates isolated state correctly, survives restart, and cleans up after itself.
- **Proof:** [../docs/reference/self-protocol.md](../docs/reference/self-protocol.md) and [../scripts/verify/verify_e2e_tests.py](../scripts/verify/verify_e2e_tests.py).
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
- **Proof:** BUG-002 required source checks plus fresh `GraphStore` initialization to prove that `kuzu_db` now materializes as a file path and that recovery should route through transaction-scoped `write.lock`, not an older internal-lock story. Guarded by [../tests/test_memory_persistence.py](../tests/test_memory_persistence.py).
- **Avoid:** Treating filesystem shape or old lock instructions as corruption proof without revalidating the active contract.

### A Write-Only Export Is Not a Backup

- **Trigger:** A script exports data to a human-readable format (JSON, CSV, YAML).
- **Rule:** Every export format must either (a) have a documented import counterpart, or (b) be explicitly labeled "read-only analysis output — not a backup" at the top of the script and in the relevant README.
- **Why:** Users will treat any exportable format as a backup. If no import path exists, the export creates false confidence and a data-loss trap.
- **Proof:** GAP-013 exposed that `export_memories.py --format json` produced a file with memory content and metadata but no import path or embeddings. The guarded `import_memories.py` counterpart now regenerates vectors with the configured local model and protects additive writes with stopped-runtime confirmation, ID-collision, backup, dry-run, and rollback gates. JSON still omits graph topology and is not a full recovery archive; the binary zip backup (`backup_elefante_data.py`) remains the complete restore path. See [postmortems/ai-behavior.md](postmortems/ai-behavior.md#issue-11).
- **Avoid:** Shipping an export script without a companion import script and without labeling the export as read-only.

### CI Pipelines Must Build Every Artifact They Package

- **Trigger:** A CI workflow calls a build tool (PyInstaller, Webpack, Docker) that packages a compiled artifact.
- **Rule:** Every build step that produces files required by the packager must be explicitly listed in the workflow, in order, before the packager runs. Never assume a file exists because it exists locally — if it is in `.gitignore`, it does not exist in CI.
- **Why:** CI checks out only what is committed. Gitignored build outputs (compiled JS, generated CSS, transpiled code) are absent. A packager that references a missing path will fail silently or with a confusing error, and the failure only surfaces on the first real release attempt — potentially days after the workflow was written.
- **Proof:** BUG-014 — `build-binaries.yml` had no `setup-node` or `npm` step. `src/dashboard/ui/dist/` is gitignored. `elefante.spec` also referenced the wrong path (`build` instead of `dist`). All three matrix jobs (Ubuntu, macOS, Windows) failed on the first `v*` tag push (v2.5.3). Neither bug was caught during development because PyInstaller was never run in CI during that period. See [postmortems/installation.md](postmortems/installation.md#issue-8).
- **Avoid:** Writing a build spec that references a directory without verifying it matches the actual build tool output path (`outDir` in `vite.config.ts`, `output.path` in `webpack.config.js`, etc.).

### A Green Build Matrix Is Not A Release Proof

- **Trigger:** A CI workflow has build jobs and a downstream publish or release job.
- **Rule:** Verify the publish step explicitly. Successful build jobs prove artifacts were created, not that the release was published.
- **Why:** If publication fails after packaging, collapsing the failure back into the old build bug destroys causal precision and reopens the wrong incident.
- **Proof:** BUG-015 — after BUG-014 was fixed, `Build on ubuntu-latest`, `Build on macos-latest`, and `Build on windows-latest` all succeeded, but `Create GitHub Release` still failed. The current workflow source proves the remaining fault is in the release stage, not frontend compilation or PyInstaller packaging. See [postmortems/installation.md](postmortems/installation.md#issue-9).
- **Avoid:** Declaring a previously fixed CI build bug "back again" without first checking whether the failure moved to a later workflow stage.

### A Local Guard Is Not End-To-End Closure

- **Trigger:** You have identified a CI or release root cause, changed source/workflow code, and added a local regression test.
- **Rule:** Do not upgrade the incident to "fixed" until the real external path has been rerun successfully when the failure mode depends on the host platform or remote service.
- **Why:** A local guard proves the logic you extracted or encoded. It does not prove GitHub, runner behavior, permissions, artifact wiring, or release publication semantics end to end.
- **Proof:** BUG-015 — the 2 GiB root cause was real, and `pytest tests/test_release_pipeline.py -v` now guards the source logic, but a fresh `v*` tag publish is still the only proof that the incident is actually closed.
- **Avoid:** Collapsing "root cause identified" and "live incident closed" into the same status label.

---

### Release Asset Quotas Must Be Enforced Before Upload

- **Trigger:** A CI workflow publishes built binaries to GitHub Releases or another platform with per-file upload caps.
- **Rule:** Measure candidate asset sizes before upload and filter or split anything that exceeds the platform's hard limit.
- **Why:** GitHub Actions artifacts and GitHub release assets have different quotas. A build can succeed, artifact upload can succeed, and release publication can still fail at the very last step.
- **Proof:** BUG-015 — run `24475129776` created release `v2.6.0`, uploaded `elefante-macOS.zip` and `elefante-Windows.zip`, then failed because `elefante-Linux-binary` was `4,021,041,080` bytes while GitHub release assets must be under `2 GiB`. See [postmortems/installation.md](postmortems/installation.md#issue-9).
- **Avoid:** Treating "artifact uploaded to Actions" as proof that the file can also be published as a release asset.

---

### Release Archives Must Be Tested As Customer Interfaces

- **Trigger:** A release pipeline packages platform download archives or launcher scripts.
- **Rule:** Extract each platform artifact, decode its launcher bytes, reject hidden control characters, inspect the root-level choices a customer sees, and execute the primary entrypoint through a non-destructive smoke path.
- **Why:** Archive membership proves only that files exist. It does not prove that a launcher path survived string escaping, that executable metadata survived ZIP creation, or that a stakeholder can identify the next action.
- **Proof:** BUG-037 — v2.11.1 contained the expected Windows `install.bat`, but `\bootstrap_release_bundle.py` had already become ASCII backspace plus `ootstrap_release_bundle.py`; the macOS bundle also presented both Windows and Unix wrappers with no first-run guide.
- **Avoid:** Tests that assert only `archive.namelist()`, or platform packages that expose internal cross-platform implementation choices as the customer UX.

---

### Dry Run Means No Durable Mutation

- **Trigger:** A command exposes `--dry-run`, preview, plan, or check-only behavior.
- **Rule:** Branch before every filesystem, service, database, network, or backup mutation, then assert the intended target remains absent or byte-identical.
- **Why:** Skipping the final subprocess is not a dry run when preparation has already moved or replaced live state.
- **Proof:** BUG-038 — bundle validation moved the live installation twice because payload placement preceded the dry-run branch.
- **Avoid:** Tests that inspect printed output without also proving durable state did not change.

---

### Write→Read Value-Space Verification (BUG-016, BUG-017, BUG-018)

- **Trigger:** A scoring system uses multiple signals with weights, or a feature that writes data and reads it back for ranking/filtering.
- **Rule:** For every scored signal, trace the write path (where values are set at storage time) and the read path (where values are consumed at query time). If the value spaces don't intersect, the signal is dysfunctional regardless of its weight.
- **Why:** A signal whose write-side enum (`DomainType.REFERENCE`) can never match its read-side inference (`None`/`"work"`/`"personal"`) produces a constant or penalty — 15% of weight budget wasted. An unconditional override (+0.30 for specs) that ignores query intent creates a ranking monopoly. Volatile state (`[]` on restart) makes a signal zero at cold start.
- **Proof:** BUG-016 — domain signal write→read mismatch proved in `retrieval.py:138-148` vs `memory.py:128`. BUG-017 — spec override at `retrieval.py:301` dominates all queries (3 real ARAA queries returned same top 4 specs). BUG-018 (historical) — the former co-activation read path required `_session_retrieval_history`, which reset at restart; the current exposure/use contract is BUG-048. See [postmortems/memory.md](postmortems/memory.md#issue-11) and [postmortems/ai-behavior.md](postmortems/ai-behavior.md#issue-16).
- **Avoid:** Assuming a multi-signal system works because it is documented. Documentation describes the design, not the runtime behavior. Only a source trace with real queries proves intersection.

---

### New Features Are Not Exempt From Gate 1

- **Trigger:** A new feature (script, tool, surface) that does not modify existing runtime code.
- **Rule:** Write the design in the canonical `workspace/proposals/` or `workspace/PLANNING.md` surface before implementation. Gate 1 applies to new behavior, not only changes to existing behavior.
- **Why:** Concrete tasks create false confidence. An agent told "build a DMG" knows hdiutil, knows zip, knows icons — and jumps straight to implementation. The spec-first gate catches scope drift, missing requirements, and misalignment with the product vision before code exists. Code-first means reconciliation; spec-first means alignment.
- **Proof:** DMG installer feature (2026-04-16) — `build_dmg.py` was written and tested before its design was recorded in the then-current vision spec. The code worked, but the contract had to be reconstructed after implementation; current work routes design through `workspace/` first.
- **Avoid:** Treating the Five Gates as "change management for existing code." They govern all development. New features feel exempt because they don't touch existing surfaces — but Gate 1 explicitly covers them.

---

### Gate 4 Must Test The Distribution Path, Not The Build Path

- **Trigger:** Any artifact (DMG, EXE, zip, binary) intended for end-user download from a platform with a trust gate (macOS Gatekeeper, Windows SmartScreen, Linux package signing).
- **Rule:** Gate 4 verification must include the platform's trust-gate check, not just structural validity. For macOS: `codesign -dvv` and `spctl --assess`. For Windows: check Authenticode signature. "Does it mount?" is not "Can a user open it?"
- **Why:** Local testing bypasses the trust gate. The artifact works on the build machine because it was never downloaded through the browser quarantine path. The user's first contact is the platform's security warning — if that blocks the artifact, the entire install experience fails at step zero.
- **Proof:** DMG installer (2026-04-16) — `hdiutil attach` + `ls` passed, `codesign -dvv` returned "code object is not signed at all", `spctl --assess` returned "rejected / source=no usable signature". The DMG was structurally perfect and distributionally blocked. ARAA caught it; Gate 4 did not, because Gate 4 tested the wrong path.
- **Avoid:** Declaring a distribution artifact "verified" based on local structural tests. The claim is "ready for users." The test must simulate what users encounter.

### Multi-Edit Sessions Require Syntax Verification Before Closure (BUG-019)

- **Trigger:** A file is patched more than once in a single session via string-replacement edits, especially aesthetic rewrites (dark→light theme, layout restructuring).
- **Rule:** After the final edit, run `python3 -c "import py_compile; py_compile.compile('FILE', doraise=True)"` (or the language-equivalent syntax check). If the file is not covered by the test suite, this check is the ONLY gate preventing a broken ship. Commit working intermediate states before aesthetic rewrites.
- **Why:** Overlapping string replacements on large files produce Frankenstein merges — interleaved fragments from both versions with orphaned kwargs, undefined variables, and duplicate widget constructors. The corruption is syntactically fatal but invisible to tests that don't import the file. A process exit code 1 observed mid-session was not diagnosed because the session moved on to unrelated questions.
- **Proof:** BUG-019 — `installer_gui.py` patched 3+ times (chmod fix, dark→light palette, path display additions). Final file had `SyntaxError` at line 173, bare `C` instead of `self.C`, `C["entry"]`/`C["white"]` keys that don't exist in the light palette, duplicate `_build_ui` sections. File was never committed (untracked), so no recovery was possible. 137/137 pytest passed because no test imports the installer GUI. See [postmortems/installation.md](postmortems/installation.md#issue-10).
- **Avoid:** Trusting a green test suite as proof that ALL files in the commit are syntactically valid. If a file is not imported by any test, the test suite is blind to it.

### Screenshot Beats Widget Introspection For Customer UI (BUG-020)

- **Trigger:** A desktop UI process launches successfully and internal controls appear to exist, but the user reports a blank, broken, or unusable customer-facing surface.
- **Rule:** For customer-facing GUI work, verify the rendered window with a screenshot before declaring success. Process liveness, widget trees, and geometry dumps are secondary diagnostics, not proof of UX correctness. If the screenshot is still broken after toolkit-specific styling fixes, stop polishing the toolkit and reassess the presentation layer itself.
- **Why:** A GUI can be syntactically valid, remain running, and still fail the customer. Toolkits can create a correct internal widget tree while painting an unacceptable surface on the target platform. A customer experiences pixels, not `winfo_ismapped()`.
- **Proof:** BUG-020 — the DMG installer `.app` launched, `GUI_RUNNING=YES` passed, and a Tk widget-tree dump showed mapped labels, entry fields, buttons, and progress controls with valid geometry. The screenshot still showed a broken white window. The correct pivot was not another color tweak. It was replacing Tk as the primary macOS installer surface with native AppKit.
- **Avoid:** Treating "the process is alive" or "the controls exist" as evidence that a user can actually install the product.

### Installer Failures Must End With Persisted File Routing

- **Trigger:** An installer run fails, stalls, or closes before the user can keep reliable terminal or GUI scrollback.
- **Rule:** The failure surface must route immediately to the persisted installer files in order: summary file first, status file second, log file third. Treat those files as the maintained journal for the incident, not as optional diagnostics.
- **Why:** Scrollback is transient. The persisted installer files survive a closed terminal, a failed GUI session, and a retried run. Without explicit routing, the next debugging pass starts by guessing where the evidence lives instead of reading the durable record.
- **Proof:** [../scripts/setup/bootstrap_release_bundle.py](../scripts/setup/bootstrap_release_bundle.py), [../scripts/setup/install.py](../scripts/setup/install.py), and [../tests/test_install_setup.py](../tests/test_install_setup.py).
- **Avoid:** Failure text like "check the logs above" with no exact file order or path. Treating the repo-root source installer log as proof of what happened in the packaged installer bundle.

### Installer UI Must Expose Recovery Files Before Failure

- **Trigger:** A packaged installer presents a GUI surface instead of a terminal-first flow.
- **Rule:** Show the persisted summary, status, and log file paths directly in the installer UI and provide one-click open actions for them before the install fails.
- **Why:** Backend persistence is only half the fix. If the GUI hides the durable recovery files until after failure, the user still experiences an opaque installer and the next debugging pass starts from confusion instead of evidence.
- **Proof:** [../scripts/ci/installer_app.swift](../scripts/ci/installer_app.swift), [../scripts/ci/installer_gui.py](../scripts/ci/installer_gui.py), and [../tests/test_installer_gui.py](../tests/test_installer_gui.py).
- **Avoid:** Treating persisted-file routing as a backend or terminal concern only. Making the GUI say "Retry" while the real recovery journal stays invisible.

### Guards Must Be Tested On Both Positive And Negative Paths (BUG-021)

- **Trigger:** A feature adds or hardens a guard that blocks certain data shapes (tag blocklist, content heuristic, schema validator, etc.), and a separate code path elsewhere in the same codebase submits to that guard.
- **Rule:** Write or update the maintained pytest to exercise *both* paths at every caller: the negative case (the guard correctly blocks bad input) AND the positive case (legitimate callers of the protected surface pass cleanly). If the guard is centralized, the positive test captures the caller's actual payload and runs it through the real guard logic, not a mock.
- **Why:** A guard plus a caller are two independent surfaces. They can each be correct in isolation and still intersect in a way that breaks production. In BUG-021, `add_memory`'s test-memory guard (BUG-011 fix) and the installer's `inject_seed_memory` both shipped as-written, but the seed's tags matched the guard's block-list. Every fresh install failed at stage 3 for months and no test caught it because only the negative path had coverage.
- **Proof:** [../src/core/orchestrator.py](../src/core/orchestrator.py) guard body, [../scripts/setup/init_databases.py](../scripts/setup/init_databases.py) seed payload, and [../tests/test_install_setup.py](../tests/test_install_setup.py) `test_inject_seed_memory_payload_does_not_trip_test_memory_guard`. Full postmortem: [postmortems/installation.md Issue #12](postmortems/installation.md#issue-12).
- **Avoid:** Trusting that because the guard has a negative test and the caller has its own unit test, their interaction is safe. Mocking the guard in positive-path tests — that hides the exact collision this rule exists to catch.

### Installer Summary Must Name The Specific Rejection, Not The Stage (BUG-021)

- **Trigger:** An installer (or any multi-stage pipeline) has a stage that can fail due to a downstream operation returning a structured rejection reason.
- **Rule:** Propagate the specific reason from the underlying operation up into the installer's summary/status file and visible error surface. A line like `Database Initialization: FAILED (Database initialization failed)` is self-referential and forces the debugger to open the deeper log. Include the real cause: `Database Initialization: FAILED (seed memory blocked by test-memory guard: tag 'test' present)`.
- **Why:** Persisted installer files are the first place a customer or triage agent looks after failure. If the summary only names the stage, the next debugging pass starts by guessing which of N possible sub-failures happened. Every layer of indirection between symptom and cause costs tokens and time. BUG-011's `rejection_reason` field made the cause available; the installer summary formatter has to actually carry it forward.
- **Proof:** [postmortems/installation.md Issue #12](postmortems/installation.md#issue-12) — the real cause was in `.elefante-install.log` as `blocked_test_memory_submission` but the summary file only said "Database initialization failed".
- **Avoid:** Treating the stage name as sufficient error text. Collapsing downstream structured errors into a generic stage failure string.

### A Reusable Venv Must Prove `pip`, Not Just `python`

- **Trigger:** The installer is about to reuse an existing or freshly repaired `.venv`.
- **Rule:** Verify `python -m pip --version` before treating the environment as reusable. If `pip` is missing, bootstrap it with `python -m ensurepip --upgrade` before any dependency install step.
- **Why:** A virtual environment can have a working interpreter and still fail immediately on `python -m pip`. Interpreter existence alone is not enough to prove install readiness.
- **Proof:** [postmortems/installation.md Issue #13](postmortems/installation.md#issue-13) and [../tests/test_install_setup.py](../tests/test_install_setup.py).
- **Avoid:** Assuming `.venv/bin/python` existing means the environment is package-manager ready.

### Installer Bundle Packagers Must Exclude Local Env Backups

- **Trigger:** You are packaging a repo-like installer bundle from a live developer workspace.
- **Rule:** Exclude top-level local environment backups by prefix, not only by one exact directory name. For Elefante, `.venv*` must never enter the bundle payload.
- **Why:** Recovery work creates directories like `.venv.broken.<timestamp>` whose broken interpreter symlinks do not belong in a release artifact. If the packager walks them, the archive step can crash and leave stale `dist` installers looking current.
- **Proof:** [postmortems/installation.md Issue #14](postmortems/installation.md#issue-14), [../tests/test_installer_bundle.py](../tests/test_installer_bundle.py), and [../scripts/ci/build_installer_bundle.py](../scripts/ci/build_installer_bundle.py).
- **Avoid:** Excluding only exact `.venv`, or assuming broken local env backups are harmless because they are not part of the intended payload.

---

### ChromaDB `query(where=...)` Fails On Production Collections — Use `get(where=...)` (BUG-022)

- **Trigger:** You are adding or changing a `collection.query()` call that includes a `where` metadata filter against the live Elefante collection.
- **Rule:** Do not use `where` in `collection.query()`. Use `collection.get(where=...)` for metadata-only filtering. If you need semantic similarity AND metadata filtering, filter by metadata first via `get()`, then rank the results.
- **Why:** ChromaDB 1.3.5's Rust backend raises `InternalError: Error finding id` on `collection.query(where=...)` when the collection has 400+ memories. Fresh/test collections work fine, so tests pass. The failure only surfaces on a production database.
- **Proof:** BUG-022 — the legacy ChromaDB preference-reassertion path used an incompatible query filter, so `elefante-Memory` with `action="add"` failed for preferences. Removing the redundant backend filter fixed it; fresh installations now use SQLite. See [postmortems/memory.md Issue #14](postmortems/memory.md#issue-14).
- **Avoid:** Combining vector similarity and `where` metadata filters in a single `collection.query()` call against any large or aged Elefante collection. Trusting test coverage from fresh collections to prove production behavior.

---

### DOC_SYNC Starts At Known Issues (BUG-026)

- **Trigger:** You are about to author or amend documentation in `docs/`.
- **Rule:** Run Loop Step 1 first — read `workspace/ISSUES.md` Known Issues, classify the work against open BUG/GAP rows, then run Gate 3 (Leakage Scan) BEFORE writing. Cite the classification in your response.
- **Why:** Skipping Loop Step 1 reproduces BUG-006 in the direct-repo file-edit surface. `ENTRYPOINT_SEQUENCE` injection (BUG-006's shipped fix) only reaches MCP-tool callers; file-edit agents have no equivalent guard, so they must self-enforce.
- **Proof:** [postmortems/ai-behavior.md Issue #12](postmortems/ai-behavior.md#issue-12), [ISSUES.md](ISSUES.md) BUG-026 row.
- **Avoid:** Treating the orchestrator constitution as already engaged because it was read at session start. Engagement at decision time is the rule. Reactive Gate 3 (after writing) is itself a violation.

---

### Verify Process CWD and Origin Path, Not Just Port Ownership (BUG-033)

- **Trigger:** A background daemon or server endpoint (e.g., dashboard on port 8000) returns `HTTP 500` or stale responses despite a clean workspace snapshot and passing tests.
- **Rule:** Inspect the listening process's working directory (`lsof -p <PID> | grep cwd` or `ps -fp <PID>`) before assuming a code defect in the current workspace. Kill any orphaned process originating from trashed (`.Trash/`), legacy, or secondary repository checkouts.
- **Why:** Background processes spawned from old repo checkouts or moved folders can survive directory deletion and retain port bindings. When requests arrive, the stale process responds against missing or corrupted files, producing HTTP 500 errors that mask healthy code in the active workspace.
- **Proof:** [postmortems/dashboard.md Issue #12](postmortems/dashboard.md#issue-12) and [ISSUES.md](ISSUES.md) BUG-033 row.
- **Avoid:** Assuming that an active listener on port 8000 is running code from the current workspace directory.

### Judge Observable Outcomes, Not Hidden Patch Shape (BUG-046)

- **Trigger:** A benchmark uses a historical repair test to judge whether an agent solved a task.
- **Rule:** Promotion tests must assert a stated CLI, API, filesystem, or browser outcome. Track judge validity, retrieval, selection, delivery, execution, and acceptance as separate gates; missing measurements are `UNKNOWN`, not zero.
- **Why:** A correct alternative implementation can fail an implementation-coupled judge, while a relevant delivered memory can still be ignored or applied incorrectly. Either mistake confounds task quality with Task Intelligence effectiveness.
- **Proof:** [postmortems/ai-behavior.md Issue #13](postmortems/ai-behavior.md#issue-13), [../scripts/ci/verify_task_intelligence_benchmark.py](../scripts/ci/verify_task_intelligence_benchmark.py), and [../tests/test_task_intelligence_benchmark.py](../tests/test_task_intelligence_benchmark.py).
- **Avoid:** Calling a test behavioral because a manifest says so; treating retrieval hit-rate or delivered memory IDs as outcome proof; cherry-picking one run; or recording unavailable retry/correction data as zero.

### Automation Cannot Grant Itself User Authority (BUG-049)

- **Trigger:** An agent or workflow can write retention, injection, lock, archive, or delete fields on a user's durable memory.
- **Rule:** Treat user-directed and workflow-managed mutations as different authority classes. Automation may work inside user policy, but cannot create, weaken, archive, or permanently delete protected policy on its own.
- **Why:** A field called `user_locked` is not protection unless every mutation and maintenance path enforces who may change it.
- **Proof:** [postmortems/memory.md Issue #16](postmortems/memory.md#issue-16), `tests/test_mcp_daemon.py`, and `tests/test_refinery.py`.
- **Avoid:** Inferring authority from the requested value, or making permanent deletion the default forgetting operation.

### Prove The Whole Evidence Path Before Claiming Intelligence (BUG-050)

- **Trigger:** Retrieval metrics improve, a memory appears in a prompt, or one answer looks better.
- **Rule:** Keep invocation, retrieval, selection, delivery, declared use, execution, and observable outcome as separate traceable facts. Deterministic preflight validates the pipe; only paired behavioral outcomes establish lift.
- **Why:** A relevant memory can be selected but not delivered, delivered but ignored, used incorrectly, or judged by an invalid test.
- **Proof:** [postmortems/ai-behavior.md Issue #16](postmortems/ai-behavior.md#issue-16), `tests/test_task_intelligence_ledger.py`, and the sealed fixture preflight.
- **Avoid:** Treating similarity, access count, delivery, declared use, lower token cost, or one successful task as causal proof.

### Bind And Preserve Evaluation Truth Before Spending Again (BUG-051)

- **Trigger:** A Task Intelligence run fails, or its task, judge, or evidence selector changes.
- **Rule:** Preserve the failed workspace; bind outcomes to the complete task contract; inspect the selected target, ownership chain, and safeguard; and verify that every judge convention is disclosed by the frozen task or base before another model run.
- **Why:** A stale filename, lost patch, nearby-but-wrong source chunk, or hidden environment path can convert evaluator error into an apparent product failure.
- **Proof:** [postmortems/ai-behavior.md Issue #17](postmortems/ai-behavior.md#issue-17), `tests/test_task_intelligence_evaluation.py`, and the schema-v3 benchmark verifier.
- **Avoid:** Rerunning after a bare red verdict, rewriting an old outcome after the contract changes, or tuning retrieval to satisfy an undisclosed test detail.

### Select Memory For Decision Value, Not Topical Similarity (GAP-053)

- **Trigger:** A memory is semantically related to the task and survives every retrieval and governance gate, but the accepted result does not improve.
- **Rule:** Before a model run, name the exact next decision the memory can change and prove that its decisive fact is absent from the source-only evidence. If no such fact exists, reject the memory-task pair.
- **Why:** Broad relevance can steer an agent toward the right subsystem without supplying the missing implementation, constraint, preference, or fact. That memory consumes context but cannot cause a better outcome.
- **Proof:** Task 032 delivered its installation-contract memory in 3/3 treatments, yet treatment accepted 0/3; all five measured patches changed installer routing and omitted the required public Recall MCP tool. See [postmortems/ai-behavior.md Issue #20](postmortems/ai-behavior.md#issue-20).
- **Avoid:** Treating selection or delivery as usefulness; adding more broadly related memories after an application failure; choosing the task because its vocabulary matches the memory.

### Capture Explicit Decisions Before Expecting Recall (GAP-054)

- **Trigger:** A user explicitly asks Elefante to remember a durable decision across sessions, but a later Recall has no eligible memory to supply.
- **Rule:** Treat durable capture as its own causal stage. Search first, then add or correct one concise record only from an explicit cross-session remember request or canonical/non-negotiable declaration; use user-directed authority and require separate explicit authority for locks or permanent retention. Leave scope unset unless an exact identifier is known, define literal future-question triggers when using triggered delivery, and verify one likely future question through Recall.
- **Why:** A globally available Recall tool cannot improve a future task if the host workflow never creates the memory or if governance makes the stored record ineligible. Automatic conversation harvesting is not a valid repair because it creates noise, privacy risk, and false authority.
- **Proof:** The 2026-08-13 live audit found five stored records and no canonical Elefante mission. After the mission was stored, raw retrieval ranked it first but Recall rejected a descriptive scope; correcting scope to literal `elefante` made Recall supply the intended memory. See [postmortems/ai-behavior.md Issue #21](postmortems/ai-behavior.md#issue-21).
- **Avoid:** Treating a stored receipt as delivery proof; using prose as an exact scope; treating an empty or low-quality store as a ranking problem; manufacturing a benchmark memory after selecting its task; silently storing ordinary chat, inferred preferences, or secrets.

### Measure Accepted Value Against Complete Token Cost (GAP-055)

- **Trigger:** An evaluation claims better Task Intelligence from correctness, retrieval, or token savings alone.
- **Rule:** Compare matched frozen tasks using accepted outcomes per total input-plus-output tokens. A failed outcome contributes zero; treatment must not reduce accepted outcomes; cross-task evidence requires a positive task-clustered lower bound.
- **Why:** Separate quality and input-only cost gates can reward an expensive correctness gain without proving overall-token value, omit output cost, or make cheap failure look efficient.
- **Proof:** [postmortems/ai-behavior.md Issue #22](postmortems/ai-behavior.md#issue-22), `scripts/ci/summarize_task_intelligence_evaluation.py`, and `tests/test_task_intelligence_report.py`.
- **Avoid:** Comparing raw ratios across unrelated task mixes; excluding output or cached input from overall cost; treating lower cost on rejected work as product improvement; retroactively relabelling consumed evidence.

### Declarative Triggers Must Be Opt-In Delivery Gates (GAP-056)

- **Trigger:** A memory schema contains `trigger` or `surfaces_when` phrases and a new caller wants the memory to appear automatically in task context.
- **Rule:** Require an explicit caller-supplied context, literal case-insensitive matching, `injection_policy="triggered"`, a small result cap, and the same lifecycle, scope, source-trust, conflict, and privacy gates as normal delivery. Keep the path read-only and do not silently turn a metadata hint into host interception.
- Known stored conflicts must be surfaced as a bounded warning while both sides remain withheld; warning delivery is not semantic conflict detection or an automatic winner.
- **Why:** A trigger phrase describes user intent, but it is not a license for broad injection. Unbounded scanning, semantic interpretation, or automatic host hooks can leak stale or private context and create a second retrieval system that users cannot inspect or roll back.
- **Proof:** [postmortems/ai-behavior.md Issue #23](postmortems/ai-behavior.md#issue-23), `src/core/governance.py`, `src/core/orchestrator.py`, `src/core/task_intelligence.py`, and `tests/test_proactive_surfacing.py`.
- **Avoid:** Treating `surfaces_when` as active behavior merely because it persists, matching ranked memories, bypassing conflict/privacy gates, or claiming proactive host behavior when only an explicit search context is supported.

---

## Update Protocol

After a significant debugging session:

1. Update the relevant `postmortems/<domain>.md`.
2. Add or revise the BUG row in [ISSUES.md](ISSUES.md).
3. Add or revise a rule here only if the lesson survives the Promotion Filter above.
4. Update [`../agents/orchestrator.md`](../agents/orchestrator.md) if the workflow itself changed.
5. Guard the rule in a maintained test or verifier when possible.

If a rule becomes structural, move it into source, tool schemas, directives, or the agent constitution and leave only the distilled lesson here.

---

## Recent Examples

- **BUG-006:** The reusable lesson was not “tool responses were missing a field.” The reusable lesson was “entry routing must be visible at first contact.” See [postmortems/ai-behavior.md](postmortems/ai-behavior.md#issue-6).
- **BUG-007:** The reusable lesson was not “a few docs were stale.” The reusable lesson was “fix the whole live surface, then guard it from source.” See [postmortems/ai-behavior.md](postmortems/ai-behavior.md#issue-7).
- **BUG-002:** The reusable lesson was not “Kuzu was locked again.” The reusable lesson was “verify the live contract before trusting the old explanation.” See [postmortems/database.md](postmortems/database.md#issue-2).
- **BUG-008:** The reusable lesson was not “GraphConnect broke once.” The reusable lesson was “graph and session tools must target the actual schema.” See [postmortems/database.md](postmortems/database.md#issue-8).
- **BUG-009:** The reusable lesson was not “the self-protocol flaked.” The reusable lesson was “maintained verifiers must follow the live contract.” See [postmortems/ai-behavior.md](postmortems/ai-behavior.md#issue-8).
- **BUG-003:** The reusable lesson was not “dashboard health was good.” The reusable lesson was “the verifier must prove the actual failure mode.” See [postmortems/dashboard.md](postmortems/dashboard.md#issue-8).
- **BUG-016/017/018:** The reusable lesson was not “the scoring weights were wrong.” The reusable lesson was “trace write→read value spaces before trusting any scored signal.” See [postmortems/memory.md](postmortems/memory.md#issue-11).
