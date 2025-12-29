# AI Behavior Debug Compendium

> **Domain:** AI Protocol Failures, Self-Analysis & Methodology  
> **Last Updated:** 2025-12-11  
> **Total Issues Documented:** 6  
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

---

## Table of Contents

- [Issue #1: Analysis-Action Gap](#issue-1-analysis-action-gap)
- [Issue #2: Premature Completion Claims](#issue-2-premature-completion-claims)
- [Issue #3: Code Mode MCP Limitation](#issue-3-code-mode-mcp-limitation)
- [Issue #4: Knowledge Not Applied](#issue-4-knowledge-not-applied)
- [Issue #5: Environment Assumption Failures](#issue-5-environment-assumption-failures)
- [Issue #6: Passive Protocol Enforcement Failure](#issue-6-passive-protocol-enforcement-failure)  CRITICAL
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
**Status:**  DOCUMENTED (Platform Limitation)

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
Memory stored: "NEVER delete files, move to ARCHIVE" (importance: 10)

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
Retrieved: Memory e752a57b (importance 10): "Never delete, move to ARCHIVE"
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
**Status:**  OPEN (Architectural Problem)

### Problem

Elefante has comprehensive protocols (Inception Memory, Tool Descriptions, Documentation) but agents ignore them because ALL enforcement mechanisms are PASSIVE.

### Symptom

```
EXISTING PROTOCOL (Inception Memory, importance=10):
"PRIME DIRECTIVE: MEMORY FIRST
1. Check Context: Before answering, ALWAYS search memory"

EXISTING TOOL DESCRIPTION (elefanteMemorySearch):
"AUTOMATIC USAGE RULES:
1. ALWAYS call this tool when user asks open-ended questions"

EXISTING DOCUMENTATION:
- pitfall-index.md (searchable pitfalls + pre-action protocol)
- Neural Registers (all laws)

AGENT BEHAVIOR:
- Attempted 15+ installation methods blindly
- Never searched Elefante for "installation pitfalls"
- Never consulted python-version-requirements.md
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
| Pitfall Index | Passive | Agent must search it |

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

### Solution Options (OPEN - Not Resolved)

**Option A: Gate Tool Architecture**

```python
# Tools refuse to work without clearance
@server.tool()
async def clearForAction(task_type: str) -> dict:
    """MUST call before any action. Returns relevant pitfalls."""
    pitfalls = await search_memories(f"{task_type} pitfalls")
    return {"cleared": True, "warnings": pitfalls}

# Other tools check clearance
@server.tool()  
async def elefanteMemoryAdd(content: str, clearance_token: str = None):
    if not valid_clearance(clearance_token):
        return {"error": "Must call clearForAction first"}
```

**Option B: User Checkpoint Mode**

```
Agent: "I need to install dependencies"

System (auto-triggered):
┌─────────────────────────────────────────────────────┐
│  ELEFANTE CHECKPOINT                              │
│ Task: INSTALLATION                                  │
│ Found 3 warnings:                                   │
│ • Python 3.11 MANDATORY                             │
│ • Do NOT pre-create kuzu_db directory              │
│ Approve? [Y/N]                                      │
└─────────────────────────────────────────────────────┘
```

**Option C: IDE-Level Enforcement**

- VS Code / Cursor rules file
- Custom mode with forced memory consultation
- Different architectural layer

### Why This Matters

This is the **ROOT CAUSE** of repeated failures:

- Installation nightmare (15+ attempts, answer was in docs)
- Schema mismatches (documented but not consulted)
- Every "lesson learned" that gets learned again

**Elefante stores knowledge. Nothing forces agents to USE it.**

### Lesson

> **Passive protocols cannot enforce compliance. Structural enforcement (tools that refuse to work) or human gates (user approval) are required.**

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
