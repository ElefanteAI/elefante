# Installation & Configuration

**Quick Start**: Run `install.bat` (Windows) or `install.sh` (Mac/Linux)
**Troubleshooting**: See [`installation-safeguards.md`](installation-safeguards.md) for automated protection against common failures

---

## Prerequisites

- **Python**: 3.10 or higher
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

## 2. Manual Installation

If automated installation fails or you prefer manual control:

### Step 1: Clone Repository
```bash
git clone https://github.com/yourusername/Elefante.git
cd Elefante
```

### Step 2: Create Virtual Environment
```bash
python -m venv .venv

# Activate (Windows)
.venv\Scripts\activate

# Activate (Mac/Linux)
source .venv/bin/activate
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

If automatic configuration fails, add this to your IDE's MCP config:

**VS Code** (`settings.json`):
```json
{
  "roo-cline.mcpServers": {
    "elefante": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "C:\\absolute\\path\\to\\Elefante",
      "env": {
        "PYTHONPATH": "C:\\absolute\\path\\to\\Elefante"
      }
    }
  }
}
```

**Cursor/Bob** (`mcp_config.json`):
```json
{
  "mcpServers": {
    "elefante": {
      "command": "python",
      "args": ["-m", "src.mcp.server"],
      "cwd": "/absolute/path/to/Elefante",
      "env": {
        "PYTHONPATH": "/absolute/path/to/Elefante"
      }
    }
  }
}
```

**Important**: Replace paths with your actual absolute system paths.

---

## 4. Verification

After installation, verify everything works:

### Test MCP Connection
```bash
python scripts/health_check.py
```

Expected output:
```
✅ ChromaDB: Connected
✅ Kuzu: Connected
✅ MCP Server: Running
✅ All systems operational
```

### Test Memory Operations
```bash
python examples/validate_system.py
```

This will:
- Store a test memory
- Search for it
- Query the graph
- Verify all operations work

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

**Version**: 1.0.0
**Last Updated**: 2025-12-04
**Status**: Production Ready
