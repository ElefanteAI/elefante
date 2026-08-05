# IDE MCP Configuration (Authoritative)

This page is the **single authoritative reference** for configuring IDEs to use the shared Elefante daemon.

Start the user-scoped daemon first (`python scripts/lifecycle/daemon_service.py install --apply`). IDEs run a transport-only stdio bridge; they never open Elefante's databases themselves.

Ownership rule: a setup or upgrade never replaces an existing `elefante` MCP
entry unless the entry and its containing JSON file exactly match the prior
installer manifest. User-managed entries, malformed JSON, and externally
modified files are preserved. Configuration writes are atomic.

The release installer is the normal customer path. It connects every detected
compatible host to the single runtime in `~/.elefante/app/current` (or
`%LOCALAPPDATA%\Elefante\app\current` on Windows) and fails rather than claiming
success when a detected host cannot be verified. The manual examples below are
fallback and developer-reference paths; they must all target the same stable
runtime and loopback daemon when used for a customer installation.

Elefante bridge command (same shape for all stdio-only IDEs):

- Command: `.../.venv/bin/python`
- Args: `-m src.mcp.stdio_bridge`
- Required env:
  - `PYTHONPATH=/absolute/path/to/Elefante`
  - `ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml`
  - `ELEFANTE_DAEMON_URL=http://127.0.0.1:8765/mcp/`
  - `ELEFANTE_CLIENT_TOOL=<host-name>`
- Recommended env:
  - `ANONYMIZED_TELEMETRY=False` (retained for legacy ChromaDB compatibility)

## Agent Grounding Instructions (System Prompts)

To keep instruction files small and durable, configure your IDE prompt so the agent queries Elefante for relevant `specification` and `directive` memories before writing code.

**Where to put the grounding instructions depending on your IDE:**

- **Cursor:** Create a `.cursorrules` file in the root of your project workspace.
- **Roo Code / Cline:** Create a `.clinerules` file in the root of your project workspace.
- **GitHub Copilot:** Create a `.github/copilot-instructions.md` file in the root of your project workspace.
- **Manual role adoption for any agent:** Read `AGENT.md` at the repo root. Elefante's installer creates `AGENT.md` as a developer-local symlink to `.github/copilot-instructions.md` so agents can be told to "read AGENT.md and adopt this identity".

**Recommended grounding text:**
> "Before you write any code or mark a task as complete, you MUST call `elefante-Memory(action="search")` to find any relevant `SPECIFICATION` or `DIRECTIVE` memories. You must comply with these architectural rules unconditionally."

## VS Code (Built-in MCP)

Important: choose **one** VS Code configuration mechanism.

- Prefer **Built-in MCP** via `mcp.json`.
- Only use `chat.mcp.servers` if your VS Code build/extension specifically requires it.
- If you configure both, VS Code may show **two** Elefante servers.

VS Code supports MCP natively. Configuration file is `mcp.json`.

Open from Command Palette:

- `MCP: Open User Configuration`
- `MCP: Open Workspace Folder Configuration`

Common locations:

- macOS (stable): `~/Library/Application Support/Code/User/mcp.json`
- macOS (Insiders): `~/Library/Application Support/Code - Insiders/User/mcp.json`
- Windows (stable): `%APPDATA%\Code\User\mcp.json`
- Windows (Insiders): `%APPDATA%\Code - Insiders\User\mcp.json`
- Linux (stable): `~/.config/Code/User/mcp.json`
- Linux (Insiders): `~/.config/Code - Insiders/User/mcp.json`

Policy: Elefante is enabled globally.

- Configure Elefante in **User** `mcp.json` (global), not per-workspace.
- Do not create `.vscode/mcp.json` with a `servers.elefante` entry, or you will get duplicates.
- If you need a template in the repo, keep it as `.vscode/mcp.example.jsonc` (VS Code will not load it).

Avoid duplicates:

- VS Code merges **User** (`~/.../User/mcp.json`) and **Workspace** (`.vscode/mcp.json`) servers.
- If both define `servers.elefante`, VS Code may show **two identical Elefante servers**.
- Required fix (global policy):
  - Keep `servers.elefante` in **User** `mcp.json`.
  - Ensure `.vscode/mcp.json` does **not** define `servers.elefante` (workspace can be empty).

Example:

```json
{
  "servers": {
    "elefante": {
      "type": "stdio",
      "command": "/absolute/path/to/Elefante/.venv/bin/python",
      "args": ["-m", "src.mcp.stdio_bridge"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
        "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
        "ELEFANTE_CLIENT_TOOL": "vscode-copilot",
        "ANONYMIZED_TELEMETRY": "False"
      }
    }
  }
}
```

## VS Code Chat MCP (Experimental)

Use this section only if you cannot use `mcp.json` or your setup explicitly requires `chat.mcp.servers`.
If you already have `mcp.json` configured, remove `chat.mcp.servers.elefante` to avoid duplicates.

Some builds/extensions use VS Code `settings.json` keys under `chat.mcp.servers`.

Example:

```json
{
  "chat.mcp.gallery.enabled": true,
  "chat.mcp.servers": {
    "elefante": {
      "command": "/absolute/path/to/Elefante/.venv/bin/python",
      "args": ["-m", "src.mcp.stdio_bridge"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
        "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
        "ELEFANTE_CLIENT_TOOL": "vscode-copilot",
        "ANONYMIZED_TELEMETRY": "False"
      },
      "autoStart": true
    }
  }
}
```

## Roo Code (formerly Roo-Cline)

Roo Code config lives in VS Code `settings.json`. The settings key may still appear as `roo-cline.mcpServers` in some installations.

```json
{
  "roo-cline.mcpServers": {
    "elefante": {
      "command": "/absolute/path/to/Elefante/.venv/bin/python",
      "args": ["-m", "src.mcp.stdio_bridge"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
        "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
        "ELEFANTE_CLIENT_TOOL": "roo-code"
      }
    }
  }
}
```

## Cursor / IBM Bob (mcp_config.json / mcp_settings.json)

Many IDEs use a config with a top-level `mcpServers` key.

```json
{
  "mcpServers": {
    "elefante": {
      "command": "/absolute/path/to/Elefante/.venv/bin/python",
      "args": ["-m", "src.mcp.stdio_bridge"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
        "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
        "ELEFANTE_CLIENT_TOOL": "ibm-bob",
        "ANONYMIZED_TELEMETRY": "False"
      }
    }
  }
}
```

Notes:

- Some Bob-IDE distributions store this as `mcp_settings.json`.
- Locations vary by IDE distribution; the auto-config script attempts multiple common paths.
- For Cursor, use `ELEFANTE_CLIENT_TOOL: "cursor"`; use `"ibm-bob"` for Bob.

Auto-config:

- Run: `python scripts/setup/configure_vscode_bob.py`
  - Default configures VS Code via `mcp.json` and removes duplicate `chat.mcp.servers.elefante`.
  - To configure `chat.mcp.servers` explicitly: `python scripts/setup/configure_vscode_bob.py --vscode chat-settings`

## Kiro

Kiro supports global `~/.kiro/settings/mcp.json` and workspace `.kiro/settings/mcp.json` files with a top-level `mcpServers` object. Elefante configures the global bridge only, so the local daemon can serve Kiro alongside other hosts.

```bash
python scripts/setup/configure_cursor_kiro.py --host kiro
```

The installer does nothing unless the `~/.kiro` host directory already exists. The emitted entry is marked `ELEFANTE_CLIENT_TOOL=kiro`; Kiro Skills and Steering are separate, currently planned surfaces. See [Kiro's MCP configuration reference](https://kiro.dev/docs/mcp/configuration/).

## Gemini CLI

Gemini CLI uses `~/.gemini/settings.json` with a top-level `mcpServers`
object. When both Gemini CLI and an existing `~/.gemini` directory are
detected, Elefante writes only `mcpServers.elefante`, preserves every other
server, and records exact entry ownership for safe uninstall:

```bash
python scripts/setup/configure_cursor_kiro.py --host gemini
gemini mcp list
```

The emitted bridge sets `ELEFANTE_CLIENT_TOOL=gemini` and intentionally omits
the Cursor/Kiro-specific `disabled` field because Gemini CLI's documented MCP
schema does not define it. Gemini treats MCP servers as untrusted by default;
Elefante does not set a host-level trust bypass. See the official [Gemini CLI
MCP guide](https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md).

## Claude Code

Claude Code uses its native CLI to manage a user-scoped MCP server in `~/.claude.json`. Elefante uses that CLI instead of editing Claude configuration directly:

```bash
python scripts/setup/configure_cli_agents.py --host claude-code
claude mcp get elefante
```

Equivalent manual command:

```bash
claude mcp add --scope user \
  --env PYTHONPATH=/absolute/path/to/Elefante \
  --env ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml \
  --env ELEFANTE_DAEMON_URL=http://127.0.0.1:8765/mcp/ \
  --env ELEFANTE_CLIENT_TOOL=claude-code \
  --transport stdio elefante -- /absolute/path/to/Elefante/.venv/bin/python -m src.mcp.stdio_bridge
```

The adapter leaves an existing user-managed `elefante` registration untouched. When a registration exactly matches Elefante's install manifest, a later installer run can refresh it after a move or upgrade; a failed refresh restores the previous command. Claude Code documents user-scoped MCP registration, inspection, and removal through its MCP CLI in its [MCP reference](https://code.claude.com/docs/en/mcp).

## Codex

Codex CLI and the Codex IDE extension share `~/.codex/config.toml`; Elefante registers through the native `codex mcp` command so the host remains the configuration authority.

```bash
python scripts/setup/configure_cli_agents.py --host codex
codex mcp get elefante
```

Equivalent manual command:

```bash
codex mcp add \
  --env PYTHONPATH=/absolute/path/to/Elefante \
  --env ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml \
  --env ELEFANTE_DAEMON_URL=http://127.0.0.1:8765/mcp/ \
  --env ELEFANTE_CLIENT_TOOL=codex \
  elefante -- /absolute/path/to/Elefante/.venv/bin/python -m src.mcp.stdio_bridge
```

See the [Codex MCP documentation](https://learn.chatgpt.com/docs/extend/mcp) for host-level management. The adapter never overwrites a user-managed registration; it can safely refresh only a matching installer-owned entry and restores the prior entry if an update fails.

## Compatibility tiers

- **Compatible:** Claude Code, Codex, Gemini CLI, OpenClaw, VS Code, Cursor, and Kiro have a documented bridge configuration and Elefante adapter coverage.
- **Preview:** Bob and Antigravity emit bridge configuration but still need their own adapter and host-lifecycle proof before entering the compatible tier.
- **Certified:** no host is certified yet. Certification requires an automated install, reconnect, upgrade, and uninstall round-trip against the host itself.
- **Community:** Agent Zero has a documented manual MCP path but no Elefante-owned container lifecycle adapter yet. Other MCP-capable clients can use the standard bridge contract.

## Antigravity (Gemini)

Antigravity uses a file similar to Cursor/Bob:

- macOS/Linux: `~/.gemini/antigravity/mcp_config.json`
- Windows: `%USERPROFILE%\.gemini\antigravity\mcp_config.json`

Auto-config:

- Run: `python scripts/setup/configure_antigravity.py`

## OpenClaw

OpenClaw is an MCP client registry, so it can launch Elefante's local stdio
bridge without giving the agent direct database ownership. When the `openclaw`
CLI is installed, Elefante configures it through the native registry and records
only the matching registration for safe refresh and uninstall:

```bash
python scripts/setup/configure_cli_agents.py --host openclaw
openclaw mcp doctor elefante --probe
```

OpenClaw owns the registration and lifecycle. The adapter is compatible, not
certified, until Elefante verifies install, reconnect, upgrade, and uninstall
against the real host. See [OpenClaw's MCP CLI reference](https://docs.openclaw.ai/cli/mcp).

## Agent Zero and Grok

Agent Zero accepts standard MCP JSON from **Settings → MCP/A2A → External MCP
Servers**, but its common Docker deployment changes the filesystem and network
boundary. Do not expose Elefante's loopback daemon publicly just to reach a
container. Use an explicitly designed, authenticated container/network path or
run Elefante inside the same trusted runtime; a container-safe shared-memory
adapter remains community-tier work. See [Agent Zero's MCP setup guide](https://www.agent-zero.ai/p/docs/mcp-a2a/).

Grok is a model provider, not an MCP client configuration surface. Elefante
integrates with the agent host that uses Grok (for example, a configured Agent
Zero or OpenClaw runtime), so memory behavior stays consistent when the model is
changed.

## Quick verification (any IDE)

Run this in the Elefante repo to confirm the server boots and speaks MCP:

```bash
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

Bridge-based hosts share the daemon and therefore do not open their own Kuzu databases. If the daemon is unavailable, inspect `http://127.0.0.1:8765/health` and restart the user service.
