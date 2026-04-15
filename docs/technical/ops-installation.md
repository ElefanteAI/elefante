# Installation & Configuration

**Quick Start**: Run `install.bat` (Windows) or `install.sh` (Mac/Linux)
**Troubleshooting**: See [`debug/ops-installation-compendium.md`](../debug/ops-installation-compendium.md) for automated protection against common failures

---

## Prerequisites

- **Python 3.11+** required (3.11 supported, 3.12-3.13 recommended). See [Appendix A](#appendix-a-python-version-details) for OS-specific installation, pyenv setup, and troubleshooting.
- **Git**: For cloning the repository
- **Disk Space**: Minimum 2GB free
- **OS**: Windows, macOS, or Linux

---

## 1. Automated Installation (Recommended)

The installation scripts handle everything automatically:

- Create virtual environment
- Install dependencies
- Initialize databases (ChromaDB + Kuzu)
- Configure IDE integration
- Run health checks

If `.venv` already exists, the installer prompts for one of four actions:

- Delete existing `.venv` and install fresh (default)
- Backup existing `.venv` to `.venv.backup.<timestamp>` and install fresh
- Reuse existing `.venv`
- Abort installation

### Windows

```cmd
install.bat
```

### Mac/Linux

```bash
chmod +x install.sh
./install.sh
```

If `.venv` already exists, press Enter for a destructive fresh reinstall, choose backup+fresh to preserve the old environment, choose reuse to keep it, or abort.

### What Happens During Installation

1. **Pre-Flight Checks** (automated safeguards)
   - Disk space verification (5GB+ required)
   - Dependency version compatibility
   - Kuzu database path validation
   - See [`debug/ops-installation-compendium.md`](../debug/ops-installation-compendium.md) for details

2. **Environment Setup**
   - Creates `.venv` virtual environment
   - If `.venv` already exists, offers fresh delete, backup+fresh, reuse, or abort
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

5. **Agent Behavior Bootstrap**
   - Verifies `.github/copilot-instructions.md` exists
   - This file is the **entry point** that makes AI agents proactively use Elefante
   - Without it, agents can use Elefante tools but won't do so automatically
   - Also creates developer-local entry points for role adoption:
     - `AGENT.md` for manual "read AGENT.md and adopt this identity" onboarding
     - `.cursorrules` for Cursor auto-load
     - `.windsurfrules` for Windsurf auto-load

6. **Health Check**
   - Verifies all components working
   - Tests database connections
   - Validates MCP server

7. **Runtime Baseline Bootstrap**
   - Built-in system directives are available immediately on first server start
   - Required specification memories are seeded automatically on first orchestrator use
   - No manual seeding step is required for a fresh installation

**Installation Time**: ~10 minutes (depending on internet speed)

---

## Golden Path (Windows + VS Code)

1. Open **Command Prompt** (not PowerShell) from the repo root:

```cmd
install.bat
```

   > PowerShell alternative (if you prefer PS):
   > ```powershell
   > py -3.11 scripts\setup\install.py
   > ```

2. Restart VS Code.

3. Verify MCP server is configured at `%APPDATA%\Code\User\mcp.json`.

4. Verify tool registration:

```cmd
.venv\Scripts\python.exe scripts\ci\list_mcp_tools.py
```

5. Dashboard (snapshot + server):

```cmd
.venv\Scripts\python.exe scripts\pipeline\update_dashboard_data.py
.venv\Scripts\python.exe -m src.dashboard.server
```

Open: http://127.0.0.1:8000

> **Windows quick-reference**: Wherever this guide uses `./.venv/bin/python`, use `.venv\Scripts\python.exe` instead.

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
./.venv/bin/python scripts/ci/list_mcp_tools.py
```

5. Dashboard (snapshot + server):

```bash
./.venv/bin/python scripts/pipeline/update_dashboard_data.py
./.venv/bin/python -m src.dashboard.server
```

Open: http://127.0.0.1:8000

---

## 2. Manual Installation

If automated installation fails or you prefer manual control:

### Step 1: Clone Repository

```bash
git clone https://github.com/ElefanteAI/elefante.git
cd elefante
```

### Step 2: Create Virtual Environment

**CRITICAL**: Use Python 3.11 explicitly (see [Appendix A](#appendix-a-python-version-details))

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
python scripts/setup/init_databases.py
```

### Step 5: Configure IDE (see section 3 below)

---

## 3. IDE Integration (MCP)

Elefante integrates with AI coding assistants via the **Model Context Protocol (MCP)**.

### Automated Configuration

Run the configuration script to auto-detect and configure your IDE:

```bash
python scripts/setup/configure_vscode_bob.py
```

Supported IDEs:

- VS Code (with Roo-Cline extension)
- Cursor
- Bob IDE

### Manual Configuration

If automatic configuration fails, do not guess the JSON shape for your IDE. Use the authoritative reference:

See [`ops-ide-configuration.md`](ops-ide-configuration.md) for the authoritative MCP configuration reference (VS Code, Cursor, Bob, Antigravity).

---

## 4. Verification

After installation, verify everything works:

### Test MCP Connection

Windows:
```cmd
.venv\Scripts\python.exe scripts\verify\verify_health.py
```
macOS/Linux:
```bash
./.venv/bin/python scripts/verify/verify_health.py
```

Expected output:

```text
 ChromaDB: Connected
 Kuzu: Connected
 MCP Server: Running
 All systems operational
```

`verify_health.py` now also verifies the embedded runtime baseline:

- Built-in system directives are present
- The `STDOUT Purity Law` directive is active
- Required specification memories are available to search on a fresh install

### Verify MCP Handshake

Windows:
```cmd
.venv\Scripts\python.exe scripts\verify\verify_mcp_handshake.py
```
macOS/Linux:
```bash
./.venv/bin/python scripts/verify/verify_mcp_handshake.py
```

### Run the Live E2E Harness

Windows:
```cmd
.venv\Scripts\python.exe scripts\verify\verify_e2e_tests.py
```
macOS/Linux:
```bash
./.venv/bin/python scripts/verify/verify_e2e_tests.py
```

This harness now proves three installation-critical properties in one pass:

- The real MCP server survives the Kuzu shutdown-race regression path
- Built-in directives and specification memories are available without manual setup
- Memory persistence still survives a simulated IDE restart

It runs inside an isolated temporary Elefante home so verification does not pollute the user's durable memory store.

### List MCP Tools

Windows:
```cmd
.venv\Scripts\python.exe scripts\ci\list_mcp_tools.py
```
macOS/Linux:
```bash
./.venv/bin/python scripts/ci/list_mcp_tools.py
```

### Dashboard Smoke Check

Windows:
```cmd
.venv\Scripts\python.exe scripts\pipeline\update_dashboard_data.py
.venv\Scripts\python.exe -m src.dashboard.server
```
macOS/Linux:
```bash
./.venv/bin/python scripts/pipeline/update_dashboard_data.py
./.venv/bin/python -m src.dashboard.server
```

Open: http://127.0.0.1:8000

### 6. System Verification (Automated)

The installation script checks:

- **MCP Liveness**: Performs a real JSON-RPC handshake (`scripts/verify/verify_mcp_handshake.py`).
- **Runtime Baseline**: Verifies built-in directives and seeded specification memories via `scripts/verify/verify_health.py`.

### Verification Command (Manual)

Windows:
```cmd
.venv\Scripts\python.exe scripts\verify\verify_health.py
```
macOS/Linux:
```bash
python scripts/verify/verify_health.py
```

To verify the Inception Memory (The Prime Directive):

Windows:
```cmd
.venv\Scripts\python.exe -c "import sys; sys.path.append('.'); import asyncio; from src.core.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().search_memories('Agentic Protocol'))"
```
macOS/Linux:
```bash
python -c "import sys; sys.path.append('.'); import asyncio; from src.core.orchestrator import get_orchestrator; asyncio.run(get_orchestrator().search_memories('Agentic Protocol'))"
```

This should return the Elefante Agentic Optimization Protocol.

To verify the crash regression path specifically, run the E2E harness above and confirm the line:

```text
[PASS] Server survives repeated search/coactivation cycle
```

---

## 5. Troubleshooting

### Windows-Specific Issues

**Issue**: `ImportError: No module named 'fcntl'`
**Solution**: This is a known bug fixed in current code. Ensure you are running the latest version — `src/utils/elefante_mode.py` must have the `sys.platform != "win32"` guard around `import fcntl`. See `debug/ops-installation-compendium.md` → `pitfall: installation fcntl windows incompatibility`.

**Issue**: `install.bat` reports wrong Python version (e.g. `3.` instead of `3.11`)
**Solution**: Fixed in current `install.bat` (was a `tokens=1,2` parsing bug, now `tokens=1,2,3`). If on an older version, run `py -3.11 -m venv .venv` manually and proceed with manual install.

**Issue**: `install.bat` not finding Python 3.11
**Solution**: Install the **Windows Python Launcher** (`py.exe`) via the official Python 3.11 installer from https://python.org. The launcher allows `py -3.11` to select the correct version. Make sure "Add to PATH" and "py launcher" are checked during install.

**Issue**: PowerShell execution policy blocks `.venv\Scripts\Activate.ps1`
**Solution**: Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser` once in PowerShell, then activate normally.

**Issue**: `KUZU_DIR` constant mismatch causing database not found
**Solution**: Fixed in current `src/utils/config.py` — constant is `kuzu_db` (not `kuzu`). If you see path errors, verify `KUZU_DIR = DATA_DIR / "kuzu_db"` in that file.

**Issue**: MCP server not found at `%APPDATA%\Code\User\mcp.json`
**Solution**: Run `python scripts\setup\configure_vscode_bob.py` from the repo root (with venv activated). The script writes the correct absolute Windows path to the venv Python.

### Common Issues (All Platforms)

**Issue**: `Database path cannot be a directory`
**Solution**: See [`debug/ops-installation-compendium.md`](../debug/ops-installation-compendium.md) — search `pitfall: installation kuzu`

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

1. Check [`debug/ops-installation-compendium.md`](../debug/ops-installation-compendium.md) for common installation pitfalls
2. Review `install.log` for detailed error messages
3. See [`../debug/README.md`](../debug/README.md) for debugging guides
4. Check GitHub Issues for known problems

---

## 6. Next Steps

After successful installation:

1. **Explore the API**: [`spec-tools.md`](spec-tools.md)
2. **Try the Dashboard**: [`ops-dashboard.md`](ops-dashboard.md)
3. **Understand Architecture**: [`spec-architecture.md`](spec-architecture.md)

---

## Behavioral Instruction Architecture

Elefante uses a **three-layer architecture** to ensure AI agents behave correctly. Understanding this architecture is critical — each layer serves a distinct purpose and failure of any layer degrades agent behavior.

### Layer 1: Bootstrap — `copilot-instructions.md`

**File**: `.github/copilot-instructions.md`
**Mechanism**: VS Code / GitHub Copilot automatically reads this file from the workspace root and injects its contents into the system prompt for every conversation.
**Scope**: Per-workspace (only active when the workspace containing the file is open).

This is the **entry point** of the entire behavioral chain. It tells the agent three things:

1. **Elefante exists** — call `elefante-MemorySearch` before answering questions about preferences, decisions, or conventions
2. **Compliance stamp** — include `[ELEFANTE] Searched:` in every response to confirm the search happened
3. **Tool Response Contract** — every MCP tool response contains three injected sections that MUST be read and acted on

Without this file, the agent has no reason to call Elefante proactively. The MCP tools are registered (via `mcp.json`), but the agent won't use them unless instructed.

**How it gets there**: This file is committed to the repository. When a user clones Elefante and opens the workspace, VS Code loads it automatically. The installer validates its existence in Step 4a.

**For external workspaces**: If using Elefante as a global MCP server in other workspaces, copy this file to those workspaces' `.github/` directories. Without it, only the tool response contract (Layers 2 and 3) is active.

### Tool Response Contract (Three Injected Sections)

Every MCP tool response from Elefante contains up to three injected sections. These are appended to every tool result automatically by the server (`src/mcp/server.py`). The agent reads them as part of the tool's data payload — at the decision boundary, right before it decides its next action.

#### `MANDATORY_PROTOCOLS_READ_THIS_FIRST`

**Source**: `_inject_pitfalls()` in `src/mcp/server.py`
**Present on**: Every tool response, always.

Critical protocols and known pitfalls. These are non-negotiable rules:

- Check for existing memories before creating new ones (prevent duplication)
- Read the relevant Neural Register in `docs/debug/` before debugging
- Do not rely on internal knowledge for project specifics — use the memory system
- Developer Etiquette v1.2 enforcement reminder

Context-specific warnings are added per tool:

- `elefante-MemoryAdd`: Score is system-computed; classify `memory_type` accurately
- `elefante-MemorySearch`: Search bias warnings; contradiction resolution rules
- `elefante-GraphQuery` / `elefante-GraphConnect`: Graph consistency warnings
- `elefante-DashboardOpen`: Refresh requires Elefante Mode enabled

#### `DIRECTIVES`

**Source**: `_inject_directives()` in `src/mcp/server.py`, reading from `DirectiveStore`
**Storage**: `~/.elefante/data/directives.json` (simple JSON file, not in ChromaDB)
**Present on**: Every tool response where active directives exist.

User-managed, persistent behavioral constraints. These are unconditional rules set by the user (e.g., "never claim success without user confirmation"). They are:

- **Not suggestions** — they are law. Read and follow them on every turn.
- **Not dependent on search** — unlike memories, they don't need keyword or semantic matching
- **Not in competition** — they cannot be outcompeted by similarity scores
- **User-managed** — added/removed via `elefante-DirectiveAdd` and `elefante-DirectiveRemove`

Directives solve the fundamental problem of behavioral rules that MUST be followed regardless of context: you cannot rely on retrieval to surface rules that should never be forgotten.

#### `RELEVANT_CONTEXT`

**Source**: `_inject_context()` in `src/mcp/server.py`, querying ChromaDB
**Present on**: Tool responses where applicable (skipped for search, system, admin, and ETL tools).

Auto-surfaced memories relevant to the current operation. The server extracts a search signal from the tool arguments (description, content, query fields), runs a fast ChromaDB search (top 3, min similarity 0.5), and appends matching memories with similarity scores.

This gives the agent ambient context without requiring an explicit `elefante-MemorySearch` call. It's supplementary — the agent should still call `elefante-MemorySearch` for deliberate queries, but `RELEVANT_CONTEXT` ensures relevant knowledge surfaces even on non-search operations.

### Layer 2: Directives — Always-Active Behavioral Rules

Directives are the `DIRECTIVES` section described above. See **Tool Response Contract** for full details.

### Layer 3: Memories — Contextual Knowledge

**Mechanism**: Stored in ChromaDB (vector) + Kuzu (graph). Retrieved by semantic similarity search.
**Scope**: Global (accessible from any workspace via MCP).

Memories are contextual knowledge: project facts, user preferences, past decisions, technical notes. They are retrieved in two ways:

1. **Explicitly** — via `elefante-MemorySearch` (agent calls it proactively, triggered by Layer 1 instructions)
2. **Automatically** — via `RELEVANT_CONTEXT` injection (server auto-surfaces top 3 relevant memories on every non-search tool call)

System-level knowledge about how to use Elefante tools is provided through the `copilot-instructions.md` bootstrap and the Tool Response Contract.

### How the Three Layers Interact

```
User opens workspace
       |
       v
[Layer 1] VS Code loads .github/copilot-instructions.md
       |  Agent now knows: "search Elefante first, respect Tool Response Contract"
       |
       v
Agent calls elefante-MemorySearch (or any Elefante tool)
       |
       v
[Tool Response] Three sections injected:
       |  MANDATORY_PROTOCOLS_READ_THIS_FIRST — pitfalls & protocols
       |  DIRECTIVES — user behavioral constraints ("never claim success", etc.)
       |  RELEVANT_CONTEXT — auto-surfaced memories (when applicable)
       |
       v
Agent responds — following protocols + directives, informed by memories
```

### Installation Ensures All Layers

| Step    | What happens                                                        |
| ------- | ------------------------------------------------------------------- |
| Step 4  | IDE MCP configuration (tools registered → response contract active) |
| Step 4a | Validates `copilot-instructions.md` exists (Layer 1 bootstrap)      |
| Step 5b | Ingests Inception Memory (Layer 3 seed knowledge)                   |
| Runtime | `MANDATORY_PROTOCOLS` injected by server on every call              |
| Runtime | `DIRECTIVES` injected by server from `directives.json`              |
| Runtime | `RELEVANT_CONTEXT` injected by server from ChromaDB                 |

The Directive store (`~/.elefante/data/directives.json`) is created on first use — no installation step needed.

---

## 7. Uninstallation

### Windows

```cmd
REM 1. Deactivate virtual environment
deactivate

REM 2. Remove installation directory (or delete the folder in Explorer)
rmdir /s /q Elefante

REM 3. Remove data directory (OPTIONAL — contains your memories)
rmdir /s /q %USERPROFILE%\.elefante
```

### macOS / Linux

```bash
# 1. Deactivate virtual environment
deactivate

# 2. Remove installation directory
rm -rf Elefante/

# 3. Remove data directory (optional - contains your memories)
rm -rf ~/.elefante/
```

**Warning**: Step 3 deletes all stored memories. Backup first:

Windows: `python scripts\lifecycle\backup_elefante_data.py`
macOS/Linux: `python scripts/lifecycle/backup_elefante_data.py`

---

## 8. Binary Compilation (Standalone)

To build a zero-dependency standalone binary (no `pip` or venv required on the target machine):

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller elefante.spec
```

The executable is created at `./dist/elefante/elefante`. Distribute the `dist/elefante/` folder as a zip.

See also: [`ops-docker.md`](ops-docker.md) for container-based deployment.

---

**Version**: 2.6.0
**Last Updated**: 2026-04-15
**Status**: Production Ready (Windows validated)

---

## Appendix A: Python Version Details

### Supported Versions

| Python Version | Status |
| -------------- | ------ |
| < 3.11 | NOT SUPPORTED |
| **3.11** | Supported and tested |
| **3.12** | Supported and tested |
| **3.13** | Recommended — best performance |

### OS-Specific Installation

**macOS (Homebrew)**:
```bash
brew install python@3.11
python3.11 -m venv .venv
```

**macOS (pyenv)**:
```bash
brew install pyenv && pyenv install 3.11.0 && pyenv local 3.11.0
```

**Windows**: Download from https://www.python.org/downloads/ — check "Add Python 3.11 to PATH". Or use Conda: `conda create -n elefante python=3.11`.

**Linux (Debian/Ubuntu)**: `sudo apt install python3.11 python3.11-venv`

**Linux (CentOS/RHEL)**: `sudo yum install python3.11 python3.11-devel`

### Locked Dependencies

**File**: `requirements.txt` — these versions are tested against Python 3.11:

```
kuzu==0.11.3
chromadb==1.3.5
sentence-transformers==2.7.0
mcp==1.23.1
fastapi==0.124.0
uvicorn==0.38.0
```

Do NOT upgrade without testing on Python 3.11.

### Wrong Python Version?

Delete and recreate the venv:

```bash
deactivate
rm -rf .venv
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### CI/CD Examples

**GitHub Actions**:
```yaml
- uses: actions/setup-python@v4
  with:
    python-version: '3.11'
```

**Docker**:
```dockerfile
FROM python:3.11-slim
```
