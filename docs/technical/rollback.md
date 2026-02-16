# Backup & Rollback Procedures

**Goal:** If a future change goes sideways, safely return to a known-good state with minimal downtime and no permanent data loss.

This runbook is operational (not a postmortem). Lessons learned belong in `docs/debug/`.

---

## Preconditions

1. **Tag the release** before making changes:
   - `git tag v1.10.0` (or the current version, if not already tagged).

2. **Take a data backup** before any changes that touch storage formats:
   - Databases live under `data/` by default (configurable in `config.yaml`).

3. **Confirm version alignment**:
   - Runtime version: `src/__init__.py`
   - Packaging version: `setup.py`
   - Dashboard ribbon: `/api/stats` -> `elefante.package_version`

---

## Backup (File-System Snapshot)

Use the backup script (safe with Elefante Mode OFF):

```bash
python scripts/backup_elefante_data.py
```

This creates a timestamped archive under the configured backup directory.

---

## Rollback Procedure

1. **Stop all services** that hold locks:
   - MCP server(s)
   - Dashboard server
   - Any Python process using Kuzu/ChromaDB

2. **Restore data backup** (if the change touched storage formats or corrupted data):

```bash
python scripts/restore_elefante_data.py --latest --force
```

3. **Roll back code** to the desired version:

```bash
git checkout v1.10.0   # or whichever tagged version
```

4. **Restart services**:

```bash
python scripts/restart_elefante.py --verify
python -m src.dashboard.server
```

5. **Verify**:
   - `http://127.0.0.1:8000/api/stats` reports the correct `package_version`
   - `python scripts/health_check.py` passes

---

## Compatibility Rules

When making changes beyond the current release:

- Prefer **backward-compatible** changes (current version can still read the data).
- If not possible, migrations must be **guarded** and **reversible**, and a backup must be taken first.
- Document all schema changes in `docs/technical/`.

