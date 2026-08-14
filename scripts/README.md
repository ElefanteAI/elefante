# scripts/

Direct operator entrypoints. Logic that belongs to the runtime lives in `src/`. Anything a human, CI job, or packaging flow runs directly lives here.

## Philosophy

Every script answers one stated question. If you cannot say the question, do not run it.

A script with no documented question is a leak. Two valid resolutions, in order:

1. **Document the question.** Add it to the table for its directory in this file.
2. **Delete it with a record.** Add a `### Removed` entry to `CHANGELOG.md` naming the script, the reason (`resolved`, `superseded by X`, `abandoned`, `one-time task complete`), and the commit. Deleting without a record is itself waste.

Authority for which script to reach for: [`agents/orchestrator.md`](../agents/orchestrator.md).

## Operator Flow

```
INSTALL    →   VERIFY INSTALL    →   OPERATE    →   DEBUG (only if compendium says so)    →   RELEASE
setup/         verify/               lifecycle/     debug/, privileged/                       ci/, pipeline/
```

## Installation Verification Ladder

Run top-down. Each step is faster but narrower. `install.py` already runs steps 1 and 2 automatically at the end of installation; the ladder exists so any operator can re-prove install health any time.

| Step | Script | Proves |
| ---- | ------ | ------ |
| 1    | `verify/verify_health.py` | Paths, imports, config load. No DB, no server. |
| 2    | `verify/verify_mcp_handshake.py` | The customer stdio bridge reaches the local daemon and answers a real JSON-RPC initialize. |
| 3    | `verify/verify_e2e_tests.py` | Full live tool/prompt surface in an isolated temp install — the **self-protocol** (see [`docs/reference/self-protocol.md`](../docs/reference/self-protocol.md)). |

If step 1 fails, step 2 cannot help. Do not skip steps.

## Placement Rules

| Directory | What lives here |
| --------- | --------------- |
| `setup/` | Bootstrap and first-run before runtime is healthy |
| `verify/` | Maintained proofs of a shipped contract |
| `lifecycle/` | Safe operational control of the running system or its durable on-disk state |
| `pipeline/` | Data extraction and snapshot generation for downstream consumption |
| `ci/` | Release, packaging, and doc-sync helpers tied to the build/release workflow |
| `debug/` | Manual incident-response tools — non-routine, never substitute for `verify/` |
| `privileged/` | High-authority maintenance that mutates core state; requires `ELEFANTE_PRIVILEGED=1` for writes |
| `demo/` | Showcase, benchmark, onboarding seeds — never operational tooling |

## Documentation Contract

- Every live entrypoint under `scripts/` is listed in this file with what it does and when to use it.
- A script with no documented question is a leak. Either give it a question or delete it **with a recorded reason in `CHANGELOG.md` under `### Removed`**.
- Add, move, or delete a script → update this file in the same commit.

---

## `scripts/setup/` — Bootstrap

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `install.py` | Single-entry installer: venv, deps, DB init, IDE MCP config, post-install verification. | First-time install or clean reinstall. |
| `bootstrap_release_bundle.py` | Stable-path wrapper that places a downloadable installer payload at `~/.elefante/app/current` then delegates to `install.py`. | Running a downloadable bundle outside a source checkout. |
| `configure_vscode_bob.py` | Adds the Elefante bridge entry to VS Code/Bob configuration, refreshing only installer-owned entries and preserving user configuration. | Initial VS Code/Bob setup or after moving the repo. |
| `configure_antigravity.py` | Adds the Elefante bridge entry to `~/.gemini/antigravity/mcp_config.json`. | Initial Antigravity setup or after moving the repo. |
| `configure_cursor_kiro.py` | Detects Cursor and Kiro user directories, then adds their Elefante bridge entries without touching absent hosts. | Initial Cursor/Kiro setup or after moving the repo. |
| `configure_cli_agents.py` | Uses the native Claude Code and Codex MCP CLIs to register the bridge and fingerprint the host-owned registration. For Codex it also installs one marked, reversible global Recall-routing block without replacing user guidance. | Initial Claude Code/Codex setup or after moving the repo. |
| `host_selection.py` | Defines the canonical installer host IDs, labels, and adapter-family routing shared by CLI and native installer flows. | Imported by installer entrypoints; not run directly. |
| `install_manifest.py` | Internal helper that atomically tracks whole files, owned JSON entries, commands, and marked text blocks emitted by Elefante installers. Uninstall removes only unchanged owned material. | Imported by setup emitters; not run directly. |
| `init_databases.py` | Initializes the configured SQLite vector store and Kuzu schema without re-running the full installer. | After a durable-store reset. |

## `scripts/verify/` — Proofs

See the Installation Verification Ladder above for steps 1–3. Other verifiers:

| Script | Proves | When to use it |
| ------ | ------ | -------------- |
| `verify_scoring_sandbox.py` | All 5 retrieval signals + dashboard taxonomy on a 100-memory sandbox; auto-cleanup. | Changes to `retrieval.py`, co-activation, temporal scoring, or dashboard serialization. |
| `verify_dashboard_health.py` | HTTP reachability and JSON shape of running dashboard endpoints. | After starting the dashboard, or when the UI is blank. |
| `verify_dashboard_snapshot.py` | Structural integrity of `dashboard_snapshot.json`. | After `update_dashboard_data.py`, before the frontend consumes it. |
| `verify_emoji_policy.py` | Strict surfaces have no emojis. | After LLM-generated content lands; pre-commit hygiene. |

## `scripts/lifecycle/` — Server & Data Control

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `restart_elefante.py` | Process-level restart with stale-lock cleanup and optional post-restart verification. | After `src/` changes that the live server needs to pick up. |
| `backup_elefante_data.py` | Checksum-manifested zip backup of `~/.elefante/data`; excludes nested recovery archives. | **Stop Elefante, then run before any destructive operation.** |
| `restore_elefante_data.py` | Dry-run-first checksum-verified restore; existing data is moved aside by default. | Undo accidental data loss or a factory reset. Stop Elefante first; inspect, then add `--apply`. |
| `reset_factory.py` | Privileged, dry-run-first reset that moves configured/default vector and Kuzu stores into a timestamped recovery area. | Last resort or explicit privacy wipe. Never for Kuzu-only or lock-only issues. It refuses a configuration that would contain its own recovery directory. |
| `backfill_memory_provenance.py` | Adds explicit `legacy` provenance to memories created before the daemon. Dry-run by default; `--apply` persists. | After reviewing migration candidates, before treating provenance as complete. |
| `migrate_chroma_to_sqlite.py` | Copies ChromaDB to an isolated snapshot, stages SQLite, and verifies UUID/metadata/embedding/search parity. Dry-run uses temporary storage; `--apply` requires an exact verified backup and `STOPPED` confirmation, leaves Chroma and configuration unchanged, and reserves a new destination without replacing any existing path. | Before replacing ChromaDB because of GAP-029; run dry-run first, then inspect its JSON proof before authorizing apply. |
| `daemon_service.py` | Renders and manages a launchd, systemd-user, or Task Scheduler user daemon. Dry-run by default; `--apply` writes or removes only Elefante's unchanged service definition. | Install, inspect, or remove the shared local daemon service. |
| `doctor.py` | Read-only report of repository runtime, daemon health, installer ownership, configured surfaces, and declared integration tiers. `--json` is agent-friendly and never exposes host-registration commands, configuration locations, or values. | Diagnose readiness before configuring an IDE or after an upgrade. |
| `uninstall_elefante.py` | Stops an unchanged Elefante daemon service, then removes only unchanged Elefante-owned files or JSON entries from the install manifest. Dry-run by default; modified or missing configuration is preserved. | Safely remove Elefante's emitted IDE configuration. |

## `scripts/pipeline/` — Extracts & Snapshots

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `update_dashboard_data.py` | Reads the configured embedded vector store plus Kuzu and emits `dashboard_snapshot.json`; legacy Chroma remains readable when explicitly configured. | After bulk memory changes, or when the dashboard shows stale counts. Follow with `verify_dashboard_snapshot.py`. |
| `export_memories.py` | Read-only JSON/CSV corpus export from the configured embedded vector store. `--format json\|csv\|all`; not a backup or restore format. | Before a surgical delete (before/after diff) or for offline analysis. |

## `scripts/ci/` — Build & Release

Release flow: `advise_version_bump.py` → write CHANGELOG → `bump_version.py X.Y.Z` → `bump_version.py --check` → commit.

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `advise_version_bump.py` | Classifies staged diff as MAJOR/MINOR/PATCH. | Before writing the CHANGELOG entry. |
| `bump_version.py` | Cascades the chosen version across runtime/package declarations. Published-release claims remain pinned until publication is verified. | After writing the CHANGELOG. Run `--check` after. |
| `build_installer_bundle.py` | Builds the full developer/diagnostic installer bundle, including repository support material. | Developer validation only; never use this archive as a customer release asset. |
| `build_release_client.py` | Builds the macOS, Windows, or Linux customer installer from a strict runtime allowlist: product source, required runtime scripts, prebuilt dashboard, and the client lock only. | This is the sole builder for customer candidates and tagged release installers. |
| `resolve_release_publication.py` | Returns `release` only when the Git ref is the exact `v<source-version>` tag; branch, pull-request, and manual builds remain candidates. | Before building any customer artifact in the tagged-release workflow. |
| `verify_release_client.py` | Rejects a customer installer with developer workspace, tests, migration/support utilities, development tools, unexpected files, broken launcher permissions/bytes, misleading timestamps, or invalid platform/publication metadata. | Immediately after every customer installer build and before artifact upload. |
| `verify_task_intelligence_benchmark.py` | Verifies the current 32-task diagnostic benchmark, calibration/holdout isolation, executable acceptance nodes, answer leakage, and behavioral acceptance/rollback readiness. | Before any Task Intelligence run; add `--require-promotion-ready` for a fail-closed promotion check. |
| `audit_task_intelligence_retrieval.py` | Measures whether v2 pre-fix retrieval reaches historical repair files without using future content for selection. Diagnostic only; it cannot prove task improvement. | After changing v2 chunking or candidate ranking, on calibration only. |
| `run_task_intelligence_baseline.py` | Runs isolated no-Brief calibration trials from one-commit historical snapshots; requires exact run counts and cumulative total/uncached token caps; separates outcomes by model configuration and stores metadata only. | Establish or resume the calibration baseline after the benchmark verifier passes. |
| `run_task_intelligence_evaluation.py` | Runs seeded paired no-Brief/Task-Brief or source-only/memory-component trials with identical reasoning rules, v1/v2 profile isolation, source-grounded local retrieval, deterministic sealed-fixture preflight, exact caps, contract-bound schema-v3 outcomes, failure-workspace preservation, and no raw transcripts. | Calibration only until a behavioral manifest is promotion-ready; inspect every preserved failure before another run and keep v1 as rollback. |
| `summarize_task_intelligence_evaluation.py` | Pairs profile- and task-contract-isolated outcomes, reports complete-pair acceptance efficiency plus all observed input-and-output token spend, applies clustered 95% confidence and resource limits, and blocks cheap failures, acceptance regressions, stale evidence, or diagnostic-only evidence from promotion. | After paired runs; promotion additionally requires a verified behavioral manifest. |
| `build_dmg.py` | Builds the branded macOS DMG. Uses Swift to compile `installer_app.swift` into `Install Elefante.app` when available; otherwise falls back to `installer_gui.py`. `--sign` for notarized releases. | In CI on a macOS runner after `build_release_client.py`. |
| `installer_app.swift` | Native AppKit installer surface showing the compatible agent hosts connected automatically to the shared customer runtime. | Compiled by `build_dmg.py`; not run directly. |
| `installer_gui.py` | Legacy Tk fallback installer surface bundled when Swift is unavailable. | Not run directly in the preferred path. |
| `render_release_notes.py` | Renders GitHub release body from the matching `CHANGELOG.md` entry. | In CI before publishing a tagged release. |
| `select_release_assets.py` | Filters artifacts against GitHub's per-file upload cap; emits workflow outputs. | In CI before `action-gh-release`. |
| `generate_release_checksums.py` | Generates or verifies a deterministic, basename-sorted `SHA256SUMS` manifest for an exact set of release assets. | On each build runner for archive integrity smoke tests, then in the release job before publishing assets. |
| `list_mcp_tools.py` | Reads `server.py` and prints the live MCP tool + prompt inventory. | After modifying `server.py` to verify `docs/reference/tools.md` is in sync. |
| `bundle_docker_package.sh` | Tarball of the Docker bundle for environments without full repo access. | Distribution packaging. |

## `scripts/debug/` — Incident Response

Reach for these only when a compendium points here. They are not routine.

`elefante-Memory(action="search", list_all=true)` is the routine inventory tool — these scripts exist only for the cases below.

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `manage_lock.py` | Inspect and optionally remove the Elefante write lock; `--kill` to stop the MCP process first. | Write operations hang or `lock held` errors. Always dry-run first. |
| `reset_kuzu_nuclear.py` | Backup-and-remove the Kuzu graph path so the next init is fresh. | Kuzu corrupted but vector memory must be preserved. |

Lock guidance: default = inspect only; `ELEFANTE_PRIVILEGED=1 manage_lock.py --apply --confirm DELETE` removes the lock; add `--kill` when the server is unresponsive.

## `scripts/privileged/` — Deep Overrides

Mutations require `ELEFANTE_PRIVILEGED=1`. Always `backup_elefante_data.py` first.

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `delete_memories_surgical.py` | Risk-scored deletion across the configured vector store + Kuzu with impact report and JSON export. Default dry-run. | Low-value memories degrading dashboard clarity. Backup → `--auto` dry-run → targeted `--apply`. |
| `inspect_memory_graph.py` | Read-only semantic/temporal review of memory IDs or backup JSONs. No external embedding calls. | Before passing IDs to `delete_memories_surgical.py`. Audit backup JSONs after a deletion run. |

## `demo/` — Showcases

| Script | What it does | When to use it |
| ------ | ------------ | -------------- |
| `generate_showcase_snapshot.py` | Writes a deterministic, source-grounded 37-memory dashboard snapshot with clearly declared synthetic behavioral metadata; never opens a durable store. | For product demos, screenshots, and UI acceptance without exposing or mutating user memory. |
| `generate_100_memories.py` | Legacy Chroma + Kuzu behavioral-store benchmark. It mutates only the explicit isolated `--db` path and requires `--force` to replace one. | Only when exercising historical 100-memory store behavior; not for the current dashboard showcase. |
| `benchmark_sqlite_vector_store.py` | Creates a deterministic, disposable SQLite store and reports exact-cosine retrieval latency as JSON. It never opens existing ChromaDB or Elefante data. | Before approving a SQLite default/migration performance envelope; use `--max-p95-ms` to enforce a measured threshold. |
