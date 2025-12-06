# Archived Documentation

**Status:** Reorganized 2025-12-06  
**Policy:** Preserve historical records, session logs, version changelogs

---

## Structure

```
archive/
├── historical/     # Session logs, completed task lists
├── releases/       # Version changelog notes
└── raw_logs/       # Raw installation logs (forensic evidence)
```

---

## Contents

### historical/
| File | Purpose |
|------|---------|
| `first-install-walkthrough.md` | Original M4 Silicon installation session (2025-11-27) |
| `2025-11-27-implementation-log.md` | Technical implementation details from first setup |
| `task-roadmap-completed.md` | Historical checkbox list of completed tasks |

### releases/
| File | Purpose |
|------|---------|
| `dashboard-v27-changelog.md` | Dashboard v27 semantic topology upgrade notes |

### raw_logs/
| File | Purpose |
|------|---------|
| `install.log` | Original pip installation output (forensic evidence) |

---

## Policy

**Archive = Historical Record**
- Information that WAS true at a point in time
- Session logs from debugging/installation
- Superseded design documents
- Version-specific changelogs

**NOT for Archive:**
- Active documentation (use `technical/`)
- Future plans (use `planning/`)
- Recurring failure patterns (use `debug/`)

---

**Last Updated**: 2025-12-06
