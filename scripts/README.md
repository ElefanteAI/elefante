# Elefante Scripts Directory

This directory contains direct operator entrypoints. These files live outside `src/` because they orchestrate Elefante from the outside — installation, verification, lifecycle control, exports, destructive recovery, or release packaging. If logic belongs to the runtime itself, it belongs in `src/`. If a human, CI job, or packaging flow runs it directly, it belongs here.

For repository debugging, choose scripts through [`docs/debug/dev-developer-agent.md`](../docs/debug/dev-developer-agent.md). `scripts/verify/` is for purposeful proof. `scripts/debug/` is for non-routine intervention only when a compendium explicitly directs it.

## Documentation Contract

- Every live `.py` and `.sh` entrypoint under `scripts/` must be listed in this file.
- Every entry must explain **what** the script does, **when** to reach for it, and what distinguishes it from alternatives.
- Every section must explain why those scripts belong in that subdirectory instead of another one.
- If a script is added, moved, or deleted, update this file in the same change.

## Placement Rules

- `scripts/setup/`: bootstrap and first-run preparation before the normal runtime is healthy.
- `scripts/verify/`: maintained proofs that validate the product or a shipped contract.
- `scripts/lifecycle/`: safe operational control over the running system or its durable on-disk state.
- `scripts/ci/`: release, packaging, and documentation-sync helpers tied to build/release workflow.
- `scripts/pipeline/`: data extraction and snapshot generation for downstream consumption.
- `scripts/debug/`: manual intervention tools for incident response and recovery, not routine validation.
- `scripts/privileged/`: high-authority maintenance tools that inspect or mutate core state and require stronger operator intent.
- `scripts/demo/`: demonstration and showcase scripts for presentations, benchmarks, and onboarding.

---

## `scripts/setup/` — Bootstrap & First-Run

Why here: these scripts prepare an environment or client integration before day-to-day runtime and verification flows make sense.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `install.py` | Single-entry cross-platform installer: venv, deps, DB init, MCP config for VS Code + Antigravity, system verification. | First-time install or clean reinstall. NOT for routine restarts or IDE reconfiguration alone. | Bootstrap, not runtime logic. |
| `bootstrap_release_bundle.py` | Copies a shipped Elefante installer payload into the stable app root, then delegates all real setup work to `install.py`. | Running a downloadable installer bundle from outside a source checkout. | Product bootstrap wrapper, not a second installer engine. |
| `configure_vscode_bob.py` | Writes VS Code `mcp.json` and removes `settings.json` duplicates to wire Elefante as an MCP server. | Initial VS Code/Bob setup, or after moving the repo. Also if you see two Elefante entries in VS Code. | IDE onboarding is setup work. |
| `configure_antigravity.py` | Writes `~/.gemini/antigravity/mcp_config.json` to wire Elefante for Antigravity IDE. | Initial Antigravity setup, or after moving the repo path. | Prepares a client environment. |
| `init_databases.py` | Initializes or re-verifies ChromaDB collections and Kuzu schema without running the full installer. | After a Kuzu nuclear reset or ChromaDB wipe; when you see "collection not found" errors. | Bootstrap safety tool, not lifecycle. |

---

## `scripts/verify/` — Health & Validation Ladder

Why here: these are maintained checks that prove a contract. Use them in order — each step is faster but narrower.

**Verification ladder**: `verify_health` → `verify_mcp_handshake` → `verify_e2e_tests`

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `verify_health.py` | Structural health check: paths, imports, config, and baseline readiness. No DB access, no server start. | First check after install, after config changes, or when any core import fails. Fastest non-destructive check. | Proves baseline health without mutating data. |
| `verify_mcp_handshake.py` | Minimal JSON-RPC initialize probe — proves the MCP server can answer a real handshake. | After restart_elefante.py, to confirm the server came back before running the full self-protocol. | Narrow protocol proof below the full self-protocol. |
| `verify_e2e_tests.py` | **Authoritative self-protocol harness.** Launches a real MCP server in an isolated temp dir and proves the full live tool/prompt surface, routing, memory/graph/ETL/refinery flows, and cleanup. | Before any release. After changes to server.py, orchestrator.py, or any core module. Not a substitute for unit tests — this proves the live surface. | Whole-system proof for release confidence. |
| `verify_scoring_sandbox.py` | Seeds 100 crafted memories in a disposable temp HOME/data sandbox, verifies all 5 retrieval signals plus dashboard-visible taxonomy, lifecycle, graph, and activity coverage, then deletes the sandbox. | When changing `retrieval.py`, co-activation, temporal scoring, dashboard serialization, or when you need a deterministic second-brain demo dataset without polluting the user's real store. | Purpose-built scoring and dashboard proof with zero durable residue. |
| `verify_dashboard_health.py` | HTTP-level probe of running dashboard endpoints; checks reachability and JSON response shape. | After starting the dashboard server, or when the UI is blank and you need to isolate server vs. data issues. | Validates the served dashboard surface. |
| `verify_dashboard_snapshot.py` | Offline validation of `dashboard_snapshot.json` structural integrity and edge validity. | After `update_dashboard_data.py` — confirm the snapshot is valid before the frontend consumes it. | Proves the export artifact, not the live server. |
| `verify_emoji_policy.py` | Enforces the no-emojis rule across strict docs/source surfaces. | After LLM-generated content is added (high emoji-injection risk). Also part of pre-commit hygiene. | Policy verifier, not a formatter. |

---

## `scripts/lifecycle/` — Server & Data Control

Why here: these scripts operate the running system or its durable on-disk state. They are operational controls, not setup or incident-only tools.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `restart_elefante.py` | Safe process-level restart with stale lock cleanup and optional post-restart verification. | After `src/` changes that need to be picked up by the live server. Preferred over manual kill/start. | Controls the live daemon lifecycle. |
| `backup_elefante_data.py` | File-level zip backup of `~/.elefante/data`; no DB handles opened. | **Always run before any destructive operation** (reset, nuclear reset, surgical delete) or before a version upgrade. | Manages durable state safely. |
| `restore_elefante_data.py` | File-level restore from a backup zip; moves existing data aside (or discards with `--discard-existing`). | After accidental data loss or to undo a factory reset. Stop all Elefante processes first. | Inverse lifecycle operation of backup. |
| `reset_factory.py` | **Destructive full reset** of all Elefante durable state with backup gates. | Last resort — when both ChromaDB AND Kuzu are unrecoverable. NOT for Kuzu-only issues or lock issues. | Lifecycle-level state reset, broader than debug intervention. |

---

## `scripts/ci/` — Build & Release Chain

Why here: these scripts support release preparation, packaging, and source-of-truth sync for shipped artifacts and docs.

**Release workflow**: (1) `advise_version_bump` → (2) write CHANGELOG → (3) `bump_version X.Y.Z` → (4) `bump_version --check` → (5) git commit

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `advise_version_bump.py` | Inspects staged git diff, classifies MAJOR/MINOR/PATCH, and recommends a bump level. | Before writing the CHANGELOG entry — use it to determine the right bump level from the diff. | Release workflow guidance, not the write step. |
| `bump_version.py` | Cascades a chosen version string across all 48 tracked version declarations. Has CHANGELOG gate, downgrade guard, and pattern-miss WARNING. | After writing the CHANGELOG entry. Never before. Run `--check` after every bump. | Authoritative release write step. |
| `build_installer_bundle.py` | Builds the downloadable Elefante installer zip: generated top-level entrypoints, bundle manifest, and repo-like payload with prebuilt dashboard assets. | In CI after dashboard assets are built, or locally when validating installer bundle contents before release. | Product installer packaging, not runtime logic. |
| `render_release_notes.py` | Renders GitHub release notes from the matching `CHANGELOG.md` entry so release pages ship with curated narrative instead of auto-generated filler. | In CI before publishing a tagged release, or locally to preview the exact release body. | Release-page content is part of the build/release chain. |
| `select_release_assets.py` | Filters candidate build artifacts against GitHub's per-file upload cap and emits the workflow outputs consumed by the release job. | In CI after downloading artifacts and before `action-gh-release`, or locally when validating release publication behavior. | Upload eligibility is a release-stage packaging concern. |
| `list_mcp_tools.py` | Reads `server.py` and prints the live MCP tool + prompt inventory without booting the runtime. | After modifying `server.py` to verify the inventory matches spec-tools.md. | Supports spec/doc sync around the MCP surface. |
| `build_dmg.py` | Builds a branded macOS `.dmg` installer from the installer bundle zip. Compressed UDZO, Elefante volume icon, README, website link. Optional `--sign` for notarized releases. | In CI (macOS runner) after `build_installer_bundle.py`, or locally when validating DMG packaging. | Platform-specific distribution packaging. Spec: `spec-vision.md` section F. |
| `installer_gui.py` | Native macOS tkinter GUI for the Elefante installer. Shows branded window with install path picker, real-time progress bar, and scrollable output log. Bundled inside the DMG `.app`. | Not run directly — embedded by `build_dmg.py` into the `Install Elefante.app` bundle. | GUI installer surface for DMG distribution. |
| `backfill_github_releases.py` | Creates missing GitHub Releases for tags that have CHANGELOG entries but no corresponding release page. Uses `gh` CLI. | One-time or periodic backfill when historical tags lack release pages. | Release hygiene for historical versions. |
| `bundle_docker_package.sh` | Builds a copy-friendly tarball of the Docker-facing bundle for shipping into environments without full repo access. | Distribution packaging only. | Distribution packaging, not runtime. |

---

## `scripts/pipeline/` — Data Extracts & Snapshots

Why here: these scripts transform stored Elefante state into downstream artifacts for dashboards, exports, and external analysis.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `update_dashboard_data.py` | Reads ChromaDB + Kuzu state and emits `dashboard_snapshot.json` for the dashboard frontend. | After bulk memory changes or when the dashboard shows stale counts/nodes. Run `verify_dashboard_snapshot.py` after. | Snapshot/export pipeline, not a live API verifier. |
| `export_memories.py` | Exports the full memory corpus to JSON and/or CSV via direct ChromaDB read (no filtering). `--format json\|csv\|all`. | Before a surgical delete (for before/after comparison). For offline analysis or spreadsheet review. | Data extraction path, not a maintenance tool. |

---

## `scripts/debug/` — Raw Interventions

Why here: manual incident-response tools. Intentionally separate from `scripts/verify/` so destructive or low-level intervention is not mistaken for routine proof.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `dump_memories_all.py` | Direct ChromaDB dump bypassing all orchestrator filtering. | When `elefante-MemorySearch` returns unexpected results — confirms what is truly stored. | Emergency visibility tool, not a supported flow. |
| `list_memories_recent.py` | Lightweight recent-memory inspection via the orchestrator (last 10 entries). | Quick sanity check after a MemoryAdd before reaching for a full export. | Narrow debug peek, not a maintained verifier. |
| `manage_lock.py` | Inspect and optionally remove the Elefante write lock; `--kill` to stop the MCP process first. | When write operations hang or return "lock held" errors. Always dry-run (no flags) first. | Incident tooling for lock contention. |
| `reset_kuzu_nuclear.py` | Backup-and-remove the Kuzu graph database path only so the next init starts fresh. | When Kuzu is corrupted and cannot be opened. Use ONLY when you need the graph reset but want to preserve ChromaDB. | Specialized graph-store intervention, not a full factory reset. |

### Lock Guidance

- Default (no flags): inspect/dry-run only — always safe.
- `ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE`: removes the lock file.
- `--kill`: attempts to stop `src.mcp.server` processes before removal — use when the server is unresponsive.

---

## `scripts/privileged/` — Deep Overrides

Why here: these scripts inspect or mutate high-authority Elefante state. They require stronger operator intent and, for mutations, `ELEFANTE_PRIVILEGED=1`.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `delete_memories_surgical.py` | Risk-scored deletion workbench: impact report + backup JSON, then deletes from both ChromaDB and Kuzu only when authorized. Default is dry-run. | When the memory graph has low-value artifacts degrading dashboard clarity. Always `backup_elefante_data.py` first, then `--auto` dry-run, then targeted `--apply`. | Privileged: can excise durable memory state across both persistence layers. |
| `inspect_memory_graph.py` | Read-only semantic/temporal review of specific memories or backup JSONs. Uses Chroma kNN — no external embedding calls. | Before passing IDs to `delete_memories_surgical.py` — understand connectivity first. Also to audit backup JSONs after a deletion run. | Paired with high-authority maintenance; inspects internal state more deeply than debug scripts. |

## `scripts/demo/` — Demonstrations & Showcases

Why here: these scripts exist for presentations, benchmarks, and onboarding demonstrations. They are not operational tools.

| Script | What it does | When to use it | Why here |
| --- | --- | --- | --- |
| `generate_100_memories.py` | Seeds 100 synthetic memories into a live Elefante instance for demonstration, benchmarking, or onboarding walkthroughs. | Before a demo or benchmark session when you need a populated memory store. | Demo/showcase asset, not operational tooling. |


This directory contains direct operator entrypoints. These files live outside `src/` because they orchestrate Elefante from the outside: installation, verification, lifecycle control, exports, destructive recovery, or release packaging. If logic belongs to the runtime itself, it belongs in `src/`. If it is a script a human, CI job, or packaging flow runs directly, it belongs here.

For repository debugging, choose scripts through [`docs/debug/dev-developer-agent.md`](../docs/debug/dev-developer-agent.md). `scripts/verify/` is for purposeful proof. `scripts/debug/` is for non-routine intervention only when a compendium explicitly directs it.

## Documentation Contract

- Every live `.py` and `.sh` entrypoint under `scripts/` must be listed in this file.
- Every entry must explain what the script does that no other script does.
- Every section must explain why those scripts belong in that subdirectory instead of another one.
- If a script is added, moved, or deleted, update this file in the same change.

## Placement Rules

- `scripts/setup/`: bootstrap and first-run preparation before the normal runtime is already healthy.
- `scripts/verify/`: maintained proofs that validate the product or a shipped contract.
- `scripts/lifecycle/`: safe operational control over the running system or its durable on-disk state.
- `scripts/ci/`: release, packaging, and documentation-sync helpers tied to build/release workflow.
- `scripts/pipeline/`: data extraction and snapshot generation for downstream consumption.
- `scripts/debug/`: manual intervention tools for incident response and recovery, not routine validation.
- `scripts/privileged/`: high-authority maintenance tools that inspect or mutate core state and require stronger operator intent.
- `scripts/demo/`: demonstration and showcase scripts for presentations, benchmarks, and onboarding.

## `scripts/setup/` - Active Production & Delivery

Why here: these scripts prepare an environment or client integration before the day-to-day runtime and verification flows make sense.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `install.py` | Single-entry installer that creates or replaces the repo `.venv`, installs dependencies, initializes data, and wires the local environment into a usable Elefante install. Existing `.venv` handling is explicit: fresh delete, backup+fresh, reuse, or abort. | It is bootstrap, not runtime logic or verification. | **Critical** (Client setup entrypoint) |
| `bootstrap_release_bundle.py` | Stable-path bootstrap for downloadable installer bundles. It places the payload into `~/.elefante/app/current` or `%LOCALAPPDATA%\Elefante\app\current` and then hands off to `install.py`. | It is the product-entry wrapper that keeps `install.py` authoritative while removing `git clone` from the end-user path. | **Critical** (Installer bundle entrypoint) |
| `configure_vscode_bob.py` | Writes the exact MCP configuration shape required by the Bob/VS Code client integration. No other script targets that IDE format. | IDE onboarding is setup work, not lifecycle control. | **Critical** (IDE integration) |
| `configure_antigravity.py` | Writes the exact MCP configuration required by the Antigravity IDE integration. No other script emits that format. | It prepares a client environment before use. | **Critical** (IDE integration) |
| `init_databases.py` | Initializes or re-verifies the ChromaDB collections and Kuzu schema without running the whole installer. | It is a bootstrap safety tool for local data stores. | **Critical** (Database safety) |

## `scripts/verify/` - Health & Validation

Why here: these are maintained checks that prove a contract. They should be preferred over ad hoc repro scripts.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `verify_health.py` | Structural health check for the core engine: paths, imports, config, and baseline readiness. | It proves baseline health without mutating durable data. | **High** (Deployment and pre-commit) |
| `verify_dashboard_health.py` | HTTP-level dashboard probe that checks endpoint reachability and response shape without touching live databases. | It validates the served dashboard surface, not the data pipeline itself. | **High** (Dashboard stability) |
| `verify_mcp_handshake.py` | Minimal JSON-RPC initialize probe that proves the MCP server can answer a real handshake. | It is the narrow protocol proof below the full self-protocol. | **High** (Protocol verification) |
| `verify_e2e_tests.py` | Authoritative self-protocol harness. Launches the real MCP server in an isolated temporary Elefante home/data dir and proves the live tool/prompt surface, routing injection, compliance gate, memory/graph/context/session/task/ETL/refinery flows, restart persistence, and cleanup. Use `--with-dashboard-open` only for the opt-in full 20-tool sweep. | It is the whole-system proof used for release confidence. | **High** (Release confidence) |
| `verify_dashboard_snapshot.py` | Validates the generated dashboard snapshot JSON so frontend consumers do not receive malformed graph/stat payloads. | It proves the export artifact, not the live server. | **High** (Dashboard stability) |
| `verify_emoji_policy.py` | Enforces the repository no-emojis rule in strict docs/source surfaces. No other verifier checks that policy. | It is a policy verifier, not a formatter or linter built into the runtime. | **Medium** (Codebase etiquette) |

## `scripts/lifecycle/` - Server & Data Control

Why here: these scripts operate the running system or its durable on-disk state over time. They are operational controls, not setup or incident-only tools.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `restart_elefante.py` | Safe process-level restart for the MCP server, including stale lock cleanup and optional restart verification. | It controls the live daemon lifecycle. | **High** (Daemon management) |
| `reset_factory.py` | Full destructive reset of Elefante durable state, with safety gates and backup behavior, for unrecoverable corruption or an explicit wipe. | It is a lifecycle-level state reset, broader than a debug intervention. | **High** (Emergency recovery) |
| `backup_elefante_data.py` | File-level zip backup of the Elefante data directory without opening the databases. | It manages durable state over time and is safe to run with Elefante off. | **High** (Maintenance safety) |
| `restore_elefante_data.py` | File-level restore from a backup archive, moving existing data aside unless explicitly discarded. | It is the inverse lifecycle operation of backup. | **High** (Maintenance safety) |

## `scripts/ci/` - Build & Release Chain

Why here: these scripts support release preparation, packaging, and source-of-truth sync for shipped artifacts and docs.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `advise_version_bump.py` | Interactive semantic-version advisor that inspects the staged git diff and recommends MAJOR, MINOR, or PATCH before handing off to the bumper. | It is release workflow guidance, not the actual write step. | **Medium** (Release workflow) |
| `bump_version.py` | Cascades a chosen version string across the scattered version declarations the repo treats as release surface. | It is the authoritative release write step for semver propagation. | **Critical** (Release formatting) |
| `build_installer_bundle.py` | Packages the downloadable Elefante installer artifact with a stable-path bootstrap script, manifest, and full payload. | It is release-stage packaging for the installer product surface. | **High** (Installer distribution) |
| `render_release_notes.py` | Renders a GitHub release body directly from the matching `CHANGELOG.md` entry so tagged releases do not ship with empty or low-signal release pages. | It is release-surface content generation tied to publication. | **High** (Release communication) |
| `select_release_assets.py` | Filters downloaded artifacts against GitHub's hard per-file upload cap and emits the `files` output consumed by the release workflow. | It is release-stage packaging logic that must stay testable outside inline YAML. | **High** (Release publication) |
| `list_mcp_tools.py` | Reads `src/mcp/server.py` and prints the live MCP tool inventory plus the prompt inventory separately for documentation and audit work. | It supports spec/doc sync around the exposed MCP surface without booting the runtime. | **Medium** (Spec syncing) |
| `bundle_docker_package.sh` | Builds a copy-friendly tarball of the Docker-facing bundle so Elefante can be shipped into environments without cloning the full repo. | It is distribution packaging, not runtime behavior. | **Medium** (Distribution) |
| `installer_gui.py` | Native macOS tkinter GUI embedded inside the DMG `.app` bundle. Shows branded installer window with path picker, progress bar, and log output. | Not run directly — bundled by `build_dmg.py` into `Install Elefante.app`. | **High** (GUI installer) |
| `backfill_github_releases.py` | Creates missing GitHub Releases for tags that have CHANGELOG entries but no release page. Uses `gh` CLI to backfill historical tags. | One-time or periodic backfill when historical tags lack release pages. | **Low** (Release hygiene) |

## `scripts/pipeline/` - Data Extracts & Snapshots

Why here: these scripts transform stored Elefante state into downstream artifacts for dashboards, exports, and external analysis.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `update_dashboard_data.py` | Reads memory/graph state and emits the `dashboard_snapshot.json` artifact consumed by the dashboard server/frontend. | It is a snapshot/export pipeline, not a live API verifier. | **High** (Dashboard backend) |
| `export_memories_json.py` | Exports the full memory corpus to a transportable JSON artifact for external analysis or offline review. | It is a data extraction path, not a maintenance tool. | **Medium** (Portability) |
| `export_memories_csv.py` | Exports memories in a flattened CSV form for spreadsheet or relational tooling. No other script emits that tabular format. | It is a downstream data format transform. | **Medium** (Portability) |

---

## `scripts/debug/` - Raw Interventions

Why here: these are manual incident-response tools. They are intentionally separate from `scripts/verify/` so destructive or low-level intervention does not get mistaken for routine proof.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `dump_memories_all.py` | Direct ChromaDB dump that bypasses normal orchestrator filtering so a developer can inspect what is truly stored. | It is an emergency visibility tool, not a supported user workflow. | **High** (Developer visibility) |
| `list_memories_recent.py` | Lightweight recent-memory inspection for quick manual validation without a full export. | It is a narrow debug peek, not a maintained verifier. | **Medium** (Agile testing) |
| `unlock_database_transactions.py` | More explicit write-lock recovery flow with optional MCP process kill behavior before removing `~/.elefante/locks/write.lock`. | It is incident tooling for lock contention, not normal lifecycle management. | **High** (Database recovery) |
| `remove_lock_kuzu.py` | Simpler legacy-compatible write-lock inspection/removal wrapper that targets the same Elefante transaction lock without the broader recovery flow. | It exists for compatibility with older Kuzu-lock guidance and quick manual inspection. | **High** (Database recovery) |
| `reset_kuzu_nuclear.py` | Backup-and-remove reset of only the Kuzu database path, whether that path is currently a file or directory. | It is a specialized graph-store intervention, not a full factory reset. | **High** (Database recovery) |

### Lock Guidance

- Use `remove_lock_kuzu.py` for quick inspection/removal of the current Elefante write lock.
- Use `unlock_database_transactions.py` when you also want the optional MCP process-kill step and a more explicit recovery flow.
- Both target the same `~/.elefante/locks/write.lock` file. The difference is operator workflow, not lock scope.

---

## `scripts/privileged/` - Deep Overrides

Why here: these scripts inspect or mutate high-authority Elefante state and are intentionally separated from routine debug tools. They require stronger operator intent and, for mutations, `ELEFANTE_PRIVILEGED=1`.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `delete_memories_surgical.py` | Risk-scored memory deletion workbench that builds an impact report, writes a backup JSON, and then deletes from both vector and graph stores only when explicitly authorized. | It is privileged because it can excise durable memory state across both persistence layers. | **Critical** (Targeted maintenance) |
| `inspect_memory_graph.py` | Read-only semantic/temporal review tool for specific memory IDs or for backup JSONs generated by the surgical delete workflow. | It is paired with high-authority maintenance and inspects internal state more deeply than routine debug scripts. | **Critical** (Graph visualization) |

## `scripts/demo/` - Demonstrations & Showcases

Why here: these scripts exist for presentations, benchmarks, and onboarding demonstrations. They are not operational tools.

| Script | Purpose & Uniqueness | Why Here | Importance |
| --- | --- | --- | --- |
| `generate_100_memories.py` | Seeds 100 synthetic memories into a live Elefante instance for demonstration, benchmarking, or onboarding walkthroughs. | It is a demo asset, not an operational tool. | **Low** (Showcase) |
