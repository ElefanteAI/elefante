# IDE MCP Configuration (Authoritative)

This page is the **single authoritative reference** for configuring IDEs to launch the Elefante MCP server.

Elefante MCP server command (same for all IDEs):

- Command: `.../.venv/bin/python`
- Args: `-m src.mcp.server`
- Required env:
  - `PYTHONPATH=/absolute/path/to/Elefante`
  - `ELEFANTE_CONFIG_PATH=/absolute/path/to/Elefante/config.yaml`
- Recommended env:
  - `ANONYMIZED_TELEMETRY=False` (disables ChromaDB telemetry)

## The Native SDD Gatekeeper (System Prompts)

To enable **Spec-Driven Development (SDD)** with Elefante, you must configure a "Gatekeeper" system prompt in your IDE. This instructs the agent to query Elefante's `SPECIFICATION` memories before writing code.

**Where to put the Gatekeeper prompt depending on your IDE:**

- **Cursor:** Create a `.cursorrules` file in the root of your project workspace.
- **Roo Code / Cline:** Create a `.clinerules` file in the root of your project workspace.
- **GitHub Copilot:** Create a `.github/copilot-instructions.md` file in the root of your project workspace.
- **Manual role adoption for any agent:** Read `AGENT.md` at the repo root. Elefante's installer creates `AGENT.md` as a developer-local symlink to `.github/copilot-instructions.md` so agents can be told to "read AGENT.md and adopt this identity".

**Recommended Gatekeeper text:**
> "Before you write any code or mark a task as complete, you MUST call `elefante-MemorySearch` to find any relevant `SPECIFICATION` or `DIRECTIVE` memories. You must comply with these architectural rules unconditionally."

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
      "args": ["-m", "src.mcp.server"],
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
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
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
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
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml"
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
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante",
        "ELEFANTE_CONFIG_PATH": "/absolute/path/to/Elefante/config.yaml",
        "ANONYMIZED_TELEMETRY": "False"
      }
    }
  }
}
```

Notes:

- Some Bob-IDE distributions store this as `mcp_settings.json`.
- Locations vary by IDE distribution; the auto-config script attempts multiple common paths.

Auto-config:

- Run: `python scripts/setup/configure_vscode_bob.py`
  - Default configures VS Code via `mcp.json` and removes duplicate `chat.mcp.servers.elefante`.
  - To configure `chat.mcp.servers` explicitly: `python scripts/setup/configure_vscode_bob.py --vscode chat-settings`

## Antigravity (Gemini)

Antigravity uses a file similar to Cursor/Bob:

- macOS/Linux: `~/.gemini/antigravity/mcp_config.json`
- Windows: `%USERPROFILE%\.gemini\antigravity\mcp_config.json`

Auto-config:

- Run: `python scripts/setup/configure_antigravity.py`

## Quick verification (any IDE)

Run this in the Elefante repo to confirm the server boots and speaks MCP:

```bash
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

If you hit a Kuzu “database locked” error, it usually means another process is holding the graph DB open. Close the other IDE/session first, then retry.
