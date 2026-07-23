# Backup & Rollback Procedures

**Goal:** If a future change goes sideways, safely return to a known-good state with minimal downtime and no permanent data loss.

This runbook is operational (not a postmortem). Lessons learned belong in the relevant `workspace/postmortems/<domain>.md` entry and are indexed by `workspace/ISSUES.md`.

---

## Preconditions

1. **Tag the release** before making changes:
   - `git tag v2.1.3` (or the current version, if not already tagged).

2. **Take a data backup** before any changes that touch storage formats:
   - Databases live under `data/` by default (configurable in `config.yaml`).

3. **Confirm version alignment**:
   - Runtime version: `src/__init__.py`
   - Packaging version: `setup.py`
   - Dashboard ribbon: `/api/stats` -> `elefante.package_version`

---

## Backup (File-System Snapshot)

Stop Elefante first, then use the backup script. It does not open database
handles, but a live database cannot be promised as a consistent file snapshot.

```bash
python scripts/lifecycle/backup_elefante_data.py
```

This creates a timestamped zip archive under the configured backup directory.
Each new archive carries a checksum manifest; nested recovery archives are not
copied into future backups.

---

## Rollback Procedure

1. **Stop all services** that hold locks:
   - MCP server(s)
   - Dashboard server
   - Any Python process using SQLite, Kuzu, or a legacy ChromaDB store

2. **Preflight then restore data backup** (if the change touched storage formats or corrupted data):

```bash
python scripts/lifecycle/restore_elefante_data.py --latest
python scripts/lifecycle/restore_elefante_data.py --latest --apply
```

The first command validates archive paths and checksums without changing data.
The applied restore stages the archive before replacement and moves current data
to `data.pre_restore.<timestamp>` for recovery. `--discard-existing` is an
exceptional destructive option and additionally requires `--confirm DISCARD`.

3. **Roll back code** to the desired version:

```bash
git checkout v2.1.3   # or whichever tagged version
```

4. **Restart services**:

```bash
python scripts/lifecycle/restart_elefante.py --verify
python -m src.dashboard.server
```

5. **Verify**:
   - `http://127.0.0.1:8000/api/stats` reports the correct `package_version`
   - `python scripts/verify/verify_health.py` passes

---

## Compatibility Rules

When making changes beyond the current release:

- Prefer **backward-compatible** changes (current version can still read the data).
- If not possible, migrations must be **guarded** and **reversible**, and a backup must be taken first.
- Document all schema changes in `docs/reference/`.
