---
PROTOCOL: operator
INVOKE: elefante-operator
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: Backup, restore, factory reset, dashboard pipeline refresh, planned downtime, any destructive op against a live install.
DIAGNOSTIC_QUESTION: "Is the backup current AND is the server stopped before any file-level operation?"
AUTHORITY: This file owns OPERATOR mode. Backup-first is non-negotiable.
---

# Operator Agent

> Live-install operations. Every destructive path passes through this agent. The non-negotiable rule: **backup before destruction, server stopped before file-level operations.**

## The Two Pre-flight Rules

Before any operation in this file:

1. **Backup is current.** `python scripts/lifecycle/backup_elefante_data.py`. Verify the backup file exists and is non-empty.
2. **Server is stopped** (for file-level ops). `python scripts/lifecycle/restart_elefante.py --stop`. Confirm.

Skip either = data loss is on you.

## Operations Map

| Need | Run | Pre-flight |
| ---- | --- | ---------- |
| Routine backup | `scripts/lifecycle/backup_elefante_data.py` | none |
| Restore from backup | `scripts/lifecycle/restore_elefante_data.py <backup-path>` | server stopped |
| Factory reset (wipe everything) | `scripts/lifecycle/reset_factory.py` | backup + server stopped |
| Restart cleanly | `scripts/lifecycle/restart_elefante.py --stop` then `--start` | none |
| Refresh dashboard data | `scripts/pipeline/update_dashboard_data.py` | server alive |
| Surgical memory delete | `scripts/privileged/delete_memories_surgical.py` | PRIVILEGED + backup + dry-run |

## Backup Protocol

`backup_elefante_data.py` snapshots both ChromaDB and Kuzu. Output is a timestamped archive.

- **Always backup before:** factory reset, Kuzu nuclear reset, surgical delete, schema migration, restore-test.
- **Verify the backup:** non-zero size, both DBs included.
- **Retention:** keep at least the last 3 backups. Older ones can be cleaned per `agents/memory-janitor.md` rule 1 (CHANGELOG `### Removed` entry).

## Restore Protocol

1. Stop the server.
2. `python scripts/lifecycle/restore_elefante_data.py <backup-path>`.
3. Start the server.
4. Verify with `python scripts/verify/verify_health.py`.
5. Run dashboard refresh: `python scripts/pipeline/update_dashboard_data.py`.

If verify_health fails after restore: stop, do not retry. Load `agents/orchestrator.md` and route through `workspace/postmortems/database.md`.

## Factory Reset (the destructive path)

`reset_factory.py` wipes all memories, resets schema, restores seed memory. Used for:

- Demo prep
- Recovery from unrecoverable corruption
- Privacy wipe before transfer

Procedure:

1. **Backup** (non-negotiable).
2. **Confirm intent.** This is irreversible; the user must explicitly authorize.
3. Stop server.
4. `python scripts/lifecycle/reset_factory.py`.
5. Run `pytest tests/test_factory_reset.py -v` to confirm clean state.
6. Start server.
7. Re-run install seed verification: ask AI `What is my Elefante test passcode?`.

## PRIVILEGED Sub-mode

Surgical operations that bypass the orchestrator (delete-by-id, graph-edit) require:

- `ELEFANTE_PRIVILEGED=1` in environment
- Backup completed in this session
- Dry-run completed first
- Reason recorded in the eventual commit message

## Closure

Every operation produces a CHANGELOG entry if the system state changed observably. Restore + factory reset always entail a `### Changed` entry naming the data window affected.
