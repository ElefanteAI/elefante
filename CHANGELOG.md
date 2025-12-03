# Changelog

All notable changes to the Elefante project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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