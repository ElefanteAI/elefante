---
PROTOCOL: restarter
INVOKE: elefante-restarter
PROTOCOL_VERSION: 2.12.2
LOAD_WHEN: MCP tools not surfacing in IDE, server stuck, dashboard returns 500, `elefante-*` tools absent from tool list, IDE shows "MCP connection failed", post-install verification step fails.
DIAGNOSTIC_QUESTION: "Is the MCP server alive over stdio JSON-RPC, and is the IDE actually connecting to it?"
AUTHORITY: This file owns the restart and recovery protocol. Scattered restart instructions in older docs are forwarding only.
---

# Restarter Agent

## The Three-Layer Check

Symptoms can come from any of three layers. Diagnose top-down; cheapest check first.

| Layer | Check | Run |
| ----- | ----- | --- |
| 1. **Server** | Is the Elefante MCP process answering JSON-RPC? | `./.venv/bin/python scripts/verify/verify_mcp_handshake.py` |
| 2. **IDE** | Has the IDE re-read its MCP config since last restart? | Restart the IDE (full quit, not reload) |
| 3. **Lock** | Is a stale lock blocking writes? | `./.venv/bin/python scripts/debug/manage_lock.py` (no flags = inspect only) |

Layer 1 fail → server problem. Layer 1 pass + Layer 2 fail → IDE re-attach. Layer 1+2 pass + writes hang → Layer 3.

## Restart Sequence

Never `kill -9` first. Choose the topology actually in use.

### Customer daemon

1. Drain new IDE calls and inspect
   `./.venv/bin/python scripts/lifecycle/daemon_service.py status`.
2. Preview the owned-service refresh with
   `./.venv/bin/python scripts/lifecycle/daemon_service.py install`.
3. If the preview reports a modified or untracked service, stop; do not replace
   it. Otherwise apply with the same command plus `--apply`.
4. Confirm `curl --fail http://127.0.0.1:8765/health` and run `doctor.py --json`.
5. Fully quit and relaunch the IDE, then retrieve the `Indigo-Echo` seed.

### Direct source server

1. Drain new calls.
2. Run `./.venv/bin/python scripts/lifecycle/restart_elefante.py --verify`.
3. Use `--force --verify` only after confirming the identified process is
   Elefante and graceful termination failed.

## Lock Recovery

If `manage_lock.py` shows a stale lock:

1. Confirm no Elefante process is alive (`ps aux | grep elefante`).
2. After explicit destructive-repair authority and a current backup, run
   `ELEFANTE_PRIVILEGED=1 ./.venv/bin/python scripts/debug/manage_lock.py --apply --confirm DELETE`.
3. Restart using the matching customer-daemon or direct-source sequence above.

If the lock is held by a live process, **do not release it**. Find why the process is hung first; that's a different bug class — load `agents/orchestrator.md` and route through `workspace/postmortems/database.md`.

## Legacy-only nuclear option (Kuzu only)

`reset_kuzu_nuclear.py` rebuilds from a legacy ChromaDB store. It is not a
recovery path for the released SQLite default. For SQLite installations, stop
and route through the verified backup/restore procedure; do not improvise a
graph rebuild.

For an explicitly configured legacy ChromaDB installation:

1. **Backup first.** `./.venv/bin/python scripts/lifecycle/backup_elefante_data.py` (non-negotiable).
2. `./.venv/bin/python scripts/debug/reset_kuzu_nuclear.py` — destroys and rebuilds the graph from the legacy ChromaDB store.
3. Restart per sequence above.

This is a `PRIVILEGED` mode operation per the orchestrator. Requires `ELEFANTE_PRIVILEGED=1`.

## Closure

After recovery:

1. If a recurring restart-class failure was hit, update `workspace/ISSUES.md` Known Issues.
2. New failure mode → append to `workspace/postmortems/database.md`.
3. Never leave `manage_lock.py` artifacts or backup files in repo root.
