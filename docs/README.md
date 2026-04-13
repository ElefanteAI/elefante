# Elefante Documentation

> **v2.2.2** · [Product overview & install](../README.md) · [Agent constitution](../.github/copilot-instructions.md)

---

## Start Here

| Goal | Go to |
|------|-------|
| What is Elefante and where is it going? | [`planning/spec-vision.md`](planning/spec-vision.md) |
| Install and connect to your IDE | [`technical/ops-installation.md`](technical/ops-installation.md) → [`technical/ops-ide-configuration.md`](technical/ops-ide-configuration.md) |
| Full tool reference (21 tools, 2 prompts) | [`technical/spec-tools.md`](technical/spec-tools.md) |
| How behavioral scoring works | [`technical/spec-scoring.md`](technical/spec-scoring.md) |
| System architecture | [`technical/spec-architecture.md`](technical/spec-architecture.md) |

---

## By Topic

### Specifications (`spec-`)

| Doc | Content |
|-----|---------|
| [`technical/spec-tools.md`](technical/spec-tools.md) | Complete MCP tool reference with parameter schemas |
| [`technical/spec-architecture.md`](technical/spec-architecture.md) | System design, triple-layer brain |
| [`technical/spec-scoring.md`](technical/spec-scoring.md) | Scoring formula, decay rates, reinforcement mechanics |
| [`technical/spec-ingestion.md`](technical/spec-ingestion.md) | 5-step ingestion pipeline |
| [`technical/spec-memory-schema.md`](technical/spec-memory-schema.md) | V4 cognitive retrieval + V5 knowledge topology |
| [`technical/spec-dashboard-snapshot.md`](technical/spec-dashboard-snapshot.md) | Snapshot JSON schema |

### Operations (`ops-`)

| Doc | Content |
|-----|---------|
| [`technical/ops-installation.md`](technical/ops-installation.md) | Full installation guide + Python version details |
| [`technical/ops-ide-configuration.md`](technical/ops-ide-configuration.md) | IDE setup (VS Code, Cursor, Windsurf, etc.) |
| [`technical/ops-mcp-server.md`](technical/ops-mcp-server.md) | Manual startup and handshake verification |
| [`technical/ops-restart.md`](technical/ops-restart.md) | Graceful restart, lock cleanup, force-kill |
| [`technical/ops-dashboard.md`](technical/ops-dashboard.md) | Dashboard launch and verification |
| [`technical/ops-docker.md`](technical/ops-docker.md) | Docker deployment |
| [`technical/ops-kuzu.md`](technical/ops-kuzu.md) | Kuzu reserved words, locking, troubleshooting |
| [`technical/ops-rollback.md`](technical/ops-rollback.md) | Backup and restore |
| [`technical/ops-agent-handoff.md`](technical/ops-agent-handoff.md) | Autonomous agent integration |

### Development (`dev-`)

| Doc | Content |
|-----|---------|
| [`technical/dev-etiquette.md`](technical/dev-etiquette.md) | **SPECIFICATION**: Feature closure (clean, docs, version) |
| [`technical/dev-sdd.md`](technical/dev-sdd.md) | Spec-Driven Development gates |

### Debugging

| Doc | Content |
|-----|---------|
| [`debug/`](debug/README.md) | 5 domain compendiums + [Developer Agent protocol](debug/dev-developer-agent.md) |

### Planning

| Doc | Content |
|-----|---------|
| [`planning/spec-vision.md`](planning/spec-vision.md) | What Elefante is, the Four Laws, vision, ideas backlog |
| [`planning/spec-usage-intelligence.md`](planning/spec-usage-intelligence.md) | Usage metrics PRD (backend 80%, frontend 0%) |

### Agent Bootstrap

| Doc | Content |
|-----|---------|
| [`.github/copilot-instructions.md`](../.github/copilot-instructions.md) | Constitution: Four Laws, cardinal sins, tool table, commands |

---

## Contributing

See [`../CONTRIBUTING.md`](../CONTRIBUTING.md). License: [BSL 1.1](../LICENSE) → Apache 2.0 on 2029-02-10.

[Changelog](../CHANGELOG.md) · [GitHub](https://github.com/ElefanteAI/elefante)
