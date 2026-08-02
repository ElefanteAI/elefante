#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : render_release_notes.py
# VERSION : 2.7.1
# CHANGED : 2026-04-15
# PURPOSE : Render curated GitHub release notes directly from CHANGELOG.md so
#           tagged releases ship with a real narrative, not an empty shell.
# WHEN    : In CI before softprops/action-gh-release, or manually to preview a
#           tag's release body before pushing the release workflow.
# USAGE   : python scripts/ci/render_release_notes.py v2.7.1 --output release-notes.md
# NOTES   : Accepts v-prefixed or bare semver. Fails if CHANGELOG lacks the
#           requested entry. Output is markdown suitable for body_path.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Render curated release notes from CHANGELOG.md."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "CHANGELOG.md"
RELEASE_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\] - (\d{4}-\d{2}-\d{2})$", re.MULTILINE)
CANDIDATE_HEADING_RE = re.compile(r"^## \[(\d+\.\d+\.\d+)\] — Release candidate$", re.MULTILINE)
POTENTIAL_HEADING_RE = re.compile(r"^## \[[^\]]+\].*$", re.MULTILINE)


def version_tuple(version: str) -> tuple[int, int, int]:
    return tuple(int(part) for part in version.split("."))


def normalize_version(raw: str) -> str:
    version = raw.strip()
    if version.startswith("v"):
        version = version[1:]
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit(f"Invalid version '{raw}'. Use X.Y.Z or vX.Y.Z.")
    return version


def parse_release_entries(text: str) -> list[dict[str, str | int]]:
    matches = list(RELEASE_HEADING_RE.finditer(text))
    entries: list[dict[str, str | int]] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append(
            {
                "version": match.group(1),
                "date": match.group(2),
                "line": text.count("\n", 0, match.start()) + 1,
                "entry": text[start:end].strip(),
            }
        )
    return entries


def release_candidate_versions(text: str) -> set[str]:
    """Return versions that are intentionally not published yet."""
    return {match.group(1) for match in CANDIDATE_HEADING_RE.finditer(text)}


def audit_changelog(text: str | None = None) -> list[str]:
    source = text if text is not None else CHANGELOG.read_text(encoding="utf-8")
    errors: list[str] = []

    for match in POTENTIAL_HEADING_RE.finditer(source):
        line = match.group(0)
        if line == "## [Unreleased]":
            continue
        if not RELEASE_HEADING_RE.fullmatch(line) and not CANDIDATE_HEADING_RE.fullmatch(line):
            line_number = source.count("\n", 0, match.start()) + 1
            errors.append(f"Line {line_number}: malformed release heading '{line}'")

    seen_versions: set[str] = set()
    previous_version: tuple[int, int, int] | None = None
    previous_label: str | None = None
    for entry in parse_release_entries(source):
        version = str(entry["version"])
        if version in seen_versions:
            errors.append(f"Line {entry['line']}: duplicate release entry [{version}]")
        seen_versions.add(version)

        current_version = version_tuple(version)
        if previous_version is not None and current_version >= previous_version:
            errors.append(
                f"Line {entry['line']}: release [{version}] is out of descending order after [{previous_label}]"
            )
        previous_version = current_version
        previous_label = version

    return errors


def extract_changelog_entry(version: str, text: str | None = None) -> str:
    source = text if text is not None else CHANGELOG.read_text(encoding="utf-8")
    pattern = rf"^## \[{re.escape(version)}\].*$"
    match = re.search(pattern, source, re.MULTILINE)
    if not match:
        raise SystemExit(f"No CHANGELOG entry found for [{version}].")

    start = match.start()
    next_match = re.search(r"^## \[", source[match.end():], re.MULTILINE)
    end = match.end() + next_match.start() if next_match else len(source)
    entry = source[start:end].strip()
    return entry


def validate_release_documentation(version: str, *, allow_candidate: bool = False) -> None:
    text = CHANGELOG.read_text(encoding="utf-8")
    errors = audit_changelog(text)
    if errors:
        formatted = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(f"CHANGELOG audit failed:\n{formatted}")

    entry = extract_changelog_entry(version, text=text)
    if "### " not in entry or len(entry.splitlines()) < 4:
        raise SystemExit(
            f"CHANGELOG entry for [{version}] is too thin to publish. Add real subsections and details first."
        )
    if version in release_candidate_versions(text) and not allow_candidate:
        raise SystemExit(
            f"v{version} is a release candidate. Assign the actual publication date in CHANGELOG.md before rendering release notes."
        )


def render_release_notes(version: str) -> str:
    validate_release_documentation(version)
    entry = extract_changelog_entry(version)
    return "\n".join(
        [
            f"# Elefante v{version}",
            "",
            "Curated release notes generated from CHANGELOG.md.",
            "",
            entry,
            "",
            "## Start Here",
            "",
            "- [README](README.md) — current product overview and install path",
            "- [CHANGELOG](CHANGELOG.md) — full historical ledger",
            "- [User Documentation](docs/README.md) — released procedures and reference",
            "- [Installation Guide](docs/how-to/install.md) — operator setup",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Elefante release notes from CHANGELOG.md")
    parser.add_argument("version", help="Version to render, e.g. 2.7.1 or v2.7.1")
    parser.add_argument("--output", help="Write markdown to this path instead of stdout")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate changelog history and the target release entry without rendering notes.",
    )
    args = parser.parse_args()

    version = normalize_version(args.version)
    validate_release_documentation(version, allow_candidate=args.validate_only)

    if args.validate_only:
        state = "release candidate" if version in release_candidate_versions(CHANGELOG.read_text(encoding="utf-8")) else "published release"
        print(f"Release documentation OK for v{version} ({state}).")
        return

    notes = render_release_notes(version)

    if args.output:
        Path(args.output).write_text(notes, encoding="utf-8")
    else:
        print(notes, end="")


if __name__ == "__main__":
    main()
