# ISSUES — BUG / GAP Tracker

**Canonical home for every tracked defect, capability gap, and recurrence in Elefante.** Each row links to its postmortem in [`postmortems/<domain>.md`](postmortems/) and to its verification command. Lifecycle step 1 (CLASSIFY) reads this file to match work against existing rows.

> **Cross-refs:** Domain postmortems = [`postmortems/`](postmortems/). Cross-bug rules = [`lessons.md`](lessons.md). Active release state + journal = [`PLANNING.md`](PLANNING.md). Constitution = [`../agents/orchestrator.md`](../agents/orchestrator.md).
>
> **Last Updated:** 2026-07-23 (BUG-032 manifest isolation; 32 BUGs + 4 GAPs)

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
| BUG-028 | Dashboard served private memory data with wildcard CORS and a public bind default; Compose also published port 8000 on all interfaces. | FIXED (guarded) — loopback bind, explicit origins, loopback Compose publication | [dashboard #10](postmortems/dashboard.md#issue-10-dashboard-private-data-exposure) | `pytest tests/test_dashboard_serializer.py -k "loopback or cors" -v` | 0x — audit discovery 2026-07-22 |
| BUG-029 | `elefante-GraphQuery` was described as retrieval but permitted graph writes through Cypher, bypassing the explicit GraphConnect path. | FIXED (guarded) — validator enforced at the MCP boundary | [database #9](postmortems/database.md#issue-9-graphquery-write-boundary-bypass) | `pytest tests/test_dashboard_serializer.py -k "graph_query_validator" -v` | 0x — audit discovery 2026-07-22 |
| BUG-030 | Default `pytest` invocation collected manual tests and failed on duplicate module names, so the automated suite could not be used as a release gate. | FIXED (guarded) — documented `pytest tests` command collects only automated coverage | [ai behavior](postmortems/ai-behavior.md) | `pytest tests -q` | 0x — audit discovery 2026-07-22 |
| BUG-031 | Dashboard claimed to be a static read-only inspection surface but opened live ChromaDB for graph hydration and semantic search; its browser API could also spawn a snapshot-generation subprocess. | FIXED (guarded) — every dashboard data endpoint reads the redacted snapshot only; the browser can reload but cannot regenerate it. Live refresh remains the explicit MCP/CLI path. | [dashboard #11](postmortems/dashboard.md#issue-11-dashboard-live-store-and-browser-mutation-bypass) | `pytest tests/test_dashboard_serializer.py -k "snapshot or dashboard" -v`; `npm run build` in `src/dashboard/ui` | 0x — audit discovery 2026-07-22 |
| BUG-032 | A direct VS Code adapter test could omit `manifest_home`, causing temporary pytest paths to be recorded in the user's real `~/.elefante/install-manifest.json`. | FIXED (guarded) — the low-level adapter requires an explicit manifest home; the production caller passes `Path.home()` and tests pass isolated homes. Residual test-only entries are quarantined before live migration. | [installation #15](postmortems/installation.md#issue-15-test-manifest-leakage-bug-032-fixed-guarded) | `pytest tests/test_install_setup.py -k "manifest_home or transport_only_bridge" -v` | 1x — residual state discovered before live migration 2026-07-23 |
| BUG-033 | Orphaned/stale background server process listening on port 8000 from a trashed repository directory (/Users/jay/.Trash/elefante) served broken responses (HTTP 500) to dashboard requests. | FIXED (guarded) — killed stale process, verified CWD and clean snapshot responses | [dashboard #12](postmortems/dashboard.md#issue-12-orphaned-stale-dashboard-process-from-trashed-directory-bug-033-fixed-guarded) | `pytest tests/test_dashboard_serializer.py -k "null_name or graph" -v` | 1x — stale process from trashed directory 2026-07-28 |
| GAP-029 | The hash-locked Python advisory scan reports one unresolved known vulnerability in `chromadb` (PYSEC-2026-311); the audit database currently publishes no fixed version. | OPEN — **release blocker**. The affected Chroma server endpoint is not exposed by Elefante: production code uses only embedded `PersistentClient`, guarded against accidental HTTP-client use. The opt-in SQLite backend now has a dry-run-first Chroma migration command with exact backup gating plus UUID, reconstructed-metadata, embedding, and search-overlap proof; isolated dry-run/apply regressions pass. No live data was migrated, no default changed, and Chroma remains in the runtime lock, so the audit still blocks release. Close only after an authorized real-store migration/default switch and a clean locked audit. | [SQLite migration proposal](proposals/sqlite-vector-store-migration.md) | `.venv/bin/python scripts/lifecycle/migrate_chroma_to_sqlite.py` (temporary proof); `uv tool run pip-audit --requirement requirements.lock --disable-pip --require-hashes --strict --progress-spinner off` | 0x — first audit 2026-07-22; migration gate implemented and audit reconfirmed 2026-07-23 |
| BUG-001 | Kuzu SIGSEGV — QueryResult lifetime escapes GraphStore ownership | FIXED (guarded) | [ops-database #7](postmortems/database.md#issue-7-async-shutdown-race--queryresult-lifetime-leak) | `pytest tests/test_memory_persistence.py -k "graph_store_close or graph_store_raw_execute or live_mcp_server" -v` | 2x — fix now has 3 regression tests + runtime citation |
| BUG-002 | Kuzu database lock contention (multi-process) | FIXED (guarded) | [ops-database #2](postmortems/database.md#issue-2-database-lock-persistence) | `pytest tests/test_memory_persistence.py -k "TestKuzuLockContract" -v` | 1x — guarded by fresh-path contract, cross-process citation, snapshot isolation, and active-doc sync tests |
| BUG-003 | Dashboard blank on first launch (race condition) | FIXED (guarded) | [ops-dashboard #8](postmortems/dashboard.md#issue-8-persistent-blank-dashboard-on-first-launch) | `pytest tests/test_dashboard_serializer.py -k "dashboard" -v` | 1x — guarded by readiness wait, forced refresh restart, and frontend retry/backoff checks |
| BUG-004 | Dashboard scores stuck at 100 | FIXED | [ops-dashboard #9](postmortems/dashboard.md#issue-9-all-dashboard-scores-stuck-at-100) | `pytest tests/test_dashboard_serializer.py -v` | 1x |
| BUG-005 | Factory reset safety (destructive operation) | TESTED | [ops-database](postmortems/database.md) | `pytest tests/test_factory_reset.py -v` | 0x — 10 safety tests cover dry-run, gates, backup |
| BUG-006 | Agent entry point bypass — skips docs, guesses fix | FIXED (guarded) | [ops-ai-behavior #6](postmortems/ai-behavior.md#issue-6-passive-protocol-enforcement-failure) | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | 1x — guarded by first-response and first-error entrypoint injection |
| BUG-007 | Developer routing drift — stale paths and ritual changelog reads in active process guidance | FIXED (guarded) | [ops-ai-behavior #7](postmortems/ai-behavior.md#issue-7-developer-routing-drift--stale-paths-and-ritual-changelog-reads) | `pytest tests/test_developer_routing.py -v` | 1x — guarded by source-path regression test + live memory amendments |
| BUG-008 | Graph/session schema contract drift — GraphConnect injected unsupported relationship properties and SessionsList assumed synthetic session columns | FIXED (guarded) | [ops-database #8](postmortems/database.md#issue-8-graph-and-session-schema-contract-drift) | `pytest tests/test_memory_persistence.py -k "TestGraphToolContract" -v` | 1x — guarded by rel-table execution coverage and SessionsList source-contract checks |
| BUG-009 | Self-protocol verifier drift — stale snapshot-path assumptions and default line limits broke the maintained whole-system proof | FIXED (guarded) | [ops-ai-behavior #8](postmortems/ai-behavior.md#issue-8-self-protocol-verifier-drift--runtime-path-and-payload-assumptions) | `pytest tests/test_developer_routing.py -k "TestSelfProtocolContract" -v` | 1x — guarded by source-level checks for dashboard snapshot path resolution and large-payload stream sizing |
| BUG-010 | Self-protocol cold-start deadlock — `from sentence_transformers import SentenceTransformer` hangs when executed in a worker thread under an active anyio event loop with piped stdio on Windows + Python 3.11 | FIXED (guarded) [WARN] Windows/Python 3.11/CPU only — untested on Linux, macOS, Python 3.12 | [ops-ai-behavior #9](postmortems/ai-behavior.md#issue-9-self-protocol-cold-start-deadlock--import-sentence_transformers-deadlocks-in-worker-thread-under-anyio--piped-stdio) | `.venv/Scripts/python.exe scripts/verify/verify_e2e_tests.py` | 1x — guarded by pre-loading embedding model before event loop starts in server.py __main__ |
| BUG-011 | MemoryAdd silent IGNORE — test-memory guard returns opaque "Memory filtered by Intelligence Pipeline" with no rejection reason, overly broad heuristic blocks legitimate tags | FIXED (guarded) | [ops-memory #10](postmortems/memory.md#issue-10-memoryadd-silent-ignore--opaque-test-memory-guard-rejection) | `pytest tests/test_memory_guard.py -v` | 2x — guarded by `rejection_reason` field in IGNORE response body |
| BUG-012 | Elefante cold-start trigger gap — agent never calls `elefante-MemorySearch` when working outside the `elefante/` workspace because `.github/copilot-instructions.md` is workspace-scoped and only loads when `elefante/` is the VS Code workspace root | FIXED (partial) [WARN] VS Code Copilot only — cross-client fix (Cursor, Windsurf) requires client-specific bootstrap files | [ops-ai-behavior #10](postmortems/ai-behavior.md#issue-10-elefante-cold-start-trigger-gap--instructions-file-is-workspace-scoped-not-system-scoped) | Manual: open a workspace outside `elefante/`, ask a memory-relevant question, confirm `[ELEFANTE] Searched:` stamp appears in response | 1x — guarded by BOB-level `copilot-instructions.md` bootstrap + system-level `settings.json` user instruction injection |
| GAP-013 | JSON export is not a backup — `export_memories.py --format json` is a read-only analysis format with no import path. Embeddings are excluded (stored explicitly via `thenlper/gte-base`; import must regenerate them). Using ChromaDB default embedding on upsert would silently corrupt semantic search. | MITIGATED — JSON/CSV are explicitly labeled non-backup outputs; the supported binary backup/restore path now has checksummed archives, dry-run-first restore, safe extraction, and recoverable replacement. `import_memories.py` remains planned for portable JSON migration. | [ops-ai-behavior #11](postmortems/ai-behavior.md#issue-11-json-export-is-not-a-backup--missing-import-path-and-embeddings) | `pytest tests/test_backup_restore.py -v`; JSON import round-trip remains pending | 0x — first discovery |
| BUG-014 | CI binary build failure — `build-binaries.yml` had no Node.js/npm step so `src/dashboard/ui/dist/` (gitignored) did not exist in CI. Additionally `elefante.spec` referenced `src/dashboard/ui/build` but Vite outputs to `dist`. All three matrix jobs failed on first tag push (v2.5.3). | FIXED — v2.5.4 | [ops-installation #8](postmortems/installation.md#issue-8-ci-binary-build--missing-frontend-build-step-and-wrong-vite-output-directory) | `Select-String -Path elefante.spec -Pattern "dashboard/ui"` → must show `dist`; `Select-String -Path .github/workflows/build-binaries.yml -Pattern "setup-node\|npm ci"` → must show both | 0x — first tag push |
| BUG-015 | GitHub Release publish failure — the `v2.6.0` release object was created and macOS/Windows assets uploaded, but the Linux artifact was `4,021,041,080` bytes. GitHub release assets must be under `2 GiB`, so `Create GitHub Release` failed while attaching the Linux zip. | FIXED — v2.7.1 (confirmed: v2.7.1, v2.6.0, v2.5.4 all published with 4 assets on GitHub Releases) | [ops-installation #9](postmortems/installation.md#issue-9-github-release-publish-failure-after-successful-matrix-builds) | `pytest tests/test_release_pipeline.py -v` | 1x — v2.6.0 publish failure |
| BUG-016 | Domain signal value-space disjunction — `analyze_query()` infers `None`/`"work"`/`"personal"`/`"project:elefante"` but memories default to `DomainType.REFERENCE`. The value spaces never intersect. 15% of composite weight produces 0.5 (neutral) or 0.0 (penalty), never 1.0. Domain actively degrades ranking vs pure vector. | FIXED — v2.7.0 | [ops-memory #11](postmortems/memory.md#issue-11-domain-signal-value-space-disjunction--15-of-scoring-weight-is-dysfunctional) | `pytest tests/test_autonomous_coactivation.py -v` | 0x — first discovery via ARAA analysis |
| BUG-017 | Unconditional spec override dominates all queries — `+0.30` boost applied to all specification/directive memories regardless of query intent. Three different real queries all returned the same top 4 specification memories. Non-spec memories mathematically cannot outrank specs. | FIXED — v2.7.0 | [ops-memory #12](postmortems/memory.md#issue-12-unconditional-spec-override-dominates-all-queries) | `pytest tests/test_autonomous_coactivation.py -v` | 0x — first discovery via ARAA analysis |
| BUG-018 | Co-activation cold-start — `_session_retrieval_history` resets to `[]` on every server restart. First query of every session gets 0.0 co-activation. Kuzu `CO_ACTIVATED` edges exist but the read path requires IDs that are lost on restart. | FIXED — v2.7.0 | [ops-memory #13](postmortems/memory.md#issue-13-co-activation-cold-start--session-history-lost-on-restart) | Manual: restart MCP server, run `elefante-MemorySearch`, check if co-activation signal > 0 for any result | 0x — first discovery via source trace |
| BUG-019 | DMG GUI installer .app broken — `installer_gui.py` corrupted by overlapping multi-edit patches (dark-to-light-mode rewrite). Fatal `SyntaxError` at line 173, undefined variables (`style`, bare `C`), duplicate widget constructors, nonexistent palette keys. .app exits code 1, no GUI window appears. File was never committed so no git recovery possible. | FIXED — v2.8.1 | [ops-installation #10](postmortems/installation.md#issue-10-dmg-gui-installer-app-broken---corrupted-multi-edit-merge) | `python3 -c "import py_compile; py_compile.compile('scripts/ci/installer_gui.py', doraise=True)"` + DMG launch test | 0x — first discovery, regression from same session |
| BUG-020 | DMG installer customer surface broken — the `.app` launches and internal controls exist, but the rendered macOS window remains visually broken and unacceptable as a customer installer experience. The root fix is to replace Tk as the primary macOS surface with native AppKit and verify by screenshot, not just process liveness. | FIXED (guarded) — v2.9.0 | [ops-installation #11](postmortems/installation.md#issue-11-dmg-installer-customer-surface-broken---tk-aqua-paint-failure) | `pytest tests/test_installer_gui.py -v` + `swiftc -parse-as-library -O scripts/ci/installer_app.swift -o /tmp/elefante-installer-native-test`; then Screenshot first → native compile → install smoke; widget-tree inspection only if screenshot fails (manual packaged-artifact screenshot remains authoritative) | 0x — first customer-experience audit |
| BUG-021 | Installer seed-memory collision with test-memory guard — every fresh install failed at stage 3 (Database Initialization) because `init_databases.py::inject_seed_memory` submitted `tags=["seed", "test", "passcode"]` and the orchestrator guard (BUG-011) does exact-match on tag `"test"` to block E2E artifacts. The guard rejected the installer's own seed, the install reported FAILED, and no regression test caught it because no pytest exercised the positive (pass) path. | FIXED (guarded) — v2.9.1 | [ops-installation #12](postmortems/installation.md#issue-12-installer-seed-memory-collision-with-test-memory-guard) | `pytest tests/test_install_setup.py -v` (guards the seed payload against every guard condition) | 1x — first full customer-experience audit |
| BUG-023 | Installer reuse mode assumed every valid `.venv` already had `pip`. A fresh `uv`-created environment reached Step 2 with a working Python 3.11 interpreter but failed immediately on `python -m pip` with `No module named pip`. | FIXED (guarded) — unreleased | [ops-installation #13](postmortems/installation.md#issue-13-installer-reuse-mode-fails-when-pip-is-missing-from-venv) | `pytest tests/test_install_setup.py -k "bootstraps_pip_when_missing" -v` | 1x — first fresh-environment audit after Homebrew Python removal |
| BUG-024 | Installer bundle build walks local `.venv.*` backups — `build_installer_bundle.py` excluded only exact `.venv`, so a recovered workspace with `.venv.broken.<timestamp>` tried to package broken interpreter symlinks, crashed with `FileNotFoundError`, and left stale `dist` artifacts behind. | FIXED (guarded) — unreleased | [ops-installation #14](postmortems/installation.md#issue-14-installer-bundle-build-walks-local-venv-backups-and-broken-symlinks) | `pytest tests/test_installer_bundle.py -k "venv_backups" -v` | 1x — first post-recovery bundle rebuild |
| BUG-022 | ChromaDB `query()` with `where` fails on production collection — `collection.query(where=...)` raises `InternalError: Error finding id` on ChromaDB 1.3.5 when the collection has 400+ memories. Caused MemoryAdd to fail completely for preference memory type. | FIXED (guarded) — v2.9.0 | [ops-memory #14](postmortems/memory.md#issue-14-chromadb-query-with-where-filter-fails-on-production-collection) | Run `elefante-MemoryAdd` with `memory_type="preference"` and confirm `success: true` | 0x — first discovery |
| GAP-025 | Multi-instance write origin tracking was absent, and stdio-per-client transport made two concurrent IDEs a Kuzu single-writer risk. | IN PROGRESS — loopback singleton daemon, transport-owned Source tuples, idempotent backfill, bridge adapters, and two-client runtime proof are implemented. Existing-user graph links still require the explicit migration apply step. | [ops-memory #15](postmortems/memory.md#issue-15-multi-instance-write-origin-tracking--no-source-attribution-concurrent-writer-data-risk) | `pytest tests/test_mcp_daemon.py -m slow -q` (two bridges, concurrent writes, distinct Source links); preview migration with `python scripts/lifecycle/backfill_memory_provenance.py` | 0x — first architectural audit |
| BUG-026 | DOC_SYNC protocol bypass — direct-repo file-edit agent skips Loop Step 1 (Known Issues) at the moment of action, applies Gate 3 (Leakage Scan) after authoring redundant content instead of before, performs unauthorized private-memory side writes, and self-evaluates falsely. Recurrence of BUG-006 in a new surface (file-edit) where the shipped MCP-response `ENTRYPOINT_SEQUENCE` injection cannot fire. Parent class: BUG-006. | MITIGATED (guarded) — active guard on filename-pattern subset lands 2026-05-02 in `tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents`. Broader passive-protocol failure (Loop Step 1 skip, Gate 3 timing, side writes) remains passive-only. | [postmortems/ai-behavior.md Issue #12](postmortems/ai-behavior.md) | `pytest tests/test_developer_routing.py::test_no_forbidden_filename_patterns_in_active_docs_or_agents -v` (filename guard); for non-filename failure modes, manual route per `agents/orchestrator.md` Documentation Skill | 3x — discovery 2026-05-02 + 3 same-session recurrences (filename version-stamping; audit-without-reread; deferred-deletion-of-forbidden-pattern-files); guard added same day |
| BUG-027 | File-edit destructive op without preservation — agent runs `rm` / `Edit` / `Write` on uncommitted or post-HEAD-modified files without `git status --porcelain` check or archive-first preservation. Parent class: BUG-006 (passive-protocol bypass on file-edit surface, parallel to BUG-026). On 2026-05-02 the agent-architect deleted `workspace/proposals/surface-split.md` (583 LOC) and `workspace/proposals/documentation-strategy-protocol.md` (450 LOC) via `rm` — both were post-HEAD untracked, so 1033 LOC of original PRD prose are permanently unrecoverable from git. Absorption-map stubs at `workspace/proposals/_archive/<name>-full.md` document where each section's substance survives but the verbatim text is gone. | MITIGATED (passive only) — Lifecycle step 4 ARCHIVE in `agents/orchestrator.md` mandates `git status --porcelain <path>` + commit-or-archive-first. Elefante directive installed 2026-05-02 (DirectiveList count 16→19) auto-injects the rule on every MCP tool response. **No active filesystem guard** wraps Edit/Write/rm yet — that is a v2.11+ architectural item (pre-edit hook calling `elefante-MemorySearch` before mutation). | [postmortems/ai-behavior.md Issue #12](postmortems/ai-behavior.md) (parent BUG-006) + [proposals/_archive/surface-split-full.md](proposals/_archive/surface-split-full.md) + [proposals/_archive/documentation-strategy-protocol-full.md](proposals/_archive/documentation-strategy-protocol-full.md) | Manual: before any `rm`, run `git status --porcelain <path>`; if untracked → commit OR archive first. No automated test yet. | 1x — discovery 2026-05-02 (1033 LOC lost) |
| GAP-028 | Hermes LLM provider configuration — needed Hermes to run as LLM-driven agent so the recursive Hermes <-> Elefante memory loop could close from the consumer side. User intent: DeepSeek for certain task types. Hermes natively supports `DEEPSEEK_API_KEY` + recognizes models `deepseek-v4-pro` / `deepseek-v4-flash` / `deepseek-r1` / `deepseek-reasoner` / `deepseek-chat` / `deepseek-v3`. | **CLOSED (FIXED) — 2026-05-02.** Layer 0+1+2+3 all PASS via verifier. Layer 3 evidence: `hermes -z` invoked `deepseek-v4-pro`, which called `elefante-MemorySearch` and surfaced memory id `f1fb77f5` with exact content match ("Elefante Workflow Lifecycle is the canonical agentic development cycle authored 2026-05-02"). The recursive Hermes <-> Elefante loop closed for the first time **from the Hermes side**. Configuration: `~/.hermes/.env` (chmod 600) holds `DEEPSEEK_API_KEY`; `~/.hermes/config.yaml` `model: deepseek-v4-flash`; verifier at `/tmp/elefante-gap-028-verify.py`. **User reminder: rotate the API key after session — pasted in chat.** | none — capability gap, no postmortem needed | `.venv/bin/python /tmp/elefante-gap-028-verify.py` (must show Layer 0/1+2/3 PASS) | 0x — closed on first audit |

- **FIXED (guarded)**: Fix is in place AND has regression tests. If the test still passes, the fix holds. If it fails, the regression is real.
- **FIXED (documented)**: Fix is in place, recovery procedure documented, but no automated regression guard yet.
- **TESTED**: Feature works and has test coverage. No known bug, but the test exists because the risk is high.
- **OPEN**: Known weakness, mitigation in place, but not fully resolved.

### Adding a New Issue

1. Assign next `BUG-NNN` ID
2. Document the postmortem in the relevant `postmortems/<domain>.md`
3. Write or identify the test that proves the fix
4. Add the row to this table
5. If the error surfaces in Python, add a runtime citation pointing to the postmortem entry (see [`../agents/orchestrator.md`](../agents/orchestrator.md) Embedding Rule)

## Layout

```
workspace/
├── ISSUES.md                   <- This file: BUG/GAP tracker (you are here)
├── lessons.md                  <- Cross-bug rules (Promotion-Filter qualified)
├── postmortems/                <- Domain compendiums (one file per domain)
│   ├── ai-behavior.md
│   ├── dashboard.md
│   ├── database.md
│   ├── installation.md
│   ├── memory.md
│   └── _archive/               <- Pre-distillation full narratives
└── PLANNING.md                 <- Active release state + §10 Journal
```

Whole-system MCP verification spec lives in [`../docs/reference/self-protocol.md`](../docs/reference/self-protocol.md) (positive contract, not a postmortem).

Repository debugging uses existing maintained verification first:

- **[`../agents/orchestrator.md`](../agents/orchestrator.md)** is the operational authority that routes script choices
- **[`../scripts/verify/`](../scripts/verify/)** for purposeful validation selected by the orchestrator
- **[`../tests/README.md`](../tests/README.md)** for targeted pytest coverage preferred over scratch repro scripts
- **[`../scripts/debug/`](../scripts/debug/)** for last-resort interventions only when a postmortem calls for them

---

## Domain Postmortems

Each postmortem is distilled to atomic Trigger / Root cause / Solution / Lesson chunks. Full pre-distillation narrative in [`postmortems/_archive/<domain>-full.md`](postmortems/_archive/).

| Domain       | Postmortem                                       |
| ------------ | ------------------------------------------------ |
| Dashboard    | [postmortems/dashboard.md](postmortems/dashboard.md)       |
| Database     | [postmortems/database.md](postmortems/database.md)         |
| Installation | [postmortems/installation.md](postmortems/installation.md) |
| Memory       | [postmortems/memory.md](postmortems/memory.md)             |
| AI Behavior  | [postmortems/ai-behavior.md](postmortems/ai-behavior.md)   |

### Orchestrator (Operational Authority)

[`../agents/orchestrator.md`](../agents/orchestrator.md) — single operational authority for AI agents developing Elefante.

### Feedback Loop Ledger

[`lessons.md`](lessons.md) — distilled cross-bug rules that connect issue rows, postmortems, maintained tests, and the live workflow.

### Whole-System Verification

[`../docs/reference/self-protocol.md`](../docs/reference/self-protocol.md) — authoritative whole-system proof for the live MCP server.

---

## How to Use

| Task            | Action                                                                        |
| --------------- | ----------------------------------------------------------------------------- |
| **First step**  | Check the Known Issues table above — if the error matches, run the verification command |
| **Deep dive**   | Open the linked domain postmortem, then run the issue row's verification command |
| **Validate**    | Use [`../agents/orchestrator.md`](../agents/orchestrator.md) plus [`../tests/README.md`](../tests/README.md) to choose the smallest existing verifier |
| **Whole-system proof** | Run `./.venv/bin/python scripts/verify/verify_e2e_tests.py` and use [`../docs/reference/self-protocol.md`](../docs/reference/self-protocol.md) to interpret coverage and exclusions |
| **Intervene**   | Use `scripts/debug/` only when the compendium says verification is insufficient |
| **New issue**   | Assign next BUG-NNN → post-mortem in compendium → test → add row to Known Issues |

---

_Last verified: 2026-07-23 | Elefante v2.10.0 | 250 automated tests + slow two-bridge proof + 46/46 self-protocol checks passed_
