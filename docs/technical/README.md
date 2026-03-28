# Technical Documentation Index

**Status**: Production (v2.2.2)  
**Purpose**: Complete technical reference for Elefante AI Memory System

---

## Quick Start

1. **New Users**: Start with [`installation.md`](installation.md)
2. **Understanding the System**: Read [`architecture.md`](architecture.md)
3. **Using the API**: See [`usage.md`](usage.md)
4. **Visual Dashboard**: Check [`dashboard-startup.md`](dashboard-startup.md)

---

## Documentation Map

### Installation & Setup (START HERE)

| File                                                               | Purpose                                                                |
| ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| [`python-version-requirements.md`](python-version-requirements.md) | **MANDATORY: Python 3.11 locking**                                     |
| [`installation.md`](installation.md)                               | Full installation guide                                                |
| [`ide-mcp-configuration.md`](ide-mcp-configuration.md)             | **Authoritative: MCP config for VS Code / Cursor / Bob / Antigravity** |

### Running Elefante

| File                                                 | Purpose                                             | Status |
| ---------------------------------------------------- | --------------------------------------------------- | ------ |
| [`mcp-server-startup.md`](mcp-server-startup.md)     | **Start MCP server, verification, troubleshooting** | NEW    |
| [`dashboard-startup.md`](dashboard-startup.md)       | **Start Dashboard, verification, troubleshooting**  | NEW    |
| [`kuzu-lock-monitoring.md`](kuzu-lock-monitoring.md) | **Prevent single-writer lock deadlocks**            | NEW    |

### Release Safety

| File                         | Purpose                        |
| ---------------------------- | ------------------------------ |
| [`rollback.md`](rollback.md) | Backup and rollback procedures |

### Core System

| File                                 | Purpose                           |
| ------------------------------------ | --------------------------------- |
| [`architecture.md`](architecture.md) | System design, triple-layer brain |
| [`usage.md`](usage.md)               | API reference, MCP tools          |

### Development Process

| File                                                                       | Purpose                                                                  |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| [`sdd-development-protocol.md`](sdd-development-protocol.md)               | **SDD protocol — human reference (enforcement is native via Directives + pre-commit hook)** |
| [`second-brain-protocols.md`](second-brain-protocols.md)                   | Hierarchical agent protocols for cognitive continuity                    |

### Memory Intelligence

| File                                                             | Purpose                                                          | Status                               |
| ---------------------------------------------------------------- | ---------------------------------------------------------------- | ------------------------------------ |
| [`temporal-memory-decay.md`](temporal-memory-decay.md)           | Access-based reinforcement, decay over time                      | Implemented                          |
| `memory-schema-v4.md`                                            | Canonical keys, versioning, namespaces (prod/test), TTL          | Archived (`docs/archive/technical/`) |
| [`memory-schema-v4-cognitive.md`](memory-schema-v4-cognitive.md) | V4 Cognitive Retrieval: concepts, surfaces_when, authority_score | Production                           |
| [`memory-schema-v5-topology.md`](memory-schema-v5-topology.md)   | Rings/topics/types topology fields for dashboard                 | Production                           |

### Database

| File                                               | Purpose                             |
| -------------------------------------------------- | ----------------------------------- |
| [`kuzu-best-practices.md`](kuzu-best-practices.md) | Reserved words, safe property names |

---

## What's Implemented vs Planned

| Feature                                                         | Status                                                                                                                      | Notes                                                                   |
| --------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Dual Storage (ChromaDB + Kuzu)                                  |                                                                                                                             | Production                                                              |
| MCP Server (20 tools + 2 prompts)                               |                                                                                                                             | Production                                                              |
| [`copilot-instructions`](../../.github/copilot-instructions.md) | Agent behavior bootstrap + Tool Response Contract (`MANDATORY_PROTOCOLS_READ_THIS_FIRST`, `DIRECTIVES`, `RELEVANT_CONTEXT`) | Production                                                              |
| Directive System (`src/core/directive_store.py`)                | Always-injected behavioral constraints, independent of memory retrieval                                                     | v2.1.0                                                                  |
| Actionable Integration Header                                   | Hardcoded system prompt injected into MCP context to force agent compliance                                                 | v2.1.2                                                                  |
| Null-Stripping Payload Compression                              | Aggressive JSON compression removing nulls and empty values                                                                 | v2.1.2                                                                  |
| Transaction-Scoped Locking                                      |                                                                                                                             | v1.1.0 (replaced session-based locks)                                   |
| **Compliance Gate**                                             |                                                                                                                             | **v1.6.0 (search-before-write enforcement)**                            |
| Auto-Inject Pitfalls                                            |                                                                                                                             | v1.0.1                                                                  |
| Cognitive Analysis (emotions, intent)                           |                                                                                                                             | Agent-managed (passed via tool inputs)                                  |
| Temporal Decay                                                  |                                                                                                                             | Production                                                              |
| Entity/Relationship Extraction                                  |                                                                                                                             | Agent-managed (provided entities/relationships; no internal extraction) |
| 3-Level Taxonomy Auto-Classification                            |                                                                                                                             | Schema exists; agent can supply domain/category                         |
| Smart UPDATE (merge)                                            |                                                                                                                             | Planned for v1.2.0                                                      |
| Dashboard UX                                                    |                                                                                                                             | v2.0.0 (Overview, Memories, Explore tabs)                               |

---

## Related Directories

- [`../planning/`](../planning/) - Future roadmap
- [`../debug/`](../debug/) - Neural Registers (lessons from failures)
- [`../archive/`](../archive/) - Historical logs

---

**Version**: 2.2.0  
**Last Updated**: 2026-03-19
