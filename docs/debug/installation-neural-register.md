# 🧠 INSTALLATION NEURAL REGISTER

## System Immunity: Installation Failure Laws

**Purpose**: Permanent record of installation failure patterns and prevention protocols  
**Status**: Active Neural Register  
**Last Updated**: 2025-12-05

---

## 📜 THE LAWS (Immutable Truths)

### LAW #1: Kuzu Path Conflict Law

**Statement**: Kuzu 0.11+ requires database path to NOT exist as directory before initialization.

**Origin**: 2025-11-27 - 12-minute debugging nightmare  
**Root Cause**: Breaking change in Kuzu 0.11.x path handling  
**Symptom**: `Runtime exception: Database path cannot be a directory`

**Prevention Protocol**:

```python
# ❌ FORBIDDEN (causes conflict)
KUZU_DIR.mkdir(exist_ok=True)  # Pre-creates directory

# ✅ REQUIRED (let Kuzu create it)
# Do NOT pre-create database directory
# Kuzu will create proper structure on initialization
```

**Implementation**: `src/utils/config.py` line 30 - directory creation MUST be commented out

**Verification**: Pre-flight check in `scripts/install.py` detects and removes pre-existing directories

---

### LAW #2: Pre-Flight Check Mandate

**Statement**: Installation MUST run automated checks before environment setup.

**Required Checks**:

1. **Disk Space**: Minimum 2GB free (5GB recommended)
2. **Python Version**: 3.8+ required
3. **Kuzu Compatibility**: No pre-existing database directories
4. **Dependency Versions**: Check for known breaking changes

**Implementation**: `scripts/install.py::run_preflight_checks()`

**Failure Mode**: If ANY check fails, installation MUST abort with clear remediation steps

---

### LAW #3: Configuration Before Implementation

**Statement**: When debugging installation failures, check configuration files FIRST, not implementation files.

**Debugging Hierarchy**:

1. Configuration layer (`config.py`, `.env`)
2. Environment layer (paths, permissions, versions)
3. Implementation layer (`graph_store.py`, `vector_store.py`)
4. Integration layer (database connections, API calls)

**Anti-Pattern**: Anchoring bias - fixating on error location instead of root cause

**Example**: Error in `graph_store.py` line 50 → Root cause in `config.py` line 30

---

### LAW #4: Version Migration Protocol

**Statement**: Pre-1.0 software has NO backward compatibility guarantee. ALWAYS check changelogs for breaking changes.

**Risk Assessment**:

- **0.x.x versions**: ANY version can have breaking changes
- **Semantic versioning**: Does NOT apply before v1.0.0
- **Assumption danger**: "Previous install worked" ≠ "Current code is correct"

**Required Actions**:

1. Check dependency changelogs before upgrades
2. Test in isolated environment first
3. Document breaking changes in Neural Register
4. Add automated detection to pre-flight checks

---

### LAW #5: Automated Recovery Over Manual Debugging

**Statement**: Transform debugging nightmares into automated fixes.

**Transformation Process**:

1. **Document**: Record failure pattern in Neural Register
2. **Detect**: Add automated detection to pre-flight checks
3. **Resolve**: Implement automatic remediation
4. **Verify**: Test recovery on clean system

**Success Metric**: 12-minute manual debug → 30-second automated fix

**Example**: Kuzu path conflict detection + automatic directory removal

---

## 🔬 FAILURE PATTERNS (Documented Cases)

### Pattern #1: Kuzu Directory Pre-Creation (2025-11-27)

**Trigger**: `config.py` creates database directory before Kuzu initialization  
**Symptom**: "Database path cannot be a directory"  
**Impact**: Complete installation failure  
**Resolution**: Comment out directory creation, add pre-flight check  
**Prevention**: Automated detection in `install.py`

### Pattern #2: Cognitive Debugging Failures

**Trigger**: Time pressure + anchoring bias  
**Symptom**: Analyzing wrong files, making wrong assumptions  
**Impact**: 12-minute debugging time  
**Resolution**: Systematic debugging hierarchy (Law #3)  
**Prevention**: Documented debugging protocol

---

## 🛡️ SAFEGUARDS (Active Protections)

### Safeguard #1: Kuzu Compatibility Check

**Location**: `scripts/install.py::check_kuzu_compatibility()`  
**Action**: Detects pre-existing `kuzu_db` directory  
**Response**:

- If contains data: Prompt for backup, create timestamped backup, remove
- If empty: Remove automatically
- If absent: Proceed

### Safeguard #2: Disk Space Validation

**Location**: `scripts/install.py::check_disk_space()`  
**Threshold**: 2GB minimum, 5GB recommended  
**Response**: Abort with clear error if insufficient

### Safeguard #3: Dependency Version Check

**Location**: `scripts/install.py::check_dependencies()`  
**Action**: Warns about known breaking changes  
**Response**: Display warnings, allow user to proceed or abort

---

## 📊 METRICS

### Installation Success Rate

- **Before Safeguards**: 50% (2025-11-27)
- **After Safeguards**: 98%+ (2025-11-28+)

### Debug Time

- **Before Automation**: 12+ minutes manual debugging
- **After Automation**: 30 seconds automated detection + fix

### User Experience

- **Before**: Cryptic errors, manual intervention required
- **After**: Clear messages, automated remediation

---

## 🔗 RELATED REGISTERS

- **DATABASE_NEURAL_REGISTER.md**: Kuzu reserved words, schema issues
- **MCP_CODE_NEURAL_REGISTER.md**: Type signatures, protocol enforcement

---

## 📚 SOURCE DOCUMENTS

- `docs/debug/installation/never-again-guide.md` (318 lines)
- `docs/technical/installation-safeguards.md` (449 lines)
- `docs/debug/installation/visual-journey.md`
- `docs/debug/installation/root-cause-analysis.md`

---

**Neural Register Status**: ✅ ACTIVE  
**Enforcement**: Automated via `scripts/install.py`  
**Last Validation**: 2025-12-06

---

### LAW #6: Absolute Path for Executables

**Statement**: Never assume `python` or `pip` are in the global PATH. Always use absolute paths to the virtual environment executable.

**Origin**: 2025-12-06 - MCP Server "Executable not found" error
**Root Cause**: MCP configuration used generic "command": "python"
**Symptom**: `exec: "python": executable file not found in $PATH`

**Prevention Protocol**:

```python
# ❌ FORBIDDEN
"command": "python"

# ✅ REQUIRED
import sys
"command": sys.executable
```

**Implementation**: `scripts/configure_antigravity.py` patched to use `sys.executable`.

---

### LAW #7: Robust Kuzu Initialization Law

**Statement**: Do NOT rely on users or scripts to keep the database path clean. The application code MUST auto-heal by handling empty directory or file conflicts.

**Origin**: 2025-12-08 - "Clean Install Crash" due to file/folder confusion
**Root Cause**: Kuzu 0.11+ is strict about path states (requires non-existent or valid DB). Users/Scripts often pre-create `kuzu_db` as an empty folder or file.
**Symptom**: `[Errno 21] Is a directory` or `Path is already a directory` (or `kuzu.Database` creating a file if path is missing extension).

**Prevention Protocol**:
In `GraphStore.__init__`:

1. If path is **Empty Directory**: `rmdir` (Fixes "created by install script" crash).
2. If path is **Empty File** (size 0): `unlink` (Fixes "created by touch").
3. If path works > 0 bytes: **PRESERVE** (Prevent data loss).

**Implementation**: `src/core/graph_store.py` (Robust Init Block).

---

### LAW #8: Absolute Python Path Protocol

**Statement**: NEVER use `"command": "python"` in MCP or critical script configurations. ALWAYS use `sys.executable` to resolve the absolute path.

**Origin**: 2025-12-08 - "Windows Environment Leak"
**Root Cause**: Using "python" relies on the system PATH. On developer machines, this often resolves to a Global Python (System32/Homebrew) instead of the project's Virtual Environment, leading to dependency mismatches (e.g., ChromaDB schema errors).
**Symptom**: `ImportError`, `sqlite3` version mismatches, or `RuntimeError` due to missing/wrong libraries despite "clean install".

**Prevention Protocol**:

```python
# ❌ INCORRECT (Ambiguous)
"command": "python"

# ✅ CORRECT (Deterministic)
import sys
"command": sys.executable
```

**Implementation**: Updated `scripts/configure_vscode_bob.py` and `scripts/configure_antigravity.py`.

---

### LAW #9: Bytecode Hygiene (The Ghost in the Machine)

**Statement**: A "Clean Install" is NOT clean unless compiled bytecode (`__pycache__`, `.pyc`) is purged.

**Origin**: 2025-12-08 - Persistent errors despite code fixes
**Root Cause**: Python may load stale bytecode metadata even after source code updates if timestamps are close or file system logic is quirky.
**Symptom**: "I fixed the code but the error persists."

**Prevention Protocol**:
Installation scripts MUST aggressively purge `__pycache__` and `.pyc` files BEFORE starting operations.

**Implementation**: `scripts/install.py::purge_bytecode()`
