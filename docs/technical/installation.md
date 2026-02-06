# Installation & Configuration

**Quick Start**: Run `install.bat` (Windows) or `install.sh` (Mac/Linux)
**Troubleshooting**: See [`installation-safeguards.md`](installation-safeguards.md) for automated protection against common failures

---

## Prerequisites

- **Python**: **3.11 ONLY** (See [`python-version-requirements.md`](python-version-requirements.md) for mandatory details)
  - 3.9, 3.10:  Not supported
  - **3.11**:  Required and tested
  - 3.12+:  Not supported
- **Git**: For cloning the repository
- **Disk Space**: Minimum 5GB free
- **OS**: Windows, macOS, or Linux

---

## 1. Automated Installation (Recommended)

The installation scripts handle everything automatically:

- Create virtual environment
- Install dependencies
- Initialize databases (ChromaDB + Kuzu)
- Configure IDE integration
- Run health checks

### Windows

```cmd
install.bat
```

### Mac/Linux

```bash
chmod +x install.sh
./install.sh
```

### What Happens During Installation

1. **Pre-Flight Checks** (automated safeguards)

   - Disk space verification (5GB+ required)
   - Dependency version compatibility
   - Kuzu database path validation
   - See [`installation-safeguards.md`](installation-safeguards.md) for details

2. **Environment Setup**

   - Creates `.venv` virtual environment
   - Installs all dependencies from `requirements.txt`
   - Configures Python path

3. **Database Initialization**

   - Creates `~/.elefante/data/` directory
   - Initializes ChromaDB (vector store)
   - Initializes Kuzu (graph database)
   - Creates default schema

4. **IDE Configuration**

   - Auto-detects VS Code, Cursor, or Bob IDE
   - Configures MCP (Model Context Protocol)
   - Sets up server connection

5. **Health Check**
   - Verifies all components working
   - Tests database connections
   - Validates MCP server

**Installation Time**: ~10 minutes (depending on internet speed)

---

## Golden Path (macOS + VS Code)

1. Run the installer from the repo root:

```bash
chmod +x install.sh
./install.sh
```

2. Restart VS Code.

3. Verify MCP server is configured in User scope (`mcp.json`).

4. Verify tool registration:

```bash
./.venv/bin/python scripts/list_mcp_tools.py
```

5. Dashboard (snapshot + server):

```bash
./.venv/bin/python scripts/update_dashboard_data.py
./.venv/bin/python -m src.dashboard.server
```

Open: http://127.0.0.1:8000

---

## 2. Manual Installation

If automated installation fails or you prefer manual control:

### Step 1: Clone Repository

```bash
git clone https://github.com/yourusername/Elefante.git
cd Elefante
```

### Step 2: Create Virtual Environment

**CRITICAL**: Use Python 3.11 explicitly (see [`python-version-requirements.md`](python-version-requirements.md))

Mac/Linux:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
```

Windows:

```bash
python3.11 -m venv .venv
.venv\Scripts\activate
```

**Verify Python 3.11 is active**:

```bash
python --version
# Must output: Python 3.11.x
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Initialize Databases

```bash
python scripts/init_databases.py
```

### Step 5: Configure IDE (see section 3 below)

---

## 3. IDE Integration (MCP)

Elefante integrates with AI coding assistants via the **Model Context Protocol (MCP)**.

### Automated Configuration

Run the configuration script to auto-detect and configure your IDE:

```bash
python scripts/configure_vscode_bob.py
```

Supported IDEs:

- VS Code (with Roo-Cline extension)
- Cursor
- Bob IDE

### Manual Configuration

If automatic configuration fails, do not guess the JSON shape for your IDE. Use the authoritative reference:

- See [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md)

**Rule of thumb**: your IDE should launch Elefante using the repo venv Python (absolute path) and `-m src.mcp.server`, with `PYTHONPATH` and `ELEFANTE_CONFIG_PATH` set.

#### VS Code (Built-in MCP)

VS Code supports MCP natively (Copilot Chat). Configure servers in `mcp.json`.

You can open the correct file from the Command Palette:

- `MCP: Open User Configuration`
- `MCP: Open Workspace Folder Configuration`

Common user configuration locations:

- macOS (stable): `~/Library/Application Support/Code/User/mcp.json`
- macOS (Insiders): `~/Library/Application Support/Code - Insiders/User/mcp.json`
- Windows (stable): `%APPDATA%\Code\User\mcp.json`
- Windows (Insiders): `%APPDATA%\Code - Insiders\User\mcp.json`
- Linux (stable): `~/.config/Code/User/mcp.json`
- Linux (Insiders): `~/.config/Code - Insiders/User/mcp.json`

Example `mcp.json` (user or workspace config): see [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md).

Notes:

- For a workspace-specific config, create `.vscode/mcp.json`.
- You can open the right file from the Command Palette with `MCP: Open User Configuration` or `MCP: Open Workspace Folder Configuration`.

#### Roo-Cline / Cursor / Bob / Antigravity

These IDEs use different MCP config file locations and JSON keys.
To avoid stale examples, this guide intentionally links to the canonical page instead of duplicating JSON blocks:

- See [docs/technical/ide-mcp-configuration.md](docs/technical/ide-mcp-configuration.md)

---

## 4. Verification

After installation, verify everything works:

### Test MCP Connection

```bash
python scripts/health_check.py
```

Expected output:

```text
 ChromaDB: Connected
 Kuzu: Connected
 MCP Server: Running
 All systems operational
```

### List MCP Tools

```bash
./.venv/bin/python scripts/list_mcp_tools.py
```

### Dashboard Smoke Check

```bash
./.venv/bin/python scripts/update_dashboard_data.py
./.venv/bin/python -m src.dashboard.server
```

Open: http://127.0.0.1:8000

### 6. System Verification (Automated)

The installation script checks:

- **MCP Liveness**: Performs a real JSON-RPC handshake (`scripts/verify_mcp_handshake.py`).
- **Inception Memory**: Ingests the "Agentic Optimization Protocol" (`scripts/ingest_inception.py`).

### Verification Command (Manual)

To verify the system yourself after install:

```bash
python scripts/health_check.py
```

To verify the Inception Memory (The Prime Directive):

```bash
python -c "import sys; sys.path.append('.'); import asyncio; from src.core.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().search_memories('Agentic Protocol'))"
```

This should return the Elefante Agentic Optimization Protocol.

---

## 5. Troubleshooting

### Common Issues

**Issue**: `Database path cannot be a directory`
**Solution**: See [`installation-safeguards.md`](installation-safeguards.md) - automated fix included

**Issue**: `ModuleNotFoundError: No module named 'src'`
**Solution**: Ensure PYTHONPATH is set correctly in MCP config

**Issue**: `MCP server not responding`
**Solution**:

1. Check virtual environment is activated
2. Verify Python path in MCP config points to venv Python
3. Restart IDE

**Issue**: `Insufficient disk space`
**Solution**: Free up at least 5GB of disk space

### Getting Help

1. Check [`installation-safeguards.md`](installation-safeguards.md) for automated protections
2. Review `install.log` for detailed error messages
3. See [`../debug/README.md`](../debug/README.md) for debugging guides
4. Check GitHub Issues for known problems

---

## 6. Next Steps

After successful installation:

1. **Read the Walkthrough**: [`walkthrough.md`](walkthrough.md)
2. **Explore the API**: [`usage.md`](usage.md)
3. **Try the Dashboard**: [`dashboard.md`](dashboard.md)
4. **Understand Architecture**: [`architecture.md`](architecture.md)

---

## 7. Uninstallation

To completely remove Elefante:

```bash
# 1. Deactivate virtual environment
deactivate

# 2. Remove installation directory
rm -rf Elefante/  # or delete folder on Windows

# 3. Remove data directory (optional - contains your memories)
rm -rf ~/.elefante/
```

**Warning**: Step 3 deletes all stored memories. Backup first if needed.

---

**Version**: 1.6.2
**Last Updated**: 2025-12-28
**Status**: Production Ready
