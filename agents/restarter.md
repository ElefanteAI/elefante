---
PROTOCOL: restarter
INVOKE: elefante-restarter
PROTOCOL_VERSION: 2.10.0-pre
LOAD_WHEN: MCP tools not surfacing in IDE, server stuck, dashboard returns 500, `elefante-*` tools absent from tool list, IDE shows "MCP connection failed", post-install verification step fails.
DIAGNOSTIC_QUESTION: "Is the MCP server alive over stdio JSON-RPC, and is the IDE actually connecting to it?"
AUTHORITY: This file owns the restart and recovery protocol. Scattered restart instructions in older docs are forwarding only.
---

# Restarter Agent

## The Three-Layer Check

Symptoms can come from any of three layers. Diagnose top-down; cheapest check first.

| Layer | Check | Run |
| ----- | ----- | --- |
| 1. **Server** | Is the Elefante MCP process answering JSON-RPC? | `python scripts/verify/verify_mcp_handshake.py` |
| 2. **IDE** | Has the IDE re-read its MCP config since last restart? | Restart the IDE (full quit, not reload) |
| 3. **Lock** | Is a stale lock blocking writes? | `python scripts/debug/manage_lock.py --dry-run` |

Layer 1 fail → server problem. Layer 1 pass + Layer 2 fail → IDE re-attach. Layer 1+2 pass + writes hang → Layer 3.

## Restart Sequence

Never `kill -9` first. Order matters because in-flight writes can corrupt Kuzu.

1. **Drain.** Stop sending new tool calls from the IDE.
2. **Stop server gracefully.** `python scripts/lifecycle/restart_elefante.py --stop`. Wait for confirmation.
3. **Verify lock cleared.** `python scripts/debug/manage_lock.py --dry-run` — should show no held locks.
4. **Restart server.** `python scripts/lifecycle/restart_elefante.py --start`.
5. **Re-attach IDE.** Full quit + relaunch (not "reload window").
6. **Verify.** Ask the AI `What is my Elefante test passcode?` — must return the seed.

## Lock Recovery

If `manage_lock.py --dry-run` shows a stale lock:

1. Confirm no Elefante process is alive (`ps aux | grep elefante`).
2. `python scripts/debug/manage_lock.py --release` (no dry-run).
3. Restart from step 4 above.

If the lock is held by a live process, **do not release it**. Find why the process is hung first; that's a different bug class — load `agents/orchestrator.md` and route through `workspace/postmortems/database.md`.

## Nuclear Option (Kuzu only)

If Kuzu is corrupted but ChromaDB is intact:

1. **Backup first.** `python scripts/lifecycle/backup_elefante_data.py` (non-negotiable).
2. `python scripts/debug/reset_kuzu_nuclear.py` — destroys and rebuilds the graph from ChromaDB.
3. Restart per sequence above.

This is a `PRIVILEGED` mode operation per the orchestrator. Requires `ELEFANTE_PRIVILEGED=1`.

## Closure

After recovery:

1. If a recurring restart-class failure was hit, update `workspace/ISSUES.md` Known Issues.
2. New failure mode → append to `workspace/postmortems/database.md`.
3. Never leave `manage_lock.py` artifacts or backup files in repo root.
