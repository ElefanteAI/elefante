#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : reset_kuzu_nuclear.py
# PURPOSE : Backup-and-remove the Kuzu graph database path only (file or dir)
#           so the next init starts fresh without a full factory reset.
# WHEN    : When Kuzu is corrupted and cannot be opened (e.g. schema mismatch
#           after a model change, or Kuzu lock file corruption). Use ONLY when
#           you need the graph store reset but want to preserve vector memory.
#           For a full wipe, use reset_factory.py instead.
# USAGE   : ELEFANTE_PRIVILEGED=1 python scripts/debug/reset_kuzu_nuclear.py --apply --confirm DELETE
# NOTES   : Always create a verified backup first. This moves the configured
#           Kuzu path into recovery and never rebuilds topology. The vector
#           store is untouched. Kuzu initializes empty on next server start.
# ─────────────────────────────────────────────────────────────────────────────
"""Nuclear reset for the Kuzu database path.

Backs up and removes the current `kuzu_db` path, whether it is a file or a
directory, so the next initialization starts fresh.
"""

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from scripts.lifecycle.reset_factory import _configured_storage

# Force UTF-8 output on Windows
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _contains(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def nuclear_reset_kuzu(*, apply: bool, confirm: str, confirm_path: str = "") -> bool:
    """Move the configured Kuzu path to recovery; never rebuild graph state."""
    try:
        data_dir, vector_path, kuzu_path = _configured_storage()
    except RuntimeError as error:
        print(f"Refusing to reset: {error}")
        return False

    backup_root = data_dir / "backups" / "kuzu_reset"

    print("=" * 70)
    print("KUZU DATABASE NUCLEAR RESET")
    print("=" * 70)
    print()
    
    if not kuzu_path.exists():
        print(f"[OK] No configured Kuzu path found at: {kuzu_path}")
        print("  Database is ready for fresh initialization.")
        return True
    
    if kuzu_path.is_file():
        print("[INFO] Configured Kuzu path is a file")
        print(f"  Path: {kuzu_path}")
        print(f"  Size: {kuzu_path.stat().st_size:,} bytes")
        print()
    elif kuzu_path.is_dir():
        print("[INFO] Configured Kuzu path is a directory (legacy or alternate layout)")
        print(f"  Path: {kuzu_path}")
        print()
    else:
        print("[FAIL] UNKNOWN: configured Kuzu path is neither file nor directory")
        print(f"  Path: {kuzu_path}")
        print("  Manual investigation required.")
        return False

    if not apply:
        print("Dry-run only. Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        if not _contains(data_dir, kuzu_path):
            print(f"External configured path also requires: --confirm-path {kuzu_path}")
        return True

    if not _truthy_env("ELEFANTE_PRIVILEGED"):
        print("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        return False

    if (confirm or "").strip() != "DELETE":
        print("Refusing to apply: pass --confirm DELETE")
        return False

    home_path = Path.home().resolve()
    filesystem_root = Path(kuzu_path.anchor)
    protected_descendants = (data_dir, vector_path, backup_root)
    if kuzu_path in {filesystem_root, home_path} or any(
        _contains(kuzu_path, protected) for protected in protected_descendants
    ):
        print("Refusing to reset: configured Kuzu path is broad or contains protected storage")
        return False

    if not _contains(data_dir, kuzu_path):
        try:
            confirmed_path = Path(confirm_path).expanduser().resolve()
        except (OSError, RuntimeError):
            confirmed_path = Path()
        if not confirm_path or confirmed_path != kuzu_path:
            print(
                "Refusing to reset external configured storage: "
                f"pass --confirm-path {kuzu_path}"
            )
            return False

    backup_root.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_root / f"{kuzu_path.name}.{timestamp}"
    collision = 0
    while backup_path.exists():
        collision += 1
        backup_path = backup_root / f"{kuzu_path.name}.{timestamp}.{collision}"

    print("[1/2] Moving current Kuzu path to backup...")
    print(f"      From: {kuzu_path}")
    print(f"      To:   {backup_path}")

    try:
        shutil.move(str(kuzu_path), str(backup_path))
        print("      [OK] Backup move completed")
    except Exception as e:
        print(f"      [FAIL] Backup move failed: {e}")
        return False

    print()
    print("[2/2] Reset complete")
    print()
    print("=" * 70)
    print("SUCCESS: Kuzu database path removed")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Next init will recreate the current Kuzu database path")
    print("2. Run scripts/verify/verify_health.py to test database access")
    print("3. No automatic graph rebuild is performed; restore the verified backup if topology is required")
    return True

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Backup and remove corrupted Kuzu DB file (dry-run by default)")
    p.add_argument("--apply", action="store_true", help="Apply removal (otherwise dry-run)")
    p.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    p.add_argument(
        "--confirm-path",
        type=str,
        default="",
        help="Exact resolved Kuzu path; required when configured outside the data root",
    )
    args = p.parse_args()

    success = nuclear_reset_kuzu(
        apply=bool(args.apply),
        confirm=str(args.confirm),
        confirm_path=str(args.confirm_path),
    )
    raise SystemExit(0 if success else 1)
