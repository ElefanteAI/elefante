# AI Behavior Debug Compendium

> **Domain:** AI Protocol Failures, Self-Analysis & Methodology  
> **Last Updated:** 2026-04-13  
> **Total Issues Documented:** 8  
> **Status:** Production Reference  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

##  CRITICAL LAWS (Extracted from Pain)

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

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the protocol enforcement is intact.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #2 Premature completion | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Real MCP server completes full lifecycle |
| #6 Protocol enforcement | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | First successful and failing tool responses inject exact entry routing, directives, and maintained verification surfaces |
| #7 Developer routing drift | `pytest tests/test_developer_routing.py -v` | Active process guidance points to current paths and tool-count contract |
| #8 Self-protocol verifier drift | `pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v` | Whole-system verifier tracks the live dashboard snapshot path contract and sizes the MCP client for large tool payloads |
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
