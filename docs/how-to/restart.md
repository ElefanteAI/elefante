# Restart Elefante Safely

Customer installations run an installer-owned user service. A source checkout
may instead run a direct stdio server. The restart commands are different.

## Customer daemon repair/restart

On macOS/Linux, inspect the stable customer runtime first:

```bash
ELEFANTE_RUNTIME="$HOME/.elefante/app/current"
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" status
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" install
```

The second command is a dry run. If it reports a modified or untracked service,
stop and preserve that service. Otherwise apply the owned-service refresh:

```bash
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/daemon_service.py" install --apply
curl --fail http://127.0.0.1:8765/health
"$ELEFANTE_RUNTIME/.venv/bin/python" \
  "$ELEFANTE_RUNTIME/scripts/lifecycle/doctor.py" --json
```

On Windows PowerShell, set
`$ElefanteRuntime = "$env:LOCALAPPDATA\Elefante\app\current"` and run the
same scripts with
`& "$ElefanteRuntime\.venv\Scripts\python.exe" <script-path>`.

Then fully quit and reopen the IDE or agent host.

## Direct source-server restart

From a source checkout, `restart_elefante.py` manages only a direct
`src.mcp.server` developer process;
it does not manage the customer daemon:

```bash
./.venv/bin/python scripts/lifecycle/restart_elefante.py --verify
./.venv/bin/python scripts/lifecycle/restart_elefante.py --verify --version 2.15.2
```

Verification waits for a private receipt written by the launched process and
matches both its PID and imported product version. `--version` is rejected
unless `--verify` is present; the helper's own source import is not accepted as
proof of the restarted process.

## If graceful shutdown fails

1. Stop sending new MCP calls.
2. Run the matching customer or source sequence once.
3. For a direct source process, inspect the reported process and lock state.
4. Use `--force` only after confirming the target is an Elefante process and a
   current backup exists:

```bash
./.venv/bin/python scripts/lifecycle/backup_elefante_data.py
./.venv/bin/python scripts/lifecycle/restart_elefante.py --force --verify
```

Do not release a lock held by a live process and do not use `kill -9` as the
first response. In-flight graph writes can be damaged.

Then reconnect one configured host and run a real memory search. The source
handshake verifier proves a local MCP implementation, not that a customer IDE
is attached to the installed bridge and shared daemon.

## Failure routing

- Service or host connection failure: [`configure-ide.md`](configure-ide.md)
- Storage/lock/corruption failure: [`kuzu-troubleshooting.md`](kuzu-troubleshooting.md)
- Backup or restore: [`rollback.md`](rollback.md)
