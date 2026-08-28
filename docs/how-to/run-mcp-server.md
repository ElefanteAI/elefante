# Run and Verify the Elefante MCP Runtime

**Applies to:** v2.13.0

The released customer topology is one user-level daemon as the **one durable store owner**, plus a **transport-only** stdio bridge for each IDE or agent
host. Direct database-owning MCP subprocesses are a developer compatibility
path, not the customer default.

## Customer runtime

The release installer starts and owns the service. Verify it without changing
state:

```bash
curl --fail http://127.0.0.1:8765/health
```

Expected JSON:

```json
{"status":"ok","service":"elefante-daemon","transport":"streamable-http"}
```

Run customer doctor for runtime, daemon, ownership, and host coverage:

```bash
~/.elefante/app/current/.venv/bin/python \
  ~/.elefante/app/current/scripts/lifecycle/doctor.py
```

On Windows, use the equivalent runtime under
`%LOCALAPPDATA%\Elefante\app\current` and `.venv\Scripts\python.exe`.

If health or host coverage fails, rerun the same v2.13.0 platform installer.
Do not configure a second daemon or point one host at a source checkout.

## Developer source runtime

Use the checkout virtual environment. If it is activated, `python` below means
that exact interpreter; otherwise use `./.venv/bin/python` (or
`.venv\Scripts\python.exe` on Windows).

Start the daemon in the foreground:

```bash
python -m src.mcp.daemon
```

It binds only to `127.0.0.1:8765`, serves MCP at
`http://127.0.0.1:8765/mcp/`, exposes `GET /health`, and rejects non-loopback
binding. MCP request bodies over 1 MiB are rejected.

Install or inspect the user service only when the development task requires it:

```bash
python scripts/lifecycle/daemon_service.py status
python scripts/lifecycle/daemon_service.py install
python scripts/lifecycle/daemon_service.py install --apply
```

Review the non-applying command first. Modified or user-managed service files
are preserved.

## Stdio bridge

With the daemon healthy, a stdio-only host launches:

```bash
python -m src.mcp.stdio_bridge
```

The bridge forwards JSON-RPC to the loopback daemon and owns no database. Host
configuration should set `ELEFANTE_CLIENT_TOOL` and may set
`ELEFANTE_CLIENT_CWD`; see [`configure-ide.md`](configure-ide.md). The bridge
rejects malformed or oversized messages before forwarding them.

## Direct stdio server

For isolated source compatibility and tests only:

```bash
python -m src.mcp.server
```

This process communicates over stdin/stdout. It does not print a listening
message and must keep stdout pure JSON-RPC. Do not run multiple database-owning
instances against the same Kuzu store.

## Verification

From a source checkout:

```bash
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
./.venv/bin/python scripts/ci/list_mcp_tools.py
```

The source inventory contains one default-off developer evaluation tool in
addition to the customer profile:

```text
Available MCP Tools: 18 (source declarations)
Available MCP Tools: 17 (default customer discovery)
Available MCP Prompts: 2
```

The tools and prompts are enumerated in
[`../reference/tools.md`](../reference/tools.md). Tool count alone is not a
health proof; the handshake verifier exercises initialization and list calls.

For the maintained whole-surface developer proof:

```bash
./.venv/bin/python scripts/verify/verify_e2e_tests.py
```

It uses isolated test data and intentionally leaves the dashboard tool outside
the default non-UI phase.

## Failure routing

- **Connection refused:** confirm the daemon service is installed and health is
  reachable, then use [`restart.md`](restart.md).
- **Host shows no Elefante tools:** restart the host and verify that its entry
  launches `src.mcp.stdio_bridge`, not `src.mcp.server`.
- **Kuzu lock:** stop the competing database-owning process; see
  [`kuzu-troubleshooting.md`](kuzu-troubleshooting.md).
- **Import error:** use the exact virtual-environment Python and a matching
  `PYTHONPATH`; do not use system Python accidentally.
- **JSON parse failure in the host:** inspect stderr logs. Any ordinary text on
  MCP stdout is a defect.

Never expose port 8765 publicly. The daemon has no public-network
authentication contract.
