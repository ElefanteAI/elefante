# Installation Debug Compendium

> **Domain:** Installation, Setup & Environment  
> **Last Updated:** 2025-12-05  
> **Total Issues Documented:** 4  
> **Status:** Production Reference  
> **Maintainer:** Add new issues following Issue #N template at bottom

---

## 🚨 CRITICAL LAWS (Extracted from Pain)

| # | Law | Violation Cost |
|---|-----|----------------|
| 1 | Do NOT pre-create Kuzu database directory | 12 minutes debugging |
| 2 | Check library changelogs before upgrading | Breaking changes |
| 3 | Test configuration files, not just code | Root cause missed |
| 4 | Run `pip install -r requirements.txt` after git pull | Missing deps |
| 5 | Verify Python version matches requirements | Cryptic errors |

---

## Table of Contents

- [Issue #1: Kuzu 0.11.x Path Breaking Change](#issue-1-kuzu-011x-path-breaking-change)
- [Issue #2: Missing Dependencies After Clone](#issue-2-missing-dependencies-after-clone)
- [Issue #3: Python Version Mismatch](#issue-3-python-version-mismatch)
- [Issue #4: Config Pre-creating Directories](#issue-4-config-pre-creating-directories)
- [Cognitive Failure Analysis](#cognitive-failure-analysis)
- [Prevention Protocol](#prevention-protocol)
- [Appendix: Issue Template](#appendix-issue-template)

---

## Issue #1: Kuzu 0.11.x Path Breaking Change

**Date:** 2025-11-27  
**Duration:** 12 minutes (THE nightmare)  
**Severity:** CRITICAL  
**Status:** ✅ FIXED

### Problem
Fresh installation fails with cryptic path error.

### Symptom
```
RuntimeError: Database path cannot be a directory: C:\Users\...\kuzu_db
```

### Root Cause
**Kuzu 0.11.x Breaking Change:** Database path handling fundamentally changed.

| Version | Behavior |
|---------|----------|
| 0.1.x | Could pre-create `kuzu_db/` directory |
| 0.11.x | Database path CANNOT exist beforehand |

The `config.py` was pre-creating the directory:
```python
KUZU_DIR.mkdir(exist_ok=True)  # ❌ BREAKS Kuzu 0.11.x
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

**File 3:** `scripts/install.py` - Added pre-flight check:
```python
def check_kuzu_compatibility():
    kuzu_dir = Path("data/kuzu_db")
    if kuzu_dir.exists() and kuzu_dir.is_dir():
        print("⚠️  KUZU COMPATIBILITY ISSUE DETECTED")
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
**Status:** ✅ DOCUMENTED

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
**Status:** ⚠️ DOCUMENTED

### Problem
System Python too old for some dependencies.

### Symptom
```
ERROR: Package 'kuzu' requires a different Python: 3.8.10 not in '>=3.9'
```

Or cryptic syntax errors:
```
SyntaxError: invalid syntax
# (usually from walrus operator := or | union types)
```

### Root Cause
Elefante requires Python 3.9+ for:
- Type hints with `|` union syntax
- Walrus operator `:=`
- Modern async features
- Kuzu package compatibility

### Solution
```bash
# Check current version
python --version

# If < 3.9, install newer Python
# Windows: Download from python.org
# Linux: sudo apt install python3.10
# Mac: brew install python@3.10

# Create venv with correct version
python3.10 -m venv .venv
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
**Status:** ✅ FIXED

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
KUZU_DIR.mkdir(exist_ok=True)  # ❌ This breaks Kuzu 0.11.x
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

| Bias | Description | How It Hurt |
|------|-------------|-------------|
| **Anchoring** | Fixated on error location | Debugged wrong file |
| **Confirmation** | Looked for evidence supporting assumption | Ignored config.py |
| **Time Pressure** | Rushed to solution | Skipped systematic analysis |
| **Pattern Matching** | Applied previous debugging patterns | Wrong mental model |

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
python --version  # Must be 3.9+

# 2. Check no existing data directory issues
ls data/kuzu_db  # Should not exist or should be directory structure

# 3. Clean virtual environment
python -m venv .venv --clear
.venv\Scripts\activate  # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run installation script
python scripts/install.py
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
python scripts/init_databases.py
```

### When Upgrading Libraries

1. ✅ Read changelog for breaking changes
2. ✅ Test in isolated environment first
3. ✅ Backup existing data directories
4. ✅ Check version constraints in `requirements.txt`
5. ✅ Update documentation if behavior changes

---

## Quick Install Reference

### Windows
```powershell
git clone https://github.com/jsubiabreIBM/Elefante.git
cd Elefante
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python scripts/install.py
```

### Linux/Mac
```bash
git clone https://github.com/jsubiabreIBM/Elefante.git
cd Elefante
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/install.py
```

### Verification
```bash
python -c "from src.core.orchestrator import MemoryOrchestrator; print('✅ Import successful')"
python scripts/health_check.py
```

---

## Appendix: Issue Template

```markdown
## Issue #N: [Short Descriptive Title]

**Date:** YYYY-MM-DD  
**Duration:** X hours/minutes  
**Severity:** LOW | MEDIUM | HIGH | CRITICAL  
**Status:** 🔴 OPEN | 🟡 IN PROGRESS | ✅ FIXED | ⚠️ DOCUMENTED

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

*Last verified: 2025-12-05 | Tested on: Windows 11, Python 3.10, Kuzu 0.11.x*
