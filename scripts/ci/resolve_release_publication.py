#!/usr/bin/env python3
"""Resolve whether a build is a candidate or an exact tagged release."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def source_version(root: Path = ROOT) -> str:
    contents = (root / "src" / "__init__.py").read_text(encoding="utf-8")
    match = re.search(
        r'^__version__\s*=\s*"(\d+\.\d+\.\d+)"\s*$',
        contents,
        flags=re.MULTILINE,
    )
    if not match:
        raise ValueError("Could not read the source semantic version")
    return match.group(1)


def publication_status(*, ref_type: str, ref_name: str, version: str) -> str:
    """Permit release-labelled artifacts only for the exact source-version tag."""
    if ref_type != "tag":
        return "candidate"

    expected_tag = f"v{version}"
    if ref_name != expected_tag:
        raise ValueError(
            f"Release tag {ref_name!r} does not match source version {expected_tag!r}"
        )
    return "release"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref-type", required=True, choices=("branch", "tag"))
    parser.add_argument("--ref-name", required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    print(
        publication_status(
            ref_type=args.ref_type,
            ref_name=args.ref_name,
            version=source_version(args.root.resolve()),
        )
    )


if __name__ == "__main__":
    main()
