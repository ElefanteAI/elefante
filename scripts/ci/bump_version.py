#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : bump_version.py
# PURPOSE : Cascade a semver string across runtime/package declarations. Public
#           release claims remain pinned until publication is verified.
# WHEN    : After writing the CHANGELOG entry for the new version. Never run before
#           the CHANGELOG entry exists — the script will refuse. After bumping, run
#           --check to confirm every authoritative declaration agrees.
# USAGE   : python scripts/ci/bump_version.py X.Y.Z [--allow-rebaseline] | --sync | --check
# NOTES   : Mandatory sequence: (1) write CHANGELOG entry, (2) bump, (3) --check,
#           (4) git commit. Lowering the local version requires explicit
#           --allow-rebaseline and is only for unpublished release correction.
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
                 - The new version is <= the current version.
             Exception: if the local repo was advanced past the intended unpublished
             release, pass --allow-rebaseline to correct it deliberately.
    3. Run: python scripts/ci/bump_version.py --check
       Verify every tracked file declares the new version (exit 1 if drift).
    4. git commit && git push

Usage:
        python scripts/ci/bump_version.py 2.2.0                       # Set version to 2.2.0
        python scripts/ci/bump_version.py 2.8.0 --allow-rebaseline    # Correct an unpublished version overshoot
        python scripts/ci/bump_version.py --check                      # Verify all files match (exit 1 if drift)
"""

import re
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = ROOT / "src" / "__init__.py"

# Every file that declares the runtime/package version and how to replace it.
# Public-facing "current published release" claims are intentionally excluded:
# a release branch may carry the next package version before it is published.
# Format: (relative_path, regex_pattern, replacement_template)
# The regex must have exactly one capture group around the version string.
TARGETS = [
    ("src/__init__.py",                               r'(__version__\s*=\s*")[^"]+(")',                          r'\g<1>{v}\2'),
    ("setup.py",                                      r'(version=")[^"]+(")',                                    r'\g<1>{v}\2'),
    ("config.yaml",                                   r'(# Version:\s*)\S+',                                    r'\g<1>{v}'),
    ("config.yaml",                                   r'(  version:\s*")[^"]+(")',                               r'\g<1>{v}\2'),
    ("config.yaml",                                   r'(    version:\s*")[^"]+(")',                             r'\g<1>{v}\2'),
    ("src/dashboard/ui/package.json",                 r'("version":\s*")[^"]+(")',                               r'\g<1>{v}\2'),
]

# Glob-based targets: matches multiple files sharing the same header pattern.
# Format: (glob_pattern, regex_pattern, replacement_template)
# These are expanded at runtime and processed alongside TARGETS.
GLOB_TARGETS = []


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


def _version_parts(version: str) -> tuple[int, int, int]:
    return tuple(int(x) for x in version.split("."))


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


def _check_version_direction(new_version: str, allow_rebaseline: bool = False):
    """Abort if new_version is invalid relative to the current version."""
    current = read_current_version()
    new_parts = _version_parts(new_version)
    current_parts = _version_parts(current)

    if new_parts == current_parts:
        raise SystemExit(
            f"GATE FAILED: New version {new_version} is the same as current {current}.\n"
            f"  Same-version re-applies are not allowed."
        )

    if new_parts < current_parts and not allow_rebaseline:
        raise SystemExit(
            f"GATE FAILED: New version {new_version} is lower than current {current}.\n"
            f"  If this is an unpublished release correction, re-run with --allow-rebaseline."
        )


def bump(new_version: str, allow_rebaseline: bool = False, sync_current: bool = False):
    """Write new_version to all target files."""
    # Validate semver format
    if not re.match(r'^\d+\.\d+\.\d+$', new_version):
        raise SystemExit(f"Invalid version format: '{new_version}'. Use X.Y.Z")
    parts = list(map(int, new_version.split(".")))
    for label, val in zip(("x", "y", "z"), parts):
        if not (0 <= val <= 99):
            raise SystemExit(f"Version part '{label}={val}' is out of range [0, 99].")

    # Release bumps require monotonic versioning plus a changelog entry. Sync is
    # a repair-only path and may write only the current package version.
    current = read_current_version()
    if sync_current:
        if new_version != current:
            raise SystemExit("GATE FAILED: --sync may only propagate the current package version")
    else:
        _check_version_direction(new_version, allow_rebaseline=allow_rebaseline)
        _check_changelog_entry(new_version)

    if allow_rebaseline and _version_parts(new_version) < _version_parts(current):
        print(f"  REBASELINE  Correcting unpublished local version {current} -> {new_version}")

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
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    allow_rebaseline = False
    if "--allow-rebaseline" in args:
        allow_rebaseline = True
        args = [arg for arg in args if arg != "--allow-rebaseline"]

    if len(args) != 1:
        print(__doc__)
        sys.exit(1)

    arg = args[0]
    if arg == "--check":
        if allow_rebaseline:
            raise SystemExit("--allow-rebaseline cannot be used with --check")
        ok = check_versions()
        sys.exit(0 if ok else 1)
    elif arg == "--sync":
        if allow_rebaseline:
            raise SystemExit("--allow-rebaseline cannot be used with --sync")
        bump(read_current_version(), sync_current=True)
    else:
        bump(arg, allow_rebaseline=allow_rebaseline)


if __name__ == "__main__":
    main()
