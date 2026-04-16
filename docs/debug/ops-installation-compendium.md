# Installation Debug Compendium

> **Domain:** Installation, Setup & Environment  
> **Last Updated:** 2026-04-16
> **Total Issues Documented:** 10
> **Status:** Production Reference  
> **Applies to**: v2.9.0+
| #   | Law                                                  | Violation Cost       |
| --- | ---------------------------------------------------- | -------------------- |
| 1   | Do NOT pre-create Kuzu database directory            | 12 minutes debugging |
| 2   | Check library changelogs before upgrading            | Breaking changes     |
| 3   | Test configuration files, not just code              | Root cause missed    |
| 4   | Run `pip install -r requirements.txt` after git pull | Missing deps         |
| 5   | Verify Python version matches requirements           | Cryptic errors       |

---

## Verification Commands

Run these BEFORE investigating. If tests pass, the documented fix is intact.

| Issue | Test Command | What It Proves |
| ----- | ------------ | -------------- |
| #1-#4 Install health | `python scripts/verify/verify_health.py` | Imports, data paths, directives, specs |
| MCP server starts | `python scripts/verify/verify_mcp_handshake.py` | stdio JSON-RPC handshake succeeds |
| Factory reset | `pytest tests/test_factory_reset.py -v` | Dry-run safety, gate rejection, backup creation |
| Full E2E | `.venv/bin/python scripts/verify/verify_e2e_tests.py` | Isolated end-to-end MCP workflow |

---

## Table of Contents

- [Issue #1: Kuzu 0.11.x Path Breaking Change](#issue-1-kuzu-011x-path-breaking-change)
- [Issue #2: Missing Dependencies After Clone](#issue-2-missing-dependencies-after-clone)
- [Issue #3: Python Version Mismatch](#issue-3-python-version-mismatch)
- [Issue #4: Config Pre-creating Directories](#issue-4-config-pre-creating-directories)
- [Issue #5: Broken Venv Escape (Trapped Agent)](#issue-5-broken-venv-escape-trapped-agent)
- [Issue #6: IDE Holding Stale MCP Server Connections](#issue-6-ide-holding-stale-mcp-server-connections)
- [Issue #7: IBM Bob Non-Standard MCP Settings Path](#issue-7-ibm-bob-non-standard-mcp-settings-path)
- [Issue #8: CI Binary Build](#issue-8-ci-binary-build--missing-frontend-build-step-and-wrong-vite-output-directory)
- [Issue #9: GitHub Release Publish Failure](#issue-9-github-release-publish-failure-after-successful-matrix-builds)
- [Cognitive Failure Analysis](#cognitive-failure-analysis)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Kuzu 0.11.x Path Breaking Change

**Date:** 2025-11-27  
**Duration:** 12 minutes (THE nightmare)  
**Severity:** CRITICAL  
**Status:** FIXED

### Problem

Fresh installation fails with cryptic path error.

### Symptom

```
RuntimeError: Database path cannot be a directory: C:\Users\...\kuzu_db
```

### Root Cause

**Kuzu 0.11.x Breaking Change:** Database path handling fundamentally changed.

| Version | Behavior                              |
| ------- | ------------------------------------- |
| 0.1.x   | Could pre-create `kuzu_db/` directory |
| 0.11.x  | Database path CANNOT exist beforehand |

The `config.py` was pre-creating the directory:

```python
KUZU_DIR.mkdir(exist_ok=True)  #  BREAKS Kuzu 0.11.x
```

### Solution

**File 1:** `src/utils/config.py`

```python
# REMOVED this line:
# KUZU_DIR.mkdir(exist_ok=True)  # Kuzu 0.11.x cannot have pre-existing directory
```

**File 2:** `src/core/graph_store.py`

```python
def _ensure_database_path(self):
    """Ensure database path is ready for Kuzu 0.11.x"""
    if self.db_path.exists():
        if self.db_path.is_dir():
            logger.warning(f"Removing existing directory: {self.db_path}")
            shutil.rmtree(self.db_path)
    # Let Kuzu create its own structure
    self.db_path.parent.mkdir(parents=True, exist_ok=True)
```

**File 3:** `scripts/setup/install.py` - Added pre-flight check:

```python
def check_kuzu_compatibility():
    kuzu_dir = Path("data/kuzu_db")
    if kuzu_dir.exists() and kuzu_dir.is_dir():
        print("  KUZU COMPATIBILITY ISSUE DETECTED")
        response = input("Remove existing directory? (y/N): ")
        if response.lower() == 'y':
            shutil.rmtree(kuzu_dir)
```

### Why This Took So Long

1. **Misleading Error:** "cannot be a directory" sounds like permissions issue
2. **Wrong File Focus:** Error appears in `graph_store.py` but fix is in `config.py`
3. **Cognitive Bias:** Assumed database issue, not configuration issue
4. **Time Pressure:** Made hasty assumptions instead of systematic analysis

### Lesson

> **Always read error messages literally. Check configuration before implementation.**

---

## Issue #2: Missing Dependencies After Clone

**Date:** 2025-11-27  
**Duration:** 5 minutes  
**Severity:** MEDIUM  
**Status:** DOCUMENTED

### Problem

Fresh clone fails with import errors.

### Symptom

```
ModuleNotFoundError: No module named 'chromadb'
ModuleNotFoundError: No module named 'kuzu'
```

### Root Cause

User skipped `pip install -r requirements.txt` step. Common when:

- Following partial instructions
- Copy-pasting commands without reading
- Assuming virtual environment has everything

### Solution

```bash
# Always run after clone:
pip install -r requirements.txt

# Or use install script:
install.bat  # Windows
./install.sh # Linux/Mac
```

### Why This Happens

- README instructions may be skimmed
- Users assume dependencies are bundled
- Error message doesn't say "run pip install"

### Lesson

> **Install scripts should run pip install automatically. Never assume user did it.**

---

## Issue #3: Python Version Mismatch

**Date:** 2025-11-27  
**Duration:** 10 minutes  
**Severity:** MEDIUM  
**Status:** DOCUMENTED

### Problem

System Python too old for some dependencies.

### Symptom

```
ERROR: Package 'kuzu' requires a different Python: 3.9.7 not in '>=3.11'
```

Or cryptic syntax errors:

```
SyntaxError: invalid syntax
# (usually from walrus operator := or | union types)
```

### Root Cause

Elefante requires Python 3.11 for:

- Type hints with `|` union syntax
- Walrus operator `:=`
- Modern async features
- Kuzu and ChromaDB package compatibility

### Solution

```bash
# Check current version
python --version

# If < 3.11, install Python 3.11
# Windows: Download from python.org
# Linux: sudo apt install python3.11
# Mac: brew install python@3.11

# Create venv with correct version
python3.11 -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac
```

### Why This Persists

- Multiple Python versions on system
- System Python often outdated
- Virtual environment not activated

### Lesson

> **Always specify Python version in requirements. Add version check to install script.**

---

## Issue #4: Config Pre-creating Directories

**Date:** 2025-11-27  
**Duration:** Part of Issue #1  
**Severity:** HIGH  
**Status:** FIXED

### Problem

Configuration module creates directories that break Kuzu initialization.

### Symptom

Kuzu fails on first run even with clean install.

### Root Cause

`config.py` had eager directory creation:

```python
# These lines ran on IMPORT:
DATA_DIR.mkdir(exist_ok=True)
CHROMA_DIR.mkdir(exist_ok=True)
KUZU_DIR.mkdir(exist_ok=True)  #  This breaks Kuzu 0.11.x
```

### Solution

Changed to lazy directory creation:

```python
# Only create directories when actually needed:
def ensure_data_dirs():
    DATA_DIR.mkdir(exist_ok=True)
    CHROMA_DIR.mkdir(exist_ok=True)
    # Note: Do NOT create KUZU_DIR - let Kuzu do it
```

### Why This Design Existed

- Seemed like good practice to ensure directories exist
- Worked fine with older Kuzu versions
- No one anticipated library behavior change

### Lesson

> **Let libraries manage their own resources. Don't be overly helpful with directories.**

---

## Cognitive Failure Analysis

### The 12-Minute Debugging Timeline

```
00:00 - Error: "Database path cannot be a directory"
00:02 - WRONG ASSUMPTION: "Must be old database files"
00:05 - WRONG ACTION: Analyzed graph_store.py instead of config.py
00:08 - WRONG FOCUS: Looked at database init, not path creation
00:10 - Searched for .mkdir() calls
00:12 - BREAKTHROUGH: Found config.py was pre-creating directory
00:13 - Commented out problematic line
00:14 - SUCCESS: Installation works
```

### Why These Mistakes Happened

| Bias                 | Description                               | How It Hurt                 |
| -------------------- | ----------------------------------------- | --------------------------- |
| **Anchoring**        | Fixated on error location                 | Debugged wrong file         |
| **Confirmation**     | Looked for evidence supporting assumption | Ignored config.py           |
| **Time Pressure**    | Rushed to solution                        | Skipped systematic analysis |
| **Pattern Matching** | Applied previous debugging patterns       | Wrong mental model          |

### The Learning

1. **Read error messages literally** - "cannot be a directory" = don't create directory
2. **Check configuration first** - Most issues are config, not code
3. **Version changes break things** - Always check changelogs
4. **Systematic > Intuitive** - Step-by-step beats guessing

---

## Prevention Protocol

### Pre-Installation Checklist

```bash
# 1. Verify Python version
python --version  # Must be 3.11

# 2. Check no existing data directory issues
ls data/kuzu_db  # Should not exist or should be directory structure

# 3. Clean virtual environment
python -m venv .venv --clear
.venv\Scripts\activate  # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run installation script
python scripts/setup/install.py
```

### After Installation Failure

```powershell
# Recovery sequence:
# 1. Remove potentially corrupted directories
Remove-Item "data\kuzu_db" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "data\chroma_db" -Recurse -Force -ErrorAction SilentlyContinue

# 2. Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# 3. Run init script
python scripts/setup/init_databases.py
```

### When Upgrading Libraries

1.  Read changelog for breaking changes
2.  Run the existing isolated verifier first (`scripts/verify/*` or targeted pytest) before inventing a new scratch environment
3.  Backup existing data directories
4.  Check version constraints in `requirements.txt`
5.  Update documentation if behavior changes

---

## Quick Install Reference

### Windows

```powershell
git clone https://github.com/jsubiabreIBM/Elefante.git
cd Elefante
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/setup/install.py
```

### Linux/Mac

```bash
git clone https://github.com/jsubiabreIBM/Elefante.git
cd Elefante
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/setup/install.py
```

### Verification

```bash
python -c "from src.core.orchestrator import MemoryOrchestrator; print(' Import successful')"
python scripts/verify/verify_health.py
```

---

## Issue #5: Broken Venv Escape (Trapped Agent)

**Date:** 2025-12-11  
**Duration:** ~2 hours  
**Severity:** HIGH  
**Status:** FIXED

### Problem

Agent trapped in corrupted workspace environment cannot run installation script.

### Symptom

```
# Agent tries to run install.py but workspace Python is broken
# Error varies: ImportError, ModuleNotFoundError, wrong Python version
# VS Code terminal shows .venv/bin/python but it's corrupted
```

### Root Cause

**Circular Dependency**: The agent (Claude/Copilot) runs within VS Code which uses the workspace's `.venv` Python. When that venv becomes corrupted:

1. Agent's Python execution uses broken interpreter
2. `scripts/setup/install.py` can't run (needs working Python)
3. Can't fix Python from within broken Python
4. Agent has no "escape hatch" to system Python

### Solution

**Escape via subprocess to system Python with absolute path:**

```python
import subprocess

# Escape the broken workspace environment
subprocess.run([
    "/opt/homebrew/bin/python3.11",  # Absolute path to SYSTEM Python
    "-c",
    """
import os, shutil, subprocess
# Now running in clean system Python
shutil.rmtree('.venv', ignore_errors=True)
subprocess.run(['/opt/homebrew/bin/python3.11', '-m', 'venv', '.venv'])
# ... rest of installation
"""
])
```

**Alternative: Shebang override**

```python
#!/usr/bin/env python3.11  # Forces system Python at OS level
```

### Why This Took So Long

1. **Environment blindness**: Agent didn't realize it was trapped
2. **Assumed solutions work**: Kept trying `python scripts/setup/install.py`
3. **Multiple escape attempts**: Had to try several strategies before finding working one
4. **No documented pattern**: First time encountering this failure mode

### Lesson

> **When workspace Python is corrupted, escape via subprocess to system Python with absolute path. The agent cannot fix itself from within a broken environment.**

### Archived Scripts

See `docs/archive/historical/install-escape-2025-12-11/` for the 6 scripts that document the escape progression.

---

## Issue #6: IDE Holding Stale MCP Server Connections

**Date:** 2026-02-27  
**Duration:** ~5 minutes  
**Severity:** HIGH  
**Status:** DOCUMENTED

### Problem

After a fresh Elefante update or re-installation, the IDE continues communicating with an older version of the MCP server.

### Symptom

Even after verifying the installation and confirming `mcp_config.json` points to the new repository path, calling the MCP server yields responses from the old version (e.g., v1.6.3 instead of v2.1.4).

### Root Cause

IDEs (VS Code, Cursor, Antigravity) launch the MCP server as a background process when the session starts. Updating the configuration file (`mcp_config.json` or `mcp.json`) does **not** automatically terminate the running instance. The IDE continues to route JSON-RPC traffic to the old background process holding the port/lock until the IDE window is explicitly reloaded.

### Solution

**Mandatory IDE Reload**: After any installation or configuration change, the user MUST manually reload the IDE window or explicitly restart the MCP server via the IDE's UI.

```bash
# In VS Code / Cursor:
# Command Palette -> Developer: Reload Window

# Or manually kill the old python process if IDE reload fails to drop the zombie process.
```

### Why This Took So Long

1. **Assumption of Hot-Reload**: Expected the IDE to watch the configuration file and restart the subprocess automatically.
2. **Hidden State**: MCP servers run statelessly in the background; there's no visual indicator in the IDE that it's talking to a specific path/PID unless explicitly queried.

### Lesson

> **Never assume the IDE hot-reloads MCP server configurations. Always mandate an explicit window reload after installation.**

---

## Issue #7: IBM Bob Non-Standard MCP Settings Path

**Date:** 2026-03-24
**Duration:** ~15 minutes
**Severity:** MEDIUM
**Status:** DOCUMENTED

### Problem

Auto-configuration script fails to configure IBM Bob IDE despite successfully configuring other IDEs (VS Code, Cursor).

### Symptom

```bash
python scripts/setup/configure_vscode_bob.py
# Reports: "Configured VS Code successfully"
# But IBM Bob IDE shows no Elefante MCP server
```

User must manually locate and edit the correct configuration file.

### Root Cause

**Non-Standard Path Convention:** IBM Bob IDE uses `C:\Users\<user>\.bob\settings\mcp_settings.json` instead of the standard AppData locations that other IDEs use.

The auto-config script checks:
- `%APPDATA%\Bob-IDE\User\globalStorage\ibm.bob-code\settings\mcp_settings.json` [WRONG]
- `%APPDATA%\Code\User\mcp.json` (VS Code) ✓
- `%APPDATA%\Cursor\User\mcp_config.json` (Cursor) ✓

But IBM Bob actually stores settings at:
- `C:\Users\<user>\.bob\settings\mcp_settings.json` ✓ (not checked by script)

### Solution

**Manual Configuration (Immediate Fix):**

1. Locate the actual IBM Bob settings file:
   ```powershell
   # Windows
   C:\Users\<YourUsername>\.bob\settings\mcp_settings.json
   
   # Linux/Mac
   ~/.bob/settings/mcp_settings.json
   ```

2. Add Elefante configuration to the `mcpServers` object:
   ```json
   {
     "mcpServers": {
       "elefante": {
         "command": "C:/path/to/elefante/.venv/Scripts/python.exe",
         "args": ["-m", "src.mcp.server"],
         "cwd": "C:/path/to/elefante",
         "env": {
           "PYTHONPATH": "C:/path/to/elefante",
           "ELEFANTE_CONFIG_PATH": "C:/path/to/elefante/config.yaml",
           "ANONYMIZED_TELEMETRY": "False"
         },
         "alwaysAllow": [
           "elefante-MemoryAdd",
           "elefante-MemorySearch",
           "elefante-System"
         ]
       }
     }
   }
   ```

3. Reload IBM Bob IDE window

**Script Enhancement (Future Fix):**

Update `scripts/setup/configure_vscode_bob.py` to check additional paths:

```python
# Add to IDE path detection
bob_paths = [
    Path.home() / ".bob" / "settings" / "mcp_settings.json",  # IBM Bob standard
    Path(os.getenv("APPDATA")) / "Bob-IDE" / "User" / "globalStorage" / "ibm.bob-code" / "settings" / "mcp_settings.json",  # IBM Bob AppData
]
```

### Why This Took Time

1. **Assumption of Standard Paths:** Expected all IDEs to follow Electron/VS Code conventions (AppData storage)
2. **Hidden Configuration:** `.bob` directory is hidden by default on Unix systems
3. **No Error Message:** Script reported success for VS Code, giving false confidence
4. **Documentation Gap:** IBM Bob path not documented in `ops-ide-configuration.md`

### Lesson

> **Never assume IDE configuration paths follow standards. Always verify actual file locations before declaring success. Document non-standard paths explicitly.**

### Platform-Agnostic Discovery Method

When auto-config fails for any IDE:

1. **Search for existing config files:**
   ```bash
   # Windows
   dir /s /b C:\Users\<user>\mcp*.json
   
   # Linux/Mac
   find ~ -name "mcp*.json" 2>/dev/null
   ```

2. **Check IDE-specific directories:**
   - Look for `.{ide-name}` in home directory
   - Check `%APPDATA%\{IDE-Name}` on Windows
   - Check `~/.config/{ide-name}` on Linux

3. **Verify with IDE documentation or community forums**

4. **Test configuration by reloading IDE window**

---

## Issue #8: CI Binary Build — Missing Frontend Build Step and Wrong Vite Output Directory

**Date:** 2026-04-15
**Duration:** Discovered immediately on first tag push (v2.5.3)
**Severity:** HIGH
**Status:** FIXED — v2.5.4 (`406baba`)

### Problem

Every push to a `v*` tag triggers `build-binaries.yml` which calls `pyinstaller elefante.spec`. The build fails on all three platforms (Ubuntu, macOS, Windows) because:
1. The `src/dashboard/ui/dist/` directory does not exist in the checked-out repo (it is gitignored).
2. Even if it existed, `elefante.spec` referenced the wrong path (`src/dashboard/ui/build`).

### Symptom

GitHub Actions email: **"Run failed: Build One-Click Binaries - v2.5.3 (9f4f116)"**

PyInstaller terminates with a path-not-found error on the `datas` entry. All three matrix jobs fail. The `release` job is skipped (no artifacts).

### Root Cause (2 layers)

1. **Wrong path in `elefante.spec`**: The spec declared `('src/dashboard/ui/build', 'src/dashboard/ui/build')` but Vite is configured in `src/dashboard/ui/vite.config.ts` with `outDir: 'dist'`. The `build/` directory has never existed. The `dist/` directory is the correct output.

2. **Missing Node.js build step in workflow**: `src/dashboard/ui/dist/` and `src/dashboard/ui/node_modules/` are both listed in `.gitignore`. CI checks out the repo with neither present. Without an `npm ci && npm run build` step before PyInstaller, the dist directory does not exist at build time.

### Where Each Was Wrong

| File | What Was Wrong | Fix |
|---|---|---|
| `elefante.spec` | `datas` entry: `src/dashboard/ui/build` | Changed to `src/dashboard/ui/dist` |
| `.github/workflows/build-binaries.yml` | No `setup-node` or `npm` steps before PyInstaller | Added `setup-node@v4` + `npm ci` + `npm run build` in `src/dashboard/ui` |

### Fix Applied

**`elefante.spec`** — single line change:
```python
# Before
datas = collect_data_files('chromadb') + [
    ('src/dashboard/ui/build', 'src/dashboard/ui/build'),
]

# After
datas = collect_data_files('chromadb') + [
    ('src/dashboard/ui/dist', 'src/dashboard/ui/dist'),
]
```

**`build-binaries.yml`** — added before the Python install step:
```yaml
- name: Setup Node.js
  uses: actions/setup-node@v4
  with:
    node-version: "20"

- name: Build Dashboard UI
  working-directory: src/dashboard/ui
  run: |
    npm ci
    npm run build
```

### Why This Was Silent Until First Tag

The workflow only triggers on `v*` tag pushes and `workflow_dispatch`. No tag had been pushed before v2.5.3 — this was the first binary release attempt. The bug existed from the moment the workflow and spec were first written but was never exercised.

### Verification

Manual: push a `v*` tag and confirm all three matrix jobs (ubuntu-latest, macos-latest, windows-latest) complete with green status and artifacts uploaded to the GitHub Release.

No automated local test exists for GitHub Actions workflows. The spec path can be spot-checked:
```powershell
# Confirm spec references the correct directory
Select-String -Path elefante.spec -Pattern "dashboard/ui"
# Should output: src/dashboard/ui/dist

# Confirm workflow has Node step
Select-String -Path .github/workflows/build-binaries.yml -Pattern "setup-node|npm ci"
# Should output: setup-node@v4, npm ci
```

### Lesson

> **A CI pipeline that builds a compiled artifact must include every build step required to produce that artifact — including frontend compilation. Gitignored build outputs do not exist in CI. Verify the output directory name against the build tool config (`vite.config.ts`, `webpack.config.js`, etc.) before referencing it in a build spec.**

---

## Issue #9: GitHub Release Publish Failure After Successful Matrix Builds

**Date:** 2026-04-15  
**Duration:** ~30 minutes from public API evidence to source fix  
**Severity:** HIGH  
**Status:** FIXED — v2.7.1 confirmed live on GitHub Releases with all platform assets published (v2.7.1, v2.6.0, v2.5.4 each show 4 assets)

### Problem

The `Build One-Click Binaries` workflow can complete all three platform builds and still fail in the final GitHub Release publication step when one asset exceeds GitHub's per-file release limit.

### Symptom

GitHub Actions warning email reports and the public GitHub API confirms:

- `Build on macos-latest` — succeeded
- `Build on ubuntu-latest` — succeeded
- `Build on windows-latest` — succeeded
- `Create GitHub Release` — failed

Public release state for `v2.6.0`:

- Release exists: `v2.6.0`
- Uploaded assets: `elefante-macOS.zip`, `elefante-Windows.zip`
- Missing asset: `elefante-Linux.zip`

This proves artifacts were built, the release object was created, and the failure occurred during asset publication.

### Root Cause

The Linux release asset exceeded GitHub's hard per-file release limit.

What is now evidenced:

1. **BUG-014 held.** The current workflow contains `setup-node@v4`, `npm ci`, and `npm run build`, and the three platform build jobs completed successfully.
2. **Release creation itself held.** Public release `v2.6.0` exists and contains two uploaded assets (`elefante-macOS.zip`, `elefante-Windows.zip`).
3. **The Linux asset was oversized.** Public Actions artifacts show `elefante-Linux-binary` for run `24475129776` at `4,021,041,080` bytes.
4. **GitHub rejects release assets at this size.** GitHub documentation states each release asset must be under `2 GiB`.
5. **The failing boundary is exact.** The `Create GitHub Release` job succeeded at `actions/download-artifact@v4`, then failed in `softprops/action-gh-release@v1` while processing the assets.

This is a separate bug class from BUG-014. Reclassifying it as the old build-stage failure would erase the evidence that the v2.5.4 fix actually worked.

### Current State Of The Workflow

```yaml
release:
  name: Create GitHub Release
  needs: build
  if: startsWith(github.ref, 'refs/tags/')
  runs-on: ubuntu-latest
  permissions:
    contents: write
  steps:
    - uses: actions/download-artifact@v4
      with:
        path: artifacts

    - uses: softprops/action-gh-release@v1
      with:
        files: |
          artifacts/elefante-Linux-binary/elefante-Linux.zip
          artifacts/elefante-macOS-binary/elefante-macOS.zip
          artifacts/elefante-Windows-binary/elefante-Windows.zip
        generate_release_notes: true
```

### Solution

Add a release-asset preflight step between artifact download and `softprops/action-gh-release@v1`:

1. Measure each candidate asset size on disk.
2. Exclude any file `>= 2 GiB` from the `files` list passed to the release action.
3. Write uploaded vs skipped assets to the GitHub step summary so the omission is explicit.
4. Keep the release job green when smaller assets are valid, instead of failing the entire release on one oversized binary.

This should preserve macOS and Windows publication while preventing the Linux oversize from poisoning the entire release job, but that outcome still requires a fresh live tag run.

### Source Fix

`.github/workflows/build-binaries.yml` now calls `scripts/ci/select_release_assets.py`, which filters files above GitHub's `2 GiB` release cap before calling `softprops/action-gh-release@v1`. Release-note rendering is also explicit via `scripts/ci/render_release_notes.py` and `body_path: release-notes.md`.

### Verification

Local regression guard:

```bash
pytest tests/test_release_pipeline.py -v
```

This proves the release-stage logic locally. It does NOT prove GitHub publication end to end.

End-to-end publish proof:

Manual: trigger `Build One-Click Binaries` on a fresh `v*` tag and confirm:

1. All three build jobs succeed
2. `Create GitHub Release` succeeds
3. The release page contains macOS and Windows zip assets
4. If Linux remains oversized, it is listed as skipped in the job summary instead of failing the workflow

### Why This Took So Long

- The failed run log was hidden behind an invalid local `gh` token and GitHub does not expose public job logs without auth.
- The public release page only showed that the run failed, not why.
- The decisive evidence required correlating three public surfaces: Actions jobs, release assets, and retained workflow artifacts.
- The bug looked like a generic "release step failed" issue until the artifact byte counts were measured.

### Lesson

> **Actions artifact success does not imply release asset eligibility. Enforce platform upload quotas before publication or one oversized asset will poison the whole release job.**

---

## Appendix: Issue Template

```markdown
## Issue #10: DMG GUI Installer .app Broken — Corrupted Multi-Edit Merge

**Date:** 2026-04-16  
**Duration:** ~30 minutes (diagnosis + rewrite)  
**Severity:** CRITICAL  
**Status:** FIXED — v2.8.1

### Problem

The `Install Elefante.app` inside the DMG exits immediately with code 1. No GUI window appears. 100% of DMG users are blocked.

### Symptom

```
$ "/Volumes/Elefante Installer/Install Elefante.app/Contents/MacOS/launcher" 2>&1
# ... launcher finds /usr/bin/python3 (3.9.6) with tkinter, then:
  File "installer_gui.py", line 173
    troughcolor="#e5e7eb", background=C["accent"],
IndentationError: unexpected indent
```

### Root Cause

`scripts/ci/installer_gui.py` was patched 3+ times in a single session via string-replacement edits (chmod fix, dark→light palette swap, path display additions). The replacements overlapped or partially applied, producing a Frankenstein merge of two UI versions:

- Line 171: `style.theme_use("aqua")` — `style` undefined (should be `ttk.Style()`)
- Line 173: Orphaned `troughcolor=...` kwarg after `self._build_ui()` — **fatal SyntaxError**
- Lines 177+: `_build_ui` uses bare `C` and `tk` instead of `self.C` and `self.tk`
- Lines 233-310: Duplicate `# ── Install path` sections, interleaved widget constructors, references to nonexistent palette keys `C["entry"]`, `C["white"]`

The file was never committed to git (untracked), so no recovery from history was possible.

### Solution

Rewrote the corrupted zone (`__init__` tail + `_build_ui` method, ~140 lines) from scratch as a single coherent light-mode version. All widget references use `self.C`, `self.tk`, `self.ttk`. All widgets are properly constructed and assigned. The action handlers (lines 310+) were intact and unchanged.

Verification:
1. `python3 -c "import py_compile; py_compile.compile('scripts/ci/installer_gui.py', doraise=True)"` — PASS
2. `ast.parse()` structural check — 11 methods, 5 module functions intact
3. DMG rebuild → mount → `diff` source vs DMG copy → FILES IDENTICAL
4. `.app` launch → `GUI_RUNNING=YES`, `GUI_TEST=PASS`
5. `pytest tests/ -x -q` → 137/137 passed

### Why This Took So Long

It didn't take long to fix once diagnosed. The real failure was **not diagnosing it when it happened**:

1. The launcher returned exit code 1 during the previous session, but the session moved on to answering file-path questions instead of investigating
2. 137/137 tests passed, creating false confidence — the test suite doesn't import `installer_gui.py`
3. No syntax check was run after the multi-edit session
4. The file was never committed, so there was no working checkpoint to diff against

### Verification Commands

```bash
# Syntax check (primary gate for this file)
python3 -c "import py_compile; py_compile.compile('scripts/ci/installer_gui.py', doraise=True)"

# Structural check
python3 -c "import ast; ast.parse(open('scripts/ci/installer_gui.py').read()); print('OK')"

# Full test suite
pytest tests/ -x -q
```

---

## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:** OPEN | IN PROGRESS | FIXED | DOCUMENTED

### Problem

[One sentence: what is broken]

### Symptom

[What the user sees / exact error message]

### Root Cause

[Technical explanation of WHY it broke]

### Solution

[Code changes or steps that fixed it]

### Why This Took So Long

[Honest reflection on methodology mistakes]

### Lesson

> [One-line takeaway in blockquote format]
```

---

_Last verified: 2026-02-16 | Tested on: macOS, Python 3.11, Kuzu 0.11.3_

---

## Extracted Learnings (from installation safeguards)

### Lessons Learned

1. **Pre-Flight Checks Are Essential**
   - Detect issues before they cause problems
   - Automated checks beat “read the docs” fixes

2. **User Experience Matters**
   - Clear errors + automated remediations save time
   - Backups provide safety and confidence

3. **Breaking Changes Need Proactive Handling**
   - Version updates can break installs
   - Encode known issues + mitigations in code

4. **Fast Failure Beats Late Failure**
   - Fail in seconds, not minutes
   - Abort early with remediation steps

### Future Improvements

1. **Automated Rollback**: restore from backup if install fails
2. **Pre-Installation Report**: emit a detailed system state report for debugging
3. **Interactive Mode**: guided install flow (optional)
4. **Remote Diagnostics**: opt-in, privacy-respecting telemetry for recurring failures
