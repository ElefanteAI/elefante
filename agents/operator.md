---
PROTOCOL: operator
INVOKE: elefante-operator
PROTOCOL_VERSION: 2.13.0
LOAD_WHEN: Backup, restore, factory reset, dashboard pipeline refresh, planned downtime, any destructive op against a live install.
DIAGNOSTIC_QUESTION: "Is the backup current AND is the server stopped before any file-level operation?"
AUTHORITY: This file owns OPERATOR mode. Backup-first is non-negotiable.
---

# Operator Agent

> Live-install operations. Every destructive path passes through this agent. The non-negotiable rule: **backup before destruction, server stopped before file-level operations.**

## The Two Pre-flight Rules

Before any destructive or database file-level operation in this file:

1. **Backup is current.** `./.venv/bin/python scripts/lifecycle/backup_elefante_data.py`. Verify the backup file exists and is non-empty.
2. **Store owner is stopped** (for file-level ops). For an installer-owned
   customer daemon, preview then apply
   `scripts/lifecycle/daemon_service.py uninstall`; this removes the owned
   service registration, not memory data. For a direct source server, stop the
   exact process gracefully. Confirm port 8765 and direct database owners are
   inactive before continuing.

Skip either on those operations = data loss is on you. Check health and the
privacy-safe support report are non-destructive exceptions: they require no
database stop and must never use that exception to read memory content.

## Operations Map

| Need | Run | Pre-flight |
| ---- | --- | ---------- |
| Routine backup | `scripts/lifecycle/backup_elefante_data.py` | none |
| Privacy-safe support report | Home → Recover → Support report → preview → confirm | none; report is local and content-free |
| Restore from backup | `scripts/lifecycle/restore_elefante_data.py --archive <backup-path>` or `--latest` | store owner stopped |
| Factory reset (wipe everything) | `scripts/lifecycle/reset_factory.py` | backup + server stopped |
| Repair/restart customer daemon | `scripts/lifecycle/daemon_service.py install` then `install --apply` | installer-owned service only |
| Uninstall product, preserve memories | matching official package → platform uninstall launcher | preview + explicit `UNINSTALL`; package creates and verifies backup |
| Restart direct source server | `scripts/lifecycle/restart_elefante.py --verify` | source/developer topology only |
| Refresh dashboard through MCP | `elefante-DashboardOpen(refresh=true)` | customer daemon healthy |
| Refresh dashboard from source | `scripts/pipeline/update_dashboard_data.py` | no competing direct database owner |
| Surgical memory delete | `scripts/privileged/delete_memories_surgical.py` | PRIVILEGED + backup + dry-run |

## Backup Protocol

`backup_elefante_data.py` snapshots the configured vector store (SQLite by default; legacy ChromaDB when explicitly configured) and Kuzu. Output is a timestamped archive.

- **Always backup before:** factory reset, Kuzu nuclear reset, surgical delete, schema migration, restore-test.
- **Verify the backup:** non-zero size, both DBs included.
- **Retention:** keep at least the last 3 backups unless the user selects a
  stricter policy. Removing local backup files is an operator audit event, not
  a product changelog entry.

## Support Report Protocol

Use Elefante Home before asking a customer to collect logs or inspect files.
Recover → Support report previews every included and excluded category, then
creates one mode-0600 managed ZIP and downloads it locally. The ZIP contains one
allowlist-built JSON manifest and is never transmitted by Elefante.

Do not add logs, memory stores, project registries, host configuration bodies,
environment dumps, prompts, questions, answers, transcripts, or credentials to
the report. A stale preview must be generated again; a failed archive readback
must remove the unverified ZIP. If Home cannot run, use the official package's
lifecycle path once that fallback is implemented rather than improvising a
broader diagnostic bundle.

## Restore Protocol

1. Stop the server.
2. Preflight with `./.venv/bin/python scripts/lifecycle/restore_elefante_data.py --archive <backup-path>` (or `--latest`), then repeat with `--apply`.
3. Reinstall/start an installer-owned daemon with a dry run followed by
   `./.venv/bin/python scripts/lifecycle/daemon_service.py install --apply`.
4. Verify with `./.venv/bin/python scripts/verify/verify_health.py`.
5. After the customer daemon is healthy, refresh through
   `elefante-DashboardOpen(refresh=true)`. From a stopped source/developer
   topology, the standalone pipeline is also valid.

If verify_health fails after restore: stop, do not retry. Load `agents/orchestrator.md` and route through `workspace/postmortems/database.md`.

## Product Uninstall Protocol

Complete product uninstall belongs to the matching official client package,
which runs outside the installed app root. The installed
`scripts/lifecycle/uninstall_elefante.py` is only the shared ownership-safe
detachment engine; running it directly does not remove the app or memory data.

1. Prefer a privacy-safe support report first when uninstall is part of
   diagnosis.
2. Use the package matching the exact installed version and source identity.
3. Review the package plan and type `UNINSTALL` only after confirming that
   memories will remain.
4. Require a newly created backup and an independent restore preflight before
   any app removal.
5. Remove only the active app and unchanged manifest-owned connections.
   Preserve modified or unverifiable customer configuration.
6. Verify the data fingerprint before and after app removal and write the
   private data-preservation and lifecycle receipts.
7. On reinstall, reuse the exact preserved data root. Consume its pointer only
   after Doctor and live Recall verification pass.

Never describe a merely restarted app as fully rolled back when any owned host
connection was already removed. Report `NEEDS_HUMAN` and route to the support
report instead. Data deletion is a separate PRIVILEGED operation and is never
implied by uninstall.

## Factory Reset (the destructive path)

`reset_factory.py` recoverably moves configured stores out of the active data
paths. Initialization after the reset recreates empty stores and the normal
seed path. Used for:

- Demo prep
- Recovery from unrecoverable corruption
- Privacy wipe before transfer

Procedure:

1. **Backup** (non-negotiable).
2. **Confirm intent.** This is irreversible; the user must explicitly authorize.
3. Stop server.
4. Review `./.venv/bin/python scripts/lifecycle/reset_factory.py`, then apply
   with `--apply --confirm DELETE`.
5. Run `./.venv/bin/python -m pytest tests/test_factory_reset.py -v` to confirm clean state.
6. Start server.
7. Re-run install seed verification: ask AI `What is my Elefante test passcode?`.

## PRIVILEGED Sub-mode

Surgical operations that bypass the orchestrator (delete-by-id, graph-edit) require:

- `ELEFANTE_PRIVILEGED=1` in environment
- Backup completed in this session
- Dry-run completed first
- Reason reported in the operator result and, when product state changed, the
  existing planning or issue ledger. Do not create a separate handoff file.

## Closure

Live data operations are not product changelog entries. Report the backup,
target, authorization, result, and rollback location to the user; update the
existing state ledger only when durable product state changed. Do not create a
new handoff document. Update `CHANGELOG.md` only when source-controlled product
behavior changes.
