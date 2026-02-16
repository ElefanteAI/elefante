# Elefante Workspace Cleanup Plan

**Date**: 2026-02-16
**Purpose**: Remove redundant files, ensure clean structure, no temporary files outside designated directories

---

## Executive Summary

After thorough analysis of the Elefante workspace, I identified several categories of issues:

1. **Duplicate scripts in archive** - identical copies that serve no purpose
2. **Redundant archive subdirectories** - originals folder duplicates parent
3. **Hardcoded paths** - scripts with user-specific absolute paths
4. **Missing gitignore entries** - `.hypothesis/` cache not ignored
5. **Completed specs in `.kiro/`** - should be archived

---

## Issues Found

### 1. Duplicate Scripts in Archive (DELETE)

These scripts in `scripts/archive/historical/` are identical or near-identical to active versions:

| Archived File | Active Equivalent | Action |
|---------------|-------------------|--------|
| `scripts/archive/historical/dashboard_health_check.py` | `scripts/dashboard_health_check.py` | DELETE archived |
| `scripts/archive/historical/validate_dashboard_snapshot.py` | `scripts/validate_dashboard_snapshot.py` | DELETE archived |
| `scripts/archive/historical/restart_elefante.py` | `scripts/restart_elefante.py` | DELETE archived |

**Rationale**: The active scripts are documented as "promoted entrypoints". Keeping duplicates in archive creates confusion.

### 2. Redundant Originals Subdirectory (DELETE)

**Location**: `docs/archive/historical/scripts_legacy_2025-12-12/originals/`

This directory contains exact duplicates of files already in the parent directory:
- `elefante_off.py` = same as parent
- `force_reinstall.py` = same as parent
- `migrate_v3_direct.py` = same as parent
- `reproduce_lock.py` = same as parent
- `semantic_search_debug.py` = same as parent

**Action**: Delete the entire `originals/` subdirectory.

### 3. Scripts with Hardcoded Paths (FIX or ARCHIVE)

| File | Issue | Action |
|------|-------|--------|
| `scripts/dump_all.py` | Hardcoded path `/Users/jay/Documents/VSCODE/Chile2026/Elefante/Elefante_early_dec2025` | DELETE - obsolete path |
| `scripts/debug/dump_all_memories.py` | Hardcoded path `/Users/jay/.elefante/data/chroma` | FIX - use config |

### 4. Missing .gitignore Entry (ADD)

The `.hypothesis/` directory contains testing cache files:
- `.hypothesis/constants/` - 31 cache files
- `.hypothesis/unicode_data/` - Unicode data

**Action**: Add `.hypothesis/` to `.gitignore`

### 5. Completed Specs in .kiro/ (ARCHIVE)

The `.kiro/specs/` directory contains completed feature specs:

| Spec | Status | Action |
|------|--------|--------|
| `v1-6-1-cognitive-standardization/` | Unknown | Review |
| `v1-6-2-cognitive-visual-enablement/` | Unknown | Review |
| `v1-6-4-cognitive-hub/` | Unknown | Review |
| `v5-cognitive-features/` | COMPLETE | Archive to `docs/archive/historical/` |

**Recommendation**: Move completed specs to `docs/archive/historical/kiro-specs/` for historical reference.

---

## Files to Delete

```
# Duplicate scripts
scripts/archive/historical/dashboard_health_check.py
scripts/archive/historical/validate_dashboard_snapshot.py
scripts/archive/historical/restart_elefante.py

# Redundant originals
docs/archive/historical/scripts_legacy_2025-12-12/originals/  (entire directory)

# Obsolete hardcoded path script
scripts/dump_all.py
```

---

## Files to Fix

```
# Hardcoded path - use config instead
scripts/debug/dump_all_memories.py
```

---

## Files to Add to .gitignore

```gitignore
# Hypothesis testing cache
.hypothesis/
```

---

## Directory Structure After Cleanup

```
Elefante/
├── .dockerignore
├── .env.example
├── .gitignore          # Updated with .hypothesis/
├── CHANGELOG.md
├── config.yaml
├── CONTRIBUTING.md
├── docker-compose.yml
├── Dockerfile
├── Elefante Logo 1024 white.png
├── install.bat
├── install.sh
├── LICENSE
├── README.md
├── RELEASES.md
├── requirements.txt
├── restart_mcp.bat
├── setup.py
├── .github/
├── .kiro/              # Keep for active planning
├── docs/
│   ├── README.md
│   ├── THE_CORE.md
│   ├── pitfall-index.md
│   ├── archive/        # Historical docs only
│   ├── debug/          # Debug compendiums
│   ├── planning/       # Active planning
│   └── technical/      # Technical docs
├── examples/
├── scripts/
│   ├── *.py            # Active scripts
│   ├── archive/        # Historical scripts (cleaned)
│   ├── dashboard/
│   ├── debug/          # Debug scripts (fixed)
│   └── utils/
├── src/
├── tests/
└── vscode-extension/
```

---

## Action Items

### Immediate (No Confirmation Needed)

- [ ] Delete `scripts/archive/historical/dashboard_health_check.py`
- [ ] Delete `scripts/archive/historical/validate_dashboard_snapshot.py`
- [ ] Delete `scripts/archive/historical/restart_elefante.py`
- [ ] Delete `docs/archive/historical/scripts_legacy_2025-12-12/originals/` directory
- [ ] Delete `scripts/dump_all.py` (obsolete hardcoded path)
- [ ] Add `.hypothesis/` to `.gitignore`

### Requires Code Mode

- [ ] Fix `scripts/debug/dump_all_memories.py` to use config instead of hardcoded path

### Requires Discussion

- [ ] Decide fate of `.kiro/` directory - keep as active planning or archive completed specs?

---

## Summary Statistics

| Category | Count |
|----------|-------|
| Files to delete | 6 files + 1 directory |
| Files to fix | 1 |
| .gitignore entries to add | 1 |
| Directories to review | 1 (.kiro/) |

---

**Next Step**: Switch to Code mode to execute the cleanup actions.
