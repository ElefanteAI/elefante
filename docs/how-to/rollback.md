# Backup and Rollback

This runbook separates customer rollback, source-code rollback, and data
restore. They are different operations. Never change a storage format or
restore files without a verified backup and a stopped runtime.

## 1. Create a recoverable backup

The released default data root is `~/.elefante/data` on macOS/Linux or the
Elefante user-data directory on Windows; configuration can override it.

Stop the daemon and all direct Elefante processes. On macOS/Linux, use the
stable customer runtime to preview and then remove only the installer-owned
service registration; this does not delete memory data:

```bash
ELEFANTE_RUNTIME="$HOME/.elefante/app/current"
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" uninstall
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" uninstall --apply
```

Then create the backup:

```bash
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/backup_elefante_data.py"
```

On Windows PowerShell, set
`$ElefanteRuntime = "$env:LOCALAPPDATA\Elefante\app\current"` and use
`$ElefanteRuntime\.venv\Scripts\python.exe` with the same lifecycle scripts.

Confirm the reported archive exists, is non-empty, and passes its checksum
verification. JSON/CSV export is analysis-only and is not a restorable backup.

## 2. Restore data safely

Stop every process using SQLite, Kuzu, or an explicitly configured legacy
ChromaDB store. Preflight first:

```bash
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/restore_elefante_data.py" --latest
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/restore_elefante_data.py" --latest --apply
```

The first command validates without mutation. Apply stages the archive and
preserves the replaced data in a recovery directory. Reinstall/start the
installer-owned customer daemon with the same runtime's
`daemon_service.py install` dry run followed by `install --apply`. Do not use
`--discard-existing` unless the user explicitly authorizes permanent removal.

## 3. Roll back product code

For a customer installation, download a known-good published release and run
its installer. Do not point IDEs at a developer checkout as a rollback.

For a developer checkout:

1. Confirm `git status --short` is clean or preserve every local change.
2. Confirm the intended tag exists locally and on GitHub.
3. Inspect the release notes and data compatibility before switching code.
4. Use a separate worktree or detached checkout for the known-good tag; do not
   rewrite the branch containing current work.

The currently published release is v2.12.3. A future rollback target must be
selected from actual published tags, not copied from this document.

## 4. Verify

```bash
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" status
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/doctor.py" --json
curl --fail http://127.0.0.1:8765/health
```

Confirm the daemon health response, configured host registrations, expected
runtime version, memory search, and dashboard snapshot. If verification fails,
stop and preserve both the failed state and backup before seeking support.

## Compatibility rule

Storage migrations must be backup-gated, dry-run-first, reversible, and
explicitly authorized. A code rollback cannot be assumed to reverse a data
migration.
