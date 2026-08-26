# Connect IDEs and Agent Hosts

**Applies to:** v2.12.3

The release installer is the configuration authority. It detects compatible
hosts and connects all of them to one user-level Elefante daemon. Rerun the
same installer after adding a host; do not create a second memory runtime.

## Shared bridge contract

Stdio-only hosts launch the installed Python with:

```text
-m src.mcp.stdio_bridge
```

The entry points to the stable customer runtime, not the extracted ZIP or a
developer checkout, and carries:

- `PYTHONPATH=<stable Elefante runtime>`
- `ELEFANTE_CONFIG_PATH=<stable runtime>/config.yaml`
- `ELEFANTE_DAEMON_URL=http://127.0.0.1:8765/mcp/`
- `ELEFANTE_CLIENT_TOOL=<canonical host id>`

The bridge is transport-only. SQLite and Kuzu remain owned by the daemon.
`ANONYMIZED_TELEMETRY=False` may remain in legacy configurations but is not
required by the default SQLite runtime.

## Configuration ownership

Elefante writes only the `elefante` registration for a detected host and
records what it owns. It preserves:

- unrelated MCP servers;
- user-managed Elefante entries;
- malformed files that cannot be changed safely;
- installer-owned entries modified after installation.

Writes are atomic. Upgrade and uninstall may refresh or remove only an entry
that still matches the recorded installer fingerprint.

## Current tiers

| Tier | Hosts | Meaning |
|---|---|---|
| Compatible | VS Code, Cursor, Kiro, Gemini CLI, Claude Code, Codex, OpenClaw | Released adapter and contract tests; host-driven lifecycle certification incomplete |
| Preview | IBM Bob, Antigravity | Installer output exists; full adapter and host-lifecycle proof is incomplete |
| Community | Agent Zero and other MCP-capable hosts | Manual bridge route; Elefante does not own the host lifecycle |
| Planned | Windsurf, Cline, Roo, Kilo, Continue, Zed, Aider, Kiro Skills/Steering | No released integration claim |
| Certified | None | Requires real-host install, reconnect, upgrade, and uninstall evidence |

Do not infer support from a host name appearing in development files. The
machine-readable developer inventory is
`agents/manifests/ide-integration.yaml`; its verification dates are not host
certification.

## Adapter-managed hosts

Customers normally use the release installer. These commands are for source
developers and support diagnostics:

```bash
./.venv/bin/python scripts/setup/configure_vscode_bob.py
./.venv/bin/python scripts/setup/configure_cursor_kiro.py --host cursor
./.venv/bin/python scripts/setup/configure_cursor_kiro.py --host kiro
./.venv/bin/python scripts/setup/configure_cursor_kiro.py --host gemini
./.venv/bin/python scripts/setup/configure_antigravity.py
./.venv/bin/python scripts/setup/configure_cli_agents.py --host claude-code
./.venv/bin/python scripts/setup/configure_cli_agents.py --host codex
./.venv/bin/python scripts/setup/configure_cli_agents.py --host openclaw
```

Each adapter detects its host before writing. The customer installer does not
create host directories merely to make detection succeed.

## Manual fallback

Use manual configuration only when the installer cannot own the host. Adapt the
following structure to the host's current MCP schema:

```json
{
  "mcpServers": {
    "elefante": {
      "command": "/absolute/stable/elefante/.venv/bin/python",
      "args": ["-m", "src.mcp.stdio_bridge"],
      "env": {
        "PYTHONPATH": "/absolute/stable/elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/stable/elefante/config.yaml",
        "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
        "ELEFANTE_CLIENT_TOOL": "generic-mcp-client"
      }
    }
  }
}
```

Host configuration schemas change. Verify the current primary vendor
documentation before translating this generic contract, and label the result
community-tier until a maintained adapter and host-driven test exist.

## Agent guidance

An instruction file may tell the host when to use Elefante, but it does not
create the MCP connection. Keep that guidance small:

```text
Search Elefante when the task may depend on prior preferences, decisions, or
project context. Treat retrieved memories as evidence candidates, surface
conflicts, and store only durable information after searching first.
```

Do not demand a memory search for every self-contained question, and do not
store every conversation. The maintained repository example is
`.github/copilot-instructions.md`.

## Verify any host

1. Confirm daemon health:

   ```bash
   curl --fail http://127.0.0.1:8765/health
   ```

2. Restart the host.
3. Confirm it lists Elefante's 16 tools and 2 prompts.
4. Call `elefante-System(action="status")`.
5. Run a read-only memory search.

From a source checkout, also run:

```bash
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

If one host shows different memories, it is probably connected to a different
runtime. Repair the customer installation; do not copy databases between
running processes.

## Container boundary

Agent Zero commonly runs in a container, so host filesystem and loopback do not
mean the same thing as on the Mac or PC. Do not expose port 8765 publicly to
reach a container. Use a trusted same-runtime or explicitly secured network
design; the released product does not claim a certified container bridge.
