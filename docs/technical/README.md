# Technical Documentation Index

**Status**:  Production (v1.6.2)  
**Purpose**: Complete technical reference for Elefante AI Memory System

---

## Quick Start

1. **New Users**: Start with [`installation.md`](installation.md)
2. **Understanding the System**: Read [`architecture.md`](architecture.md)
3. **Using the API**: See [`usage.md`](usage.md)
4. **Visual Dashboard**: Check [`dashboard.md`](dashboard.md)

---

## Documentation Map

### Installation & Setup (START HERE)

| File | Purpose |
|------|---------|
| [`python-version-requirements.md`](python-version-requirements.md) | **MANDATORY: Python 3.11 locking** |
| [`installation.md`](installation.md) | Full installation guide |
| [`ide-mcp-configuration.md`](ide-mcp-configuration.md) | **Authoritative: MCP config for VS Code / Cursor / Bob / Antigravity** |
| [`installation-safeguards.md`](installation-safeguards.md) | Pre-flight checks & Kuzu compatibility |

### Running Elefante

| File | Purpose | Status |
|------|---------|--------|
| [`mcp-server-startup.md`](mcp-server-startup.md) | **Start MCP server, verification, troubleshooting** |  NEW |
| [`dashboard-startup.md`](dashboard-startup.md) | **Start Dashboard, verification, troubleshooting** |  NEW |
| [`kuzu-lock-monitoring.md`](kuzu-lock-monitoring.md) | **Prevent single-writer lock deadlocks** |  NEW |

### Release Safety

| File | Purpose |
|------|---------|
| [`rollback.md`](rollback.md) | Roll back to the v1.6.0 baseline (code + data) |

### Core System

| File | Purpose |
|------|---------|
| [`architecture.md`](architecture.md) | System design, triple-layer brain |
| [`usage.md`](usage.md) | API reference, MCP tools |
| [`dashboard.md`](dashboard.md) | Legacy dashboard guide (see dashboard-startup.md) |

### Development Process

| File | Purpose |
|------|---------|
| [`second-brain-protocols.md`](second-brain-protocols.md) | Hierarchical agent protocols for cognitive continuity |

### Memory Intelligence

| File | Purpose | Status |
|------|---------|--------|
| [`cognitive-memory-model.md`](cognitive-memory-model.md) | Agent-managed enrichment contract (no internal LLM calls) |  Implemented |
| [`temporal-memory-decay.md`](temporal-memory-decay.md) | Access-based reinforcement, decay over time |  Implemented |
| [`memory-schema-v3.md`](memory-schema-v3.md) | Layer/sublayer taxonomy |  Production |
| [`memory-schema-v4.md`](memory-schema-v4.md) | Canonical keys, versioning, namespaces (prod/test), TTL |  Proposed |
| [`memory-schema-v4-cognitive.md`](memory-schema-v4-cognitive.md) | **V4 Cognitive Retrieval: concepts, surfaces_when, authority_score** |  **Implemented** |
| [`memory-schema-v5-topology.md`](memory-schema-v5-topology.md) | Rings/topics/types topology fields for dashboard |  Draft |

### Database

| File | Purpose |
|------|---------|
| [`kuzu-best-practices.md`](kuzu-best-practices.md) | Reserved words, safe property names |
| [`installation-safeguards.md`](installation-safeguards.md) | Pre-flight checks, Kuzu 0.11.x fixes |

---

## What's Implemented vs Planned

| Feature | Status | Notes |
|---------|--------|-------|
| Dual Storage (ChromaDB + Kuzu) |  | Production |
| MCP Server (18 tools) |  | Production |
| MCP Prompts (2) |  | Production |
| Transaction-Scoped Locking |  | v1.1.0 (replaced session-based locks) |
| **Compliance Gate** |  | **v1.6.0 (search-before-write enforcement)** |
| Auto-Inject Pitfalls |  | v1.0.1 |
| Cognitive Analysis (emotions, intent) |  | Agent-managed (passed via tool inputs) |
| Temporal Decay |  | Production |
| Entity/Relationship Extraction |  | Agent-managed (provided entities/relationships; no internal extraction) |
| 3-Level Taxonomy Auto-Classification |  | Schema exists; agent can supply domain/category |
| Smart UPDATE (merge) |  | Planned for v1.2.0 |
| Dashboard UX |  | Functional but needs work |

---

## Related Directories

- [`../planning/`](../planning/) - Future roadmap
- [`../debug/`](../debug/) - Neural Registers (lessons from failures)
- [`../archive/`](../archive/) - Historical logs

---

**Version**: 1.6.2  
**Last Updated**: 2025-12-28
