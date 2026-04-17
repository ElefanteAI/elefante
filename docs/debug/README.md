# Debug Documentation Index

**Compendiums and pitfall reference for Elefante v2.9.3**

> **Last Updated:** 2026-04-17

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
| BUG-010 | Self-protocol cold-start deadlock — `from sentence_transformers import SentenceTransformer` hangs when executed in a worker thread under an active anyio event loop with piped stdio on Windows + Python 3.11 | FIXED (guarded) [WARN] Windows/Python 3.11/CPU only — untested on Linux, macOS, Python 3.12 | [ops-ai-behavior #9](ops-ai-behavior-compendium.md#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio) | `.venv/Scripts/python.exe scripts/verify/verify_e2e_tests.py` | 1x — guarded by pre-loading embedding model before event loop starts in server.py __main__ |
| BUG-011 | MemoryAdd silent IGNORE — test-memory guard returns opaque "Memory filtered by Intelligence Pipeline" with no rejection reason, overly broad heuristic blocks legitimate tags | FIXED (guarded) | [ops-memory #10](ops-memory-compendium.md#issue-10-memoryadd-silent-ignore--opaque-test-memory-guard-rejection) | `pytest tests/test_memory_guard.py -v` | 2x — guarded by `rejection_reason` field in IGNORE response body |
| BUG-012 | Elefante cold-start trigger gap — agent never calls `elefante-MemorySearch` when working outside the `elefante/` workspace because `.github/copilot-instructions.md` is workspace-scoped and only loads when `elefante/` is the VS Code workspace root | FIXED (partial) [WARN] VS Code Copilot only — cross-client fix (Cursor, Windsurf) requires client-specific bootstrap files | [ops-ai-behavior #10](ops-ai-behavior-compendium.md#issue-10-elefante-cold-start-trigger-gap--instructions-file-is-workspace-scoped-not-system-scoped) | Manual: open a workspace outside `elefante/`, ask a memory-relevant question, confirm `[ELEFANTE] Searched:` stamp appears in response | 1x — guarded by BOB-level `copilot-instructions.md` bootstrap + system-level `settings.json` user instruction injection |
| GAP-013 | JSON export is not a backup — `export_memories.py --format json` produces a read-only analysis file with no import path. Embeddings are excluded (stored explicitly via `thenlper/gte-base`; import must regenerate them). Using ChromaDB default embedding on upsert would silently corrupt semantic search. No round-trip until `import_memories.py` ships. | DOCUMENTED — `import_memories.py` planned for next release | [ops-ai-behavior #11](ops-ai-behavior-compendium.md#issue-11-json-export-is-not-a-backup--missing-import-path-and-embeddings) | Manual: confirm `import_memories.py` exists and round-trip test passes | 0x — first discovery |
| BUG-014 | CI binary build failure — `build-binaries.yml` had no Node.js/npm step so `src/dashboard/ui/dist/` (gitignored) did not exist in CI. Additionally `elefante.spec` referenced `src/dashboard/ui/build` but Vite outputs to `dist`. All three matrix jobs failed on first tag push (v2.5.3). | FIXED — v2.5.4 | [ops-installation #8](ops-installation-compendium.md#issue-8-ci-binary-build--missing-frontend-build-step-and-wrong-vite-output-directory) | `Select-String -Path elefante.spec -Pattern "dashboard/ui"` → must show `dist`; `Select-String -Path .github/workflows/build-binaries.yml -Pattern "setup-node\|npm ci"` → must show both | 0x — first tag push |
| BUG-015 | GitHub Release publish failure — the `v2.6.0` release object was created and macOS/Windows assets uploaded, but the Linux artifact was `4,021,041,080` bytes. GitHub release assets must be under `2 GiB`, so `Create GitHub Release` failed while attaching the Linux zip. | FIXED — v2.7.1 (confirmed: v2.7.1, v2.6.0, v2.5.4 all published with 4 assets on GitHub Releases) | [ops-installation #9](ops-installation-compendium.md#issue-9-github-release-publish-failure-after-successful-matrix-builds) | `pytest tests/test_release_pipeline.py -v` | 1x — v2.6.0 publish failure |
| BUG-016 | Domain signal value-space disjunction — `analyze_query()` infers `None`/`"work"`/`"personal"`/`"project:elefante"` but memories default to `DomainType.REFERENCE`. The value spaces never intersect. 15% of composite weight produces 0.5 (neutral) or 0.0 (penalty), never 1.0. Domain actively degrades ranking vs pure vector. | FIXED — v2.7.0 | [ops-memory #11](ops-memory-compendium.md#issue-11-domain-signal-value-space-disjunction--15-of-scoring-weight-is-dysfunctional) | `pytest tests/test_autonomous_coactivation.py -v` | 0x — first discovery via ARAA analysis |
| BUG-017 | Unconditional spec override dominates all queries — `+0.30` boost applied to all specification/directive memories regardless of query intent. Three different real queries all returned the same top 4 specification memories. Non-spec memories mathematically cannot outrank specs. | FIXED — v2.7.0 | [ops-memory #12](ops-memory-compendium.md#issue-12-unconditional-spec-override-dominates-all-queries) | `pytest tests/test_autonomous_coactivation.py -v` | 0x — first discovery via ARAA analysis |
| BUG-018 | Co-activation cold-start — `_session_retrieval_history` resets to `[]` on every server restart. First query of every session gets 0.0 co-activation. Kuzu `CO_ACTIVATED` edges exist but the read path requires IDs that are lost on restart. | FIXED — v2.7.0 | [ops-memory #13](ops-memory-compendium.md#issue-13-co-activation-cold-start--session-history-lost-on-restart) | Manual: restart MCP server, run `elefante-MemorySearch`, check if co-activation signal > 0 for any result | 0x — first discovery via source trace |
| BUG-019 | DMG GUI installer .app broken — `installer_gui.py` corrupted by overlapping multi-edit patches (dark-to-light-mode rewrite). Fatal `SyntaxError` at line 173, undefined variables (`style`, bare `C`), duplicate widget constructors, nonexistent palette keys. .app exits code 1, no GUI window appears. File was never committed so no git recovery possible. | FIXED — v2.8.1 | [ops-installation #10](ops-installation-compendium.md#issue-10-dmg-gui-installer-app-broken---corrupted-multi-edit-merge) | `python3 -c "import py_compile; py_compile.compile('scripts/ci/installer_gui.py', doraise=True)"` + DMG launch test | 0x — first discovery, regression from same session |
| BUG-020 | DMG installer customer surface broken — the `.app` launches and internal controls exist, but the rendered macOS window remains visually broken and unacceptable as a customer installer experience. The root fix is to replace Tk as the primary macOS surface with native AppKit and verify by screenshot, not just process liveness. | FIXED (guarded) — v2.9.0 | [ops-installation #11](ops-installation-compendium.md#issue-11-dmg-installer-customer-surface-broken---tk-aqua-paint-failure) | `pytest tests/test_installer_gui.py -v` + `swiftc -parse-as-library -O scripts/ci/installer_app.swift -o /tmp/elefante-installer-native-test`; then Screenshot first → native compile → install smoke; widget-tree inspection only if screenshot fails (manual packaged-artifact screenshot remains authoritative) | 0x — first customer-experience audit |
| BUG-021 | Installer seed-memory collision with test-memory guard — every fresh install failed at stage 3 (Database Initialization) because `init_databases.py::inject_seed_memory` submitted `tags=["seed", "test", "passcode"]` and the orchestrator guard (BUG-011) does exact-match on tag `"test"` to block E2E artifacts. The guard rejected the installer's own seed, the install reported FAILED, and no regression test caught it because no pytest exercised the positive (pass) path. | FIXED (guarded) — v2.9.1 | [ops-installation #12](ops-installation-compendium.md#issue-12-installer-seed-memory-collision-with-test-memory-guard) | `pytest tests/test_install_setup.py -v` (guards the seed payload against every guard condition) | 1x — first full customer-experience audit |
| BUG-023 | Installer reuse mode assumed every valid `.venv` already had `pip`. A fresh `uv`-created environment reached Step 2 with a working Python 3.11 interpreter but failed immediately on `python -m pip` with `No module named pip`. | FIXED (guarded) — unreleased | [ops-installation #13](ops-installation-compendium.md#issue-13-installer-reuse-mode-fails-when-pip-is-missing-from-venv) | `pytest tests/test_install_setup.py -k "bootstraps_pip_when_missing" -v` | 1x — first fresh-environment audit after Homebrew Python removal |
| BUG-024 | Installer bundle build walks local `.venv.*` backups — `build_installer_bundle.py` excluded only exact `.venv`, so a recovered workspace with `.venv.broken.<timestamp>` tried to package broken interpreter symlinks, crashed with `FileNotFoundError`, and left stale `dist` artifacts behind. | FIXED (guarded) — unreleased | [ops-installation #14](ops-installation-compendium.md#issue-14-installer-bundle-build-walks-local-venv-backups-and-broken-symlinks) | `pytest tests/test_installer_bundle.py -k "venv_backups" -v` | 1x — first post-recovery bundle rebuild |
| BUG-022 | ChromaDB `query()` with `where` fails on production collection — `collection.query(where=...)` raises `InternalError: Error finding id` on ChromaDB 1.3.5 when the collection has 400+ memories. Caused MemoryAdd to fail completely for preference memory type. | FIXED (guarded) — v2.9.0 | [ops-memory #14](ops-memory-compendium.md#issue-14-chromadb-query-with-where-filter-fails-on-production-collection) | Run `elefante-MemoryAdd` with `memory_type="preference"` and confirm `success: true` | 0x — first discovery |

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

_Last verified: 2026-04-15 | Elefante v2.9.3_
