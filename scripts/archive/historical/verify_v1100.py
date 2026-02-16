#!/usr/bin/env python3
"""Final verification script for v1.10.0 production readiness."""
import ast
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO)
errors = []

# 1. Version check
print("=== 1. VERSION SYNC ===")
version_files = {
    "src/__init__.py": r'__version__\s*=\s*"1\.10\.0"',
    "config.yaml": r'version:\s*"1\.10\.0"',
    "setup.py": r'version="1\.10\.0"',
}
for f, pattern in version_files.items():
    content = open(f).read()
    if re.search(pattern, content):
        print(f"  OK: {f}")
    else:
        errors.append(f"VERSION MISMATCH: {f}")
        print(f"  FAIL: {f}")

# 2. Old tool names
print("\n=== 2. OLD CAMELCASE TOOL NAMES ===")
skip_dirs = {"archive", ".git", "__pycache__", ".venv", "venv", "node_modules", ".kiro"}
skip_files = {"CHANGELOG.md", "verify_v1100.py"}
old_name_pattern = re.compile(r'elefante[A-Z](?!.*→)')  # Exclude "elefanteCamelCase →" (descriptive text)
found_old = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for fname in files:
        if fname in skip_files:
            continue
        if not fname.endswith(('.md', '.py', '.yaml', '.json')):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath) as fh:
            for i, line in enumerate(fh, 1):
                if old_name_pattern.search(line):
                    rel = os.path.relpath(fpath, REPO)
                    found_old.append(f"  {rel}:{i}: {line.strip()[:80]}")
if found_old:
    print(f"  FAIL: {len(found_old)} old names found:")
    for x in found_old:
        print(x)
    errors.extend(found_old)
else:
    print("  OK: Zero old camelCase tool names in active files")

# 3. Placeholder check
print("\n=== 3. PLACEHOLDER VALUES ===")
placeholders = ["Your Name", "your.email@example.com", "yourusername", "EnterpriseUser", "enterprise_user_001"]
found_ph = []
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for fname in files:
        if not fname.endswith(('.py', '.yaml', '.md')):
            continue
        if fname in skip_files:
            continue
        fpath = os.path.join(root, fname)
        content = open(fpath).read()
        for ph in placeholders:
            if ph in content:
                rel = os.path.relpath(fpath, REPO)
                found_ph.append(f"  {rel}: contains '{ph}'")
if found_ph:
    print(f"  FAIL: {len(found_ph)} placeholders found:")
    for x in found_ph:
        print(x)
    errors.extend(found_ph)
else:
    print("  OK: No placeholder values in active files")

# 4. Python syntax
print("\n=== 4. PYTHON SYNTAX ===")
py_ok = 0
py_fail = 0
for root, dirs, files in os.walk(REPO):
    dirs[:] = [d for d in dirs if d not in skip_dirs]
    for fname in files:
        if not fname.endswith('.py'):
            continue
        fpath = os.path.join(root, fname)
        try:
            ast.parse(open(fpath).read())
            py_ok += 1
        except SyntaxError as e:
            py_fail += 1
            rel = os.path.relpath(fpath, REPO)
            errors.append(f"SYNTAX: {rel}: {e}")
            print(f"  FAIL: {rel}: {e}")
print(f"  {py_ok} files OK, {py_fail} failures")

# 5. Key files exist
print("\n=== 5. KEY FILES ===")
key_files = ["README.md", "docs/README.md", ".github/copilot-instructions.md", 
             "RELEASES.md", "CHANGELOG.md", "config.yaml", "setup.py",
             "examples/AGENT_TUTORIAL.md"]
for f in key_files:
    if os.path.exists(f):
        print(f"  OK: {f}")
    else:
        errors.append(f"MISSING: {f}")
        print(f"  FAIL: {f} MISSING")

# Summary
print("\n" + "=" * 50)
if errors:
    print(f"RESULT: {len(errors)} issues found")
    sys.exit(1)
else:
    print("RESULT: ALL CHECKS PASSED - v1.10.0 production ready")
    sys.exit(0)
