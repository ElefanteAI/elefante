# Elefante Documentation

**Complete documentation index for Elefante AI Memory System v1.2.0**

---

## 🚀 Quick Navigation

| I want to... | Go to... |
|--------------|----------|
| Install Elefante | [`technical/installation.md`](technical/installation.md) |
| Understand the system | [`technical/architecture.md`](technical/architecture.md) |
| Use the MCP tools | [`technical/usage.md`](technical/usage.md) |
| Open the dashboard | [`technical/dashboard.md`](technical/dashboard.md) |
| Learn from failures | [`debug/`](debug/) - **Neural Registers** |
| See what's next | [`planning/NEXT_STEPS.md`](planning/NEXT_STEPS.md) |

---

## 📚 Documentation Structure

### [`technical/`](technical/) - Production Documentation
**"How Things Work Now"** - Complete technical reference for using Elefante

**Core Documentation**:
- [`architecture.md`](technical/architecture.md) - System design & triple-layer architecture
- [`cognitive-memory-model.md`](technical/cognitive-memory-model.md) - AI memory model
- [`installation.md`](technical/installation.md) - Installation guide
- [`usage.md`](technical/usage.md) - **Complete API reference (11 MCP tools)**
- [`dashboard.md`](technical/dashboard.md) - Visual knowledge graph guide

**Advanced Documentation**:
- [`installation-safeguards.md`](technical/installation-safeguards.md) - Automated safeguards
- [`kuzu-best-practices.md`](technical/kuzu-best-practices.md) - Database best practices
- [`memory-schema-v2.md`](technical/memory-schema-v2.md) - Database schema
- [`v2-schema-simple.md`](technical/v2-schema-simple.md) - Schema simplified
- [`technical-implementation.md`](technical/technical-implementation.md) - Implementation details
- [`temporal-memory-decay.md`](technical/temporal-memory-decay.md) - Memory decay algorithm
- [`walkthrough.md`](technical/walkthrough.md) - Step-by-step guide

**See**: [`technical/README.md`](technical/README.md) for complete index

---

### [`debug/`](debug/) - Neural Registers (System Immunity)
**"Lessons from Failures"** - Immutable laws extracted from debugging sessions

**🧠 Master Neural Registers** (5 registers):
- [`INSTALLATION_NEURAL_REGISTER.md`](debug/INSTALLATION_NEURAL_REGISTER.md) - Installation failure laws
- [`DATABASE_NEURAL_REGISTER.md`](debug/DATABASE_NEURAL_REGISTER.md) - Database failure laws
- [`DASHBOARD_NEURAL_REGISTER.md`](debug/DASHBOARD_NEURAL_REGISTER.md) - Dashboard failure laws
- [`MCP_CODE_NEURAL_REGISTER.md`](debug/MCP_CODE_NEURAL_REGISTER.md) - MCP protocol failure laws
- [`MEMORY_NEURAL_REGISTER.md`](debug/MEMORY_NEURAL_REGISTER.md) - Memory system failure laws

**Source Documents by Topic**:
- **[`installation/`](debug/installation/)** (6 files) - Installation troubleshooting
- **[`dashboard/`](debug/dashboard/)** (2 files) - Dashboard debugging
- **[`database/`](debug/database/)** (5 files) - Database issues
- **[`memory/`](debug/memory/)** (3 files) - Memory system debugging
- **[`general/`](debug/general/)** (13 files) - Cross-cutting concerns

**See**: [`debug/README.md`](debug/README.md) for complete index

---

### [`planning/`](planning/) - Strategic Roadmaps
**"What We Will Build"** - Future plans and strategic direction

**Active Roadmaps**:
- [`NEXT_STEPS.md`](planning/NEXT_STEPS.md) - Immediate next steps
- [`task-roadmap.md`](planning/task-roadmap.md) - Task breakdown
- [`dashboard-improvement-roadmap.md`](planning/dashboard-improvement-roadmap.md) - Dashboard enhancements
- [`sprint2-knowledge-topology-plan.md`](planning/sprint2-knowledge-topology-plan.md) - Knowledge graph design

**See**: [`planning/README.md`](planning/README.md) for complete index

---

### [`archive/`](archive/) - Historical Documentation
**"What Happened"** - Preserved historical documents and session logs

**Contents**:
- Installation reports from 2025-11-27
- Sprint 26 handoff documents
- Historical troubleshooting logs
- v1.2.0 release notes
- Deployment debug logs

**See**: [`archive/README.md`](archive/README.md) for complete index

---

## 🔌 MCP Tools Reference

Elefante provides **11 MCP tools** for AI agents:

| Tool | Purpose |
|------|---------|
| `addMemory` | Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY) |
| `searchMemories` | Hybrid search (semantic + structured + context) |
| `queryGraph` | Execute Cypher queries on knowledge graph |
| `getContext` | Get comprehensive session context |
| `createEntity` | Create nodes in knowledge graph |
| `createRelationship` | Link entities with relationships |
| `getEpisodes` | Browse past sessions with summaries |
| `getStats` | System health & usage statistics |
| `consolidateMemories` | Merge duplicates & resolve contradictions |
| `listAllMemories` | Export/inspect all memories (no filtering) |
| `openDashboard` | Launch visual Knowledge Garden UI |

**Complete API reference**: [`technical/usage.md`](technical/usage.md)

---

## 📖 Documentation by Use Case

### "I'm new to Elefante"
1. Read [`../README.md`](../README.md) - High-level overview
2. Follow [`technical/installation.md`](technical/installation.md) - Install
3. Try [`technical/walkthrough.md`](technical/walkthrough.md) - Hands-on guide
4. Explore [`technical/dashboard.md`](technical/dashboard.md) - Visual interface

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
2. Check [`planning/task-roadmap.md`](planning/task-roadmap.md) - Active tasks
3. Review [`planning/NEXT_STEPS.md`](planning/NEXT_STEPS.md) - Roadmap
4. See [`../CHANGELOG.md`](../CHANGELOG.md) - Recent changes

---

## 🎯 Current Development Status

**Version**: v1.2.0 (Production)  
**Next**: v1.3.0 - Enhanced Intelligence Pipeline

**Priority Features** (from [`planning/NEXT_STEPS.md`](planning/NEXT_STEPS.md)):
- Enhanced LLM extraction
- Smart UPDATE (merge logic)
- Smart EXTEND (link logic)

**Active Roadmap**: [`planning/task-roadmap.md`](planning/task-roadmap.md)

---

## 🧠 Neural Register Architecture

**What are Neural Registers?**  
Immutable "Laws" extracted from debugging sessions - the system's immune memory.

**The 5 Master Registers**:
1. **Installation** - Pre-flight checks, configuration hierarchy, version migration
2. **Database** - Reserved words, single-writer locks, schema validation
3. **Dashboard** - Data path separation, semantic zoom, force-directed physics
4. **MCP Code** - Type signatures, action verification, error enrichment
5. **Memory** - Export bypass, semantic filtering, temporal decay

**Format**: Laws → Failure Patterns → Safeguards → Metrics → Source Documents

**Purpose**: Prevent recurring failures by encoding lessons as enforceable rules.

---

## 📊 Documentation Statistics

- **Technical Docs**: 13 production documents
- **Neural Registers**: 5 master registers
- **Debug Source Docs**: 29 debugging documents
- **Planning Docs**: 4 roadmap documents
- **Archive**: 19 historical documents
- **Total**: 70+ documents
- **MCP Tools**: 11 fully documented
- **Code Examples**: 100+ across all docs

---

## 🔍 Search Tips

**Looking for specific topics**:
- Installation → `technical/installation.md` or `debug/INSTALLATION_NEURAL_REGISTER.md`
- API/Tools → `technical/usage.md` (all 11 tools)
- Architecture → `technical/architecture.md`
- Dashboard → `technical/dashboard.md` or `debug/DASHBOARD_NEURAL_REGISTER.md`
- Database → `technical/kuzu-best-practices.md` or `debug/DATABASE_NEURAL_REGISTER.md`
- Troubleshooting → `debug/` Neural Registers
- Roadmap → `planning/task-roadmap.md`

**File naming convention**: All files use kebab-case (lowercase-with-hyphens)

---

## 📋 Documentation Etiquette (LLM Instructions)

> **Purpose:** Prevent LLM amnesia and déjà vu errors when maintaining documentation.

### Before Adding Documentation

```
1. READ FIRST, THEN WRITE
   - List the target folder contents
   - Read existing files' headers/structure
   - Search for related content with grep
   
2. NEVER DUPLICATE
   - If topic exists → AUGMENT the existing file
   - If file is outdated → UPDATE in place
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
| Protocol evolved (v1 → v2 → v3 → FINAL) | Keep FINAL, archive versions |

### Documentation Update Checklist

```
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

```
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

❌ Creating `new-fix-v2.md` when `fix.md` exists  
❌ Writing same info in multiple places  
❌ Leaving point-in-time status docs in active folders  
❌ Creating doc without checking Neural Register first  
❌ Archiving without updating indexes  

---

## 📝 Maintenance

**Last Updated**: 2025-12-05  
**Documentation Version**: v1.2.0  
**Status**: ✅ Complete and up-to-date

**Major Changes in v1.2.0**:
- ✅ Introduced Neural Register architecture
- ✅ Reorganized into technical/debug/planning/archive taxonomy
- ✅ Synthesized 29 debug docs into 5 Master Neural Registers
- ✅ Cleaned root directory (34 → 14 files)

**Maintainers**: Elefante Core Team

---

**For the main project overview, see [`../README.md`](../README.md)**