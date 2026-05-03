# Elefante Documentation

> **v2.9.3** · [Product overview & install](../README.md) · [Universal agent entry](../AGENTS.md) · [End-user agent constitution](../.github/copilot-instructions.md) · [Developer workspace](../workspace/PLANNING.md)
>
> **Three-axis navigation:**
> - **Audience:** client-facing → `docs/`; developer-workspace → `../workspace/` ; agents → `../agents/` and `../AGENTS.md`
> - **Content type:** `spec-*` (reference) · `ops-*` (how-to) · `dev-*` (developer process) · debug compendiums (explanation)
> - **Integration target:** in-repo docs (this directory) vs IDE-side integration files (see `technical/ide-integration-matrix.yaml`)

---

## Start Here

| Goal | Go to |
| -------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| What is Elefante and where is it going? | [`planning/spec-vision.md`](planning/spec-vision.md)                                                          |
| What is the current release state?     | [`../workspace/PLANNING.md §2`](../workspace/PLANNING.md) (Active Release v2.10.0 + Resume Verdict) — also mirrored in [`planning/spec-surface-split.md §0`](planning/spec-surface-split.md) |
| Where do all 16 IDE integrations live? | [`technical/ide-integration-matrix.yaml`](technical/ide-integration-matrix.yaml) (machine-readable manifest) |
| Using Elefante as a memory engine      | [`user/README.md`](user/README.md)                                                                            |
| Building or debugging Elefante itself  | [`developer/README.md`](developer/README.md) → [`../agents/orchestrator.md`](../agents/orchestrator.md) |
| Loading an agent protocol              | [`../agents/`](../agents/) — start with [`agents/orchestrator.md`](../agents/orchestrator.md) for build/debug work |
| Install and connect to your IDE        | [`technical/ops-installation.md`](technical/ops-installation.md) → [`technical/ops-ide-configuration.md`](technical/ops-ide-configuration.md) |
| Full tool reference (20 tools, 2 prompts) | [`technical/spec-tools.md`](technical/spec-tools.md)                                                       |
| How behavioral scoring works           | [`technical/spec-scoring.md`](technical/spec-scoring.md)                                                      |
| System architecture                    | [`technical/spec-architecture.md`](technical/spec-architecture.md)                                            |

---

## By Topic

### Specifications (`spec-`)

| Doc | Content |
| ----------------------------------------------- | ---------------------------------------------------- |
| [`technical/spec-tools.md`](technical/spec-tools.md) | Complete MCP tool reference with parameter schemas |
| [`technical/spec-architecture.md`](technical/spec-architecture.md) | System design, triple-layer brain |
| [`technical/spec-scoring.md`](technical/spec-scoring.md) | Scoring formula, decay rates, reinforcement mechanics |
| [`technical/spec-ingestion.md`](technical/spec-ingestion.md) | 5-step ingestion pipeline |
| [`technical/spec-memory-schema.md`](technical/spec-memory-schema.md) | V4 cognitive retrieval + V5 knowledge topology |
| [`technical/spec-dashboard-snapshot.md`](technical/spec-dashboard-snapshot.md) | Snapshot JSON schema |

### Operations (`ops-`)

| Doc | Content |
| ----------------------------------------------------------- | ------------------------------------------------------ |
| [`technical/ops-installation.md`](technical/ops-installation.md) | Full installation guide + Python version details    |
| [`technical/ops-ide-configuration.md`](technical/ops-ide-configuration.md) | IDE setup (VS Code, Cursor, Windsurf, etc.) |
| [`technical/ops-mcp-server.md`](technical/ops-mcp-server.md) | Manual startup and handshake verification            |
| [`technical/ops-restart.md`](technical/ops-restart.md) | Graceful restart, lock cleanup, force-kill              |
| [`technical/ops-dashboard.md`](technical/ops-dashboard.md) | Dashboard launch and verification                    |
| [`technical/ops-docker.md`](technical/ops-docker.md) | Docker deployment                                         |
| [`technical/ops-kuzu.md`](technical/ops-kuzu.md) | Kuzu reserved words, locking, troubleshooting              |
| [`technical/ops-rollback.md`](technical/ops-rollback.md) | Backup and restore                                     |
| [`technical/ops-agent-handoff.md`](technical/ops-agent-handoff.md) | Autonomous agent integration                    |

### Development (`dev-`)

| Doc | Content |
| ----------------------------------------------------- | ----------------------------------------------------------- |
| [`../agents/puppeteer.md`](../agents/puppeteer.md) | **DANGEROUS PRIVILEGED SURFACE**: Retune governing behavior itself. Explicit authorization required. |
| [`../agents/orchestrator.md`](../agents/orchestrator.md) | **THE ORCHESTRATOR**: Single operational authority for agents building Elefante. Read this first. |
| [`technical/dev-etiquette.md`](technical/dev-etiquette.md) | **SPECIFICATION**: Feature closure (clean, docs, version) |

### Debugging

| Doc | Content |
| ------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------- |
| [`debug/`](debug/README.md) | Known Issues tracker, 5 domain compendiums, [best_practices.md](debug/best_practices.md) |
| [`technical/spec-self-protocol.md`](technical/spec-self-protocol.md) | Authoritative isolated MCP self-protocol for proving Elefante is actually running end-to-end |

### Planning

| Doc | Content |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| [`planning/README.md`](planning/README.md) | Directory guide for future-facing specs. Operational learnings and reusable debugging rules belong in `debug/`, not here. |
| [`planning/spec-vision.md`](planning/spec-vision.md) | What Elefante is, the Four Laws, vision, ideas backlog |
| [`planning/spec-surface-split.md`](planning/spec-surface-split.md) | Active release spec for v2.10.0 (additive User/Developer/Agents surface split). §0 carries Execution Status + Resume Snapshot. |
| [`planning/spec-ide-integration-surface.md`](planning/spec-ide-integration-surface.md) | v2.11.0/v2.12.0 plan: cross-IDE skill/rules/MCP distribution, singleton daemon, GAP-025 closure |
| [`planning/spec-installer-procedure.md`](planning/spec-installer-procedure.md) | Draft phase-1 PRD for a downloadable Elefante installer product that wraps the existing installer and removes `git clone` from the end-user flow |
| [`planning/spec-session-intelligence.md`](planning/spec-session-intelligence.md) | Draft PRD for privacy-respecting session, invocation, and usefulness telemetry across MCP clients |
| [`planning/spec-retrieval-effectiveness.md`](planning/spec-retrieval-effectiveness.md) | Per-memory retrieval provenance and helpfulness signal |
| [`planning/prd-documentation-strategy-protocol.md`](planning/prd-documentation-strategy-protocol.md) | Strategy protocol for agent-maintained documentation (audience, loading model, authority, leakage scan) |

### Agent Bootstrap

| Doc | Content |
| --------------------------------------------------------------- | -------------------------------------------------------------- |
| [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) | End-user agent constitution: Four Laws, cardinal sins, tool table, commands |
| [`../agents/orchestrator.md`](../agents/orchestrator.md) | Developer-mode constitution + Documentation Skill (Closed Surface Map, Forbidden Patterns, Pre-write checklist, New-File Test). Read first when building or debugging Elefante itself. |
| [`../agents/`](../agents/) | 11 specialist agents + glossary. `agents/orchestrator.md` is the loadable orchestrator; specialists dispatch by trigger (installer, restarter, memory-janitor, memory-inspector, release-manager, operator, researcher, puppeteer, integration-inspector). |

---

## Contributing

See [`../CONTRIBUTING.md`](../CONTRIBUTING.md). License: [BSL 1.1](../LICENSE) → Apache 2.0 on 2029-02-10.

[Changelog](../CHANGELOG.md) · [GitHub](https://github.com/ElefanteAI/elefante)
