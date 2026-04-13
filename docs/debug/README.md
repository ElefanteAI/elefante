# Debug Documentation Index

**Compendiums and pitfall reference for Elefante v2.3.1**

> **Last Updated:** 2026-04-13

---

## MANDATORY: Read This First

**Every debugging session starts here.** Check Known Issues below. If the error matches an open or recurring issue, follow the compendium link and run the verification command. Do not skip to source code.

```
Entry flow:  README.md (this file) → Known Issues → Compendium → Verification Commands → Test
Exit flow:   Fix → Test passes → Update compendium → Close issue here → dev-etiquette.md closure
```

---

## Known Issues & Development Priorities

Active bugs and recurring failure classes. Each links to its compendium post-mortem and test gate.

| ID | Issue | Status | Compendium | Verification Command | Recurrence |
| -- | ----- | ------ | ---------- | -------------------- | ---------- |
| BUG-001 | Kuzu SIGSEGV — QueryResult lifetime escapes GraphStore ownership | FIXED (guarded) | [ops-database #7](ops-database-compendium.md#issue-7-async-shutdown-race--queryresult-lifetime-leak) | `pytest tests/test_memory_persistence.py -k "graph_store_close or graph_store_raw_execute or live_mcp_server" -v` | 2x — fix now has 3 regression tests + runtime citation |
| BUG-002 | Kuzu database lock contention (multi-process) | FIXED (documented) | [ops-database #2](ops-database-compendium.md#issue-2-database-lock-persistence) | `pytest tests/test_memory_persistence.py -k "config_paths_exist" -v` | 1x |
| BUG-003 | Dashboard blank on first launch (race condition) | FIXED | [ops-dashboard #8](ops-dashboard-compendium.md#issue-8-persistent-blank-dashboard-on-first-launch) | `python scripts/verify/verify_health.py` | 1x |
| BUG-004 | Dashboard scores stuck at 100 | FIXED | [ops-dashboard #9](ops-dashboard-compendium.md#issue-9-all-dashboard-scores-stuck-at-100) | `pytest tests/test_dashboard_serializer.py -v` | 1x |
| BUG-005 | Factory reset safety (destructive operation) | TESTED | [ops-database](ops-database-compendium.md) | `pytest tests/test_factory_reset.py -v` | 0x — 10 safety tests cover dry-run, gates, backup |
| BUG-006 | Agent entry point bypass — skips docs, guesses fix | OPEN | [ops-ai-behavior #6](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure) | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Structural — mitigated by runtime citations |
| BUG-007 | Developer routing drift — stale paths and ritual changelog reads in active process guidance | FIXED (guarded) | [ops-ai-behavior #7](ops-ai-behavior-compendium.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads) | `pytest tests/test_developer_routing.py -v` | 1x — guarded by source-path regression test + live memory amendments |

### How to Use This Table

- **FIXED (guarded)**: Fix is in place AND has regression tests. If the test still passes, the fix holds. If it fails, the regression is real.
- **FIXED (documented)**: Fix is in place, recovery procedure documented, but no automated regression guard yet.
- **TESTED**: Feature works and has test coverage. No known bug, but the test exists because the risk is high.
- **OPEN**: Known weakness, mitigation in place, but not fully resolved.

### Adding a New Issue

1. Assign next `BUG-NNN` ID
2. Document full post-mortem in the relevant `ops-*-compendium.md`
3. Write or identify the test that proves the fix
4. Add the row to this table
5. If the error surfaces in Python: add a runtime citation pointing to the compendium entry (see `dev-developer-agent.md` Knowledge Embedding Protocol #2)

## Structure

```
docs/debug/
├── README.md                   <- You are here (index)
├── dev-developer-agent.md          <- AI agent protocol for developing Elefante
└── *-compendium.md             <- Detailed post-mortems by domain
```

Repository debugging uses existing maintained verification first:

- **[`scripts/verify/`](../../scripts/verify/)** for purposeful validation selected by the Developer Agent Protocol
- **[`tests/README.md`](../../tests/README.md)** for targeted pre-cooked pytest coverage that should be preferred over ad hoc scratch repro scripts
- **[`scripts/debug/`](../../scripts/debug/)** for last-resort interventions only when a compendium explicitly calls for them

---

## Domain Compendiums (Detailed Post-Mortems)

Each compendium follows the **Unified Post-Mortem Structure**:
Problem → Symptom → Root Cause → Solution → Lesson

| Domain       | Compendium                                               |
| ------------ | -------------------------------------------------------- |
| Dashboard    | [ops-dashboard-compendium.md](ops-dashboard-compendium.md)       |
| Database     | [ops-database-compendium.md](ops-database-compendium.md)         |
| Installation | [ops-installation-compendium.md](ops-installation-compendium.md) |
| Memory       | [ops-memory-compendium.md](ops-memory-compendium.md)             |
| AI Behavior  | [ops-ai-behavior-compendium.md](ops-ai-behavior-compendium.md)   |

### Developer Agent Protocol

[`dev-developer-agent.md`](dev-developer-agent.md) — Routing protocol for AI agents developing Elefante itself. It points to the embedded development process reference, developer etiquette, the correct compendium, and the correct verification script for the failure mode. Not injected into normal user sessions.

---

## How to Use

| Task            | Action                                                                        |
| --------------- | ----------------------------------------------------------------------------- |
| **First step**  | Check the Known Issues table above — if the error matches, run the verification command |
| **Deep dive**   | Open the linked `*-compendium.md` → read the Verification Commands block → run the test |
| **Validate**    | Use `dev-developer-agent.md` plus [`tests/README.md`](../../tests/README.md) to choose the smallest existing verifier |
| **Intervene**   | Use `scripts/debug/` only when the compendium says verification is insufficient |
| **New issue**   | Assign next BUG-NNN → post-mortem in compendium → test → add row to Known Issues |

---

## File Inventory

```
docs/debug/
├── README.md
├── dev-developer-agent.md
├── ops-ai-behavior-compendium.md
├── ops-dashboard-compendium.md
├── ops-database-compendium.md
├── ops-installation-compendium.md
└── ops-memory-compendium.md
```

**Total: 7 files (flat structure)**

---

_Last verified: 2026-04-13 | Elefante v2.3.1_
