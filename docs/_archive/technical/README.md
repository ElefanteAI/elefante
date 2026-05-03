# Technical Documentation

**Elefante v2.9.3** · 18 docs · 3 prefixes

---

## Naming Convention

| Prefix | Meaning | Authority |
|--------|---------|-----------|
| `spec-` | What the system IS. Normative. Change requires the embedded verification and closure process. | 1.0 |
| `ops-` | How to DO things. Procedural. | — |
| `dev-` | How to BUILD things. Contributor process. | 1.0 |

---

## Quick Start

1. **Install**: [`ops-installation.md`](ops-installation.md)
2. **Understand**: [`spec-architecture.md`](spec-architecture.md)
3. **Use the API**: [`spec-tools.md`](spec-tools.md)
4. **Dashboard**: [`ops-dashboard.md`](ops-dashboard.md)

---

## Specifications (`spec-`)

| File | Content |
|------|---------|
| [`spec-architecture.md`](spec-architecture.md) | System design, triple-layer brain, specification/directive retrieval workflow |
| [`spec-tools.md`](spec-tools.md) | API reference — 20 MCP tools + 2 prompts |
| [`spec-ingestion.md`](spec-ingestion.md) | 5-step pipeline (Extract → Classify → Integrity → Write → Reinforce) |
| [`spec-scoring.md`](spec-scoring.md) | Temporal decay, reinforcement, 4-factor scoring formula |
| [`spec-memory-schema.md`](spec-memory-schema.md) | V4 cognitive fields + V5 knowledge topology |
| [`spec-memory-identity.md`](spec-memory-identity.md) | Memory identity contract: `namespace` + `canonical_key` as first-class schema fields (DRAFT) |
| [`spec-dashboard-snapshot.md`](spec-dashboard-snapshot.md) | Snapshot JSON schema for dashboard |
| [`spec-self-protocol.md`](spec-self-protocol.md) | Whole-system MCP self-protocol verification contract |
| [`spec-token-intelligence.md`](spec-token-intelligence.md) | Token intelligence layer (TOKEN_STATS, type budgets, density warnings) — shipped v2.5.0 |

## Operations (`ops-`)

| File | Content |
|------|---------|
| [`ops-installation.md`](ops-installation.md) | Full install guide + Python version details |
| [`ops-ide-configuration.md`](ops-ide-configuration.md) | MCP config for VS Code, Cursor, Bob, Antigravity |
| [`ops-mcp-server.md`](ops-mcp-server.md) | Server startup, handshake, troubleshooting |
| [`ops-dashboard.md`](ops-dashboard.md) | Dashboard launch and verification |
| [`ops-restart.md`](ops-restart.md) | Graceful restart, lock cleanup, force-kill |
| [`ops-rollback.md`](ops-rollback.md) | Backup and restore |
| [`ops-docker.md`](ops-docker.md) | Docker deployment |
| [`ops-kuzu.md`](ops-kuzu.md) | Kuzu reserved words, locking, troubleshooting |
| [`ops-agent-handoff.md`](ops-agent-handoff.md) | Agent Zero / autonomous agent integration |

## Development (`dev-`)

| File | Content |
|------|---------|
| [`../../agents/orchestrator.md`](../../agents/orchestrator.md) | **THE ORCHESTRATOR**: Single operational authority for agents building Elefante |
| [`dev-etiquette.md`](dev-etiquette.md) | **SPECIFICATION**: Feature closure (clean, docs, version) |

---

**Last Updated**: 2026-05-02
