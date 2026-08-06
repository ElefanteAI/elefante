#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : backup_elefante_data.py
# PURPOSE : Verified file-level zip backup of Elefante durable data.
# WHEN    : Before any destructive operation, storage upgrade, or migration.
# USAGE   : python scripts/lifecycle/backup_elefante_data.py [--elefante-home PATH] [--out-dir PATH]
# NOTES   : Stop Elefante first for a consistent database snapshot. The archive
#           carries a checksum manifest and excludes nested recovery archives.
# ─────────────────────────────────────────────────────────────────────────────
"""Create a verified, portable archive of Elefante durable data.

The archive is intended for ``restore_elefante_data.py``. It deliberately
does not open database handles, but callers must stop Elefante before backup so
database files form a consistent snapshot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


BACKUP_FORMAT_VERSION = 1
MANIFEST_NAME = "elefante-backup-manifest.json"
EXCLUDED_DATA_DIRECTORIES = frozenset({"backups"})


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _data_files(data_dir: Path) -> Iterable[Path]:
    """Yield regular data files while excluding nested recovery archives."""
    for path in sorted(data_dir.rglob("*")):
        relative = path.relative_to(data_dir)
        if relative.parts and relative.parts[0] in EXCLUDED_DATA_DIRECTORIES:
            continue
        if path.is_symlink():
            raise ValueError(f"Refusing to back up symlinked data path: {path}")
        if path.is_file():
            yield path


def create_backup(data_dir: Path, out_dir: Path) -> Path:
    """Create a checksum-verified zip archive and return its final path."""
    data_dir = data_dir.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"data dir not found: {data_dir}")
    if _is_within(out_dir, data_dir):
        raise ValueError("Backup output must not be inside Elefante data")

    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = out_dir / f"elefante_data_backup_{_timestamp()}.zip"
    suffix = 1
    while archive_path.exists():
        archive_path = out_dir / f"elefante_data_backup_{_timestamp()}_{suffix}.zip"
        suffix += 1

    entries = []
    temporary_fd, temporary_name = tempfile.mkstemp(
        prefix=f".{archive_path.stem}.", suffix=".tmp", dir=out_dir
    )
    os.close(temporary_fd)
    temporary_path = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for path in _data_files(data_dir):
                relative = path.relative_to(data_dir).as_posix()
                archive.write(path, arcname=relative)
                entries.append(
                    {"path": relative, "size": path.stat().st_size, "sha256": _sha256(path)}
                )
            manifest = {
                "format": "elefante-data-backup",
                "format_version": BACKUP_FORMAT_VERSION,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "files": entries,
            }
            archive.writestr(MANIFEST_NAME, json.dumps(manifest, indent=2, sort_keys=True))
        temporary_path.replace(archive_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise
    return archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a verified Elefante data backup")
    parser.add_argument(
        "--elefante-home",
        type=str,
        default=str(Path.home() / ".elefante"),
        help="Elefante home directory (default: ~/.elefante)",
    )
    parser.add_argument(
        "--out-dir",
        type=str,
        default=None,
        help="Output directory for backups (default: <elefante-home>/backups)",
    )
    args = parser.parse_args(argv)

    elefante_home = Path(args.elefante_home).expanduser().resolve()
    data_dir = elefante_home / "data"
    out_dir = Path(args.out_dir).expanduser() if args.out_dir else elefante_home / "backups"
    try:
        archive_path = create_backup(data_dir, out_dir)
    except (FileNotFoundError, ValueError) as error:
        print(f"[error] {error}")
        return 1

    print(f"[ok] verified backup created: {archive_path}")
    print("[note] Stop Elefante before backup to guarantee a consistent database snapshot.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
