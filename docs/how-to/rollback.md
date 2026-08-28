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
verification. JSON is a portable memory-migration source, not a full backup;
CSV is analysis-only. Both omit the graph database and binary embeddings.

## 1.5. Migrate memories from portable JSON

For a cross-install or cross-backend memory migration, export from the source:

```bash
python scripts/pipeline/export_memories.py --format json --output /tmp/elefante-memories.json
```

Preview the target without generating embeddings or writing data:

```bash
python scripts/pipeline/import_memories.py /tmp/elefante-memories.json
```

Stop the target runtime before applying. If the target store is non-empty,
create and pass a verified binary backup; the importer is additive and refuses
to overwrite an existing memory ID:

```bash
python scripts/pipeline/import_memories.py /tmp/elefante-memories.json \
  --apply --confirm-stopped STOPPED \
  --backup-archive /path/to/elefante_data_backup.zip
```

The importer regenerates vectors with the target's configured local embedding
model and preserves memory IDs and metadata. It does not restore graph entities
or relationships; use the binary backup/restore path for complete durable-data
recovery.

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
