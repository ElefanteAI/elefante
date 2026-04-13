# Spec-Driven Development (SDD) Protocol for Elefante Contributors

> [!IMPORTANT]
> **This file is HUMAN REFERENCE ONLY.**  
> Living enforcement is inside Elefante as **DIRECTIVES** (6 SDD gates, injected unconditionally into every tool response) + **SPECIFICATION memories** (authority=1.0, zero decay) + **pre-commit hook** (`.git/hooks/pre-commit` — mechanical Gate 4).  
> See the Gatekeeper & Oracle pattern in `docs/technical/spec-architecture.md` (section 2: The Native SDD Workflow).

**Version**: 2.2.3  
**Status**: Reference document — enforcement is native  
**Last Updated**: 2026-03-20

---

## What This Is

SDD is the development methodology for Elefante itself. It enforces the same principles Elefante enforces on AI agents — source-first grounding, gate-ordered verification, zero tolerance for drift — applied to the act of building Elefante.

> If Elefante prevents agents from hallucinating architecture decisions,  
> then SDD prevents contributors from hallucinating patches.

The core discipline:

1. **Source-First** — Verify against the actual file before touching anything
2. **Gate-Ordered** — Each phase must pass before the next begins. No skipping.
3. **Leakage-Scanned** — Every surface that could break must be explicitly checked
4. **Simulator-Validated** — No patch is accepted without a verifiable test result
5. **Minimal** — Surgical changes only. One fix, one CHANGELOG entry.

---

## The Five Gates (Run in Exact Order)

---

### Gate 0: Source-First (MANDATORY — Before Touching Any File)

**You are forbidden from working from memory of a previous session.**

Before any change:

1. **Read the actual source file.** Not the docs about it — the file itself.
3. **Read the relevant section of `CHANGELOG.md`** to understand what was already decided.

If your memory of the file contradicts what you read: **the file wins. Always.**

**Verdict rule**: Any mismatch between recalled state and actual file state = **STOP**. Re-ground. Then proceed.

---

### Gate 1: Spec Integrity

Every change must trace back to a documented requirement. The accepted spec sources are, in order of authority:

| Authority Level | Source | Decay? |
|----------------|--------|--------|
| **Immutable** | `docs/planning/spec-vision.md` — The Four Laws | Never |
| **Immutable** | `docs/technical/spec-architecture.md` — Architecture contracts | Never |
| **High** | `docs/technical/spec-tools.md` — MCP tool schema contracts | On version bump |
| **High** | `docs/planning/spec-vision.md` — Vision and ideas backlog | On version bump |
| **Reference** | `CHANGELOG.md` — Decisions already made and shipped | Historical |

**"I think this would be better"** is not a spec.  
A spec is: documented, version-stamped, traceable to one of the sources above.

If you are proposing a new behavior not covered by any spec: **write the spec first**. Get it into `docs/planning/spec-vision.md` before writing code.

---

### Gate 2: Leakage Surface Scan

For every proposed change, scan ALL of the following surfaces. Any positive hit must be addressed before proceeding.

| Surface | What to Check |
|---------|--------------|
| **MCP response format** | Does this change affect `_CONTEXT_SKIP_TOOLS`, `GATED_TOOLS`, or the Tool Response Contract (`MANDATORY_PROTOCOLS_READ_THIS_FIRST` / `DIRECTIVES` / `RELEVANT_CONTEXT`)? |
| **ChromaDB write/read roundtrip** | If a memory field is added or changed: is it in BOTH the write path (`add_memory()`) AND the read path (`_reconstruct_memory()`)? Missing from either = always returns default. |
| **Kuzu schema/DML split** | Any new property name: test `CREATE NODE TABLE (...)` AND `CREATE (entity {...})` in the same test. Schema-valid names can be Cypher-invalid. |
| **stdout pollution** | Does any new code `print()` anywhere reachable from the MCP server? All logging MUST go to `sys.stderr`. One `print()` on stdout = corrupted JSON-RPC stream = dead connection. |
| **Compliance Gate state machine** | Does the change touch `_compliance_state`, `GATED_TOOLS`, or any handler that calls `_check_compliance_gate()`? |
| **Dashboard snapshot contract** | Dashboard reads from `snapshot.json`, not live DB. If you add a field, update `scripts/update_dashboard_data.py` AND `src/dashboard/server.py` AND the TypeScript types. |
| **Co-activation history** | If a memory is deleted or updated, is its UUID purged from `_session_retrieval_history` before `record_coactivation()` can reference it? |
| **Documentation links** | Before moving or archiving ANY file: `grep -r "filename" docs/` — update ALL inbound links first. Ghost links persist for weeks. |

---

### Gate 3: Numeric and Logic Verification

**Never quote a formula from docs. Run the actual calculation.**

Critical formulas to verify from `src/models/memory.py` directly (not this document):

```python
# Behavioral Relevance Score
relevance = 0.5 * recency * freshness * reinforcement

recency       = exp(-decay_rate * days_since_created)
freshness     = exp(-0.02 * days_since_accessed)
reinforcement = 1.0 + (reinforcement_factor * log(access_count + 1))
```

```python
# Cognitive Retrieval Composite (src/core/retrieval.py)
composite_score = (
    0.30 * vector_score +
    0.20 * concept_score +
    0.15 * domain_score +
    0.15 * coactivation_score +
    0.10 * authority_score +
    0.10 * temporal_score
)
```

**If any number in your change touches these formulas**: run the math with concrete test values. Does the output match the documented expected behavior? If the doc and the code disagree: **the code is truth. Update the doc.**

---

### Gate 4: Simulator Gate (NON-NEGOTIABLE)

**No patch is accepted without a verifiable test result. "It looks correct" is not a result.**

Run in order:

```bash
# 1. System health check
.venv/bin/python scripts/health_check.py

# 2. MCP handshake verification (proves the server actually responds)
.venv/bin/python scripts/verify_mcp_handshake.py

# 3. If memory storage/retrieval path touched: round-trip test
#    Store a memory → retrieve it → verify all changed fields survived
ELEFANTE_ALLOW_TEST_MEMORIES=1 .venv/bin/python -m pytest tests/ -k "your_test"
```

**Required outcomes**:

| Check | Required |
|-------|----------|
| `health_check.py` | Exit code 0, no CRITICAL warnings |
| MCP handshake | `"tools"` list returned, all 21 tools present |
| Round-trip test | Changed fields present and correct in retrieved memory |

Any failure → fix, then re-run from Gate 2. Do not skip back to Gate 4 directly.

---

### Gate 5: Output Discipline

Before committing:

- [ ] **Minimal patch** — No unrelated refactors bundled in. One problem, one fix.
- [ ] **CHANGELOG.md entry written** — `### The Problem Solved` + `### The Solution` + `### Changes` format
- [ ] **Version bumped** using `scripts/version_counsel.py` — never edit version strings by hand
- [ ] **All linked docs updated** — if you changed a tool signature, update `docs/technical/spec-tools.md`
- [ ] **`grep -r "filename" docs/`** — if you moved or renamed any file, all links resolved

---

## Severity Scale

| Severity | Meaning | Action |
|----------|---------|--------|
| 🔴 **CRITICAL** | Wrong behavior, spec violation, leakage surface hit, stdout pollution | **Stop. Do not proceed. Fix first.** |
| 🟠 **HIGH** | Simulator fails, missing roundtrip update, undocumented change | Fix before merging |
| 🟡 **MEDIUM** | Documentation drift, naming inconsistency, missing test | Fix in same PR |
| ✅ **CLEAN** | All gates passed, simulator verified, CHANGELOG written | Ship |

**One CRITICAL = blocked.** Not noted. Not flagged for later. Blocked.

---

## Anti-Hallucination Rules

These are non-negotiable:

1. **Never assume a file's content** — Read it. Every time.
2. **Never copy a number from docs into code** — Verify from `src/` source directly.
3. **Never assume a previous patch is still applied** — Re-read the file to confirm.
4. **Never assume a test passed because it passed before** — Re-run it.
5. **If you cannot verify a value by running the exact logic yourself, flag it CRITICAL and stop.**

---

## The Mapping to Elefante's Own Design

Elefante enforces these same principles on agents using it:

| SDD Gate | Elefante Equivalent |
|----------|-------------------|
| Gate 0: Source-First | Law of Absolute Grounding — if not in Brain/Workspace, UNKNOWN |
| Gate 1: Spec Integrity | `SPECIFICATION` memory type with authority=1.0 — immutable oracle |
| Gate 3: Numeric Verification | Law of Compliance — verify before writing, not after |
| Gate 4: Simulator Gate | Compliance Gate — write is blocked until search is proven real |
| Gate 5: Output Discipline | Contributing standards + `bump_version.py` versioning contract |

Elefante was built to give agents this discipline. SDD is that discipline applied to building Elefante itself.

---

## Quick Reference Card

```
Before ANY change:
  1. Read the actual file (not memory of it)

Before writing code:
  3. Trace your change to a spec source
  4. Scan ALL leakage surfaces (Gate 2 table)
  5. Verify any formula with actual math

Before committing:
  6. health_check.py → exit 0
  7. verify_mcp_handshake.py → 21 tools listed
  8. Round-trip test if memory path touched
  9. CHANGELOG entry written
 10. version_counsel.py run
```

---

*"One CRITICAL failure blocks the entire patch. Always."*

---

**Related docs**  
- [`docs/planning/spec-vision.md`](../planning/spec-vision.md) — The Four Laws  
- [`docs/technical/dev-etiquette.md`](dev-etiquette.md) — Code standards  
- [`CONTRIBUTING.md`](../../CONTRIBUTING.md) — Versioning and PR workflow
