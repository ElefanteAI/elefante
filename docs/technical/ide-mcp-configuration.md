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

## VS Code (Built-in MCP)

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

Workspace-local option:

- Create `.vscode/mcp.json`

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

## Roo-Cline (VS Code extension)

Roo-Cline config lives in VS Code `settings.json`.

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

- Run: `python scripts/configure_vscode_bob.py`

## Antigravity (Gemini)

Antigravity uses a file similar to Cursor/Bob:

- macOS/Linux: `~/.gemini/antigravity/mcp_config.json`
- Windows: `%USERPROFILE%\.gemini\antigravity\mcp_config.json`

Auto-config:

- Run: `python scripts/configure_antigravity.py`

## Quick verification (any IDE)

Run this in the Elefante repo to confirm the server boots and speaks MCP:

```bash
./.venv/bin/python scripts/verify_mcp_handshake.py
```

If you hit a Kuzu “database locked” error, it usually means another process is holding the graph DB open. Close the other IDE/session first, then retry.
