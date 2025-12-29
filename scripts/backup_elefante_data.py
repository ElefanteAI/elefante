#!/usr/bin/env python3
"""Backup Elefante on-disk data (no DB access).

Default target is ~/.elefante/data.
Creates a timestamped zip archive under ~/.elefante/backups.

Safe to run with Elefante Mode OFF.

Usage:
  python scripts/backup_elefante_data.py
  python scripts/backup_elefante_data.py --elefante-home ~/.elefante
  python scripts/backup_elefante_data.py --out-dir ~/.elefante/backups
"""

from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Backup Elefante data directory")
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
    args = parser.parse_args()

    elefante_home = Path(args.elefante_home).expanduser().resolve()
    data_dir = elefante_home / "data"
    if not data_dir.exists():
        raise SystemExit(f"[error] data dir not found: {data_dir}")

    out_dir = Path(args.out_dir).expanduser().resolve() if args.out_dir else (elefante_home / "backups")
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = out_dir / f"elefante_data_backup_{stamp}"

    archive_path = shutil.make_archive(str(base_name), "zip", root_dir=str(data_dir))
    print(f"[ok] backup created: {archive_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
