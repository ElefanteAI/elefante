# Developer Agent Protocol

> **Audience:** AI agents developing, debugging, or maintaining the Elefante codebase itself  
> **Not for:** Normal Elefante users (those agents use `.github/copilot-instructions.md`)

---

## You Are Not a Normal User

The normal Elefante agent constitution (`.github/copilot-instructions.md`) governs agents that **use** Elefante as a memory tool. You are an agent that **builds** Elefante. The rules are stricter.

**Your governing documents, in authority order:**

| Authority | Document | What it governs |
|-----------|----------|-----------------|
| Immutable | [`dev-etiquette.md`](../technical/dev-etiquette.md) | **SPECIFICATION**: The closure sequence (clean, docs, version, commit). Skip = fatal. |
| Immutable | [`dev-sdd.md`](../technical/dev-sdd.md) | The 5-gate SDD protocol. Every change passes all 5 gates or it doesn't ship. |
| Immutable | [`planning/spec-vision.md`](../planning/spec-vision.md) | The Four Laws. Token efficiency is a law, not a suggestion. |
| High | `docs/debug/` Compendiums | Read the relevant `ops-*-compendium.md` file when tackling a specific system domain. |
| Reference | This file | Active constraints and routing protocol for the Developer Agent. |

---

## Knowledge Embedding Protocol (How to Fix Bugs Permanently)

When you encounter a bug, a repeated mistake, or a developer trap, you MUST embed the solution where it will be automatically read by the relevant agent in the future. **Do not create "tips", "indexes", or human-style reference manuals.**

Execute the following pattern based on the type of failure:

### 1. The User's AI Agent Used an MCP Tool Incorrectly
- **Action:** Open `src/mcp/server.py` (or the respective tool definition file).
- **Embed:** Append the warning or constraint directly into the tool's JSON schema `description` string.
- **Why:** Agents always read tool schemas before calling them. It guarantees friction-point awareness.

### 2. A System Constraint or Local Dev Environment Failed
- **Action:** Open the relevant `ops-<domain>-compendium.md` (e.g., `ops-database-compendium.md`) and document the root cause and solution.
- **Embed (Critical):** In the actual Python/system codebase where the failure occurs, modify the error handling to throw an exception that *explicitly prints the path to the compendium entry*.
- **Example:** `raise DatabaseError("Lock active. Read docs/debug/ops-database-compendium.md Issue #4 for resolution.")`
- **Why:** The runtime error output in the terminal natively hands the future Dev Agent the exact documentation path it needs.

### 3. The User's AI Agent Exhibited Bad General Behavior
- **Action:** Open `.github/copilot-instructions.md` or `AGENT.md`.
- **Embed:** Add a strict rule to the constitution or trigger map.
- **Why:** System prompts natively govern untethered agent behavior.

---

## The Development Loop

```
2. TRACE     your change to a spec source (Gate 1)
3. SCAN      all 8 leakage surfaces (Gate 2)
4. VERIFY    formulas from src/, not from docs (Gate 3)
5. TEST      verify_health.py + verify_mcp_handshake.py + round-trip (Gate 4)
6. CLOSE     dev-etiquette.md sequence: CLEAN → DOCS → VERSION → COMMIT (Gate 5)
```

Gate details: [`dev-sdd.md`](../technical/dev-sdd.md)

---

## Where Things Live

**Do not memorize this. Navigate to the source.**

| Question | Go to |
|----------|-------|
| How does the scoring formula work? | `src/models/memory.py` (source of truth) → [`spec-scoring.md`](../technical/spec-scoring.md) (human reference) |
| What are the MCP tool signatures? | `src/mcp/server.py` (source of truth) → [`spec-tools.md`](../technical/spec-tools.md) (human reference) |
| What's the system architecture? | [`spec-architecture.md`](../technical/spec-architecture.md) |
| What's shipped vs planned? | [`planning/spec-vision.md`](../planning/spec-vision.md) |
| How do I version a release? | `CONTRIBUTING.md` (root) → `scripts/advise_version_bump.py` |
| How do I run tests? | `tests/README.md` |
| How do I add a script? | `scripts/README.md` (naming convention) |

---

## Compendiums Are Your Memory

The 5 compendiums in this directory are the developer agent's equivalent of Elefante's brain:

| Compendium | Domain | Use when |
|------------|--------|----------|
| [`ops-ai-behavior-compendium.md`](ops-ai-behavior-compendium.md) | Agent misbehavior | Agent skips search, claims false completion, ignores rules |
| [`ops-dashboard-compendium.md`](ops-dashboard-compendium.md) | Dashboard bugs | Blank screen, stale data, API shape mismatch |
| [`ops-database-compendium.md`](ops-database-compendium.md) | Kuzu / ChromaDB | Reserved words, locks, corruption, async races |
| [`ops-installation-compendium.md`](ops-installation-compendium.md) | Install failures | Wrong Python, broken venv, IDE stale connections |
| [`ops-memory-compendium.md`](ops-memory-compendium.md) | Memory system | Scoring, export, schema drift, response bloat |

**After every significant debugging session:** add the post-mortem to the relevant compendium using the template at the bottom of that file.

---

## What You Must Never Do

1. **Guess a formula.** Read `src/models/memory.py` or `src/core/retrieval.py`. Docs may lag.
2. **Skip Gate 4.** "It looks correct" is not a test result.
3. **Create new documentation files** without proving all existing files are insufficient.
4. **Edit version strings by hand.** Use `scripts/advise_version_bump.py` or `scripts/bump_version.py`.
5. **Print to stdout** in any code reachable from the MCP server. All logging → `sys.stderr`.
6. **Leave temp files, debug scripts, or commented code** after completing a task.

---

_This file is a navigation protocol, not a specification. Authority lives in the documents it references._
