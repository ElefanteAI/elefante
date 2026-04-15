#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : bump_version.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Cascade a semver string across every tracked version declaration in
#           the repo. Has CHANGELOG gate, downgrade guard, and pattern-miss WARNING.
# WHEN    : After writing the CHANGELOG entry for the new version. Never run before
#           the CHANGELOG entry exists — the script will refuse. After bumping, run
#           --check to confirm all 48 tracked files agree.
# USAGE   : python scripts/ci/bump_version.py X.Y.Z | --check
# NOTES   : Mandatory sequence: (1) write CHANGELOG entry, (2) bump, (3) --check,
#           (4) git commit. Downgrade (e.g. 2.5.2 -> 2.5.1) is blocked by design.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""
Bump Elefante version across all files.

Single source of truth: src/__init__.py -> propagated everywhere.

Protocol (MANDATORY — enforced by this script):
    1. Write a CHANGELOG.md entry for the new version FIRST.
       Format: ## [X.Y.Z] - YYYY-MM-DD
    2. Run: python scripts/ci/bump_version.py X.Y.Z
       The script will refuse to proceed if:
         - No CHANGELOG entry exists for the new version.
         - The new version is <= the current version (no downgrades).
    3. Run: python scripts/ci/bump_version.py --check
       Verify every tracked file declares the new version (exit 1 if drift).
    4. git commit && git push

Usage:
    python scripts/ci/bump_version.py 2.2.0      # Set version to 2.2.0
    python scripts/ci/bump_version.py --check     # Verify all files match (exit 1 if drift)
"""

import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "src" / "__init__.py"

# Every file that declares the current version and how to find/replace it.
# Format: (relative_path, regex_pattern, replacement_template)
# The regex must have exactly one capture group around the version string.
TARGETS = [
    ("src/__init__.py",                               r'(__version__\s*=\s*")[^"]+(")',                          r'\g<1>{v}\2'),
    ("setup.py",                                      r'(version=")[^"]+(")',                                    r'\g<1>{v}\2'),
    ("config.yaml",                                   r'(# Version:\s*)\S+',                                    r'\g<1>{v}'),
    ("config.yaml",                                   r'(  version:\s*")[^"]+(")',                               r'\g<1>{v}\2'),
    ("config.yaml",                                   r'(    version:\s*")[^"]+(")',                             r'\g<1>{v}\2'),
    ("src/dashboard/ui/package.json",                 r'("version":\s*")[^"]+(")',                               r'\g<1>{v}\2'),
    ("README.md",                                     r'(\*\*v)\d+\.\d+\.\d+(\*\*\s*—)',                     r'\g<1>{v}\2'),
    ("CONTRIBUTING.md",                               r'(Pydantic models \(v)\d+\.\d+\.\d+( schema\))',          r'\g<1>{v}\2'),
    ("docs/README.md",                                r'(> \*\*v)\d+\.\d+\.\d+',                                r'\g<1>{v}'),
    ("docs/debug/README.md",                          r'(Elefante v)\d+\.\d+\.\d+',                            r'\g<1>{v}'),
    ("docs/technical/README.md",                      r'(\*\*Elefante v)\d+\.\d+\.\d+',                         r'\g<1>{v}'),
    ("docs/technical/spec-tools.md",                  r'(API Reference \(v)\d+\.\d+\.\d+(\))',                  r'\g<1>{v}\2'),
    ("docs/technical/spec-architecture.md",            r'(\*\*Version:\*\* )\d+\.\d+\.\d+',                     r'\g<1>{v}'),
    ("docs/technical/ops-dashboard.md",                r'(\*\*Document Version\*\*: )\d+\.\d+\.\d+',            r'\g<1>{v}'),
    ("docs/technical/dev-etiquette.md",                r'(\*\*Version:\*\*\s*)\d+\.\d+\.\d+',                 r'\g<1>{v}'),
    ("docs/technical/ops-mcp-server.md",               r'(\*\*Document Version\*\*: )\d+\.\d+\.\d+',            r'\g<1>{v}'),
    ("docs/technical/ops-restart.md",                  r'(\*\*Version\*\*: )\d+\.\d+\.\d+',                     r'\g<1>{v}'),
    ("docs/technical/dev-sdd.md",                      r'(\*\*Version\*\*:\s*)\d+\.\d+\.\d+',                 r'\g<1>{v}'),
    ("docs/technical/spec-scoring.md",                 r'(\*\*Feature Version\*\*: )\d+\.\d+\.\d+',             r'\g<1>{v}'),
    ("docs/technical/ops-kuzu.md",                     r'(Applies to\*\*: v)\d+\.\d+\.\d+',                     r'\g<1>{v}'),
    ("examples/AGENT_TUTORIAL.md",                    r'(\*\*Version:\*\*\s*)\S+',                             r'\g<1>{v}'),
    ("tests/README.md",                               r'(\*\*Version:\*\*\s*)\S+',                             r'\g<1>{v}'),
    ("docs/technical/ops-installation.md",            r'(\*\*Version\*\*: )\d+\.\d+\.\d+',                    r'\g<1>{v}'),
    ("docs/planning/spec-vision.md",                  r'(Current version: v)\d+\.\d+\.\d+',                   r'\g<1>{v}'),
    ("docs/technical/ops-rollback.md",                r'(\*\*Version\*\*: )\d+\.\d+\.\d+',                    r'\g<1>{v}'),
    ("docs/technical/spec-ingestion.md",              r'(\*\*Version\*\*: )\d+\.\d+\.\d+',                    r'\g<1>{v}'),
    ("docs/debug/best_practices.md",                  r'(\*\*Applies to\*\*: v)\d+\.\d+\.\d+\+',              r'\g<1>{v}+'),
    ("docs/debug/ops-ai-behavior-compendium.md",      r'(\*\*Applies to\*\*: v)\d+\.\d+\.\d+\+',              r'\g<1>{v}+'),
    ("docs/debug/ops-dashboard-compendium.md",        r'(\*\*Applies to\*\*: v)\d+\.\d+\.\d+\+',              r'\g<1>{v}+'),
    ("docs/debug/ops-installation-compendium.md",     r'(\*\*Applies to\*\*: v)\d+\.\d+\.\d+\+',              r'\g<1>{v}+'),
    ("docs/debug/ops-memory-compendium.md",           r'(\*\*Applies to\*\*: v)\d+\.\d+\.\d+\+',              r'\g<1>{v}+'),
]

# Glob-based targets: matches multiple files sharing the same header pattern.
# Format: (glob_pattern, regex_pattern, replacement_template)
# These are expanded at runtime and processed alongside TARGETS.
GLOB_TARGETS = [
    ("src/dashboard/ui/src/**/*.tsx",  r'(// Elefante Dashboard v)\d+\.\d+\.\d+',  r'\g<1>{v}'),
    ("src/dashboard/ui/src/**/*.ts",   r'(// Elefante Dashboard v)\d+\.\d+\.\d+',  r'\g<1>{v}'),
]


def _expand_glob_targets():
    """Expand GLOB_TARGETS into concrete (rel_path, pattern, template) tuples.

    Only files whose content actually matches the pattern are included.
    Bootstrap/utility files without a version header are silently skipped.
    """
    expanded = []
    for glob_pat, pattern, template in GLOB_TARGETS:
        for fpath in sorted(ROOT.glob(glob_pat)):
            text = fpath.read_text(encoding='utf-8')
            if re.search(pattern, text):
                rel = fpath.relative_to(ROOT).as_posix()
                expanded.append((rel, pattern, template))
    return expanded


def read_current_version() -> str:
    text = VERSION_FILE.read_text(encoding='utf-8')
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise SystemExit("Cannot read __version__ from src/__init__.py")
    return m.group(1)


def check_versions() -> bool:
    """Return True if all files match src/__init__.py, False otherwise."""
    expected = read_current_version()
    ok = True
    all_targets = TARGETS + _expand_glob_targets()
    for rel_path, pattern, _ in all_targets:
        fpath = ROOT / rel_path
        if not fpath.exists():
            print(f"  MISSING  {rel_path}")
            ok = False
            continue
        text = fpath.read_text(encoding='utf-8')
        # Simpler: just check if expected version appears in pattern matches
        found = [m for m in re.finditer(pattern, text, re.DOTALL)]
        for m in found:
            full = m.group(0)
            if expected not in full:
                print(f"  DRIFT    {rel_path}: found '{full}' (expected {expected})")
                ok = False
                break
        else:
            if not found:
                print(f"  NO MATCH {rel_path}: pattern didn't match anything")
                ok = False

    # Also check package-lock.json project-level version
    lockfile = ROOT / "src" / "dashboard" / "ui" / "package-lock.json"
    if lockfile.exists():
        data = json.loads(lockfile.read_text(encoding='utf-8'))
        if data.get("version") != expected:
            print(f"  DRIFT    src/dashboard/ui/package-lock.json: '{data.get('version')}' (expected {expected})")
            ok = False

    if ok:
        print(f"  ALL OK   Every file declares {expected}")
    return ok


def _check_changelog_entry(new_version: str):
    """Abort if CHANGELOG.md has no entry for new_version."""
    changelog = ROOT / "CHANGELOG.md"
    if not changelog.exists():
        raise SystemExit("CHANGELOG.md not found. Write the changelog entry first.")
    text = changelog.read_text(encoding='utf-8')
    pattern = rf'^## \[{re.escape(new_version)}\]'
    if not re.search(pattern, text, re.MULTILINE):
        raise SystemExit(
            f"GATE FAILED: No CHANGELOG.md entry found for [{new_version}].\n"
            f"  Write '## [{new_version}] - YYYY-MM-DD' in CHANGELOG.md first, then re-run."
        )


def _check_no_downgrade(new_version: str):
    """Abort if new_version is <= the current version."""
    current = read_current_version()
    def _parts(v): return tuple(int(x) for x in v.split("."))
    if _parts(new_version) <= _parts(current):
        raise SystemExit(
            f"GATE FAILED: New version {new_version} is not greater than current {current}.\n"
            f"  Downgrades and same-version re-applies are not allowed."
        )


def bump(new_version: str):
    """Write new_version to all target files."""
    # Validate semver format
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        raise SystemExit(f"Invalid version format: '{new_version}'. Use X.Y.Z")
    parts = list(map(int, new_version.split(".")))
    for label, val in zip(("x", "y", "z"), parts):
        if not (0 <= val <= 99):
            raise SystemExit(f"Version part '{label}={val}' is out of range [0, 99].")

    # Precondition gates — abort before touching any file
    _check_no_downgrade(new_version)
    _check_changelog_entry(new_version)

    changed = []
    warned = []
    all_targets = TARGETS + _expand_glob_targets()
    for rel_path, pattern, template in all_targets:
        fpath = ROOT / rel_path
        if not fpath.exists():
            print(f"  SKIP     {rel_path} (not found)")
            continue
        text = fpath.read_text(encoding='utf-8')
        flags = re.DOTALL if '\n' in pattern else 0
        # RELEASES.md: only replace first match (Current Baseline), not historical entries
        count = 1 if 'Current Baseline' in pattern else 0
        new_text = re.sub(pattern, template.format(v=new_version), text, count=count, flags=flags)
        if new_text != text:
            fpath.write_text(new_text, encoding='utf-8')
            changed.append(rel_path)
        elif not re.search(pattern, text, flags):
            # File exists but pattern never matched — version header may have changed format
            print(f"  WARNING  {rel_path}: pattern matched nothing — version may not have been updated")
            warned.append(rel_path)

    # package-lock.json: update project-level version (top-level + packages[""])
    lockfile = ROOT / "src" / "dashboard" / "ui" / "package-lock.json"
    if lockfile.exists():
        data = json.loads(lockfile.read_text(encoding='utf-8'))
        old_top = data.get("version")
        data["version"] = new_version
        if "" in data.get("packages", {}):
            data["packages"][""]["version"] = new_version
        lockfile.write_text(json.dumps(data, indent=2) + "\n", encoding='utf-8')
        if old_top != new_version:
            changed.append("src/dashboard/ui/package-lock.json")

    print(f"\n  Bumped to {new_version} — {len(changed)} file(s) updated:")
    for f in changed:
        print(f"    {f}")

    if warned:
        print(f"\n  WARNINGS — {len(warned)} file(s) had no pattern match (inspect manually):")
        for f in warned:
            print(f"    {f}")

    if not changed:
        print("    (no changes needed — already at this version)")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    arg = sys.argv[1]
    if arg == "--check":
        ok = check_versions()
        sys.exit(0 if ok else 1)
    else:
        bump(arg)


if __name__ == "__main__":
    main()
