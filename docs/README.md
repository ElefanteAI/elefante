# Elefante User Documentation

> **v2.14.0** · Published user documentation.
> Published package: 18 tools, 2 prompts, including verified Recover.

This index covers the released customer product: installation, configuration,
operation, and public behavior. Developer plans, experiments, release mechanics,
postmortems, and internal evaluation are maintained outside this user surface.

## Start here

| Goal | Guide |
|---|---|
| Install, upgrade, repair, or uninstall | [Install Elefante](how-to/install.md) |
| Connect an IDE or CLI agent | [Configure a host](how-to/configure-ide.md) |
| Verify the MCP service manually | [Run the MCP server](how-to/run-mcp-server.md) |
| Understand and manage Elefante Home | [Complete dashboard guide](how-to/view-dashboard.html) |
| Back up or restore local data | [Backup and rollback](how-to/rollback.md) |

Released compatible adapters cover VS Code, Cursor, Kiro, Gemini CLI, Claude
Code, Codex, OpenClaw, Zed, and Continue. Compatible means Elefante owns the
adapter and contract tests; it does not mean vendor certification. See
[Configure a host](how-to/configure-ide.md) for preview and community tiers.

## Reference: what the product is

| Document | Contract |
|---|---|
| [Architecture](reference/architecture.md) | Local daemon, MCP transports, SQLite vectors, Kuzu graph, dashboard, and optional intelligence ledgers |
| [Tools and prompts](reference/tools.md) | Current source MCP surface (18 tools, 2 prompts), release boundary, parameters, results, and safety rules |
| [Memory schema](reference/memory-schema.md) | Classification, provenance, governance, lifecycle, conflicts, and local media attachments |
| [Scoring](reference/scoring.md) | Behavioral vitality and five-signal retrieval scoring |
| [Ingestion](reference/ingestion.md) | Search-before-write, validation, persistence, graph links, and ETL |
| [Dashboard snapshot](reference/dashboard-snapshot.md) | Redacted snapshot plus bounded local Home-control contract |
| [Token Intelligence](reference/token-intelligence.md) | Local response estimates and the boundary with provider-actual Session Intelligence |

## How-to: what to do

| Document | Procedure |
|---|---|
| [Install Elefante](how-to/install.md) | Customer installation, checksum verification, health proof, repair, upgrade, and uninstall |
| [Configure a host](how-to/configure-ide.md) | Supported, preview, and community host paths |
| [Run the MCP server](how-to/run-mcp-server.md) | Manual startup and handshake verification |
| [Complete dashboard guide](how-to/view-dashboard.html) | Every Home state, view, score, control, receipt, safety boundary, and troubleshooting path |
| [Restart](how-to/restart.md) | Graceful restart and lock-safe recovery |
| [Backup and rollback](how-to/rollback.md) | Checksummed binary backup and restore |
| [Docker](how-to/docker.md) | Loopback-safe container operation |
| [Kuzu troubleshooting](how-to/kuzu-troubleshooting.md) | Graph locking, reserved words, and recovery |
| [Agent handoff](how-to/agent-handoff.md) | Connect an existing MCP-capable agent |

## Explanation: why it works this way

| Document | Concept |
|---|---|
| [Product vision](explanation/vision.md) | Persistent memory boundary, Four Laws, local-first trust model, and agent-loop role |

## Documentation boundary

- **User documentation** states only the released customer contract.
- **Developer documentation** begins at [the repository entrypoint](../AGENTS.md).
- Source and tagged artifacts are authoritative. If documentation disagrees
  with executable behavior, report the mismatch; do not silently reinterpret it.
