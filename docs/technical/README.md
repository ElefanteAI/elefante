# Technical Documentation Index

**Status**: ✅ Production (v1.0.1)  
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
| [`installation-safeguards.md`](installation-safeguards.md) | Pre-flight checks & Kuzu compatibility |

### Running Elefante
| File | Purpose | Status |
|------|---------|--------|
| [`mcp-server-startup.md`](mcp-server-startup.md) | **Start MCP server, verification, troubleshooting** | ✅ NEW |
| [`dashboard-startup.md`](dashboard-startup.md) | **Start Dashboard, verification, troubleshooting** | ✅ NEW |
| [`kuzu-lock-monitoring.md`](kuzu-lock-monitoring.md) | **Prevent single-writer lock deadlocks** | ✅ NEW |

### Core System
| File | Purpose |
|------|---------|
| [`architecture.md`](architecture.md) | System design, triple-layer brain |
| [`usage.md`](usage.md) | API reference, MCP tools |
| [`dashboard.md`](dashboard.md) | Legacy dashboard guide (see dashboard-startup.md) |

### Memory Intelligence
| File | Purpose | Status |
|------|---------|--------|
| [`cognitive-memory-model.md`](cognitive-memory-model.md) | LLM extraction of emotions, intent, entities | ✅ Implemented |
| [`temporal-memory-decay.md`](temporal-memory-decay.md) | Access-based reinforcement, decay over time | ✅ Implemented |
| [`memory-schema-v2.md`](memory-schema-v2.md) | Full schema specification | 🟡 Schema exists, auto-classification pending |
| [`v2-schema-simple.md`](v2-schema-simple.md) | Simplified schema explanation | 🟡 Same as above |

### Database
| File | Purpose |
|------|---------|
| [`kuzu-best-practices.md`](kuzu-best-practices.md) | Reserved words, safe property names |
| [`installation-safeguards.md`](installation-safeguards.md) | Pre-flight checks, Kuzu 0.11.x fixes |

---

## What's Implemented vs Planned

| Feature | Status | Notes |
|---------|--------|-------|
| Dual Storage (ChromaDB + Kuzu) | ✅ | Production |
| MCP Server (14 tools) | ✅ | Production |
| ELEFANTE_MODE (Multi-IDE Safety) | ✅ | v1.0.1 |
| Auto-Inject Pitfalls | ✅ | v1.0.1 |
| Cognitive Analysis (emotions, intent) | ✅ | Requires OpenAI API key |
| Temporal Decay | ✅ | Production |
| Entity/Relationship Extraction | ✅ | Production |
| 3-Level Taxonomy Auto-Classification | 🟡 | Schema exists, LLM doesn't auto-detect domain/category |
| Smart UPDATE (merge) | ❌ | Planned for v1.1.0 |
| Dashboard UX | 🟡 | Functional but needs work |

---

## Related Directories

- [`../planning/`](../planning/) - Future roadmap
- [`../debug/`](../debug/) - Neural Registers (lessons from failures)
- [`../archive/`](../archive/) - Historical logs

---

**Version**: 1.0.1  
**Last Updated**: 2025-12-11