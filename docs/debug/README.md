# Debug Documentation Index

**Compendiums and pitfall reference for Elefante v2.5.0**

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
| BUG-002 | Kuzu database lock contention (multi-process) | FIXED (guarded) | [ops-database #2](ops-database-compendium.md#issue-2-database-lock-persistence) | `pytest tests/test_memory_persistence.py -k "TestKuzuLockContract" -v` | 1x — guarded by fresh-path contract, cross-process citation, snapshot isolation, and active-doc sync tests |
| BUG-003 | Dashboard blank on first launch (race condition) | FIXED (guarded) | [ops-dashboard #8](ops-dashboard-compendium.md#issue-8-persistent-blank-dashboard-on-first-launch) | `pytest tests/test_dashboard_serializer.py -k "dashboard" -v` | 1x — guarded by readiness wait, forced refresh restart, and frontend retry/backoff checks |
| BUG-004 | Dashboard scores stuck at 100 | FIXED | [ops-dashboard #9](ops-dashboard-compendium.md#issue-9-all-dashboard-scores-stuck-at-100) | `pytest tests/test_dashboard_serializer.py -v` | 1x |
| BUG-005 | Factory reset safety (destructive operation) | TESTED | [ops-database](ops-database-compendium.md) | `pytest tests/test_factory_reset.py -v` | 0x — 10 safety tests cover dry-run, gates, backup |
| BUG-006 | Agent entry point bypass — skips docs, guesses fix | FIXED (guarded) | [ops-ai-behavior #6](ops-ai-behavior-compendium.md#issue-6-passive-protocol-enforcement-failure) | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | 1x — guarded by first-response and first-error entrypoint injection |
| BUG-007 | Developer routing drift — stale paths and ritual changelog reads in active process guidance | FIXED (guarded) | [ops-ai-behavior #7](ops-ai-behavior-compendium.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads) | `pytest tests/test_developer_routing.py -v` | 1x — guarded by source-path regression test + live memory amendments |
| BUG-008 | Graph/session schema contract drift — GraphConnect injected unsupported relationship properties and SessionsList assumed synthetic session columns | FIXED (guarded) | [ops-database #8](ops-database-compendium.md#issue-8-graph-and-session-schema-contract-drift) | `pytest tests/test_memory_persistence.py -k "TestGraphToolContract" -v` | 1x — guarded by rel-table execution coverage and SessionsList source-contract checks |
| BUG-009 | Self-protocol verifier drift — stale snapshot-path assumptions and default line limits broke the maintained whole-system proof | FIXED (guarded) | [ops-ai-behavior #8](ops-ai-behavior-compendium.md#issue-8-self-protocol-verifier-drift--runtime-path-and-payload-assumptions) | `pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v` | 1x — guarded by source-level checks for dashboard snapshot path resolution and large-payload stream sizing |

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
├── best_practices.md           <- Distilled cross-bug feedback loop learnings
├── dev-developer-agent.md      <- AI agent protocol for developing Elefante
├── self-elefante-protocol.md   <- Whole-system MCP proof in isolated temp HOME/data
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

### Feedback Loop Ledger

[`best_practices.md`](best_practices.md) — Distilled cross-bug learnings that connect the Known Issues index, compendium post-mortems, maintained tests, and the live developer workflow. Use it to keep reusable development rules online instead of buried in one-off conversations.

### Whole-System Verification

[`self-elefante-protocol.md`](self-elefante-protocol.md) — Authoritative whole-system proof for the live MCP server. Use this when the question is "is Elefante actually running end-to-end?" rather than "did one narrow regression stay fixed?"

---

## How to Use

| Task            | Action                                                                        |
| --------------- | ----------------------------------------------------------------------------- |
| **First step**  | Check the Known Issues table above — if the error matches, run the verification command |
| **Deep dive**   | Open the linked `*-compendium.md` → read the Verification Commands block → run the test |
| **Validate**    | Use `dev-developer-agent.md` plus [`tests/README.md`](../../tests/README.md) to choose the smallest existing verifier |
| **Whole-system proof** | Run `./.venv/bin/python scripts/verify/verify_e2e_tests.py` and use [`self-elefante-protocol.md`](self-elefante-protocol.md) to interpret coverage and exclusions |
| **Intervene**   | Use `scripts/debug/` only when the compendium says verification is insufficient |
| **New issue**   | Assign next BUG-NNN → post-mortem in compendium → test → add row to Known Issues |

---

## File Inventory

```
docs/debug/
├── README.md
├── best_practices.md
├── dev-developer-agent.md
├── self-elefante-protocol.md
├── ops-ai-behavior-compendium.md
├── ops-dashboard-compendium.md
├── ops-database-compendium.md
├── ops-installation-compendium.md
└── ops-memory-compendium.md
```

**Total: 9 files (flat structure)**

---

_Last verified: 2026-04-13 | Elefante v2.5.0_
