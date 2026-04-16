#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : select_release_assets.py
# VERSION : 2.7.1
# CHANGED : 2026-04-15
# PURPOSE : Select GitHub release assets that fit under the platform's hard
#           per-file size cap and emit the workflow outputs consumed by the
#           release job.
# WHEN    : In CI after artifact download and before action-gh-release, or
#           locally when validating release publication behavior.
# USAGE   : python scripts/ci/select_release_assets.py
# NOTES   : Defaults to the Elefante build artifact paths and uses GITHUB_OUTPUT
#           and GITHUB_STEP_SUMMARY when present.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Select releasable GitHub assets under the platform file-size cap."""

from __future__ import annotations

import argparse
import os
from pathlib import Path


GITHUB_RELEASE_FILE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024
DEFAULT_CANDIDATES = [
    Path("artifacts/elefante-Linux-binary/elefante-Linux.zip"),
    Path("artifacts/elefante-macOS-binary/elefante-macOS.zip"),
    Path("artifacts/elefante-Windows-binary/elefante-Windows.zip"),
]


def select_release_assets(
    candidates: list[Path],
    *,
    max_release_bytes: int = GITHUB_RELEASE_FILE_LIMIT_BYTES,
) -> tuple[list[str], list[str]]:
    """Return releasable files and human-readable skip reasons."""
    release_files: list[str] = []
    skipped: list[str] = []

    for candidate in candidates:
        path = Path(candidate)
        if not path.exists():
            skipped.append(f"MISSING {path}")
            continue

        size = path.stat().st_size
        if size >= max_release_bytes:
            skipped.append(
                f"SKIP {path} ({size} bytes) exceeds GitHub release asset limit of 2 GiB"
            )
            continue

        release_files.append(str(path))

    return release_files, skipped


def write_github_output(release_files: list[str], output_path: Path) -> None:
    with output_path.open("a", encoding="utf-8") as fh:
        fh.write("files<<EOF\n")
        if release_files:
            fh.write("\n".join(release_files))
            fh.write("\n")
        fh.write("EOF\n")


def write_step_summary(release_files: list[str], skipped: list[str], summary_path: Path) -> None:
    with summary_path.open("a", encoding="utf-8") as fh:
        fh.write("## Release asset selection\n\n")
        if release_files:
            fh.write("### Uploaded\n")
            for item in release_files:
                fh.write(f"- `{item}`\n")
            fh.write("\n")
        if skipped:
            fh.write("### Skipped\n")
            for item in skipped:
                fh.write(f"- {item}\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select GitHub release assets that are under the per-file upload cap"
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        help="Artifact path to consider. Defaults to the Elefante build artifact trio.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=GITHUB_RELEASE_FILE_LIMIT_BYTES,
        help="Maximum per-file size allowed for upload.",
    )
    parser.add_argument(
        "--github-output",
        help="Override the path used for the GitHub Actions output file.",
    )
    parser.add_argument(
        "--step-summary",
        help="Override the path used for the GitHub Actions step summary file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates = [Path(candidate) for candidate in args.candidate] or list(DEFAULT_CANDIDATES)
    release_files, skipped = select_release_assets(
        candidates,
        max_release_bytes=args.max_bytes,
    )

    github_output = args.github_output or os.environ.get("GITHUB_OUTPUT")
    if github_output:
        write_github_output(release_files, Path(github_output))

    step_summary = args.step_summary or os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        write_step_summary(release_files, skipped, Path(step_summary))

    for item in skipped:
        print(item)
    for item in release_files:
        print(f"UPLOAD {item}")

    if not release_files:
        raise SystemExit("No release assets are under GitHub's 2 GiB per-file limit")


if __name__ == "__main__":
    main()