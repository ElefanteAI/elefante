# Elefante Releases

**Versioning:** [Semantic Versioning 2.0.0](https://semver.org/)  
**Format:** MAJOR.MINOR.PATCH

---

## v1.0.0 - 2025-12-05 (Production Baseline)

**Status:** ✅ FUNCTIONAL  
**Tag:** To be created

### What This Version Is
First stable production release after comprehensive cleanup and consolidation.

### Core Functionality
- **MCP Server:** 11 tools operational via stdio
- **ChromaDB:** Vector memory storage (91 memories)
- **Kuzu Graph:** Knowledge graph (49 entities, 19 relationships)
- **Dashboard:** React/Vite visualization on port 8010

### Documentation State
- 5 Neural Registers (debug knowledge)
- 5 Domain Compendiums (issue tracking)
- Clean archive (only raw forensic logs)
- Single source of truth per topic

### Breaking Changes from Pre-1.0
- Removed 35 redundant archive files
- Consolidated all debug knowledge into Neural Registers
- Moved `export_all_memories.py` to `scripts/`
- Deleted duplicate `NEXT_STEPS.md` from root
- Established file hygiene policy

### Known Limitations
- MCP `searchMemories` occasionally returns empty (ChromaDB init timing)
- Dashboard requires hard refresh after builds (browser cache)
- Kuzu single-writer lock (one process at a time)

---

## Version History (Pre-1.0 Development)

| Date | Internal Label | Notes |
|------|---------------|-------|
| 2025-11-27 | v1.1.0 (tag) | Initial GitHub release |
| 2025-12-02 | v1.2.0 (docs) | User profile integration |
| 2025-12-05 | v1.3.0 (docs) | Cleanup session - NOW v1.0.0 |

**Note:** Pre-1.0 version numbers were inflated during rapid development. 
This release resets to proper semantic versioning starting at 1.0.0.

---

## Versioning Rules

### When to Increment

| Change Type | Version Bump | Example |
|-------------|--------------|---------|
| Bug fix (no API change) | PATCH (1.0.x) | Fix ChromaDB timing issue |
| New feature (backward compatible) | MINOR (1.x.0) | Add memory consolidation tool |
| Breaking API change | MAJOR (x.0.0) | Change MCP tool signatures |

### Release Checklist

1. Update this file with new version section
2. Run functional tests
3. Commit with message `release: vX.Y.Z`
4. Create git tag: `git tag vX.Y.Z -m "Release vX.Y.Z"`
5. Push tag: `git push origin vX.Y.Z`

---

## File History

| Old File | Status | Reason |
|----------|--------|--------|
| `RELEASE_NOTES_v1.2.md` | ARCHIVED | Superseded by this file |
| `V1.2_SUMMARY.md` | TO DELETE | Redundant |
| `CHANGELOG.md` | KEEP | Detailed commit history |
