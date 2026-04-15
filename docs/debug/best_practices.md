# Debug Best Practices

> **Purpose:** Distilled reusable debugging rules for Elefante contributors
> **Companion Docs:** [README.md](README.md) and [dev-developer-agent.md](dev-developer-agent.md)
> **Status:** Live feedback-loop ledger

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
- **Proof:** [ops-ai-behavior-compendium.md Issue #6](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure) and [../../scripts/verify/verify_e2e_tests.py](../../scripts/verify/verify_e2e_tests.py).
- **Avoid:** Sizing timeouts and confidence only around a warmed-up development shell.

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