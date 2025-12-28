# Elefante Documentation

## Overview

Complete documentation index for Elefante AI Memory System v1.1.0.

---

## Quick Navigation


| I want to... | Go to... |
|--------------|----------|
| Install Elefante | [`technical/installation.md`](technical/installation.md) |
| Configure MCP in my IDE | [`technical/ide-mcp-configuration.md`](technical/ide-mcp-configuration.md) |
| Understand the system | [`technical/architecture.md`](technical/architecture.md) |
| Use the MCP tools | [`technical/usage.md`](technical/usage.md) |
| Open the dashboard | [`technical/dashboard.md`](technical/dashboard.md) |
| Follow agent/developer rules | [`technical/developer-etiquette.md`](technical/developer-etiquette.md) |
| Learn from failures | [`debug/`](debug/) - **Neural Registers** |
| See what's next | [`planning/roadmap.md`](planning/roadmap.md) |

---

## Documentation Structure

### [`technical/`](technical/) - Production Documentation

**"How Things Work Now"** - Complete technical reference for using Elefante

**Core Documentation**:

- [`architecture.md`](technical/architecture.md) - System design & triple-layer architecture
- [`cognitive-memory-model.md`](technical/cognitive-memory-model.md) - AI memory model
- [`installation.md`](technical/installation.md) - Installation guide
- [`usage.md`](technical/usage.md) - **Complete API reference (15 MCP tools)**
- [`dashboard.md`](technical/dashboard.md) - Visual knowledge graph guide

**Advanced Documentation**:

- [`installation-safeguards.md`](technical/installation-safeguards.md) - Automated safeguards
- [`kuzu-best-practices.md`](technical/kuzu-best-practices.md) - Database best practices
- [`memory-schema-v3.md`](technical/memory-schema-v3.md) - Current memory schema
- [`memory-schema-v4.md`](technical/memory-schema-v4.md) - Proposed: canonical keys, versioning, test isolation
- [`memory-schema-v5-topology.md`](technical/memory-schema-v5-topology.md) - Rings/topics/types topology
- [`temporal-memory-decay.md`](technical/temporal-memory-decay.md) - Memory decay algorithm

**See**: [`technical/README.md`](technical/README.md) for complete index

---

### [`debug/`](debug/) - Neural Registers (System Immunity)

**"Lessons from Failures"** - Immutable laws extracted from debugging sessions

**Master Neural Registers** (5 registers):

- [`installation-neural-register.md`](debug/installation-neural-register.md) - Installation failure laws
- [`database-neural-register.md`](debug/database-neural-register.md) - Database failure laws
- [`dashboard-neural-register.md`](debug/dashboard-neural-register.md) - Dashboard failure laws
- [`mcp-code-neural-register.md`](debug/mcp-code-neural-register.md) - MCP protocol failure laws
- [`memory-neural-register.md`](debug/memory-neural-register.md) - Memory system failure laws

**Source Documents by Topic**:

- **[`installation/`](debug/installation/)** (1 file) - Installation troubleshooting
- **[`dashboard/`](debug/dashboard/)** (1 file) - Dashboard debugging
- **[`database/`](debug/database/)** (1 file) - Database issues
- **[`memory/`](debug/memory/)** (1 file) - Memory system debugging
- **[`general/`](debug/general/)** (1 file) - Cross-cutting concerns

**See**: [`debug/README.md`](debug/README.md) for complete index

---

### [`planning/`](planning/) - Strategic Roadmaps

**"What We Will Build"** - Future plans and strategic direction

**Active Roadmaps**:

- [`roadmap.md`](planning/roadmap.md) - Main development roadmap
- [`dashboard-improvement-roadmap.md`](planning/dashboard-improvement-roadmap.md) - Dashboard enhancements
- [`sprint2-knowledge-topology-plan.md`](planning/sprint2-knowledge-topology-plan.md) - Knowledge graph design

**See**: [`planning/README.md`](planning/README.md) for complete index

---

### [`archive/`](archive/) - Historical Documentation

**"What Happened"** - Preserved historical documents and session logs

**Structure**:

- `historical/` - Session logs, completed task lists
- `releases/` - Version changelog notes
- `raw_logs/` - Raw installation logs

**See**: [`archive/README.md`](archive/README.md) for complete index

---

## MCP Tools Reference

Elefante provides **15 MCP tools** for AI agents:


| Tool | Purpose |
|------|---------|
| `elefanteMemoryAdd` | Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY) |
| `elefanteMemorySearch` | Hybrid search (semantic + structured + context) |
| `elefanteGraphQuery` | Execute Cypher queries on knowledge graph |
| `elefanteContextGet` | Get comprehensive session context |
| `elefanteGraphEntityCreate` | Create nodes in knowledge graph |
| `elefanteGraphRelationshipCreate` | Link entities with relationships |
| `elefanteSessionsList` | Browse past sessions with summaries |
| `elefanteSystemStatusGet` | System status + lock info + database health |
| `elefanteMemoryConsolidate` | Deterministic cleanup (canonicalize, quarantine tests, mark duplicates) |
| `elefanteMemoryListAll` | Export/inspect all memories (no filtering) |
| `elefanteDashboardOpen` | Open dashboard (optionally refresh snapshot) |
| `elefanteGraphConnect` | Upsert entities + create relationships in one call |
| `elefanteMemoryMigrateToV3` | Admin schema migration to V3 |
| `elefanteSystemEnable` | *(v1.1.0: No-op)* Backward compatibility shim |
| `elefanteSystemDisable` | *(v1.1.0: No-op)* Backward compatibility shim |

**Complete API reference**: [`technical/usage.md`](technical/usage.md)

---

## Documentation by Use Case

### "I'm new to Elefante"

1. Read [`../README.md`](../README.md) - High-level overview
2. Follow [`technical/installation.md`](technical/installation.md) - Install
3. Explore [`technical/dashboard.md`](technical/dashboard.md) - Visual interface
4. Review [`technical/usage.md`](technical/usage.md) - Complete API reference

### "I want to use the API"

1. Start with [`technical/usage.md`](technical/usage.md) - Complete API reference
2. Review [`technical/architecture.md`](technical/architecture.md) - Understand the system
3. Check [`technical/cognitive-memory-model.md`](technical/cognitive-memory-model.md) - Memory intelligence

### "I'm having problems"

1. Check **Neural Registers** in [`debug/`](debug/) - Learn from past failures
2. Review [`debug/installation/never-again-guide.md`](debug/installation/never-again-guide.md) - Installation help
3. Search [`debug/`](debug/) by topic (installation, dashboard, database, memory)

### "I want to contribute"

1. Read [`../CONTRIBUTING.md`](../CONTRIBUTING.md) - Guidelines
2. Check [`planning/roadmap.md`](planning/roadmap.md) - Development roadmap

---

## Current Development Status

**Version**: v1.4.0 (Production)  
**Next**: v1.5.0 - Enhanced Graph Traversal

**v1.1.0 Features** (see [CHANGELOG.md](../CHANGELOG.md)):

- Transaction-scoped locking (multi-IDE safety without deadlocks)
- Auto-expiry of stale locks (no more 12-day orphan locks!)
- Backward compatible `enable()`/`disable()` shims


**Active Roadmap**: [`planning/roadmap.md`](planning/roadmap.md)

---

## Neural Register Architecture

**What are Neural Registers?**  
Immutable "Laws" extracted from debugging sessions - the system's immune memory.

**The 5 Master Registers**:

1. **Installation** - Pre-flight checks, configuration hierarchy, version migration
2. **Database** - Reserved words, single-writer locks, schema validation
3. **Dashboard** - Data path separation, semantic zoom, force-directed physics
4. **MCP Code** - Type signatures, action verification, error enrichment
5. **Memory** - Export bypass, semantic filtering, temporal decay


**Format**: Laws -> Failure Patterns -> Safeguards -> Metrics -> Source Documents

**Purpose**: Prevent recurring failures by encoding lessons as enforceable rules.

---

## Documentation Statistics

- **Technical Docs**: 10 production documents
- **Neural Registers**: 5 master registers (12+ Laws)
- **Debug Source Docs**: 5 compendium folders
- **Planning Docs**: 3 roadmap documents
- **Archive**: Historical/releases folders
- **MCP Tools**: 15 fully documented

---

## Search Tips

**Looking for specific topics**:

- Installation -> `technical/installation.md` or `debug/installation-neural-register.md`
- API/Tools -> `technical/usage.md` (all 15 tools)
- Architecture -> `technical/architecture.md`
- Dashboard -> `technical/dashboard.md` or `debug/dashboard-neural-register.md`
- Database -> `technical/kuzu-best-practices.md` or `debug/database-neural-register.md`
- Troubleshooting -> `debug/` Neural Registers
- Roadmap -> `planning/roadmap.md`


**File naming convention**: All files use kebab-case (lowercase-with-hyphens)

---

## Documentation Etiquette (LLM Instructions)

> **Purpose:** Prevent LLM amnesia and déjà vu errors when maintaining documentation.

### Before Adding Documentation

```text
1. READ FIRST, THEN WRITE
   - List the target folder contents
   - Read existing files' headers/structure
   - Search for related content with grep
   
2. NEVER DUPLICATE
   - If topic exists -> AUGMENT the existing file
   - If file is outdated -> UPDATE in place
   - Only create new files for genuinely NEW topics

3. KNOW YOUR FOLDERS
   docs/
   ├── technical/     # HOW things work NOW (production docs)
   ├── debug/         # WHAT WENT WRONG (Neural Registers + sources)
   ├── planning/      # WHAT WE WILL BUILD (roadmaps)
   └── archive/       # HISTORICAL (superseded, outdated)
```

### When to Archive vs Delete vs Update

| Scenario | Action |
|----------|--------|
| Doc is outdated but has historical value | Move to `archive/` with date suffix |
| Doc is superseded by Neural Register | Move to `archive/`, update Register |
| Doc has wrong info | UPDATE in place, don't create new |
| Point-in-time status (e.g., "current-status-2025-11-27") | Archive after issue resolved |
| Protocol evolved (v1 -> v2 -> v3 -> FINAL) | Keep FINAL, archive versions |

### Documentation Update Checklist

```text
[ ] 1. Searched for existing docs on this topic
[ ] 2. Read relevant Neural Register (if debug-related)
[ ] 3. Checked archive to avoid resurrecting old content
[ ] 4. Updated ONE file (not created duplicate)
[ ] 5. Updated README index if structure changed
[ ] 6. Verified links still work
```

### Neural Register Update Process

When a significant failure occurs:

1. **Document immediately** in appropriate `debug/{topic}/` file
2. **Extract laws** into the corresponding `*_NEURAL_REGISTER.md`
3. **Link source** in the Neural Register's "Source Documents" section
4. **Archive** point-in-time status docs after resolution

### File Naming Convention

```text
# Technical docs: descriptive-name.md
technical/installation.md
technical/kuzu-best-practices.md

# Debug docs: specific-issue-YYYY-MM-DD.md (if date-specific)
debug/dashboard/dashboard-postmortem.md
debug/database/kuzu-reserved-words-issue.md

# Archive: original-name-YYYY-MM-DD.md (preserve origin date)
archive/debug-current-status-2025-11-27.md
archive/protocol-enforcement-v2.md
```

### Anti-Patterns (DON'T DO THIS)

- Creating `new-fix-v2.md` when `fix.md` exists
- Writing the same info in multiple places
- Leaving point-in-time status docs in active folders
- Creating docs without checking Neural Registers first
- Archiving without updating indexes

---

## Maintenance

**Last Updated**: 2025-12-27  
**Documentation Version**: v1.4.0  
**Status**: Complete and up-to-date

**Changes in v1.1.0**:

- Transaction-scoped locking (replaces session-based locks)
- Auto-expiry of stale locks (30 second timeout)
- Multi-IDE safety without deadlocks
- `elefanteSystemEnable`/`elefanteSystemDisable` become no-ops (backward compatible)

**Changes in v1.0.1**:

- Added ELEFANTE_MODE (3 new tools for multi-IDE safety)
- Added Auto-Inject Pitfalls (protocol enforcement)
- Updated tool count to 15
- LAW 5 file hygiene audit completed

**Changes in v1.0.0**:

- Reorganized into technical/debug/planning/archive taxonomy
- Introduced Neural Register architecture
- Standardized kebab-case naming
- Moved historical logs to archive/

**Maintainers**: Elefante Core Team

---

**For the main project overview, see [`../README.md`](../README.md)**
