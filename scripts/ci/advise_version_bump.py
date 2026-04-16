#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : advise_version_bump.py
# VERSION : 2.7.1
# CHANGED : 2026-04-15
# PURPOSE : Inspect staged git diff, classify MAJOR/MINOR/PATCH, then hand off
#           to bump_version.py only when the matching CHANGELOG entry already exists.
# WHEN    : After staging changes. Usually run BEFORE writing the CHANGELOG entry
#           to determine the right version; rerun after the entry exists if you want
#           the advisor to hand off to bump_version.py automatically.
# USAGE   : python scripts/ci/advise_version_bump.py
# NOTES   : Requires staged git changes (git add first). If CHANGELOG.md does not
#           yet contain the proposed release entry, the advisor stops after printing
#           the recommended next steps instead of calling bump_version.py.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""
advise_version_bump.py — Smart version bump advisor.

Analyzes staged git changes, classifies them as MAJOR / MINOR / PATCH,
presents a recommendation with reason, and asks for confirmation before
calling bump_version.py.

Usage:
    python scripts/ci/advise_version_bump.py

Flow:
    1. git add <your files>
    2. python scripts/ci/advise_version_bump.py   ← this script
    3. Confirm or override the proposed version
    4. Write CHANGELOG.md entry for the chosen version
    5. Re-run this advisor or call bump_version.py directly
    6. git commit && git push
"""

import re
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# ── Classification signal tables ─────────────────────────────────────────────

# File path patterns that imply a MAJOR change (breaking)
MAJOR_FILE_SIGNALS = [
    (r"^src/models/",   "core data-model / schema changed"),
]

# Diff-text patterns that imply a MAJOR change
MAJOR_DIFF_SIGNALS = [
    (r"BREAKING[_\s]CHANGE",                  "explicit BREAKING CHANGE marker in diff"),
    (r'^-\s*(async\s+)?def elefante_\w+',     "existing Elefante MCP tool removed"),
    (r'^-\s*"elefante-\w+"\s*:',              "Elefante tool entry removed from registry"),
    (r'\bmigration\b',                         "migration keyword detected in diff"),
    (r'\bdrop\s+(table|column|index)\b',       "database destructive operation"),
]

# File path patterns that imply a MINOR change (new feature, backward-compat)
MINOR_FILE_SIGNALS = [
    (r"^src/mcp/",      "MCP layer changed — likely new or updated tool"),
]

# Diff-text patterns that imply a MINOR change
MINOR_DIFF_SIGNALS = [
    (r'^\+\s*(async\s+)?def elefante_\w+',    "new Elefante MCP tool added"),
    (r'^\+\s*"elefante-\w+"\s*:',             "new tool entry added to registry"),
]


# ── Git helpers ───────────────────────────────────────────────────────────────

def _git(*args) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def staged_files() -> list[str]:
    return [f.strip() for f in _git("diff", "--cached", "--name-only").splitlines() if f.strip()]


def new_files() -> list[str]:
    """Files being added for the first time (A = added in diff-filter)."""
    return [f.strip() for f in _git("diff", "--cached", "--name-only", "--diff-filter=A").splitlines() if f.strip()]


def staged_diff() -> str:
    return _git("diff", "--cached")


# ── Version helpers ───────────────────────────────────────────────────────────

def current_version() -> str:
    init = ROOT / "src" / "__init__.py"
    text = init.read_text(encoding="utf-8")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("ERROR: Cannot read __version__ from src/__init__.py")
    return m.group(1)


VERSION_PART_MAX = 99
VERSION_PART_MIN = 0


def validate_version(version: str) -> None:
    """Raise SystemExit if any part of x.y.z is outside [0, 99]."""
    try:
        parts = list(map(int, version.split(".")))
    except ValueError:
        raise SystemExit(f"  ERROR: '{version}' is not a valid x.y.z version.")
    if len(parts) != 3:
        raise SystemExit(f"  ERROR: '{version}' must have exactly three parts (x.y.z).")
    for label, val in zip(("x", "y", "z"), parts):
        if not (VERSION_PART_MIN <= val <= VERSION_PART_MAX):
            raise SystemExit(
                f"  ERROR: version part '{label}={val}' is out of range "
                f"[{VERSION_PART_MIN}, {VERSION_PART_MAX}]."
            )


def changelog_has_entry(version: str) -> bool:
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        return False
    text = changelog.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\] - \d{{4}}-\d{{2}}-\d{{2}}$"
    return re.search(pattern, text, re.MULTILINE) is not None


def bump(version: str, level: str) -> str:
    x, y, z = map(int, version.split("."))
    if level == "MAJOR":
        result = f"{x + 1}.0.0"
    elif level == "MINOR":
        result = f"{x}.{y + 1}.0"
    else:
        result = f"{x}.{y}.{z + 1}"   # PATCH
    validate_version(result)
    return result


# ── Classifier ────────────────────────────────────────────────────────────────

def classify(files: list[str], diff: str, added: list[str]) -> tuple[str, str]:
    """Return (level, short_reason). level ∈ {'MAJOR', 'MINOR', 'PATCH'}."""

    # ── MAJOR ──────────────────────────────────────────────────────────────
    for path in files:
        for pattern, reason in MAJOR_FILE_SIGNALS:
            if re.search(pattern, path):
                return "MAJOR", f"{reason} ({path})"

    for pattern, reason in MAJOR_DIFF_SIGNALS:
        if re.search(pattern, diff, re.MULTILINE | re.IGNORECASE):
            return "MAJOR", reason

    # ── MINOR ──────────────────────────────────────────────────────────────
    for path in files:
        for pattern, reason in MINOR_FILE_SIGNALS:
            if re.search(pattern, path):
                return "MINOR", f"{reason} ({path})"

    for pattern, reason in MINOR_DIFF_SIGNALS:
        if re.search(pattern, diff, re.MULTILINE):
            return "MINOR", reason

    # New Python source files added anywhere under src/
    new_src = [f for f in added if f.startswith("src/") and f.endswith(".py")]
    if new_src:
        label = new_src[0] + (f" (+{len(new_src) - 1} more)" if len(new_src) > 1 else "")
        return "MINOR", f"new source file added: {label}"

    # New scripts (utility tools)
    new_scripts = [f for f in added if f.startswith("scripts/") and f.endswith(".py")]
    if new_scripts:
        return "MINOR", f"new script added: {new_scripts[0]}"

    # ── PATCH (default) ────────────────────────────────────────────────────
    doc_only = all(
        f.endswith(".md") or f.startswith("docs/") or f.startswith("tests/")
        for f in files
    )
    if doc_only:
        return "PATCH", "documentation or test changes only"

    return "PATCH", "bug fixes or internal cleanup (no new public surface)"


# ── UI ────────────────────────────────────────────────────────────────────────

_TABLE = """\
  ┌──────┬──────────┬──────────────────────────────────────────────┐
  │ Part │ Meaning  │ When to bump                                 │
  ├──────┼──────────┼──────────────────────────────────────────────┤
  │  x   │ MAJOR    │ Breaking change — existing installs break    │
  │  y   │ MINOR    │ New feature, backward-compatible             │
  │  z   │ PATCH    │ Bug fix, docs, internal cleanup              │
  └──────┴──────────┴──────────────────────────────────────────────┘"""

_LEVEL_LABEL = {
    "MAJOR": "x  (MAJOR)",
    "MINOR": "y  (MINOR)",
    "PATCH": "z  (PATCH)",
}


def main() -> None:
    files = staged_files()
    if not files:
        print("\n  No staged changes found.")
        print("  Stage your files with `git add <files>` first.\n")
        sys.exit(0)

    diff  = staged_diff()
    added = new_files()
    curr  = current_version()

    level, reason = classify(files, diff, added)
    proposed      = bump(curr, level)

    print()
    print("  I believe this development, if you want to save it,")
    print(f"  it should be v{proposed}  (bump {_LEVEL_LABEL[level]}),")
    print(f"  because: {reason}.")
    print()
    print(_TABLE)
    print()
    print(f"  Staged files ({len(files)}):")
    for f in files[:12]:
        print(f"    {f}")
    if len(files) > 12:
        print(f"    ... and {len(files) - 12} more")
    print()
    answer = input(f"  Bump to v{proposed}?  [y / N / enter override e.g. 2.3.0]: ").strip()
    print()

    if not answer or answer.lower() == "n":
        print("  Cancelled. No version change made.")
        sys.exit(0)

    if answer.lower() == "y":
        target = proposed
    elif re.match(r"^\d+\.\d+\.\d+$", answer):
        try:
            validate_version(answer)
        except SystemExit as e:
            print(str(e))
            sys.exit(1)
        target = answer
        print(f"  Using override: v{target}")
    else:
        print(f"  Unrecognised input '{answer}'. Cancelled.")
        sys.exit(1)

    if not changelog_has_entry(target):
        print(f"  Recommended version locked: v{target}.")
        print("  CHANGELOG.md does not contain that release entry yet, so no files were bumped.")
        print("  Next steps:")
        print(f"    1. Write '## [{target}] - YYYY-MM-DD' plus real notes in CHANGELOG.md")
        print(f"    2. Run {Path(sys.executable).name} scripts/ci/bump_version.py {target}")
        print(f"    3. Run {Path(sys.executable).name} scripts/ci/bump_version.py --check")
        print("    4. git add -A")
        print(f"    5. git commit -m \"chore: bump to v{target} <description>\"")
        print("    6. git push")
        print()
        sys.exit(0)

    # ── Run bump_version.py ────────────────────────────────────────────────
    bump_script = ROOT / "scripts" / "ci" / "bump_version.py"
    result = subprocess.run([sys.executable, str(bump_script), target], cwd=ROOT)
    if result.returncode != 0:
        print("\n  bump_version.py failed. Version not updated.")
        sys.exit(1)

    print()
    print(f"  Version bumped to v{target}.")
    print("  Next steps:")
    print(f"    1. Run {Path(sys.executable).name} scripts/ci/bump_version.py --check")
    print("    2. git add -A")
    print(f"    3. git commit -m \"chore: bump to v{target} <description>\"")
    print("    4. git push")
    print()


if __name__ == "__main__":
    main()
