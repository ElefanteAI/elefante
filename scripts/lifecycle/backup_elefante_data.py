#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : backup_elefante_data.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : File-level zip backup of ~/.elefante/data; safe with Elefante OFF;
#           does not open any database connection.
# WHEN    : BEFORE any destructive operation (reset_factory, reset_kuzu_nuclear,
#           delete_memories_surgical --apply). Also before version upgrades that
#           change schema. Routine pre-maintenance hygiene.
# USAGE   : python scripts/lifecycle/backup_elefante_data.py [--elefante-home PATH] [--out-dir PATH]
# NOTES   : Safe to run with Elefante ON or OFF — no DB handles opened. Output
#           goes to ~/.elefante/backups/ by default. Backup is a simple zip; no
#           special tool needed to inspect or restore.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Backup Elefante on-disk data (no DB access).

Default target is ~/.elefante/data.
Creates a timestamped zip archive under ~/.elefante/backups.

Safe to run with Elefante Mode OFF.

Usage:
  python scripts/lifecycle/backup_elefante_data.py
  python scripts/lifecycle/backup_elefante_data.py --elefante-home ~/.elefante
  python scripts/lifecycle/backup_elefante_data.py --out-dir ~/.elefante/backups
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
