#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : restore_elefante_data.py
# VERSION : 2.5.2
# CHANGED : 2026-07-22
# PURPOSE : Dry-run-first, checksum-verified restore of Elefante durable data.
# WHEN    : After accidental data loss, a factory reset, or a storage migration.
# USAGE   : python scripts/lifecycle/restore_elefante_data.py --latest [--apply]
# NOTES   : Stop Elefante first. Existing data is moved aside by default; unsafe
#           archive paths and checksum failures are rejected before any mutation.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Restore an Elefante data archive without trusting its zip contents.

The default command is a read-only preflight. ``--apply`` stages and verifies
the archive before replacing the data directory, preserving existing data in a
timestamped sibling unless an explicitly confirmed discard is requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import stat
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any


MANIFEST_NAME = "elefante-backup-manifest.json"
BACKUP_FORMAT_VERSION = 1


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _find_latest_backup(backup_dir: Path) -> Path:
    backups = sorted(backup_dir.glob("elefante_data_backup_*.zip"))
    if not backups:
        raise FileNotFoundError(f"No backups found in {backup_dir}")
    return backups[-1]


def _safe_relative_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"Unsafe archive member path: {name!r}")
    return path


def _regular_members(archive: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Validate archive paths/types and return non-directory members."""
    members: list[zipfile.ZipInfo] = []
    seen: set[str] = set()
    for member in archive.infolist():
        path = _safe_relative_path(member.filename)
        if stat.S_ISLNK(member.external_attr >> 16):
            raise ValueError(f"Refusing symlink in backup archive: {member.filename}")
        if member.is_dir():
            continue
        normalized = path.as_posix()
        if normalized in seen:
            raise ValueError(f"Duplicate archive member: {normalized}")
        seen.add(normalized)
        members.append(member)
    return members


def _digest_stream(source: Any) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: source.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _read_manifest(archive: zipfile.ZipFile, members: list[zipfile.ZipInfo]) -> dict[str, Any] | None:
    manifest_info = next((member for member in members if member.filename == MANIFEST_NAME), None)
    if manifest_info is None:
        return None
    try:
        manifest = json.loads(archive.read(manifest_info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Backup manifest is not valid JSON") from error
    if not isinstance(manifest, dict) or manifest.get("format") != "elefante-data-backup":
        raise ValueError("Backup manifest has an unsupported format")
    if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
        raise ValueError("Backup manifest has an unsupported format version")
    listed_files = manifest.get("files")
    if not isinstance(listed_files, list):
        raise ValueError("Backup manifest has no file list")
    expected: dict[str, dict[str, Any]] = {}
    for entry in listed_files:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("Backup manifest contains an invalid file entry")
        expected[entry["path"]] = entry
    actual = {member.filename for member in members if member.filename != MANIFEST_NAME}
    if set(expected) != actual:
        raise ValueError("Backup manifest file list does not match archive contents")
    for member in members:
        if member.filename == MANIFEST_NAME:
            continue
        entry = expected[member.filename]
        with archive.open(member) as source:
            digest = _digest_stream(source)
        if entry.get("size") != member.file_size or entry.get("sha256") != digest:
            raise ValueError(f"Backup integrity check failed for: {member.filename}")
    return manifest


def _validated_archive_contents(
    archive_path: Path,
) -> tuple[Path, list[zipfile.ZipInfo], dict[str, Any] | None]:
    """Validate an archive once and return its normalized contents."""
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.is_file():
        raise FileNotFoundError(f"archive not found: {archive_path}")
    if archive_path.suffix.lower() != ".zip":
        raise ValueError("Elefante restore accepts a .zip archive")
    try:
        with zipfile.ZipFile(archive_path, "r") as archive:
            members = _regular_members(archive)
            manifest = _read_manifest(archive, members)
    except zipfile.BadZipFile as error:
        raise ValueError("Archive is not a valid zip file") from error
    return archive_path, members, manifest


def read_verified_manifest(archive_path: Path) -> dict[str, Any]:
    """Return a validated backup manifest without extracting the archive."""
    _archive_path, _members, manifest = _validated_archive_contents(archive_path)
    if manifest is None:
        raise ValueError("Backup archive has no verified manifest")
    return manifest


def inspect_archive(archive_path: Path) -> dict[str, Any]:
    """Read and validate an archive without writing to the destination."""
    archive_path, members, manifest = _validated_archive_contents(archive_path)
    return {
        "archive": archive_path,
        "files": len([member for member in members if member.filename != MANIFEST_NAME]),
        "verified_manifest": manifest is not None,
    }


def _next_path(parent: Path, stem: str) -> Path:
    candidate = parent / f"{stem}.{_timestamp()}"
    suffix = 1
    while candidate.exists():
        candidate = parent / f"{stem}.{_timestamp()}.{suffix}"
        suffix += 1
    return candidate


def _extract_to_staging(archive_path: Path, staging_dir: Path) -> None:
    with zipfile.ZipFile(archive_path, "r") as archive:
        members = _regular_members(archive)
        _read_manifest(archive, members)
        staging_dir.mkdir(parents=True, exist_ok=False)
        for member in members:
            if member.filename == MANIFEST_NAME:
                continue
            destination = staging_dir.joinpath(*_safe_relative_path(member.filename).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(member) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)


def restore_archive(
    archive_path: Path,
    data_dir: Path,
    *,
    apply: bool = False,
    discard_existing: bool = False,
    discard_confirmation: str = "",
) -> dict[str, Any]:
    """Preflight or atomically restore an archive into ``data_dir``."""
    inspection = inspect_archive(archive_path)
    data_dir = data_dir.expanduser().resolve()
    result = {
        **inspection,
        "data_dir": data_dir,
        "existing_data": data_dir.exists(),
        "applied": False,
    }
    if not apply:
        return result
    if discard_existing and discard_confirmation != "DISCARD":
        raise ValueError("--discard-existing requires --confirm DISCARD")

    data_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = _next_path(data_dir.parent, ".data.restore")
    previous_dir: Path | None = None
    try:
        _extract_to_staging(Path(inspection["archive"]), staging_dir)
        if data_dir.exists():
            previous_dir = _next_path(data_dir.parent, "data.pre_restore")
            data_dir.rename(previous_dir)
        try:
            staging_dir.rename(data_dir)
        except Exception:
            if previous_dir is not None and previous_dir.exists() and not data_dir.exists():
                previous_dir.rename(data_dir)
            raise
        if discard_existing and previous_dir is not None:
            shutil.rmtree(previous_dir)
            previous_dir = None
        result.update({"applied": True, "previous_data": previous_dir})
        return result
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preflight or restore an Elefante data backup")
    parser.add_argument(
        "--elefante-home",
        type=str,
        default=str(Path.home() / ".elefante"),
        help="Elefante home directory (default: ~/.elefante)",
    )
    parser.add_argument("--archive", type=str, default=None, help="Path to a backup zip archive")
    parser.add_argument("--latest", action="store_true", help="Use the newest backup in <elefante-home>/backups")
    parser.add_argument("--apply", action="store_true", help="Apply the restore after the default read-only preflight")
    parser.add_argument("--force", action="store_true", help="Deprecated alias for --apply")
    parser.add_argument("--discard-existing", action="store_true", help="Delete replaced data after a successful restore")
    parser.add_argument("--confirm", default="", help="Must be DISCARD with --discard-existing")
    args = parser.parse_args(argv)

    if args.latest and args.archive:
        print("[error] specify only one of --latest or --archive")
        return 1
    elefante_home = Path(args.elefante_home).expanduser().resolve()
    try:
        archive_path = _find_latest_backup(elefante_home / "backups") if args.latest else Path(args.archive or "")
        if not args.latest and not args.archive:
            raise ValueError("specify --latest or --archive")
        result = restore_archive(
            archive_path,
            elefante_home / "data",
            apply=args.apply or args.force,
            discard_existing=args.discard_existing,
            discard_confirmation=args.confirm,
        )
    except (FileNotFoundError, ValueError, OSError) as error:
        print(f"[error] {error}")
        return 1

    if not result["applied"]:
        print(f"[dry-run] archive valid: {result['archive']} ({result['files']} files)")
        print("[dry-run] no data changed; stop Elefante, then re-run with --apply to restore")
        return 0
    print(f"[ok] restored data from: {result['archive']}")
    if result["previous_data"] is not None:
        print(f"[ok] previous data preserved at: {result['previous_data']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
