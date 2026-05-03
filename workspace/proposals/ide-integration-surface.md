# PRD: IDE Integration Surface — Skill, Rules, MCP Distribution

> **Status**: DRAFT — pre-implementation
>
> **Owner**: Elefante dev team
>
> **Date**: 2026-04-18
>
> **Scope**: Document how Elefante positions itself across the heterogeneous 2026 agent-carrying surface (native IDEs, CLI agents, VS Code agent-extensions, non-IDE agent hosts), the installer protocol that lands it there, the daemon architecture that makes concurrent multi-instance use safe, and the continuous-learning procedure that keeps per-surface knowledge current as vendors change conventions.

---

## Question This Spec Answers

When a user has N different AI IDEs or agents on their machine — potentially running concurrently — how does Elefante reach all of them with a consistent identity/memory layer, while staying correct as each vendor changes its skill/MCP conventions underneath us?

---

## 1. Problem Statement

Elefante's shipped surface of "cross-IDE support" is incomplete and brittle:

- Today: Constitution is symlinked for VS Code, Cursor, Windsurf. Bob-IDE has no documented path. See [`spec-vision.md`](spec-vision.md) § E.
- The 2026 agent ecosystem has at least 16 distinct surfaces (Claude Code, VS Code Copilot, Cursor, Windsurf, Kiro, IBM Bob, Gemini Code Assist / Antigravity / Gemini CLI, Codex CLI, Cline, Roo Code, Kilo Code, Continue, Zed, Trae, Aider) with N different file formats, discovery paths, and MCP config conventions — and this list grew during the current quarter.
- Conventions drift. Kiro added a Skills feature distinct from Steering. VS Code Copilot added Agent Skills support that natively reads `.claude/skills/`. Cursor deprecated `.cursorrules` in favor of `.cursor/rules/*.mdc`. Staleness in Elefante's integration logic is unsafe — an installer that writes to a deprecated path leaves the user silently uninjected.
- Concurrent multi-instance use is a real UX: a user can have Claude Code and Cursor open on the same repo simultaneously. If both instances launch their own stdio MCP subprocess pointing at the same Kuzu/ChromaDB files, the second writer will corrupt the graph — Kuzu does not tolerate concurrent writers. This is a latent data-integrity failure tracked as GAP-025.

Elefante cannot defend Law 4 (Full Signal Injection) if the agent never reaches Elefante or reaches a corrupted store.

### Core Requirement

A single source of truth for IDE integration knowledge, a daemonized runtime that tolerates concurrent clients, a detect-then-emit installer, and an agent-driven continuous-learning loop that keeps the system current without manual audit cadence.

---

## 2. Honest Assessment: Current Elefante Reality

| Surface | Current State | Gap |
| ------- | ------------- | --- |
| Cross-IDE configs | VS Code + Cursor + Windsurf via `scripts/setup/configure_vscode_bob.py` + `configure_antigravity.py` | Hard-coded paths, per-tool Python scripts, no shared matrix, no detection logic, 11+ surfaces untouched |
| MCP transport | stdio only in docs | Forces each client to spawn its own MCP subprocess — concurrent-write failure waiting to happen |
| Origin metadata on writes | Not captured | See GAP-025 |
| Doc currency | Manual | Paths already drift. April-2026 audit found at least three vendor changes since last Elefante update |
| Installer scope | Phase 1 places payload in stable location ([`spec-installer-procedure.md`](spec-installer-procedure.md)) | Does not emit per-IDE config for 13 of 16 surfaces; does not detect which IDEs exist; does not uninstall cleanly |
| Spec on cross-IDE | [`spec-vision.md`](spec-vision.md) § E acknowledges gap | No dedicated spec; no acceptance criteria; no test coverage |

---

## 3. Verified Integration Matrix (2026-04-18)

Source of every row below is the official vendor doc fetched on 2026-04-18. Each row must include `doc_url` + `last_verified` + `verified_doc_hash` when transcribed into machine-readable form.

| Surface | Skill/rule path (project) | Global path (macOS) | File | Format | MCP config |
| ------- | ------------------------- | ------------------- | ---- | ------ | ---------- |
| Claude Code | `.claude/skills/<n>/SKILL.md` | `~/.claude/skills/<n>/SKILL.md` | SKILL.md | Anthropic Skill v1 | `~/.claude/mcp.json` |
| VS Code + Copilot | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `~/.copilot/skills/`, `~/.claude/skills/`, `~/.agents/skills/` | SKILL.md | Anthropic Skill v1 | `.vscode/mcp.json` (workspace) + user profile |
| IBM Bob | `.bob/skills/<n>/SKILL.md` | `~/.bob/skills/<n>/SKILL.md` | SKILL.md | Anthropic Skill v1 | `~/.bob/mcp_settings.json` + `.bob/mcp.json` |
| Kiro (skills) | `.kiro/skills/<n>/SKILL.md` | `~/.kiro/skills/<n>/SKILL.md` | SKILL.md | Anthropic Skill v1 | `.kiro/settings/mcp.json` + `~/.kiro/settings/mcp.json` |
| Kiro (steering) | `.kiro/steering/*.md` | `~/.kiro/steering/*.md` | any `.md` | `inclusion:` frontmatter | same |
| Cursor | `.cursor/rules/*.mdc` | user rules (UI-only) | `.mdc` | `description`/`globs`/`alwaysApply` | `.cursor/mcp.json` + `~/.cursor/mcp.json` |
| Windsurf | `.windsurf/rules/*.md` | `~/.codeium/windsurf/memories/global_rules.md` | `.md` | `trigger:` frontmatter | extension-settings |
| Cline | `.clinerules/*` or `.clinerules` | `~/Documents/Cline/Rules/` | `.md`/`.txt` | plain | extension-settings |
| Roo Code | `.roo/rules/*` or `.roorules` | `~/.roo/rules/` | `.md`/`.txt` | plain | extension-settings |
| Kilo Code | `.kilocode/rules/*` or `.kilocoderules` | `~/.kilocode/rules/` | `.md`/`.txt` | plain | extension-settings |
| Continue | `.continue/rules/*.md` | `~/.continue/rules/` | `.md` | `name`/`globs`/`alwaysApply` | via `config.yaml` |
| Zed | root first-match: `.rules` → `AGENTS.md` → `CLAUDE.md` → `GEMINI.md` → `.cursorrules` → `.windsurfrules` → `.clinerules` → `.github/copilot-instructions.md` → `AGENT.md` | — | any markdown | plain | `~/.config/zed/settings.json` |
| Gemini Code Assist / Antigravity / CLI | `GEMINI.md` | `~/.gemini/GEMINI.md` | `.md` | plain | `~/.gemini/settings.json` `mcpServers` |
| Codex CLI | `AGENTS.md` (root, nested) | — | `.md` | plain | `~/.codex/config.toml` |
| Aider | `CONVENTIONS.md` (explicit `/read`) | — | `.md` | plain | `.aider.conf.yml` |

Out of scope (confirmed not IDE-integrated): OpenClaw (chat gateway, not coding-agent surface).

### Three Convergence Points

1. **`SKILL.md` with `name`/`description` frontmatter is the emerging open standard.** Claude Code, VS Code Copilot, IBM Bob, and Kiro all read the same format — one authored skill serves four surfaces.
2. **`.claude/skills/` is a native shared namespace** for Claude Code + VS Code Copilot — documented, not a hack.
3. **`AGENTS.md` at project root** is auto-detected by Codex, Cursor (nested), VS Code Copilot, Cline, Roo, Kilo, and Zed. Seven surfaces covered by one root file.

These three convergences are the reason this spec is feasible at a manageable implementation cost. A naive "one adapter per surface" design would balloon the maintenance surface; convergence-aware design collapses 16 surfaces into roughly 6 write actions.

---

## 4. The Four Non-Negotiables

### 4.1 Machine-Readable Single Source of Truth

`agents/manifests/ide-integration.yaml` owns every path / format / detection-signal in the matrix above. Schema must carry `doc_url`, `last_verified`, `verified_doc_hash`, `compatible_versions` per row. Every installer adapter and every doc-drift check reads this file. No hard-coded paths anywhere else in the codebase.

Reason: duplicated path knowledge is the #1 staleness vector.

### 4.2 Singleton Daemon, Not Per-Client Subprocess

Elefante MCP runs as a single long-running daemon (launchd on macOS, systemd user on Linux, equivalent on Windows) exposing streamable-http on a fixed port. All IDE MCP configs point to the same endpoint. Daemon owns the DBs exclusively.

Reason: concurrent multi-instance writes to Kuzu corrupt the graph (see GAP-025). This is the only concurrency model that survives a user opening two IDEs at once.

Hard rule: installer-emitted MCP configs MUST use http/sse transport against the local daemon. stdio is deprecated as the default client transport.

### 4.3 Detect Before Emit

Installer never writes a config for an unverified surface. The flow is:

1. **Detect** — enumerate surfaces present on the machine (binary on PATH, app in `/Applications`, VS Code extension IDs from `code --list-extensions`, config dir existence).
2. **Report** — dry-run shows user what will be written where, for detected surfaces only.
3. **Emit** — write per-detected-surface only, track every file in an uninstall manifest.

Reason: the user's repo and home are user state. Elefante does not mutate paths for IDEs the user doesn't have.

### 4.4 Continuous Doc-Drift Audit

Doc conventions drift. Manual audit cadence does not scale. The system must:

- hold `doc_url` + `verified_doc_hash` per matrix row
- run a scheduled CI job that WebFetches each `doc_url`, compares hash, opens an issue on mismatch
- expose `elefante doctor` to re-verify live before trusting any install
- version the matrix file (`ide-integration-matrix-v1.yaml`, `-v2.yaml`) so users can pin

The agent protocol for this loop lives at [`agents/integration-inspector.md`](../../agents/integration-inspector.md).

---

## 5. Product Decision

Phase 1 (shipped, [`spec-installer-procedure.md`](spec-installer-procedure.md)): payload placement, stable install dir.

**Phase 2 (this spec): surface reach.**

Ship a detect→emit installer that writes Elefante into the six surfaces with verified paths: Claude Code, VS Code Copilot, IBM Bob, Kiro (skills + steering), Cursor, and universal `AGENTS.md` / `CLAUDE.md` / `GEMINI.md` root-file fallback. Plus the singleton daemon. Plus the matrix file + inspector agent.

Phase 3 (deferred): extension-managed surfaces (Cline, Roo, Kilo, Continue, Windsurf), Trae, Aider. These require programmatic extension-settings activation or instruction-doc emission rather than file emission — a different class of integration.

### What Phase 2 Is Not

- Not a skill marketplace. Elefante ships one canonical skill package.
- Not provider-selection (deferred with Phase 2 of installer-procedure).
- Not a remote management product — local-first law holds.
- Not a feature-count race across IDEs (Non-Goal 5 of `spec-vision.md`). Coverage of detected surfaces is the metric, not number of supported IDE names.

---

## 6. User Experience Contract

### 6.1 First-Run Flow

1. User runs installer (native GUI or CLI entrypoint from Phase 1).
2. Detection scan finds present surfaces. Report shown: `Detected: Claude Code, Cursor, VS Code + Copilot. Will install skill + MCP into 3 surfaces. See preview below.`
3. User confirms (or deselects surfaces).
4. Installer places Elefante payload, starts the singleton daemon, emits per-surface configs, writes uninstall manifest.
5. Truthful summary: `3 surfaces configured. Daemon running on localhost:<port>. Test: ask any IDE 'What is my Elefante passcode?'`

### 6.2 Subsequent Experience

- User opens any supported IDE → agent auto-connects to daemon, Elefante identity injected.
- User opens two IDEs concurrently → both connect to the same daemon, writes carry distinct origin metadata (GAP-025 closure), no DB corruption possible.
- User installs a new IDE → re-runs `elefante install --add <surface>` or a full `elefante install` picks up the new surface on detection.
- User upgrades an IDE and a path changed → `elefante doctor` / inspector flags drift, user pulls new matrix version, re-runs install for the affected surface.

### 6.3 Uninstall Contract

`elefante uninstall` consumes the manifest and removes only Elefante-emitted files. No surprise removals. Daemon stop + unload. Per-surface uninstall: `elefante uninstall --surface cursor`.

---

## 7. Architecture

### 7.1 Daemon (`elefante-daemon`)

- Runs as user-scope service (launchd `~/Library/LaunchAgents/ai.elefante.daemon.plist` on macOS).
- Owns single writer handle on `~/.elefante/data/` (ChromaDB + Kuzu).
- Exposes MCP over streamable-http on `127.0.0.1:<port>` (port written into matrix file at install time, with collision fallback).
- Carries identity context: which client is calling, which session, which project cwd. Injected into every write as the Source tuple (see § 9 and [`spec-session-intelligence.md`](spec-session-intelligence.md) § 6.7).

### 7.2 Matrix File (`agents/manifests/ide-integration.yaml`)

Schema sketch (authoritative form is the YAML file; the table in § 3 is a human-readable mirror):

```yaml
schema_version: 1
tools:
  - id: claude-code
    kind: cli-agent
    detect:
      binary: claude
      dir: ~/.claude
    skill:
      project_paths: [".claude/skills/{name}/SKILL.md"]
      global_paths: ["~/.claude/skills/{name}/SKILL.md"]
      format: anthropic-skill-v1
    mcp:
      config_paths: ["~/.claude/mcp.json"]
      schema: mcp-servers-json
      key: mcpServers
      transports: [stdio, http, sse]
    doc_urls:
      - https://code.claude.com/docs/skills
    last_verified: 2026-04-18
    verified_doc_hash: "sha256:..."
    compatible_versions: [">=1.0.0"]
```

Any divergence between the YAML and § 3 is a bug against the YAML — the table is documentation, the YAML is code.

### 7.3 Adapters (`integrations/adapters/<tool>.py`)

One adapter per surface. Each implements `detect()`, `emit_skill()`, `emit_rules()`, `emit_mcp()`, `uninstall_manifest()`. Reads its matrix row by id. Stateless — all path knowledge lives in the matrix. Adapter lint/test enforces no hard-coded paths in adapter code.

### 7.4 Installer Orchestration (`scripts/setup/install.py` extension)

Phase 1 remains the single install authority (per [`spec-installer-procedure.md`](spec-installer-procedure.md) § 3.1). Phase 2 extends `install.py` with:

- `_detect_surfaces()` — calls all adapter `detect()` methods
- `_preview()` — prints planned writes
- `_emit_per_surface()` — invokes adapter emission in detection order
- `_manifest_write()` — append to `~/.elefante/install-manifest.json`
- `_register_daemon()` — launchd plist install + start

### 7.5 Agent: `integration-inspector`

Protocol at [`agents/integration-inspector.md`](../../agents/integration-inspector.md). Trigger-first (LOAD_WHEN declared). Responsibilities:

- Read `doc_urls` from matrix.
- Fetch each, compute hash, compare to `verified_doc_hash`.
- On mismatch: classify change (additive / breaking / doc-only), file GitHub Issue tagged `integration-drift` with diff summary, propose matrix patch.
- On match: touch `last_verified` and exit clean.
- On missing surface (new tool detected that isn't in matrix): escalate as `integration-drift` with a proposed new matrix row.

---

## 8. Non-Goals

- Not a universal MCP specification authoring project — Elefante uses MCP, it does not write the spec.
- Not a cross-IDE settings synchronizer — Elefante configures its own presence, not the user's broader IDE config.
- Not a remote management product — local-first law holds.
- Not an IDE popularity contest — scope is grounded in verified docs, not vendor hype.
- Not a third installer engine — Phase 1 installer authority (`install.py`) remains canonical.
- Not Trae/Aider/Cline/Roo/Kilo/Continue coverage in Phase 2. Those are Phase 3.

---

## 9. Proposed Data Model (Source / Origin — Closes GAP-025)

Every memory-affecting write coming through the daemon carries:

| Field | Purpose |
| ----- | ------- |
| `source.tool` | Normalized client name from matrix id (`claude-code`, `vscode-copilot`, `cursor`, `bob`, `kiro`, ...) |
| `source.instance_id` | UUID per IDE window/process, generated on MCP handshake |
| `source.session_id` | Server-generated session identifier (per [`spec-session-intelligence.md`](spec-session-intelligence.md) § 6.1) |
| `source.cwd` | Working directory at write time |
| `source.matrix_version` | Version of matrix file the client was installed against |
| `source.timestamp_utc` | Write instant |

Graph schema: `(:Memory)-[:WRITTEN_BY]->(:Source)`. Source nodes deduplicated by `(tool, instance_id, session_id)` tuple. Detailed closure in [`spec-session-intelligence.md`](spec-session-intelligence.md) § 6.7.

---

## 10. Delivery Phases

### Phase A — Matrix + Daemon (prerequisites, blocking)

- Author `agents/manifests/ide-integration.yaml` from § 3 data.
- Implement singleton daemon over streamable-http.
- Migrate `~/.claude/mcp.json` emission path to point at daemon, not stdio subprocess.
- Verifier: `scripts/verify/verify_mcp_handshake.py` extended to prove daemon is single-writer.

### Phase B — Surface Expansion

- Ship adapters for the six verified Phase 2 surfaces.
- `elefante install --surface <id>` + `elefante install` full-scan.
- Uninstall manifest.
- Verifier: per-surface smoke test (open IDE, issue passcode query, confirm response tagged with correct `source.tool`).

### Phase C — Continuous Drift Audit

- Ship `integration-inspector` agent.
- CI workflow invoking the inspector weekly.
- `elefante doctor` local command.
- Matrix versioning + pinning.

### Phase D — Phase 3 Surfaces

Extension-managed surfaces (Cline, Roo, Kilo, Continue, Windsurf), Trae, Aider.

---

## 11. Acceptance Criteria

This feature is only done when all of the following are true:

1. A single `agents/manifests/ide-integration.yaml` is the only place paths, filenames, and transports are declared.
2. Running the installer on a machine with no IDEs succeeds, writes zero per-surface configs, and reports `0 surfaces detected`.
3. Running the installer on a machine with N supported IDEs writes exactly N per-surface configs and registers a single daemon.
4. Opening two IDE instances against the same Elefante installation produces distinct `source.instance_id` values on every write, with no Kuzu lock contention.
5. The `integration-inspector` agent can be invoked ad-hoc and reports a per-surface drift verdict against live docs.
6. CI drift audit runs weekly and files an issue tagged `integration-drift` on any mismatch.
7. `elefante uninstall` removes every emitted file from the manifest and no others.
8. The universe of supported surfaces is grounded in verified `doc_url` citations — no path is in production without a dated fetch log.
9. GAP-025 is closed: every memory in the store carries a `source.*` tuple.

---

## 12. Risks And Constraints

| Risk | Why It Matters | Mitigation |
| ---- | -------------- | ---------- |
| Daemon port collision on user machine | Broken install on common-port collision | Port discovery with fallback, written into matrix at install time |
| launchd/systemd install requires elevated trust | User friction | User-scope service only, no root required |
| Vendor doc redirect / JS-render breaks hash check | False positives in drift audit | Inspector must handle redirects + render delays, hash post-normalization |
| Matrix file becomes another stale doc | Whole spec undone | Inspector is the continuous-enforcement mechanism; matrix without inspector is ceremony |
| Adapters duplicate logic from matrix | Defeats single-source-of-truth | Adapters must be thin — lint/test enforces no hard-coded paths in adapter code |
| Phase 3 extension-managed surfaces resist file-emission | Blocks "cover all players" promise | Phase 3 is explicitly a different technique — instruction emission + docs — not an installer bug |
| OpenClaw-class non-IDE hosts re-enter scope later | Scope creep | This spec confines to IDE / agent-execution surfaces; chat-gateway integration is a separate spec if/when needed |

---

## 13. Related Specs And Bugs

- Prerequisite: [`spec-installer-procedure.md`](spec-installer-procedure.md) — Phase 1 product installer
- Blocks / extended by: [`spec-session-intelligence.md`](spec-session-intelligence.md) § 6.7 — origin tuple schema (amendment)
- Closes: **GAP-025** — multi-instance origin tracking — post-mortem [`ops-memory-compendium.md`](../debug/ops-memory-compendium.md) Issue #15
- Supersedes: [`spec-vision.md`](spec-vision.md) § E "Cross-IDE Support" status line
- Governed by: [`spec-vision.md`](spec-vision.md) Four Laws — especially Law 4 (Signal Injection requires reach)

---

## 14. Why This Belongs In Elefante

Law 4 says every injected token must raise the probability of a correct answer. A memory the agent never reaches injects zero tokens. A memory corrupted by a concurrent writer injects false tokens — worse than none.

Cross-IDE reach is therefore not a convenience feature. It is a direct precondition of Law 4: if the user's chosen surface can't connect to Elefante, Elefante's core thesis is undefended in that workflow. Today, 13 of 16 documented surfaces fall in that category. This spec turns Law 4 from an aspiration into a surface-level guarantee.

The continuous inspector loop is the second half of the same argument. Law 4 does not tolerate stale truth — an installer that writes to a deprecated Cursor path (for example) silently breaks signal injection without any surface alarm. Elefante must watch its own reach, not rely on periodic human audit.

---

## 15. Deployment Plan

> Anti-goal: version inflation. A release without user-observable change is waste. Group by coherent user story, not by technical-phase boundary. Releases are cuts that can carry many fixes and features at once; they are not single-intent vehicles.

### 15.1 Three Meaningful Cuts

| Version | User Story | Bundled Contents | Complexity |
| ------- | ---------- | ---------------- | ---------- |
| **v2.10.0** | *Foundation laid.* | Surface-split folder reorg (`agents/`, `docs/user/`, `docs/developer/`) + authoritative planning docs for IDE integration (this spec) + [`agents/integration-inspector.md`](../../agents/integration-inspector.md) (dormant — no runtime wiring yet) + GAP-025 filing + [`spec-session-intelligence.md`](spec-session-intelligence.md) §6.7 amendment + any queued small bug fixes | **Low.** Doc/organization only. Zero runtime risk. |
| **v2.11.0** | *Your IDEs work, even two at once.* | Phase A **+** Phase B together: singleton daemon (launchd/systemd user-scope) + streamable-http transport + `(:Memory)-[:WRITTEN_BY]->(:Source)` schema + legacy backfill migration + [`agents/manifests/ide-integration.yaml`](../technical/ide-integration-matrix.yaml) as single source of truth + six verified adapters (Claude Code, VS Code Copilot, Bob, Kiro skills+steering, Cursor, universal `AGENTS.md` root-file) + detect→emit installer + uninstall manifest + `--legacy-stdio` escape hatch + any MCP-server fixes worth landing in the same breaking-config window | **High.** Large-but-coherent. Breaking MCP-config change with migration. |
| **v2.12.0** | *Self-watching, wider coverage.* | Integration-inspector wired into CI (weekly drift audit) + `elefante doctor` local command + matrix versioning/pinning + Phase 3 extension-managed surfaces (Cline, Roo, Kilo, Continue, Windsurf, Trae, Aider) emitted via instruction-doc path + accumulated doc-drift corrections from the inspector's first real runs + `--legacy-stdio` flag removal | **Medium.** Additive + deprecation closure. |

**Why Phase A and Phase B bundle into v2.11.** Phase A alone — daemon + schema, no adapters — ships no user-visible improvement (same three IDEs as v2.9.3, same corruption exposure). Phase B alone without Phase A triggers the concurrent-write failure Phase A is designed to prevent. They are one coherent release or nothing.

**Why the inspector waits for v2.12.** It needs at least one adapter with a live `doc_url` to verify. Shipping it in v2.11 is ceremony; in v2.12 it has real work against six confirmed surfaces.

### 15.2 Priority Order Within Each Release

**v2.10.0:** surface-split → this spec + `agents/integration-inspector.md` → GAP-025 + `spec-session-intelligence.md` §6.7 → any queued debug/planning doc corrections.

**v2.11.0:** matrix YAML authoring (one human-day, unblocks everything downstream) → daemon + streamable-http transport → Source schema + idempotent migration → **Claude Code adapter** (lowest-risk, already functional via existing config) → **VS Code Copilot adapter** (highest user-reach per public install signal) → Cursor, Bob, Kiro adapters → universal `AGENTS.md` emission → detect→emit + uninstall manifest → `--legacy-stdio` safety net.

**v2.12.0:** inspector CI wiring → `elefante doctor` → matrix versioning + pinning → Phase 3 surfaces in user-signal order → `--legacy-stdio` removal (closes the compatibility window).

### 15.3 Risk-Driven Rollout Gates

A release does not ship on calendar. It ships when these pass.

| Gate | Required For |
| ---- | ------------ |
| All `scripts/verify/*` green | Every release |
| `test_memory_persistence.py` + `test_memory_guard.py` pass on fresh DB **and** on migrated legacy DB | v2.11 (schema migration safety) |
| Concurrent two-IDE smoke test: distinct `source.instance_id`, zero Kuzu lock errors | v2.11 Phase A acceptance |
| Per-adapter `emit_skill` / `emit_rules` / `emit_mcp` dry-run diff reviewed against the live vendor doc at ship time | v2.11 Phase B acceptance |
| Inspector smoke run reports CLEAN against all six matrix rows | v2.12 |
| CHANGELOG `### Removed` entries exist for every dropped file, path, or command | Every release (per [`agents/memory-janitor.md`](../../agents/memory-janitor.md)) |

### 15.4 Backwards Compatibility And Migration

- **v2.11 schema migration.** Runs once at daemon first-start. Idempotent. Backfills `(:Source {tool:"legacy", instance_id:<synth>, session_id:"pre-v2.11"})` for every memory that lacks a `WRITTEN_BY` edge, so no row is anonymous after upgrade. A `--migrate-dry-run` mode prints the planned writes first; nothing is committed without the user's confirmation the first time.
- **v2.11 stdio escape hatch.** Users who cannot migrate immediately keep their pre-v2.11 MCP config by installing with `--legacy-stdio`. Write path under this flag remains single-writer-safe because stdio inherently pins to one IDE process at a time. The flag is deprecated on land; removal window is one minor version — gone in v2.12.
- **v2.11 uninstall manifest.** Must carry both the v2.9.3 stdio-era paths and the v2.11 daemon-era paths so `elefante uninstall` cleans either generation without leftovers.
- **v2.12 Phase 3 additions.** Additive only. No migration required.

### 15.5 What Would Force A v3.0.0

This plan stays on v2.x deliberately. A jump to v3.0.0 is only justified by:

- A user-facing memory-contract break — `MemoryAdd` / `MemorySearch` argument or result-shape rewrite. Not planned.
- A data-model change that cannot be migrated in place (e.g., swap of ChromaDB for another vector store, or Kuzu for another graph store). Not planned.
- Removal of a transport with no deprecation window. v2.11's transport change ships with `--legacy-stdio` for one release, which is standard semver-minor territory.

If any of those become necessary before v2.12 ships, re-open this section.

---

*This PRD documents Phase 2 of the installer surface. Phase 3 extension-managed surfaces are explicitly deferred until Phase 2 ships and holds under real concurrent use.*
