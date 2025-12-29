#!/usr/bin/env python3
"""Restore Elefante on-disk data from a backup archive.

This overwrites ~/.elefante/data by default, so STOP all Elefante processes first.

Usage:
  python scripts/restore_elefante_data.py --latest --force
  python scripts/restore_elefante_data.py --archive ~/.elefante/backups/elefante_data_backup_YYYYMMDD_HHMMSS.zip --force
  python scripts/restore_elefante_data.py --elefante-home ~/.elefante --latest --force

Notes:
- The existing data dir is moved aside to data.pre_restore.<timestamp> unless --discard-existing is set.
- This script performs file operations only (no DB access).
"""

from __future__ import annotations

import argparse
import shutil
import zipfile
from datetime import datetime
from pathlib import Path


def _find_latest_backup(backup_dir: Path) -> Path:
    backups = sorted(backup_dir.glob("elefante_data_backup_*.zip"))
    if not backups:
        raise FileNotFoundError(f"No backups found in {backup_dir}")
    return backups[-1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore Elefante data directory")
    parser.add_argument(
        "--elefante-home",
        type=str,
        default=str(Path.home() / ".elefante"),
        help="Elefante home directory (default: ~/.elefante)",
    )
    parser.add_argument("--archive", type=str, default=None, help="Path to backup zip archive")
    parser.add_argument("--latest", action="store_true", help="Restore the latest backup from <elefante-home>/backups")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Required to perform restore (prevents accidental overwrite)",
    )
    parser.add_argument(
        "--discard-existing",
        action="store_true",
        help="Delete existing data dir instead of moving it aside",
    )

    args = parser.parse_args()

    if not args.force:
        raise SystemExit("[error] refusing to restore without --force")

    elefante_home = Path(args.elefante_home).expanduser().resolve()
    backup_dir = elefante_home / "backups"
    data_dir = elefante_home / "data"

    if args.latest:
        archive_path = _find_latest_backup(backup_dir)
    elif args.archive:
        archive_path = Path(args.archive).expanduser().resolve()
    else:
        raise SystemExit("[error] specify --latest or --archive")

    if not archive_path.exists():
        raise SystemExit(f"[error] archive not found: {archive_path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    if data_dir.exists():
        if args.discard_existing:
            shutil.rmtree(data_dir)
        else:
            moved = elefante_home / f"data.pre_restore.{stamp}"
            if moved.exists():
                shutil.rmtree(moved)
            data_dir.rename(moved)
            print(f"[info] moved existing data to: {moved}")

    data_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(archive_path, "r") as zf:
        zf.extractall(path=data_dir)

    print(f"[ok] restored data from: {archive_path}")
    print(f"[ok] data directory: {data_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
