"""
Verify that the Elefante repository is clean and ready for GitHub.
Checks for leftover files, test artifacts, and proper organization.
"""

import os
import sys
import io
import subprocess
from pathlib import Path

# Do not generate __pycache__ / .pyc while running this checker.
sys.dont_write_bytecode = True

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_clean_repo():
    """Verify repository cleanliness"""
    
    print("\n" + "="*70)
    print("ELEFANTE REPOSITORY CLEANLINESS CHECK")
    print("="*70 + "\n")
    
    issues = []
    warnings = []

    # Directories that are expected to contain bytecode or vendor files.
    # We exclude these from cleanliness checks.
    ignore_dir_names = {
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".pytest_cache",
        "__pycache__",  # handled separately; included here to avoid descending
    }

    def _iter_repo_paths() -> list[Path]:
        """Iterate repo files/dirs excluding known vendor/ignored directories."""
        root = Path(".").resolve()
        paths: list[Path] = []
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip ignored directories by mutating dirnames in-place.
            dirnames[:] = [d for d in dirnames if d not in ignore_dir_names]
            base = Path(dirpath)
            for name in filenames:
                paths.append(base / name)
        return paths

    def _git_ignored(path: Path) -> bool:
        """Best-effort check whether a path is gitignored."""
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return result.returncode == 0
        except Exception:
            # Fallback: simple .gitignore line match for common top-level ignores.
            try:
                gi = Path(".gitignore")
                if not gi.exists():
                    return False
                content = gi.read_text(encoding="utf-8", errors="ignore")
                needle = f"{path.as_posix().rstrip('/')}/"
                return needle in content
            except Exception:
                return False
    
    # Check for data directory (gitignored, but may contain sensitive exports)
    data_dir = Path("data")
    if data_dir.exists():
        if _git_ignored(data_dir):
            warnings.append("WARN: data/ directory exists (gitignored; ensure it contains no sensitive exports before sharing)")
        else:
            issues.append("ERROR: data/ directory exists and is not gitignored")
    else:
        print("OK: No data/ directory (clean)")
    
    # Check for logs directory (should be gitignored)
    logs_dir = Path("logs")
    if logs_dir.exists():
        if _git_ignored(logs_dir):
            warnings.append("WARN: logs/ directory exists (gitignored; remove before sharing if it contains sensitive logs)")
        else:
            issues.append("ERROR: logs/ directory exists and is not gitignored")
    else:
        print("OK: No logs/ directory (clean)")
    
    # Check for __pycache__ (exclude venv/vendor dirs)
    pycache_dirs: list[Path] = []
    for dirpath, dirnames, _filenames in os.walk(Path(".").resolve()):
        dirnames[:] = [d for d in dirnames if d not in ignore_dir_names]
        if "__pycache__" in dirnames:
            pycache_dirs.append(Path(dirpath) / "__pycache__")

    if pycache_dirs:
        issues.append(f"ERROR: Found {len(pycache_dirs)} __pycache__ directories")
    else:
        print("OK: No __pycache__ directories (clean)")
    
    # Check for .pyc files (exclude venv/vendor dirs)
    repo_files = _iter_repo_paths()
    pyc_files = [p for p in repo_files if p.suffix in {".pyc", ".pyo"}]
    if pyc_files:
        issues.append(f"ERROR: Found {len(pyc_files)} .pyc/.pyo files")
    else:
        print("OK: No .pyc files (clean)")
    
    # Check for .env file
    if Path(".env").exists():
        warnings.append("WARN: .env file exists (should be .env.example only)")
    else:
        print("OK: No .env file (use .env.example)")
    
    # Check for proper structure
    required_dirs = ["src", "scripts", "docs", "examples", "tests"]
    for dir_name in required_dirs:
        if Path(dir_name).exists():
            print(f"OK: {dir_name}/ directory exists")
        else:
            issues.append(f"ERROR: Missing {dir_name}/ directory")
    
    # Check for required files
    required_files = [
        "README.md",
        "LICENSE",
        "requirements.txt",
        "setup.py",
        ".gitignore",
        "CONTRIBUTING.md",
        "CHANGELOG.md"
    ]
    for file_name in required_files:
        if Path(file_name).exists():
            print(f"OK: {file_name} exists")
        else:
            issues.append(f"ERROR: Missing {file_name}")
    
    # Summary
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    
    if not issues and not warnings:
        print("\nOK: Repository is clean and ready")
        print("OK: All checks passed")
        print("OK: No test artifacts found")
        print("OK: Proper structure verified")
        print("OK: All required files present")
        return 0
    
    if warnings:
        print("\nWARNINGS:")
        for warning in warnings:
            print(f"  {warning}")
    
    if issues:
        print("\nISSUES FOUND:")
        for issue in issues:
            print(f"  {issue}")
        print("\nPlease fix these issues before pushing")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(check_clean_repo())

# Made with Bob
