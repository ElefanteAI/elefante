# Connect an Autonomous Agent to Elefante

This procedure is for an MCP-capable agent host. Released customers should use
the v2.12.2 platform installer; source and Docker instructions are separate
developer/community paths.

## Customer path

1. Download the v2.12.2 archive for the customer's platform from the
   [GitHub release](https://github.com/ElefanteAI/elefante/releases/tag/v2.12.2).
2. Verify the archive against `SHA256SUMS` from the same release.
3. Extract it and run the platform launcher described in
   [`install.md`](install.md).
4. Let the installer connect every compatible host it detects to the same
   account-level Elefante runtime.
5. Restart the host and verify the MCP surface.

Do not point a customer host at a repository checkout. The installed daemon and
storage-free bridge are the supported customer topology.

## Verify the connection

Ask the host to list Elefante's MCP surface. The released contract is 16 tools
and 2 prompts; see [`../reference/tools.md`](../reference/tools.md).

Then perform a non-destructive check:

1. Call `elefante-System(action="status")`.
2. Call `elefante-Memory(action="search", query="Elefante connection check",
   limit=3)`.
3. Confirm the response is valid JSON-RPC and contains `TOKEN_STATS`.

Do not create a dummy memory in the customer's real store. Installer and CI
tests use isolated data directories for write verification.

## Operating rule

Before an agent writes, updates, deletes, or connects graph entities, it must
search first. This is enforced by the MCP Compliance Gate. Search results are
context candidates, not automatically correct answers; the agent must compare
them with the current task and source evidence.

## Source or community integration

For development from a checkout, follow [`run-mcp-server.md`](run-mcp-server.md)
and configure the host with the exact virtual-environment Python path. Agent
Zero is a community-only container route; follow [`docker.md`](docker.md). Do
not describe it as certified until host-driven acceptance evidence exists.

## Troubleshooting

- If the host shows no tools, restart it after installation and run the
  installed health/handshake verifier.
- If writes are blocked, perform a memory search in the same MCP session first.
- If different hosts show different memories, repair the customer installation;
  all compatible hosts should point to one user-level runtime.
- If the dashboard is stale, refresh its snapshot through
  `elefante-DashboardOpen(refresh=true)`; browser reload does not read live
  stores.

See [`configure-ide.md`](configure-ide.md) for host-specific compatibility and
configuration boundaries.
