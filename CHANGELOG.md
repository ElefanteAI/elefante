# Changelog

All notable changes to the Elefante project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2025-12-04

### 🔧 Fixed
- **CRITICAL: Kuzu Reserved Word Bug** - Fixed `properties` field causing runtime errors
  - Root cause: `properties` is reserved in Cypher but valid in SQL schema
  - Solution: Renamed `properties` → `props` in Entity schema
  - Impact: All entity creation operations now work correctly
  - File: `src/core/graph_store.py` (lines 178, 274)

### 📚 Added
- **Comprehensive Example System** - Complete rewrite of examples with generic content
  - `examples/comprehensive_demo.py` (547 lines) - Full system demonstration
    - 8 parts covering memory types, query modes, limitations, workarounds, best practices
    - Real-world code review scenario
    - Production-ready patterns
  - `examples/seed_preferences.py` - Generic user preferences (115 lines)
  - `examples/validate_system.py` - Generic validation with Alex/CloudScale scenario (239 lines)
  - `examples/interactive_demo.py` - Updated with generic examples

### 📖 Documentation
- **Critical Bug Analysis** - `docs/debug/kuzu-reserved-words-issue.md` (329 lines)
  - Complete root cause analysis of Kuzu SQL/Cypher hybrid anomaly
  - Proof of concept tests demonstrating the issue
  - Step-by-step fix with migration path
  - Prevention strategies for future development
- **Best Practices Guide** - `docs/technical/kuzu-best-practices.md` (254 lines)
  - Comprehensive list of Cypher reserved words to avoid
  - Safe alternatives and naming conventions
  - Testing checklist for new properties
  - Common errors and solutions
  - Quick reference for Kuzu operations

### 🧪 Testing
- **Test Scripts** - Verification tools for Kuzu behavior
  - `test_kuzu_create.py` - Proves `properties` is reserved word
  - `test_kuzu_syntax.py` - Confirms Cypher CREATE works, SQL INSERT doesn't
  - `reset_kuzu_schema.py` - Helper for clean database reset

### 🎓 Key Learnings
- Kuzu uses SQL DDL for schema, Cypher DML for operations
- Property names valid in SQL schema can be invalid in Cypher operations
- Reserved words are context-dependent and create semantic traps
- Always test both schema definition AND data operations
- String interpolation more reliable than parameterized queries in Kuzu

### ⚠️ Breaking Changes
- **Database Schema Change** - `properties` field renamed to `props`
- **Migration Required** - Existing databases must be reset and re-initialized
- **Action Required**: Run `python reset_kuzu_schema.py && python scripts/init_databases.py`

### 🔗 Related Issues
- Fixes entity creation failures in graph store
- Resolves "Cannot find property properties for e" error
- Enables all graph operations to work correctly

---

## [1.1.0] - 2025-12-03

### Added
- **11 MCP Tools** - Complete Model Context Protocol integration
  - `addMemory` - Store with intelligent ingestion (NEW/REDUNDANT/RELATED/CONTRADICTORY detection)
  - `searchMemories` - Hybrid search (semantic + structured + context) with query rewriting
  - `queryGraph` - Execute Cypher queries on Kuzu knowledge graph
  - `getContext` - Retrieve comprehensive session context
  - `createEntity` - Create nodes in knowledge graph
  - `createRelationship` - Link entities with relationships
  - `getEpisodes` - Browse past sessions with summaries
  - `getStats` - System health & usage statistics
  - `consolidateMemories` - Merge duplicates & resolve contradictions
  - `listAllMemories` - Export/inspect all memories without filtering
  - `openDashboard` - Launch visual Knowledge Garden UI in browser
- **Dashboard Visualization** - Interactive knowledge graph visualization at http://127.0.0.1:8000
  - Real-time memory graph with force-directed layout
  - Node labels showing truncated memory descriptions
  - Hover tooltips with full content and timestamps
  - Statistics panel showing memory count and episodes
  - Spaces filter for categorizing memories
  - Auto-refresh capability (no server restart needed)
- **Dashboard Documentation** - Comprehensive usage guide in `docs/DASHBOARD.md`
- **Utility Scripts** - Helper scripts for memory management
  - `scripts/utils/add_memories.py` - Batch add memories
  - `scripts/utils/add_debugging_lessons.py` - Add debugging insights
  - `scripts/utils/manual_test_memory_persistence.py` - Manual testing utility
  - `scripts/utils/verify_memories.py` - Memory verification tool
  - `scripts/dashboard/restart_dashboard.bat` - Clean dashboard restart
- **Debug Tools** - Organized debug utilities in `scripts/debug/`
  - Database repair and inspection tools
  - Kuzu lock management utilities
- **Integration Tests** - Dashboard and memory persistence tests in `tests/integration/`
- **Debug Documentation** - Post-mortem analysis in `DEBUG/DASHBOARD_DEBUGGING_POSTMORTEM.md`

### Fixed
- **Kuzu 0.11.x Compatibility** - Fixed database initialization for Kuzu 0.11.0+
  - Changed from directory-based to single-file database format
  - Fixed `buffer_pool_size` parameter parsing (string to bytes conversion)
  - Added automatic backup and migration for existing databases
- **Dashboard Stats Display** - Fixed memory count showing 0 despite having memories
  - Corrected API response path from `stats.total_memories` to `stats.vector_store.total_memories`
  - Updated `App.tsx` line 36 to read nested response structure
- **Graph Node Labels** - Fixed unlabeled memory nodes in visualization
  - Added default labels showing first 3 words of description
  - Implemented hover tooltips with full content
  - Modified `GraphCanvas.tsx` to extract and display node properties
- **Browser Caching Issues** - Documented proper cache clearing procedures
  - Added hard refresh instructions (Ctrl+Shift+R)
  - Created restart utility for clean server restarts
  - Updated troubleshooting guide

### Changed
- **Repository Organization** - Major cleanup for production release
  - Removed 9 development debug scripts from root directory
  - Moved 2 utility scripts to `scripts/utils/`
  - Moved 7 debug scripts from `DEBUG/` to `scripts/debug/`
  - Archived 5 redundant documentation files to `docs/archive/`
  - DEBUG folder now contains documentation only
- **Documentation Structure** - Improved clarity and navigation
  - Archived redundant MCP troubleshooting docs (3 files)
  - Archived COMPLETE_DOCUMENTATION_INDEX.md (duplicate)
  - Archived ZLCTP_PROJECT_DOCUMENTATION.md (overlaps README)
  - Created single source of truth for each topic
  - Added cross-references between related docs
- **.gitignore Updates** - Enhanced exclusion patterns
  - Added cleanup and planning artifacts
  - Added session notes patterns
  - Added `*.log` files
  - Added test artifacts (`.pytest_cache/`, `.coverage`)
  - Added dashboard build artifacts
  - Added database backups and temporary files

### Improved
- **Error Handling** - Better error messages and logging
  - Added traceback output in dashboard server
  - Improved Kuzu initialization error messages
  - Enhanced memory addition error reporting
- **Testing Methodology** - Established end-to-end testing protocol
  - Always verify complete user experience before claiming success
  - Account for browser caching in web application testing
  - Test data flow from database through API to frontend
  - Wait for user confirmation before proceeding
- **Code Quality** - Enforced clean codebase standards
  - No leftover test files in repository
  - No temporary files or artifacts
  - Proper cleanup after testing
  - Minimal, purposeful files only

## [Unreleased]

### Planned (v1.2.0)
- **Advanced Memory Intelligence Pipeline**
  - Enhanced LLM extraction (deeper semantic understanding)
  - Smart UPDATE (intelligent merge logic)
  - Smart EXTEND (automatic relationship discovery)
- Performance optimizations for large memory sets
- Enhanced dashboard filtering and search capabilities

### Added
- **Dashboard Visualization** - Interactive knowledge graph visualization at http://127.0.0.1:8000
  - Real-time memory graph with force-directed layout
  - Node labels showing truncated memory descriptions
  - Hover tooltips with full content and timestamps
  - Statistics panel showing memory count and episodes
  - Spaces filter for categorizing memories
  - Auto-refresh capability (no server restart needed)
- **Dashboard Documentation** - Comprehensive usage guide in `docs/DASHBOARD.md`
- **Utility Scripts** - Helper scripts for memory management
  - `scripts/utils/add_memories.py` - Batch add memories
  - `scripts/utils/add_debugging_lessons.py` - Add debugging insights
  - `scripts/dashboard/restart_dashboard.bat` - Clean dashboard restart
- **Integration Tests** - Dashboard and memory persistence tests in `tests/integration/`
- **Debug Documentation** - Post-mortem analysis in `DEBUG/DASHBOARD_DEBUGGING_POSTMORTEM.md`

### Fixed
- **Kuzu 0.11.x Compatibility** - Fixed database initialization for Kuzu 0.11.0+
  - Changed from directory-based to single-file database format
  - Fixed `buffer_pool_size` parameter parsing (string to bytes conversion)
  - Added automatic backup and migration for existing databases
- **Dashboard Stats Display** - Fixed memory count showing 0 despite having memories
  - Corrected API response path from `stats.total_memories` to `stats.vector_store.total_memories`
  - Updated `App.tsx` line 36 to read nested response structure
- **Graph Node Labels** - Fixed unlabeled memory nodes in visualization
  - Added default labels showing first 3 words of description
  - Implemented hover tooltips with full content
  - Modified `GraphCanvas.tsx` to extract and display node properties
- **Browser Caching Issues** - Documented proper cache clearing procedures
  - Added hard refresh instructions (Ctrl+Shift+R)
  - Created restart utility for clean server restarts
  - Updated troubleshooting guide

### Changed
- **Repository Organization** - Cleaned up file structure
  - Moved redundant installation docs to `docs/archive/`
  - Relocated utility scripts to `scripts/utils/`
  - Moved test files to `tests/integration/`
  - Consolidated dashboard docs to `docs/DASHBOARD.md`
- **Documentation Structure** - Improved clarity and navigation
  - Archived 7 redundant installation reports
  - Created single source of truth for each topic
  - Added cross-references between related docs
- **.gitignore Updates** - Enhanced exclusion patterns
  - Added `*.log` files
  - Added test artifacts (`.pytest_cache/`, `.coverage`)
  - Added dashboard build artifacts
  - Added database backups and temporary files

### Improved
- **Error Handling** - Better error messages and logging
  - Added traceback output in dashboard server
  - Improved Kuzu initialization error messages
  - Enhanced memory addition error reporting
- **Testing Methodology** - Established end-to-end testing protocol
  - Always verify complete user experience before claiming success
  - Account for browser caching in web application testing
  - Test data flow from database through API to frontend
  - Wait for user confirmation before proceeding

## [1.0.0] - 2024-11-XX (Previous Release)

### Added
- Initial release with core memory system
- ChromaDB vector store integration
- Kuzu knowledge graph integration
- MCP server implementation
- Basic CLI tools
- Comprehensive test suite (73+ tests)
- Installation scripts (install.bat, install.sh)
- Documentation suite

### Features
- Semantic memory search
- Structured knowledge graph queries
- Hybrid search combining vector and graph
- User profile tracking
- Episodic memory (session tracking)
- Automatic entity extraction
- Relationship detection
- Memory consolidation

---

## Version History Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| Unreleased | 2024-11-28 | Dashboard visualization, Kuzu 0.11.x fixes, repository cleanup |
| 1.0.0 | 2024-11-XX | Initial production release |

---

## Migration Notes

### Upgrading to Unreleased (Dashboard Update)

**Database Migration:**
If you have an existing Kuzu database from before 2024-11-28:
1. The system will automatically detect the old format
2. A backup will be created at `~/.elefante/data/kuzu_db_backup_TIMESTAMP`
3. The database will be re-initialized in the new format
4. Your memories in ChromaDB are preserved (no migration needed)

**Dashboard Access:**
```bash
cd Elefante
.venv\Scripts\python.exe -m src.dashboard.server
# Open http://127.0.0.1:8000 in browser
```

**File Relocations:**
If you have custom scripts referencing moved files:
- `add_memories.py` → `scripts/utils/add_memories.py`
- `restart_dashboard.bat` → `scripts/dashboard/restart_dashboard.bat`
- `DASHBOARD_USAGE.md` → `docs/DASHBOARD.md`

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on:
- Reporting bugs
- Suggesting enhancements
- Submitting pull requests
- Code style and testing requirements

---

## Support

For issues or questions:
1. Check [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
2. Review [DEBUG/DASHBOARD_DEBUGGING_POSTMORTEM.md](DEBUG/DASHBOARD_DEBUGGING_POSTMORTEM.md)
3. Search existing GitHub issues
4. Create a new issue with detailed reproduction steps