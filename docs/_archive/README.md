# `docs/_archive/` — Pre-restructure docs/ tree (audit trail)

> **Frozen 2026-05-02.** This folder preserves the OLD `docs/` structure as it existed before the agentic restructure. Do not author new content here. Do not link to files here from active surfaces.

## Why this exists

On 2026-05-02 the `docs/` tree was rebuilt from the ground up. The previous structure mixed four orthogonal organizing axes (audience / type / lifecycle / surface) in eight subfolders, producing endless migration cycles, empty boundary READMEs, tombstones in active dispatch, and persistent drift.

The new structure is Diátaxis-pure (`reference/`, `how-to/`, `explanation/`) with state separated into `workspace/` and loadable protocols in `agents/`. See [`../README.md`](../README.md) for the new shape.

## What's here

The five obsolete README files from the pre-restructure indexes (the old folder structure, with index files preserved verbatim):

| File | What it indexed (pre-restructure) | Where the content moved |
|------|-----------------------------------|--------------------------|
| [`_index-pre-restructure.md`](_index-pre-restructure.md) | Old top-level `docs/README.md` | [`../README.md`](../README.md) (rebuilt) |
| [`developer/README.md`](developer/README.md) | Audience-axis dispatch (developer) | Audience axis dissolved; routing now via [`../README.md`](../README.md) + [`../../AGENTS.md`](../../AGENTS.md) |
| [`user/README.md`](user/README.md) | Audience-axis dispatch (user) | Same. Diátaxis subsumes audience. |
| [`technical/README.md`](technical/README.md) | Mixed-type technical docs index | Split: spec-* → [`../reference/`](../reference/), ops-* → [`../how-to/`](../how-to/), dev-etiquette → [`../how-to/close-a-feature.md`](../how-to/close-a-feature.md) |
| [`planning/README.md`](planning/README.md) | Planning index | Split: vision → [`../explanation/vision.md`](../explanation/vision.md); drafts → [`../../workspace/proposals/`](../../workspace/proposals/) |

## Where every pre-restructure file went

All non-README files were migrated **out** of this archive into the new structure. The migrations:

### Specs (`technical/spec-*` → `reference/`)

| Old path | New path |
|----------|----------|
| `technical/spec-architecture.md` | [`../reference/architecture.md`](../reference/architecture.md) |
| `technical/spec-tools.md` | [`../reference/tools.md`](../reference/tools.md) |
| `technical/spec-scoring.md` | [`../reference/scoring.md`](../reference/scoring.md) |
| `technical/spec-ingestion.md` | [`../reference/ingestion.md`](../reference/ingestion.md) |
| `technical/spec-memory-schema.md` | [`../reference/memory-schema.md`](../reference/memory-schema.md) |
| `technical/spec-memory-identity.md` | [`../reference/memory-identity.md`](../reference/memory-identity.md) |
| `technical/spec-dashboard-snapshot.md` | [`../reference/dashboard-snapshot.md`](../reference/dashboard-snapshot.md) |
| `technical/spec-self-protocol.md` | [`../reference/self-protocol.md`](../reference/self-protocol.md) |
| `technical/spec-token-intelligence.md` | [`../reference/token-intelligence.md`](../reference/token-intelligence.md) |

### Ops (`technical/ops-*` → `how-to/`)

| Old path | New path |
|----------|----------|
| `technical/ops-installation.md` | [`../how-to/install.md`](../how-to/install.md) |
| `technical/ops-ide-configuration.md` | [`../how-to/configure-ide.md`](../how-to/configure-ide.md) |
| `technical/ops-mcp-server.md` | [`../how-to/run-mcp-server.md`](../how-to/run-mcp-server.md) |
| `technical/ops-dashboard.md` | [`../how-to/view-dashboard.html`](../how-to/view-dashboard.html) |
| `technical/ops-restart.md` | [`../how-to/restart.md`](../how-to/restart.md) |
| `technical/ops-rollback.md` | [`../how-to/rollback.md`](../how-to/rollback.md) |
| `technical/ops-docker.md` | [`../how-to/docker.md`](../how-to/docker.md) |
| `technical/ops-kuzu.md` | [`../how-to/kuzu-troubleshooting.md`](../how-to/kuzu-troubleshooting.md) |
| `technical/ops-agent-handoff.md` | [`../how-to/agent-handoff.md`](../how-to/agent-handoff.md) |
| `technical/dev-etiquette.md` | [`../how-to/close-a-feature.md`](../how-to/close-a-feature.md) |

### Vision (`planning/spec-vision.md` → `explanation/`)

| Old path | New path |
|----------|----------|
| `planning/spec-vision.md` | [`../explanation/vision.md`](../explanation/vision.md) |

### Manifests (`technical/*.yaml` → `agents/manifests/`)

| Old path | New path |
|----------|----------|
| `technical/ide-integration-matrix.yaml` | [`../../agents/manifests/ide-integration.yaml`](../../agents/manifests/ide-integration.yaml) |

### State (`debug/*` → `workspace/`)

| Old path | New path |
|----------|----------|
| `debug/README.md` | [`../../workspace/ISSUES.md`](../../workspace/ISSUES.md) |
| `debug/best_practices.md` | [`../../workspace/lessons.md`](../../workspace/lessons.md) |
| `debug/ops-ai-behavior-compendium.md` | [`../../workspace/postmortems/ai-behavior.md`](../../workspace/postmortems/ai-behavior.md) |
| `debug/ops-dashboard-compendium.md` | [`../../workspace/postmortems/dashboard.md`](../../workspace/postmortems/dashboard.md) |
| `debug/ops-database-compendium.md` | [`../../workspace/postmortems/database.md`](../../workspace/postmortems/database.md) |
| `debug/ops-installation-compendium.md` | [`../../workspace/postmortems/installation.md`](../../workspace/postmortems/installation.md) |
| `debug/ops-memory-compendium.md` | [`../../workspace/postmortems/memory.md`](../../workspace/postmortems/memory.md) |

### Drafts (`planning/spec-* / prd-*` → `workspace/proposals/`)

| Old path | New path |
|----------|----------|
| `planning/spec-installer-procedure.md` | [`../../workspace/proposals/installer-procedure.md`](../../workspace/proposals/installer-procedure.md) |
| `planning/spec-ide-integration-surface.md` | [`../../workspace/proposals/ide-integration-surface.md`](../../workspace/proposals/ide-integration-surface.md) |
| `planning/spec-session-intelligence.md` | [`../../workspace/proposals/session-intelligence.md`](../../workspace/proposals/session-intelligence.md) |
| `planning/spec-retrieval-effectiveness.md` | [`../../workspace/proposals/retrieval-effectiveness.md`](../../workspace/proposals/retrieval-effectiveness.md) |
| `planning/spec-surface-split.md` | [`../../workspace/proposals/surface-split.md`](../../workspace/proposals/surface-split.md) |
| `planning/prd-documentation-strategy-protocol.md` | [`../../workspace/proposals/documentation-strategy-protocol.md`](../../workspace/proposals/documentation-strategy-protocol.md) |
| `planning/integrations/agent-zero.md` | [`../../workspace/proposals/integrations/agent-zero.md`](../../workspace/proposals/integrations/agent-zero.md) |

## Constitution merge (separate, also 2026-05-02)

A pre-restructure constitution merge also occurred 2026-05-02 (Phase B of the agentic restructure):

| Old | Now |
|-----|-----|
| `elefante-orchestrator-agent.md` (full constitution, 298 LOC) | merged into [`../../agents/orchestrator.md`](../../agents/orchestrator.md) |
| `developer/dev-doctrine.md` (303-LOC synthesis) | deleted (redundant — see `../../CHANGELOG.md` `### Removed`) |
| `debug/dev-developer-agent.md` (8-LOC tombstone) | deleted |
| `technical/dev-sdd.md` (10-LOC tombstone) | deleted |

## Authority

This archive has **no authority** over current behavior. It is a frozen snapshot. If a future agent finds documentation here that contradicts the current `docs/`, `workspace/`, or `agents/` surfaces — the current surfaces win. The archive exists for migration provenance, not as a fallback truth source.

## Removal policy

This archive may be deleted entirely once:

1. The new structure has been live for ≥1 release cycle without rollback need;
2. CHANGELOG `[2.10.0]` `### Changed` clearly documents the structural move;
3. No external link references `_archive/` paths.

Until then, preserve.
