# Installation & Configuration

## 1. Automated Installation (Recommended)

The included scripts create a virtual environment, install dependencies, initialize databases, and inject IDE configuration.

- **Windows:** Double-click `install.bat`.
- **Mac/Linux:** Run `chmod +x install.sh && ./install.sh`.

## 2. Manual Installation

1.  **Environment:** Python 3.10+ and Git required.
2.  **Venv Setup:**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # or .venv\Scripts\activate on Windows
    pip install -r requirements.txt
    ```
3.  **Database Init:** Run `python scripts/init_databases.py`.

## 3. IDE Integration (MCP)

Elefante integrates via the **Model Context Protocol**.

### Automated Config

Run `python scripts/configure_vscode_bob.py` to auto-detect and configure VS Code or Bob IDE.

### Manual Config

Add the following to your IDE's `settings.json` or MCP config:

```json
{
  "mcpServers": {
    "elefante": {
      "command": "python", // Ensure this points to the VENV python executable
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/Elefante",
      "env": { "PYTHONPATH": "/absolute/path/to/Elefante" }
    }
  }
}
```

_[Note: Replace paths with your absolute system paths]_.
