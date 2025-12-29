# Rollback Plan (→ v1.5.0 Baseline)

**Goal:** If a future change goes sideways, we can safely return to the **v1.5.0** baseline with minimal downtime and no permanent data loss.

This runbook is operational (not a postmortem). Lessons learned belong in `docs/debug/`.

---

## Preconditions (before upgrading beyond v1.5.0)

1. Ensure there is a stable v1.5.0 reference:
   - Tag the current known-good commit as `v1.5.0` (or confirm it already exists).

2. Take a data backup (recommended):
   - Databases live under `~/.elefante/data/` by default.
   - Backup this folder before any changes that touch storage formats.

3. Confirm version alignment:
   - Runtime version: `src/__init__.py`
   - Packaging version: `setup.py`
   - Dashboard ribbon: `/api/stats` → `elefante.package_version`

---

## Backup (file-system snapshot)

Use the backup script (safe with Elefante Mode OFF):

```bash
python scripts/backup_elefante_data.py
```

This creates a timestamped archive under `~/.elefante/backups/` by default.

---

## Rollback Procedure (→ v1.5.0)

1. Stop anything that may hold locks:
   - MCP server(s)
   - Dashboard server
   - Any Python process using Kuzu/Chroma

2. Restore data backup (if the change touched storage formats or corrupted data):

```bash
python scripts/restore_elefante_data.py --latest --force
```

3. Roll back code to v1.5.0:

```bash
git checkout v1.5.0
```

4. Restart services:

```bash
python scripts/restart_elefante.py --verify
python -m src.dashboard.server
```

5. Verify:
   - `http://127.0.0.1:8000/api/stats` reports `package_version = 1.5.0`
   - Dashboard ribbon displays `Elefante v1.5.0`

---

## Compatibility Rule (for post-v1.5.0 work)

If a post-v1.5.0 change introduces any migration or schema change:

- Prefer **backward-compatible** changes (v1.5.0 can still read the data).
- If not possible, migrations must be **guarded** and **reversible**, and a backup must be taken.

