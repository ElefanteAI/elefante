#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : generate_release_checksums.py
# VERSION : 2.12.0
# CHANGED : 2026-07-30
# PURPOSE : Generate and verify the deterministic SHA256SUMS manifest shipped
#           beside Elefante release assets.
# WHEN    : After platform archives are built and again after release artifacts
#           are collected for publication.
# USAGE   : python scripts/ci/generate_release_checksums.py --output SHA256SUMS FILE...
#           python scripts/ci/generate_release_checksums.py --verify SHA256SUMS FILE...
# NOTES   : Manifest entries use asset basenames, are sorted by basename, and
#           reject duplicate basenames so verification remains unambiguous.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Generate or verify a deterministic SHA256SUMS release manifest."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import re
from pathlib import Path

CHECKSUM_LINE = re.compile(r"^(?P<digest>[0-9a-f]{64})  (?P<name>[^\r\n/\\]+)$")
READ_SIZE = 1024 * 1024


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(READ_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def normalize_assets(assets: list[Path]) -> list[Path]:
    paths = [Path(asset) for asset in assets]
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Release assets missing or not files: " + ", ".join(missing))

    by_name: dict[str, Path] = {}
    for path in paths:
        if path.name in by_name:
            raise ValueError(
                f"Duplicate release asset basename {path.name!r}: "
                f"{by_name[path.name]} and {path}"
            )
        by_name[path.name] = path
    return [by_name[name] for name in sorted(by_name)]


def render_checksums(assets: list[Path]) -> str:
    paths = normalize_assets(assets)
    return "".join(f"{sha256_file(path)}  {path.name}\n" for path in paths)


def write_checksums(assets: list[Path], output_path: Path) -> Path:
    output_path = Path(output_path)
    if any(Path(asset).resolve() == output_path.resolve() for asset in assets):
        raise ValueError("The checksum manifest cannot checksum itself")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_checksums(assets))
    return output_path


def parse_manifest(manifest_path: Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    lines = Path(manifest_path).read_text(encoding="utf-8").splitlines()
    if not lines:
        raise ValueError("Checksum manifest is empty")

    for line_number, line in enumerate(lines, start=1):
        match = CHECKSUM_LINE.fullmatch(line)
        if match is None:
            raise ValueError(f"Invalid checksum line {line_number}: {line!r}")
        name = match.group("name")
        if name in entries:
            raise ValueError(f"Duplicate checksum entry: {name}")
        entries[name] = match.group("digest")
    return entries


def verify_checksums(manifest_path: Path, assets: list[Path]) -> list[str]:
    paths = normalize_assets(assets)
    expected = parse_manifest(manifest_path)
    actual_names = {path.name for path in paths}
    if set(expected) != actual_names:
        missing = sorted(set(expected) - actual_names)
        unexpected = sorted(actual_names - set(expected))
        details = []
        if missing:
            details.append("assets not provided: " + ", ".join(missing))
        if unexpected:
            details.append("assets absent from manifest: " + ", ".join(unexpected))
        raise ValueError("Checksum asset set mismatch (" + "; ".join(details) + ")")

    verified: list[str] = []
    for path in paths:
        actual_digest = sha256_file(path)
        if not hmac.compare_digest(expected[path.name], actual_digest):
            raise ValueError(f"SHA-256 mismatch: {path}")
        verified.append(path.name)
    return verified


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate or verify Elefante's deterministic SHA256SUMS manifest"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="Write a new checksum manifest")
    mode.add_argument("--verify", type=Path, help="Verify an existing checksum manifest")
    parser.add_argument("assets", nargs="+", type=Path, help="Release asset files")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.output is not None:
            output_path = write_checksums(args.assets, args.output)
            print(f"Wrote {output_path} for {len(args.assets)} release assets")
            return

        verified = verify_checksums(args.verify, args.assets)
        for name in verified:
            print(f"VERIFIED {name}")
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise SystemExit(f"ERROR: {exc}") from exc


if __name__ == "__main__":
    main()
