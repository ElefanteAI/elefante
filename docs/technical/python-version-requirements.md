````markdown
# Python Version Requirements & Locking

**Status**: CRITICAL - Mandatory for all installations  
**Last Updated**: 2026-02-25  
**Applies to**: v2.0.0+

---

## MANDATORY: Python 3.11 ONLY

### Why Python 3.11?

**Elefante requires Python 3.11 specifically** due to:

1. **Sentence Transformers Compatibility** (2.7.0+)
   - Optimized for Python 3.11
   - May have compatibility issues with 3.9, 3.10, 3.12+

2. **Kuzu 0.11.3 Compatibility**
   - Best tested on Python 3.11
   - ARM64 (Apple Silicon) support reliable on 3.11

3. **MCP Protocol (1.23.1+)**
   - Async context handling optimized for 3.11
   - Type hints behavior differs in 3.12+

4. **ChromaDB 1.3.5 Stability**
   - SQLite3 version management stable on 3.11
   - Concurrent access patterns tested on 3.11

### Supported Versions

| Python Version | Status          | Notes                              |
| -------------- | --------------- | ---------------------------------- |
| 3.9            | NOT SUPPORTED   | Too old, missing features          |
| 3.10           | UNCERTAIN       | May work, but not tested           |
| **3.11**       | **RECOMMENDED** | **All features tested & working**  |
| 3.12           | UNCERTAIN       | Type hint changes may cause issues |
| 3.13           | NOT SUPPORTED   | Too new, dependency gaps           |

---

## Installation: Ensuring Python 3.11

### Check Your Python Version

```bash
python3 --version
# Should output: Python 3.11.x
```
````

### macOS

**Using Homebrew** (Recommended):

```bash
# Install Python 3.11
brew install python@3.11

# Verify
python3.11 --version
# Output: Python 3.11.x

# Create venv with explicit version
python3.11 -m venv .venv
```

**Using pyenv** (Alternative):

```bash
# Install pyenv
brew install pyenv

# Install Python 3.11
pyenv install 3.11.0

# Set local version
pyenv local 3.11.0

# Verify
python --version
# Output: Python 3.11.0
```

### Windows

**Using Official Installer**:

1. Download: https://www.python.org/downloads/release/python-3-11-latest/
2. Install with "**Add Python 3.11 to PATH**" checked
3. Verify:
   ```bash
   python --version
   REM Should output: Python 3.11.x
   ```

**Using Conda** (Recommended):

```bash
# Install Conda (Anaconda or Miniconda)
# Then create environment with Python 3.11
conda create -n elefante python=3.11

# Activate
conda activate elefante
```

### Linux (Ubuntu/Debian)

```bash
# Update package manager
sudo apt update

# Install Python 3.11
sudo apt install python3.11 python3.11-venv

# Verify
python3.11 --version
# Output: Python 3.11.x

# Create venv
python3.11 -m venv .venv
```

### Linux (CentOS/RHEL)

```bash
# Install Python 3.11
sudo yum install python3.11 python3.11-devel

# Verify
python3.11 --version

# Create venv
python3.11 -m venv .venv
```

---

## Verification: After Installation

### 1. Check Virtual Environment Python

```bash
# Activate virtual environment
source .venv/bin/activate  # Mac/Linux
# or
.venv\Scripts\activate  # Windows

# Verify Python version IN the venv
python --version
# Must output: Python 3.11.x
```

### 2. Check Dependencies Against Python 3.11

```bash
# Activate venv
source .venv/bin/activate

# Test imports
python -c "
import sys
print(f'Python: {sys.version}')

# Test critical dependencies
import kuzu
print(f' Kuzu: {kuzu.__version__}')

import chromadb
print(f' ChromaDB: {chromadb.__version__}')

import sentence_transformers
print(f' Sentence Transformers: OK')

import mcp
print(f' MCP: OK')

print('\n All dependencies compatible with Python 3.11')
"
```

### 3. Run Health Check

```bash
source .venv/bin/activate
python scripts/health_check.py

# Should output:  All systems operational!
```

---

## Troubleshooting: Wrong Python Version

### Symptom: "Python 3.12 / 3.13 is being used"

**Error Signs**:

```
TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'
ModuleNotFoundError: No module named 'async_timeout'
ImportError: cannot import name 'ABC' from 'collections'
```

### Fix #1: Delete and Recreate Virtual Environment

```bash
# Deactivate if active
deactivate

# Remove old venv
rm -rf .venv  # Mac/Linux
REM or
rmdir /s .venv  # Windows

# Create new venv with Python 3.11
python3.11 -m venv .venv

# Activate
source .venv/bin/activate  # Mac/Linux

# Reinstall dependencies
pip install -r requirements.txt

# Test
python scripts/health_check.py
```

### Fix #2: Explicitly Specify Python in Installation

**Edit `install.sh`** (Mac/Linux):

Change:

```bash
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
```

To:

```bash
if command -v python3.11 &> /dev/null; then
    PYTHON_CMD=python3.11
elif command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
```

**Edit `install.bat`** (Windows):

Add before venv creation:

```batch
REM Check for Python 3.11 specifically
python3.11 --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python 3.11 is required but not found
    echo Please install Python 3.11 from https://python.org
    pause
    exit /b 1
)
```

### Fix #3: Using pyenv (macOS/Linux)

```bash
# Set local Python version
pyenv local 3.11.0

# Verify
python --version
# Should output: Python 3.11.0

# Now create venv
python -m venv .venv
source .venv/bin/activate
```

---

## Locked Dependencies

**File**: `requirements.txt`

The following versions are locked for Python 3.11:

```
kuzu==0.11.3          # Tested on Python 3.11
chromadb==1.3.5       # Tested on Python 3.11
sentence-transformers==2.7.0  # Optimized for 3.11
mcp==1.23.1           # Tested on Python 3.11
fastapi==0.124.0
uvicorn==0.38.0
```

**Do NOT upgrade these** without testing on Python 3.11 first.

---

## Migration: Upgrading Python Version

If you're currently on Python 3.9/3.10 and want to upgrade to 3.11:

### Step 1: Install Python 3.11

Follow installation instructions above for your OS.

### Step 2: Backup Current Installation

```bash
# Deactivate current venv
deactivate

# Backup old venv
mv .venv .venv.backup.3.10
```

### Step 3: Create New Python 3.11 Environment

```bash
# Create new venv with Python 3.11
python3.11 -m venv .venv

# Activate
source .venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt

# Verify
python scripts/health_check.py
```

### Step 4: Migrate Data (Optional)

```bash
# If you have existing Kuzu database, it should still work
# But recommend running integrity check
python scripts/health_check.py
```

### Step 5: Cleanup

```bash
# If new environment works, remove backup
rm -rf .venv.backup.3.10
```

---

## CI/CD & Automation

### GitHub Actions Example

```yaml
name: Test with Python 3.11
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11"]

    steps:
      - uses: actions/checkout@v3
      - name: Set up Python 3.11
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python -m pytest
```

### Docker Example

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["python", "-m", "src.mcp.server"]
```

---

## Frequently Asked Questions

### Q: Can I use Python 3.12?

**A:** Not recommended. Python 3.12 has breaking changes in type hints and async handling that may cause compatibility issues. If you must use 3.12:

1. Test thoroughly on your system
2. Report issues to project maintainers
3. Be prepared to downgrade to 3.11

### Q: What if I'm forced to use Python 3.9?

**A:** Elefante will not work reliably on Python 3.9. You would need to:

1. Downgrade sentence-transformers to 2.2.0
2. Downgrade mcp to 0.x (if available)
3. Accept potential bugs and incompatibilities

Not recommended. Upgrade to Python 3.11 instead.

### Q: Can I have multiple Python versions?

**A:** Yes, using pyenv or virtual environments. Each project can have its own Python version:

```bash
# Project A uses 3.11
cd ~/project-a
pyenv local 3.11.0

# Project B uses 3.12
cd ~/project-b
pyenv local 3.12.0
```

### Q: How do I know if my dependencies are compatible?

```bash
# Activate venv and test
source .venv/bin/activate
python -c "import kuzu, chromadb, sentence_transformers, mcp; print(' All OK')"
```

---

## Conclusion

**Python 3.11 is MANDATORY for Elefante v1.0.0+**

Always verify your virtual environment uses Python 3.11:

```bash
python --version  # Should output: Python 3.11.x
```

If you're on a different version, follow the troubleshooting steps above to upgrade.

---

**Document Version**: 2.2.1  
**Status**: MANDATORY  
**Last Validated**: 2026-02-25

```

```
