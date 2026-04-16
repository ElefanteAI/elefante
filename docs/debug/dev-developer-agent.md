# Developer Agent Protocol

> **Audience:** AI agents developing, debugging, or maintaining the Elefante codebase itself  
> **Not for:** Usage-focused Elefante agents following the end-user constitution for this repo (currently `.github/copilot-instructions.md`)

---

## You Are Not a Normal User

The usage-focused agent constitution for this repository (currently `.github/copilot-instructions.md`) governs agents that **use** Elefante as a memory tool. You are a helpful and nonsycophantic agent that **builds** Elefante. The rules are stricter.

Before debugging anything, open [`README.md`](README.md) in this folder, then [`best_practices.md`](best_practices.md), then the relevant `ops-*-compendium.md`, then [`tests/README.md`](../../tests/README.md). Do not pick scripts first and invent the reason afterward.

### Mandatory Entry Sequence (Non-Negotiable)

```text
1. READ   docs/debug/README.md  → Check Known Issues table for matching BUG-NNN
2. RUN    The verification command from the matching issue row
3. IF     test passes → fix is intact, root-cause elsewhere
4. IF     test fails → real regression, open the linked compendium
5. READ   compendium Verification Commands block → run the specific test
6. FIX    with compendium context loaded
7. TEST   the fix with the same verification command
8. CLOSE  update Known Issues status, compendium, dev-etiquette closure
```

Skipping step 1 is how BUG-001 (Kuzu SIGSEGV) recurred. The fix existed, the docs existed, the tests existed — the agent just didn't read them. Runtime error messages now cite compendium entries directly so even a non-compliant agent gets routed to the docs via terminal output.

**Your governing documents, in authority order:**

| Authority | Document | What it governs |
| --------- | -------- | --------------- |
| Immutable | [`dev-etiquette.md`](../technical/dev-etiquette.md) | **SPECIFICATION**: The closure sequence (clean, docs, version, commit). Skip = fatal. |
| Immutable | [`dev-sdd.md`](../technical/dev-sdd.md) | Embedded development process reference. Legacy filename retained for continuity. |
| Immutable | [`planning/spec-vision.md`](../planning/spec-vision.md) | The Four Laws. Token efficiency is a law, not a suggestion. |
| High | [`best_practices.md`](best_practices.md) | Distilled cross-bug feedback loop learnings that should stay online and tracked. |
| High | `docs/debug/` Compendiums | Read the relevant `ops-*-compendium.md` file when tackling a specific system domain. |
| Reference | This file | Active constraints and routing protocol for the Developer Agent. |

---

## Agnostic Wording Rule

Keep this protocol as environment-agnostic as reality allows.

- Prefer interface names over vendor names: say `agent instruction surface`, `tool schema`, `runtime error surface`, `verification command`, or `editor-level instructions`.
- Name a concrete product, file, or editor only when the bug or fix actually depends on that concrete surface.
- If multiple instruction surfaces exist, patch the highest-authority surface the active environment actually loads.
- Do not strip Elefante-specific technical facts for the sake of abstraction. Generalize the agent environment, not the system behavior.

---

## Knowledge Embedding Protocol (How to Fix Bugs Permanently)

When you encounter a bug, a repeated mistake, or a developer trap, you MUST embed the solution where it will be automatically read by the relevant agent in the future. **Do not create ad hoc "tips", duplicate indexes, or parallel reference manuals. Use [`best_practices.md`](best_practices.md) as the designated cross-bug feedback ledger.**

Execute the following pattern based on the type of failure:

### 1. An Agent Used a Tool or Interface Incorrectly

- **Action:** Open the source file that defines the callable interface, such as `src/mcp/server.py`, a CLI entry point, or the relevant schema/handler.
- **Embed:** Put the warning or constraint in the invocation surface the agent is most likely to read first: a tool `description`, schema field, parser help string, prompt header, or preflight error.
- **Why:** Agents follow instructions that appear at the point of action more reliably than passive docs.

### 2. A System Constraint or Local Dev Environment Failed

- **Action:** Open the relevant `ops-<domain>-compendium.md` (e.g., `ops-database-compendium.md`) and document the root cause and solution.
- **Embed (Critical):** In the actual Python/system codebase where the failure occurs, modify the error handling so the primary runtime error surface explicitly names the compendium entry.
- **Example:** `raise DatabaseError("Lock active. Read docs/debug/ops-database-compendium.md Issue #4 for resolution.")`
- **Why:** The runtime failure itself should hand the future developer agent the exact documentation path it needs.

### 3. The Active Agent Environment Exhibited Bad General Behavior

- **Action:** Open the highest-authority instruction surface actually loaded in the current environment, such as `AGENT.md`, `.github/copilot-instructions.md`, editor-level instructions, or the equivalent agent constitution.
- **Embed:** Add a strict rule to the constitution, trigger map, or other loaded instruction surface.
- **Why:** Loaded instruction surfaces govern untethered agent behavior. Passive repository docs do not.

### 4. The Lesson Generalizes Beyond One Bug

- **Action:** Open [`best_practices.md`](best_practices.md).
- **Embed:** Add the distilled rule using `Trigger -> Rule -> Why -> Proof -> Avoid`, link it back to the relevant compendium entry and verifier, and keep it short enough to stay useful during active development.
- **Why:** This keeps the feedback loop online. Compendiums keep the full post-mortem; `best_practices.md` keeps the reusable rule that should shape the next debugging pass.

---

## The Development Loop

```text
1. ENTER     docs/debug/README.md Known Issues table (mandatory)
2. ROUTE     check if existing test already proves/disproves the hypothesis
3. TRACE     your change to a spec source
4. SCAN      all 8 leakage surfaces
5. VERIFY    formulas from src/, not from docs
6. TEST      run the verification command from the Known Issues row
7. CLOSE     dev-etiquette.md sequence: CLEAN → DOCS → VERSION → COMMIT
8. UPDATE    Known Issues table status + compendium; add to best_practices.md if the lesson generalizes
```

Process details: [`dev-sdd.md`](../technical/dev-sdd.md) (legacy filename, embedded process reference)

## Purposeful Script Routing

Do not run scripts as a ritual. Every script call must answer a specific debugging question.

Before writing any scratch reproducer or one-off validation, check whether `tests/README.md` already maps the failure mode to a maintained pytest target. If it does, run that first. If the test is stale, update the existing test instead of creating a parallel scratch path.

| Question you are answering | Run this | Why this script exists |
| ------------------------- | -------- | ---------------------- |
| Is the installation or baseline healthy? | `scripts/verify/verify_health.py` | Verifies imports, data paths, directives, and required specification memories |
| Does the MCP server actually speak stdio JSON-RPC? | `scripts/verify/verify_mcp_handshake.py` | Proves real `initialize`/handshake liveness instead of assuming startup succeeded |
| Does Elefante actually run end-to-end in isolation? | `scripts/verify/verify_e2e_tests.py` | Runs the self-protocol: live MCP surface, prompt retrieval, routing injection, compliance, memory/graph/task/ETL flows, restart persistence, and cleanup in an isolated temp Elefante home/data dir |
| Did a specific code path regress? | targeted `pytest` test from `tests/README.md` | Smallest reproducible proof for the changed path |
| Is the factory reset script safe? | `pytest tests/test_factory_reset.py -v` | Validates dry-run, safety gates, backup creation, and idempotency against isolated temp HOME |
| Is there a severe operational failure the verify scripts cannot explain? | `scripts/debug/*` only if the compendium tells you to | Intervention tools, not routine validation |
| Need a populated demo database for dashboard testing? | `scripts/demo/generate_100_memories.py --db ./a0-data/demo_db` | Injects 100 memories with full behavioral history: 6-month temporal spread, Zipf access patterns (hot/warm/cool/cold), session IDs on conversations, conflict cross-links on contradictions, topical clusters via related_memory_ids, authority scores, supersessions, co-activation edges, purposeful deletions. 8-point spec verification built in. Zero LLM. Spec: `scripts/demo/SPEC_behavioral_history.md` |

---

## Where Things Live

**Do not memorize this. Navigate to the source.**

| Question | Go to |
| -------- | ----- |
| How does the scoring formula work? | `src/models/memory.py` (source of truth) → [`spec-scoring.md`](../technical/spec-scoring.md) (human reference) |
| What are the exposed tool signatures? | `src/mcp/server.py` (source of truth for the current MCP surface) → [`spec-tools.md`](../technical/spec-tools.md) (human reference) |
| What's the system architecture? | [`spec-architecture.md`](../technical/spec-architecture.md) |
| What's shipped vs planned? | [`planning/spec-vision.md`](../planning/spec-vision.md) |
| How do I version a release? | `CONTRIBUTING.md` (root) → `scripts/ci/advise_version_bump.py` |
| How do I run tests? | `tests/README.md` |
| How do I add a script? | `scripts/README.md` (naming convention) |
| Which script do I run and why? | This file → **Purposeful Script Routing** → `scripts/README.md` |

---

## Compendiums Are Your Memory

The 5 compendiums in this directory are the developer agent's equivalent of Elefante's brain:

| Compendium | Domain | Use when |
| ---------- | ------ | -------- |
| [`ops-ai-behavior-compendium.md`](ops-ai-behavior-compendium.md) | Agent misbehavior | Agent skips search, claims false completion, ignores rules |
| [`ops-dashboard-compendium.md`](ops-dashboard-compendium.md) | Dashboard bugs | Blank screen, stale data, API shape mismatch |
| [`ops-database-compendium.md`](ops-database-compendium.md) | Kuzu / ChromaDB | Reserved words, locks, corruption, async races |
| [`ops-installation-compendium.md`](ops-installation-compendium.md) | Install failures | Wrong Python, broken venv, IDE stale connections |
| [`ops-memory-compendium.md`](ops-memory-compendium.md) | Memory system | Scoring, export, schema drift, response bloat |

**After every significant debugging session:** add the post-mortem to the relevant compendium using the template at the bottom of that file.

## Best Practices Is The Distilled Loop

[`best_practices.md`](best_practices.md) is the short-form companion to the compendiums. Use it for reusable development rules that connect multiple issues, not for full narratives. If the compendiums are the long-term memory, `best_practices.md` is the distilled operating layer that keeps the feedback loop visible during active development.

---

## What You Must Never Do

1. **Guess a formula.** Read `src/models/memory.py` or `src/core/retrieval.py`. Docs may lag.
2. **Skip purposeful verification.** "It looks correct" is not a test result.
3. **Create new documentation files** without proving all existing files are insufficient.
4. **Edit version strings by hand.** Use `scripts/ci/advise_version_bump.py` or `scripts/ci/bump_version.py`.
5. **Print to stdout** in any code reachable from the MCP server. All logging → `sys.stderr`.
6. **Run scripts without a concrete failure mode or validation target.**
7. **Leave temp files, debug scripts, or commented code** after completing a task.

---

*This file is a navigation protocol, not a specification. Authority lives in the documents it references.*
