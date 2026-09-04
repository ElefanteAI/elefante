# Agent Zero Integration

> **Status:** COMMUNITY PATH. Agent Zero has documentation and container
> guidance, but no Elefante-owned, host-certified lifecycle adapter.

## Intended outcome

Agent Zero should use the same account-level Elefante memory as other agent
hosts. It must not create a second authoritative store or bypass the shared
daemon's write and provenance controls.

## Current safe path

- Elefante stores semantic memory in SQLite and relationships in Kuzu.
- The current published MCP surface is 18 tools and 2 prompts, including
  verified `elefante-Recover`. The separate default-off Task Intelligence
  evaluation surface is developer-only. Memory CRUD/search uses the consolidated
  `elefante-Memory(action=...)` tool.
- A container connects to the host runtime only through an explicitly configured
  local boundary. Do not expose the dashboard or MCP service publicly.
- The operator remains responsible for container networking, volume ownership,
  and backup/restore verification.

See [`docs/how-to/agent-handoff.md`](../../../docs/how-to/agent-handoff.md) for
the current manual procedure and [`docs/reference/tools.md`](../../../docs/reference/tools.md)
for the live MCP contract.

## What is not proven

- One-click Agent Zero detection, installation, upgrade, or uninstall.
- Host-driven reconnect and concurrent-use certification.
- Automatic synchronization with Agent Zero's internal FAISS memory.
- Safe operation across an untrusted or public container network.

These are Upcoming ideas without an assigned version or date. Until the full
lifecycle is automated and tested in the actual host, describe Agent Zero as a
community integration only.

## Certification gate

1. Detect a real Agent Zero installation without mutation.
2. Configure only an explicit, inspectable MCP entry.
3. Complete a real memory add/search round trip through the installed runtime.
4. Preserve distinct Source provenance during concurrent use with another host.
5. Prove upgrade and uninstall without altering unrelated Agent Zero state.
6. Document the container trust boundary and recovery path.
