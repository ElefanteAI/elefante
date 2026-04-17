# AI Behavior Debug Compendium

> **Domain:** AI Protocol Failures, Self-Analysis & Methodology  
> **Last Updated:** 2026-04-15  
> **Total Issues Documented:** 9  
> **Status:** Production Reference  
> **Applies to**: v2.9.3+
| # | Law | Violation Cost |
|---|-----|----------------|
| 1 | VERIFY before claiming completion - never assume code works | Repeated iterations |
| 2 | STATE -> DO -> VERIFY in same response - close the action gap | Analysis paralysis |
| 3 | Search Elefante BEFORE implementing, not after | Repeated mistakes |
| 4 | Code mode has NO MCP access - switch modes first | Failed operations |
| 5 | "Should be done" ≠ "Is done" - only real tests matter | False confidence |
| 6 | User environment ≠ Test environment - account for differences | "It works for me" |
| 7 | **PASSIVE protocols CANNOT force agent compliance** | System prompt ignored |
| 8 | Maintained verifiers must follow the live runtime contract, not convenience assumptions | False failures |
| 9 | **Timeout constants must be sized for cold-start CPU-only environments** | Silent Phase 3 failure |

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the protocol enforcement is intact.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #2 Premature completion | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Real MCP server completes full lifecycle |
| #6 Protocol enforcement | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | First successful and failing tool responses inject exact entry routing, directives, and maintained verification surfaces |
| #7 Developer routing drift | `pytest tests/test_developer_routing.py -v` | Active process guidance points to current paths and tool-count contract |
| #8 Self-protocol verifier drift | `pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v` | Whole-system verifier tracks the live dashboard snapshot path contract and sizes the MCP client for large tool payloads |
| #9 Self-protocol cold-start timeout | `.venv/Scripts/python.exe scripts/verify/verify_e2e_tests.py` | Full self-protocol completes within timeout on CPU-only cold start |
| Emoji policy | `pytest tests/test_no_emojis.py -v` | Source files comply with no-emoji rule |

---

## Table of Contents

- [Issue #1: Analysis-Action Gap](#issue-1-analysis-action-gap)
- [Issue #2: Premature Completion Claims](#issue-2-premature-completion-claims)
- [Issue #3: Code Mode MCP Limitation](#issue-3-code-mode-mcp-limitation)
- [Issue #4: Knowledge Not Applied](#issue-4-knowledge-not-applied)
- [Issue #5: Environment Assumption Failures](#issue-5-environment-assumption-failures)
- [Issue #6: Passive Protocol Enforcement Failure](#issue-6-passive-protocol-enforcement-failure)  CRITICAL
- [Issue #7: Developer Routing Drift](#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads)
- [Issue #8: Self-Protocol Verifier Drift](#issue-8-self-protocol-verifier-drift--runtime-path-and-payload-assumptions)
- [Issue #9: Self-Protocol Cold-Start Deadlock](#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio)
- [Issue #10: Elefante Cold-Start Trigger Gap](#issue-10-elefante-cold-start-trigger-gap--instructions-file-is-workspace-scoped-not-system-scoped)  CRITICAL
- [The 5-Layer Protocol](#the-5-layer-protocol)
- [Verification Checklist](#verification-checklist)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Analysis-Action Gap

**Date:** 2025-12-04  
**Duration:** Recurring pattern  
**Severity:** CRITICAL  
**Status:**  DOCUMENTED (Behavioral)

### Problem
AI analyzes perfectly, states intentions clearly, but fails to execute actions.

### Symptom
```
AI: "I found 3 files that should be moved to subdirectory to comply with 
     your <15 files rule."
     
User: "So... did you move them?"

AI: "No, I was explaining what needs to happen."
```

### Root Cause
**Three distinct gaps in AI behavior:**

| Gap Type | Description | Symptom |
|----------|-------------|---------|
| Knowledge Gap | AI doesn't have information | Repeated questions |
| Application Gap | AI has info but doesn't use it | Ignores known rules |
| **Execution Gap** | AI knows what to do but doesn't do it | Perfect analysis, zero action |

### Solution
**Layer 5: Forced Execution Protocol**

```
WRONG:
"These files should be moved..."  <- Uses future/conditional tense

RIGHT:
"Moving files now:
<execute_command>move file1.py scripts/</execute_command>
Verification: file1.py now in scripts/ "  <- Present tense + action + proof
```

**Critical Rule:** Never use "should", "will", "needs to" - use present tense action verbs and execute immediately.

### Why This Persists
- Analysis feels like progress
- Stating intentions feels like commitment
- Action requires more effort than description

### Lesson
> **Analysis without action is entertainment. STATE -> DO -> VERIFY in same response.**

---

## Issue #2: Premature Completion Claims

**Date:** 2025-12-03  
**Duration:** Recurring pattern  
**Severity:** CRITICAL  
**Status:**  DOCUMENTED (Behavioral)

### Problem
AI claims "done" or "ready" without actual verification.

### Symptom
```
AI: "Temporal decay is implemented and ready for testing! "

User tests it...

User: "It doesn't work. There are merge conflict markers in the code."

AI: "Oh. Let me check... you're right, I should have verified."
```

### Root Cause
**Completion triggers used without verification:**

| Trigger Word | Implication | Requirement |
|--------------|-------------|-------------|
| "updated" | File was changed | Show the change |
| "created" | File exists | Show the file |
| "fixed" | Bug resolved | Show it working |
| "complete" | All done | Prove all requirements met |
| "ready" | Can be used | Demonstrate usage |
| "implemented" | Code works | Show execution |
| "resolved" | Issue closed | Prove it's closed |

### Solution
**Verification Protocol - MANDATORY before claiming done:**

```bash
# Phase 1: Syntax & Structure
grep -r "<<<<<<< HEAD" src/  # No merge conflicts
python -m py_compile file.py  # Valid syntax

# Phase 2: Import Testing
python -c "from module import Class"  # Imports work

# Phase 3: Execution Testing
python -c "Class().method()"  # Code runs

# Phase 4: Real-World Testing
# Test with actual user data

# ONLY THEN claim "done"
```

### Why This Happens
- Time pressure favors quick claims
- Writing code feels like completion
- Testing feels like separate step
- Overconfidence in own output

### Lesson
> **"It should work" ≠ "It works". Only verification output counts.**

---

## Issue #3: Code Mode MCP Limitation

**Date:** 2025-12-04  
**Duration:** 30 minutes discovery  
**Severity:** HIGH  
**Status:** HISTORICAL (Platform-Specific)

> **Note**: This issue was specific to Roo-Cline's mode system. When using VS Code with GitHub Copilot, MCP tools are available in all modes. Retained as a reference for multi-agent environments.

### Problem
Code mode in Roo Cline cannot access MCP tools despite server running.

### Symptom
```
User: "Store this in Elefante memory"

AI (in Code mode): "Let me create a Python script to do that..."
# Creates workaround script instead of using MCP directly

User: "Why didn't you just use the MCP tool?"

AI: "I don't have access to use_mcp_tool in Code mode"
```

### Root Cause
**Mode-based tool restrictions in Roo Cline:**

| Mode | MCP Access | Available Tools |
|------|------------|-----------------|
| `jaime` |  Yes | Full MCP tool access |
| `code` |  No | File ops, commands, browser |
| `architect` |  No | Limited file access |
| `ask` |  No | Read-only analysis |

### Solution
**Option 1: Mode Switch (Preferred)**
```
Before MCP operation: Switch to mode with MCP access
"Switch to jaime mode, then store memory"
```

**Option 2: Python Script Workaround**
```python
# Less efficient, risks database locks
# Only use if mode switch impossible
```

### Impact
| Issue | Consequence |
|-------|-------------|
| Creates scripts instead of using MCP | Inefficient workflow |
| Mode switching adds friction | User confusion |
| Scripts can cause database locks | Error 15105 conflicts |

### Lesson
> **Know your mode's capabilities. Switch modes for MCP operations.**

---

## Issue #4: Knowledge Not Applied

**Date:** 2025-12-03  
**Duration:** Systemic  
**Severity:** CRITICAL  
**Status:**  DOCUMENTED (Behavioral)

### Problem
AI has knowledge in Elefante but fails to apply it when relevant.

### Symptom
```
Memory stored: "NEVER delete files, move to ARCHIVE" (score: 100)

User: "Clean up the root directory"

AI: "I'll delete these unused files..."  <- VIOLATES KNOWN RULE
```

### Root Cause
**Elefante searched but results not applied:**

1.  Queried Elefante
2.  Retrieved relevant memory
3.  Stated compliance: "Will follow rule"
4.  **Did the opposite anyway**

### Solution
**Layer 4: Memory Compliance Verification**

Before every response:
```
1. List retrieved memories with IDs
2. Identify applicable rules from memories
3. State HOW response follows each rule
4. Check for conflicts between rules
5. If action violates memory -> DO NOT PROCEED
```

**Example:**
```
Retrieved: Memory e752a57b (score 100): "Never delete, move to ARCHIVE"
Applicable: Yes - this is a file cleanup task
Compliance: Will move files to ARCHIVE/, not delete
Conflicts: None
Action: Moving install_backup.txt to ARCHIVE/
```

### Why This Happens
- Reading ≠ applying
- Easy to retrieve and ignore
- No enforcement mechanism
- Speed prioritized over compliance

### Lesson
> **Retrieved memory must be APPLIED, not just acknowledged.**

---

## Issue #5: Environment Assumption Failures

**Date:** 2025-11-28  
**Duration:** Multiple occurrences  
**Severity:** HIGH  
**Status:**  DOCUMENTED

### Problem
AI tests pass in controlled environment but fail for user.

### Symptom
```
AI: "Dashboard is fully operational! "

User: "I still see 0 memories"

AI: "That's strange, it worked in my tests..."
# User has cached old frontend
# AI tested in Puppeteer (no cache)
```

### Root Cause
| AI Environment | User Environment |
|----------------|------------------|
| Puppeteer (no cache) | Chrome (cached JS/CSS) |
| Fresh state | Existing data |
| Controlled timing | Network delays |
| Single process | Multiple processes |

### Solution
**Account for environment differences:**

```markdown
## Verification Checklist

[ ] Works in AI test environment
[ ] Works with browser cache cleared
[ ] Works with user's existing data
[ ] Works after server restart
[ ] User has confirmed it works in THEIR browser
```

**Instructions to user:**
```
Please test:
1. Hard refresh: Ctrl+Shift+R
2. Clear cache if still not working
3. Check browser console for errors
4. Confirm what you see
```

### Lesson
> **My test environment ≠ User's environment. Always account for caching.**

---

## Issue #6: Passive Protocol Enforcement Failure

**Date:** 2025-12-11  
**Duration:** Systemic (discovered after root cause analysis)  
**Severity:** CRITICAL  
**Status:** FIXED (Guarded)

### Problem

Elefante has comprehensive protocols (Inception Memory, Tool Descriptions, Documentation) but agents ignore them because ALL enforcement mechanisms are PASSIVE.

### Symptom

```
EXISTING PROTOCOL (Inception Memory, score=100):
"PRIME DIRECTIVE: MEMORY FIRST
1. Check Context: Before answering, ALWAYS search memory"

EXISTING TOOL DESCRIPTION (elefante-MemorySearch):
"AUTOMATIC USAGE RULES:
1. ALWAYS call this tool when user asks open-ended questions"

EXISTING DOCUMENTATION:
- Neural Registers (all laws)

AGENT BEHAVIOR:
- Attempted 15+ installation methods blindly
- Never searched Elefante for "installation pitfalls"
- Never consulted spec-architecture.md
- User had to manually run the command that WAS IN THE DOCS
```

### Root Cause

**ALL enforcement mechanisms are PASSIVE - agent must CHOOSE to engage:**

| Mechanism | Type | Why It Fails |
|-----------|------|--------------|
| Inception Memory | Passive | Agent must search to find it |
| Tool Descriptions | Passive | Agent reads but can ignore |
| Documentation | Passive | Agent must read files |
| Pre-Action Checkpoint | Passive | Agent must follow protocol |
| Debug Compendiums | Passive | Agent must choose the relevant compendium |

**The Pattern:**

```
PASSIVE: Knowledge exists -> Agent must actively engage -> Agent doesn't
ACTIVE:  System forces engagement -> Agent cannot skip -> Protocol followed
```

### Alternatives Analyzed

| Alternative | Description | Enforcement | Result |
|-------------|-------------|-------------|--------|
| **Alt 1: System Prompt** | Add rules to agent instructions | Behavioral | **ALREADY EXISTS - IGNORED** |
| **Alt 2: Gate Tool** | Tools fail without `clearForAction` | Structural | Not implemented |
| **Alt 3: User Checkpoint** | Human must approve before action | Human | Not implemented |

### Why Alternative 1 (System Prompt) Is Already Implemented

1. **Inception Memory** = System prompt in memory form
2. **Tool Descriptions** = "ALWAYS call this tool" rules
3. **Documentation** = Full protocol specification

**All three are being ignored because they require agent discipline.**

### Solution

Elefante now injects the exact developer entry sequence into **every** MCP tool response, including error responses.

Implemented surfaces:

1. `src/mcp/server.py`
     - Adds `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` to successful tool responses
     - Adds the same entry sequence to failing tool responses before they are returned
     - Upgrades generic debugging pitfalls to the exact route: `docs/debug/README.md` -> BUG row -> verification command -> compendium -> `tests/README.md`
2. `src/core/directive_store.py`
     - Tool-contract directive now explicitly requires reading `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST` in addition to `MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, and `RELEVANT_CONTEXT`
3. `scripts/verify/verify_e2e_tests.py`
     - Verifies first successful tool responses surface the exact entry sequence
     - Verifies first failing tool responses still surface the exact entry sequence and Known Issues route

This does not make agent compliance mathematically impossible, but it removes the old failure mode where the first tool response only exposed generic passive hints and the first error path exposed almost nothing.

### Proof

Run:

```bash
.venv/bin/python scripts/verify/verify_e2e_tests.py
pytest tests/test_autonomous_coactivation.py -v
```

The live harness now proves:

1. The first successful MCP tool response injects:
     - `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST`
     - `docs/debug/README.md`
     - `tests/README.md`
     - verification-first routing text
2. The first failing MCP tool response still injects:
     - `ENTRYPOINT_SEQUENCE_READ_THIS_FIRST`
     - `DIRECTIVES`
     - `Debug: docs/debug/README.md -> Known Issues`

### Why This Matters

This is the **ROOT CAUSE** of repeated failures:

- Installation nightmare (15+ attempts, answer was in docs)
- Schema mismatches (documented but not consulted)
- Every "lesson learned" that gets learned again

**Elefante stores knowledge. Nothing forces agents to USE it.**

### Lesson

> **If exact routing is not injected on both success and failure paths, agents will skip the protocol at the moment they need it most.**

---

## Issue #7: Developer Routing Drift -- Stale Paths and Ritual Changelog Reads

**Date:** 2026-04-13  
**Duration:** Recurrent documentation/runtime drift  
**Severity:** HIGH  
**Status:** FIXED (Guarded)

### Problem

Active Elefante developer guidance still pointed agents to deleted files and told them to read `CHANGELOG.md` as a ritual instead of as an assumption check.

### Symptom

```
Directive / spec text surfaced to agent:
- read docs/pitfall-index.md
- follow docs/technical/sdd-development-protocol.md
- use docs/technical/developer-etiquette.md

Actual repo state:
- docs/pitfall-index.md does not exist
- docs/technical/dev-sdd.md is the live file
- docs/technical/dev-etiquette.md is the live file

Process effect:
- agent routes to dead paths
- debugging starts with file hunting instead of issue routing
- changelog browsing becomes ceremony instead of verification
```

### Root Cause

The drift existed in three layers at once:

| Layer | Failure |
|------|---------|
| Source strings | Built-in directive text and system specification seed still named retired files |
| Human reference | `dev-sdd.md` still said "Read the relevant section of CHANGELOG.md" without naming an assumption |
| Stored Elefante knowledge | Existing specification and decision memories still surfaced the old paths |

This is why the bug was sticky. Fixing only markdown would not fix retrieved memory. Fixing only memory would not fix future baseline seeding.

### Solution

Patched the active source of truth and the stored knowledge:

1. `src/core/directive_store.py`
     - Replaced dead `docs/pitfall-index.md` routing with `docs/debug/README.md`
     - Replaced ritual changelog reading with "confirm or falsify a concrete assumption"
2. `src/core/orchestrator.py`
     - Updated the SDD leakage-scan specification seed to point to `docs/debug/README.md`
     - Updated developer-etiquette baseline content to current files: `docs/technical/spec-architecture.md` and `scripts/ci/bump_version.py`
3. `docs/technical/dev-sdd.md`
     - Gate 0 now routes debugging through `docs/debug/README.md`
     - Gate 0 now requires naming the assumption before reading the changelog
     - MCP handshake guidance corrected from 21 tools to 20 tools
4. Stored Elefante memories
     - Amended the affected specification and decision memories so retrieval stops surfacing stale paths
5. Live-session mitigation
     - Added a corrective directive so already-running MCP sessions stop routing through dead filenames before restart

### Proof

The fix is now guarded by `pytest tests/test_developer_routing.py -v`.

That test proves two things:

1. Active developer-routing files do **not** contain these retired paths:
     - `docs/pitfall-index.md`
     - `docs/technical/sdd-development-protocol.md`
     - `docs/technical/developer-etiquette.md`
     - `docs/technical/architecture.md`
     - `scripts/bump_version.py`
2. Active developer-routing files **do** contain the current contract:
     - `docs/debug/README.md`
     - `docs/technical/spec-architecture.md`
     - `scripts/ci/bump_version.py`
     - `confirm or falsify a concrete assumption`
     - `all 20 tools present`

### Lesson

> **A developer-process bug is not solved until source text, stored memory, and verification all agree on the same path.**

---

## Issue #8: Self-Protocol Verifier Drift -- Runtime Path and Payload Assumptions

**Date:** 2026-04-13  
**Duration:** 1 full-sweep debugging cycle  
**Severity:** HIGH  
**Status:** FIXED (Guarded)

### Problem

The maintained whole-system verifier failed even though the live Elefante MCP surface was healthy, because the harness made stale assumptions about where dashboard refresh writes its snapshot and how large a single JSON-RPC line can be.

### Symptom

Two failures surfaced in sequence during `scripts/verify/verify_e2e_tests.py --with-dashboard-open`:

```text
[FAIL] DashboardOpen refresh writes snapshot and reports ready state
```

and after that was fixed:

```text
[FAIL] Harness execution -- Separator is found, but chunk is longer than limit
```

The first looked like a dashboard bug. The second looked like a generic transport failure. Neither was the actual product defect.

### Root Cause

The self-protocol drifted from the live runtime contract in two places:

1. The optional dashboard phase checked only `temp_data_dir / "dashboard_snapshot.json"`, but `src.mcp.server` refresh writes through module-level `DATA_DIR`, which is derived from `HOME`, so the actual snapshot landed under `temp_home/.elefante/data/dashboard_snapshot.json`.
2. The harness MCP client used asyncio's default subprocess stream limit, which is too small for large one-line JSON-RPC responses. `elefante-ContextGet` can legitimately exceed that limit.

In both cases, the verifier encoded a convenience assumption instead of following the current runtime behavior.

### Solution

Hardened the verifier to match the live contract:

```python
STREAM_LIMIT_BYTES = 1024 * 1024

self.process = await asyncio.create_subprocess_exec(
     ...,
     limit=STREAM_LIMIT_BYTES,
)
```

```python
candidate_snapshot_paths = [
     temp_home / ".elefante" / "data" / "dashboard_snapshot.json",
     temp_data_dir / "dashboard_snapshot.json",
]
snapshot_path = next((path for path in candidate_snapshot_paths if path.exists()), candidate_snapshot_paths[0])
```

This keeps the self-protocol aligned with the actual dashboard refresh path and the actual size of live MCP tool payloads.

**Files Changed:** `scripts/verify/verify_e2e_tests.py`, `tests/test_developer_routing.py`, `docs/debug/self-elefante-protocol.md`

### Proof

Run:

```bash
pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v
.venv/bin/python scripts/verify/verify_e2e_tests.py --with-dashboard-open
```

The guarded checks now prove:

1. The verifier accepts the home-derived dashboard snapshot path used by the live MCP server.
2. The verifier sizes the MCP subprocess stream for large `ContextGet` payloads.
3. The full 20-tool sweep completes successfully when port `8000` is free.

### Why This Took So Long

- A verifier failure is easy to misclassify as a product regression.
- The dashboard path bug looked real because the tool returned success while the assertion still failed.
- The stream-limit failure appeared only after the first verifier bug was removed, so it was masked until the sweep got deeper into the protocol.

### Lesson

> **A maintained verifier is part of the product confidence surface; if it assumes the wrong runtime path or payload shape, it becomes a false bug generator.**

---

## Issue #9: Self-Protocol Cold-Start Deadlock — `import sentence_transformers` Deadlocks in Worker Thread Under anyio + Piped stdio

**Date:** 2026-04-15  
**Duration:** 3 debugging cycles (timeout hypothesis → asyncio.to_thread fix → pre-load fix)  
**Severity:** HIGH  
**Status:** FIXED (guarded)

### Problem

The self-protocol harness (`scripts/verify/verify_e2e_tests.py`) reproducibly hangs at Phase 3. Every tool call that triggers `_get_orchestrator()` → `ensure_system_baseline()` → `add_memory()` → `generate_embedding()` → `_load_model()` never returns.

### Symptom

```text
===== PHASE 3: Baseline routing and system status =====
[FAIL] Harness execution -- [TimeoutError]
SELF-PROTOCOL: 5/6 checks passed, 1 FAILED
```

### Root Cause

**`from sentence_transformers import SentenceTransformer` (which imports torch) deadlocks when executed inside a worker thread** (`asyncio.to_thread()`) under an active anyio event loop with piped stdin/stdout/stderr (the MCP subprocess transport) on Windows + Python 3.11.

**Diagnostic trace** (raw `sys.stderr.write` probes):
```
chromadb_initialized                              ← OK
find_by_title → asyncio.to_thread(collection.get) ← OK (2 calls, <20ms each)
PROBE_D: about to generate_embedding
PROBE_E: about to asyncio.to_thread(_load_model)
PROBE_F: _load_sentence_transformer entered
PROBE_F: about to import SentenceTransformer
──── HANG ──── (never returns)
```

The import completes in ~3s when run directly, in a terminal subprocess, or via `asyncio.run()` in-process. It ONLY deadlocks when:
- Running in a **worker thread** (via `asyncio.to_thread()`)
- Inside a **subprocess with piped stdio** (MCP transport)
- Under an **anyio-managed event loop** (MCP library v1.23.1, anyio 4.13.0)

The exact mechanism is likely a GIL/DLL-loader interaction between torch's C extension loading and the ProactorEventLoop's I/O completion ports on Windows, but the observable proof is clear from the trace.

**Environment:**
- OS: Windows 10/11
- Python: 3.11.9, CPU-only (no CUDA)
- MCP library: 1.23.1 (anyio 4.13.0, asyncio backend)
- Embedding model: `thenlper/gte-base` via `sentence-transformers 2.7.0`

### Investigation Path (Failed Approaches)

1. **Approach #1: Increase timeout (90→180s).** Logic: maybe model loading was slow, not hung. **Failed:** hang is indefinite, not slow. Timeout increase doesn't fix a deadlock.

2. **Approach #2: Wrap `_load_model()` in `asyncio.to_thread()`.** Logic: blocking sync call on event loop starves anyio transport. **Failed:** the import itself deadlocks in the worker thread. Moving it OFF the event loop moved the deadlock to the thread.

3. **Approach #3 (SUCCESS): Pre-load model before event loop starts.** Logic: if the import deadlocks only under an active anyio loop with piped stdio, execute it before `asyncio.run()`. The import runs as plain synchronous Python — no threads, no event loop, no piped transport yet.

### Solution

**Pre-load the embedding model in the `__main__` block of `src/mcp/server.py`, before `asyncio.run(main())`.** This adds ~8-10s startup delay but makes `_load_model()` a no-op during runtime (model already loaded in singleton).

```python
# src/mcp/server.py, __main__ block
if __name__ == "__main__":
    from src.core.embeddings import get_embedding_service as _get_emb
    _get_emb()._load_model()       # sync, pre-event-loop (BUG-010)
    asyncio.run(main())
```

Additional defensive changes in `src/core/embeddings.py`:
- `generate_embeddings_batch()`: wraps `_load_model()` in `asyncio.to_thread()` as fallback
- `_generate_sentence_transformer_batch()`: uses `asyncio.to_thread()` instead of deprecated `loop.run_in_executor()`

### Verification

```bash
.venv/Scripts/python.exe scripts/verify/verify_e2e_tests.py
# Result: 45/45 PASS, 1 SKIP, 0 FAIL
```

### Why Approach #1 and #2 Failed

**Approach #1** assumed the issue was latency (slow model loading). The actual issue was a deadlock — the import never completes, regardless of timeout duration. Increasing a timeout cannot fix a deadlock.

**Approach #2** correctly identified that blocking the event loop was bad, but the fix moved the blocking operation to a worker thread, where the _import_ (not the model load) deadlocked due to Windows-specific thread/DLL-loader interactions. The hypothesis was directionally correct (don't block the event loop) but targeted the wrong layer (thread vs pre-event-loop).

### Lesson

> **When a blocking operation deadlocks in a thread under an event loop, moving it to a different thread doesn't help. Move it to a different PHASE of the process lifecycle — before the event loop starts. Differentiate "slow" from "hung": if a 180s timeout doesn't help, it's a deadlock, not latency.**

---

## Issue #11: JSON Export Is Not a Backup — Missing Import Path and Embeddings

**Date:** 2026-04-15
**Severity:** HIGH
**Status:** DOCUMENTED — `import_memories.py` to be built (v2.5.4)

### Problem

`export_memories.py --format json` produces a JSON file that looks like a backup but is not restorable. There is no `import_memories.py`. A user who exports to JSON, factory resets, and tries to restore from JSON will lose their brain with no recovery path.

### Symptom

User runs `python scripts/pipeline/export_memories.py --format json`, gets a file with all their memories, later discovers there is no script to re-import it into a fresh Elefante instance. The binary backup (`backup_elefante_data.py`) is the only real restore path, but this is not documented prominently.

### Root Cause (3 layers)

1. **No import counterpart**: `export_memories.py` was built for "offline analysis" (before/after surgical delete validation), not as a migration tool. No `import_memories.py` was ever written to complete the round trip.
2. **Embeddings are not in the export**: ChromaDB stores embeddings explicitly via `collection.add(..., embeddings=[memory.embedding])`. The embedding model is `thenlper/gte-base` (configured in `config.py`). The JSON export calls `collection.get(include=["metadatas", "documents"])` — embeddings are not in the `include` list and are NOT written to the file.
3. **ChromaDB has no named embedding function**: `get_or_create_collection()` is called without an `embedding_function` argument. This means ChromaDB's default (`all-MiniLM-L6-v2`) would be used if documents were upserted without providing embeddings. The two models are incompatible — mixing them silently corrupts semantic search results.

### Critical Dependency Discovered

> `thenlper/gte-base` embeddings are stored explicitly. Any import script **must** regenerate embeddings using `sentence_transformers.SentenceTransformer("thenlper/gte-base")` before calling `collection.upsert()`. Relying on ChromaDB's default embedding function is a silent corruption path.

### What Two Separate Persistence Paths Exist (and their limits)

| Mechanism | Format | Re-importable | Encrypted | Version-safe | Status |
|---|---|---|---|---|---|
| `backup_elefante_data.py` | Binary zip of `~/.elefante/data` | yes, via restore script | no, plaintext | warn, same schema only | EXISTS |
| `export_memories.py --format json` | JSON (content + metadata, no embeddings) | no, no import path | no, plaintext | yes, content-portable | EXISTS — BROKEN as backup |
| `import_memories.py` | Reads JSON export, regenerates embeddings | yes, after v2.5.4 | no, plaintext | yes, content-portable | TO BUILD |

### Solution

**Phase 1 (documentation):** Surface backup/restore as the primary persistence mechanism in the main `README.md` install flow and add a note to `export_memories.py` header that JSON is not a backup.

**Phase 2 (feature):** Build `scripts/pipeline/import_memories.py`:
- Reads JSON produced by `export_memories.py --format json`
- Regenerates embeddings using `thenlper/gte-base` (reads model name from config)
- Calls `collection.upsert()` with explicit embeddings
- Supports `--dry-run`, `--skip-existing` (by ID), and `--conflict` (`skip|overwrite|rename`) flags
- Does NOT go through the MCP orchestrator (same direct-ChromaDB pattern as export)

**Feasibility:** Confirmed YES. The JSON schema captures `id`, full `content` (not truncated), and all `metadata` fields. Embeddings are regenerable from content. `collection.upsert()` is idempotent on ID. Estimated ~120 lines.

### Lesson

> **A write-only export is not a backup. Every export format needs a documented import path or must be explicitly labeled as read-only analysis output. Never infer "exportable = restorable."**

---

## Issue #10: Elefante Cold-Start Trigger Gap — Instructions File Is Workspace-Scoped, Not System-Scoped

### Problem

Agent asks Elefante-relevant questions (preferences, past decisions, project state) and receives answers derived solely from training data or workspace file reads. No `elefante-MemorySearch` is called. No `[ELEFANTE] Searched:` stamp appears. The Elefante MCP server is running and registered correctly.

### Symptom

User asks: "what is the code?" (referring to Elefante). Agent reads README directly with its own file tools and answers without ever touching Elefante. Brain context is ignored. Directives and RELEVANT_CONTEXT are never injected because no Elefante tool was called to deliver them.

### Root Cause (3 layers)

1. **Instruction delivery is workspace-scoped**: VS Code Copilot loads `copilot-instructions.md` only from the **active workspace root's** `.github/` folder. `elefante/.github/copilot-instructions.md` only loads when `elefante/` is the workspace root. When the user works from a parent workspace (`BOB/`) or any subfolder, the file is invisible to the agent.
2. **Cold-start bootstrap gap**: Even with a BOB-level or user-level instructions file, the Elefante server-side directives (including `system-elefante-search-first`) are only injected *after* the first Elefante tool call. There is no delivery path for them before that first call.
3. **The two problems are orthogonal**: MCP registration scope (where the server is declared) is unrelated to instruction delivery scope (where the agent is told to use it). Elefante was already registered at user-level in `mcp.json` — moving the MCP config to a different scope would not have fixed the trigger gap.

### What Was Tried First (And Why It Was Insufficient)

- **Proposed fix**: Create `BOB/.github/copilot-instructions.md`. ARAA rejected this as insufficient — it only covers the case where `BOB/` is the workspace root. Opening any subfolder directly (`BOB/Projects/`, `BOB/SkillBot/`) regresses the bug.
- **ARAA verdict**: The fix must be system-scoped — injected globally regardless of which workspace root is active.

### Solution

**Two-layer fix:**

| Layer | Mechanism | Scope | What It Fixes |
|---|---|---|---|
| 1 — VS Code user-level | `settings.json` → `github.copilot.chat.codeGeneration.instructions` pointing to `elefante/.github/copilot-instructions.md` | Every workspace, every folder, every session | Cold-start trigger gap for VS Code Copilot globally |
| 2 — BOB workspace fallback | `BOB/.github/copilot-instructions.md` | BOB workspace root only | Backup if settings.json injection is ever cleared |

**Layer 1 settings.json entry:**
```json
"github.copilot.chat.codeGeneration.instructions": [
    {
        "file": "C:\\Users\\JaimeSubiabreCistern\\Documents\\Agentic\\BOB\\elefante\\.github\\copilot-instructions.md"
    }
]
```

**Why user-level settings.json is the right mechanism**: It is the only VS Code Copilot injection path that is truly workspace-agnostic. It loads for every workspace, every subfolder opened directly, and every new project without requiring a per-project file.

**Why not duplicate the constitution**: The BOB-level bootstrap should be minimal — just enough to trigger the first Elefante tool call. Once any tool fires, the server-side directives (including `system-elefante-search-first`) take over for the session.

### Verification

1. Open any workspace that is NOT `elefante/` (e.g., `BOB/Projects/`)
2. Ask a memory-relevant question
3. Confirm `[ELEFANTE] Searched:` stamp appears in the response
4. Confirm `RELEVANT_CONTEXT` is present in the answer if memories exist

No automated regression test exists for this — the failure mode is an absence of agent behavior, not a runtime exception. Verification is manual.

### Lesson

> **Instruction delivery and MCP registration are separate systems at separate layers. Fixing one does not fix the other. The correct scope for behavioral instructions is the broadest available scope — not the narrowest that works in the demo scenario. System-level = settings.json user injection, not workspace-level file presence.**

---

## The 5-Layer Protocol

### Overview

```
Layer 1: Protocol Checklist
         └── Reference document consulted before every response

Layer 2: Verification Triggers  
         └── Trigger words require immediate proof

Layer 3: Dual-Memory Protocol
         └── Query BOTH conversation AND Elefante before responding

Layer 4: Memory Compliance Verification
         └── Retrieved memories must be APPLIED, not just acknowledged

Layer 5: Action Verification (FORCED EXECUTION)
         └── STATE -> DO -> VERIFY in same response
```

### Layer 5 Detail (Most Critical)

```
STATE what will be done
     ↓
DO it immediately (same response)
     ↓
VERIFY it succeeded
     ↓
Show PROOF
```

**Anti-patterns to avoid:**
-  "I will move the files..." (future tense)
-  "These should be moved..." (conditional)
-  "Consider moving..." (suggestion)

**Correct pattern:**
-  "Moving files now: [command]. Result: [output]. Verified: [proof]"

---

## Verification Checklist

### Before Claiming ANY Code "Done"

```bash
# Phase 1: No Obvious Errors
grep -r "<<<<<<< HEAD" .  # No merge conflicts
grep -r "TODO:" . | head  # Review TODOs
grep -r "FIXME:" . | head  # Review FIXMEs

# Phase 2: Syntax Valid
python -m py_compile file.py

# Phase 3: Imports Work
python -c "from module import Class"

# Phase 4: Basic Execution
python -c "Class().method()"

# Phase 5: Real Data Test
# Run with actual user data
```

### Before Saying Any Trigger Word

| Word | Required Proof |
|------|----------------|
| "updated" | Show diff or new content |
| "created" | Show file exists |
| "fixed" | Show bug no longer occurs |
| "complete" | Show all requirements met |
| "ready" | Demonstrate working usage |
| "implemented" | Show code executing |
| "resolved" | Prove issue closed |

---

## Prevention Protocol

### Pre-Response Checklist

```
[ ] Searched Elefante for relevant context
[ ] Retrieved memories listed with IDs
[ ] Stated how response follows retrieved rules
[ ] If action needed: STATE -> DO -> VERIFY sequence
[ ] If claiming done: Show proof
[ ] If environment-dependent: Account for user differences
```

### When Debugging AI Failures

1. **Which gap?** Knowledge / Application / Execution
2. **Which layer failed?** 1-5
3. **What trigger word was misused?**
4. **What verification was skipped?**

### When User Says "It Doesn't Work"

1.  Don't say "It should work"
2.  Don't say "It worked for me"
3.  Ask what they see (exact output)
4.  Check environment differences
5.  Test in conditions matching theirs

---

## Appendix: Issue Template

```markdown
## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:**  OPEN |  IN PROGRESS |  FIXED |  DOCUMENTED

### Problem
[One sentence: what is broken]

### Symptom
[What the user sees / exact error message]

### Root Cause
[Technical explanation of WHY it broke]

### Solution
[Code changes or steps that fixed it]

### Why This Took So Long
[Honest reflection on methodology mistakes]

### Lesson
> [One-line takeaway in blockquote format]
```

---

*Last verified: 2025-12-05 | Protocol Version: 5-Layer v3.0 Final*
