# Troubleshoot Kuzu Safely

**Applies to:** v2.12.3

Kuzu stores Elefante's entities and relationships. The normal customer runtime
has one daemon owner; IDE bridges never open Kuzu directly.

## Normal ownership

```text
IDE or agent host
  -> transport-only stdio bridge
  -> loopback daemon
  -> Kuzu
```

The dashboard reads `dashboard_snapshot.json`, not Kuzu. Snapshot/export tools
may open a short-lived read-only graph connection, but read-only mode is not a
guarantee that a second live process can share a database already owned by
another process.

## First response to a lock error

1. Stop the extra source MCP server, dashboard export, or other process that is
   opening the same Kuzu path.
2. Keep the customer daemon as the single owner.
3. Retry the operation after the active transaction finishes.
4. If the daemon is unhealthy, use [`restart.md`](restart.md).

Do not delete Kuzu's internal lock file. Do not run a nuclear reset as the
default repair.

## Inspect Elefante's transaction lock

The separate Elefante write guard normally lives at
`~/.elefante/locks/write.lock`. It is transaction-scoped; the timeout comes
from `lock_timeout_seconds` in current configuration and is not a fixed
documentation constant.

From a developer checkout, inspect without changing anything:

```bash
./.venv/bin/python scripts/debug/manage_lock.py
```

If the recorded process is alive, do not remove the lock. If the owner is dead
or the configured timeout has expired, the runtime normally clears the stale
guard on the next acquisition.

The privileged apply path can corrupt state if the diagnosis is wrong. Use it
only after stopping the real owner, preserving a backup, reviewing the dry run,
and obtaining authority for destructive repair.

## Validate a graph query

Use `elefante-GraphQuery` for read-only Cypher. Start with the smallest query
that proves the needed node, relationship, or property. `GraphConnect`, not
`GraphQuery`, owns mutations.

Schema authority is `src/core/graph_store.py`. Kuzu property and relationship
names must match that live schema; do not infer them from an old example.

## Empty or invalid database path

Fresh Kuzu paths materialize as a database file. The graph store removes an
empty pre-created file or empty legacy directory before initialization, but it
does not overwrite a non-empty unknown path.

If initialization fails:

1. stop the daemon;
2. run the read-only doctor;
3. back up the configured data paths;
4. inspect whether `config.yaml` points to the intended Kuzu location;
5. repair only the confirmed path.

Never assume `~/.elefante/data/kuzu_db` when configuration says otherwise.

## Legacy rebuild boundary

`scripts/debug/reset_kuzu_nuclear.py` rebuilds graph state from an explicitly
configured legacy ChromaDB store. It is not the recovery route for the default
SQLite/Kuzu customer runtime. Do not run it against a fresh v2.12.3
installation.

## Verification

After recovery:

```bash
curl --fail http://127.0.0.1:8765/health
```

Then run the installed `doctor`, restart one configured host, and perform a
read-only memory search and graph query. From a source checkout, also run
`./.venv/bin/python scripts/verify/verify_mcp_handshake.py`. A healthy process
alone does not prove that the intended memory store was opened, so confirm the
configured paths with `doctor` when customer installation state is in question.
