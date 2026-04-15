#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : reset_kuzu_nuclear.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Backup-and-remove the Kuzu graph database path only (file or dir)
#           so the next init starts fresh without a full factory reset.
# WHEN    : When Kuzu is corrupted and cannot be opened (e.g. schema mismatch
#           after a model change, or Kuzu lock file corruption). Use ONLY when
#           you need the graph store reset but want to preserve ChromaDB data.
#           For a full wipe, use reset_factory.py instead.
# USAGE   : ELEFANTE_PRIVILEGED=1 python scripts/debug/reset_kuzu_nuclear.py --apply --confirm DELETE
# NOTES   : Always backup first (backup_elefante_data.py). This permanently
#           removes all Kuzu relationship data — ChromaDB memories are untouched.
#           Kuzu will be re-initialized on next server start.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Nuclear reset for the Kuzu database path.

Backs up and removes the current `kuzu_db` path, whether it is a file or a
directory, so the next initialization starts fresh.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime
import argparse
import os

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def nuclear_reset_kuzu(*, apply: bool, confirm: str):
    """Backup and remove the current Kuzu database path."""
    
    # Paths
    data_dir = Path.home() / ".elefante" / "data"
    kuzu_path = data_dir / "kuzu_db"
    
    print("=" * 70)
    print("KUZU DATABASE NUCLEAR RESET")
    print("=" * 70)
    print()
    
    # Check if kuzu_db exists
    if not kuzu_path.exists():
        print(f"[OK] No kuzu_db found at: {kuzu_path}")
        print("  Database is ready for fresh initialization.")
        return True
    
    if kuzu_path.is_file():
        print("[INFO] kuzu_db is a file under the current runtime contract")
        print(f"  Path: {kuzu_path}")
        print(f"  Size: {kuzu_path.stat().st_size:,} bytes")
        print()
    elif kuzu_path.is_dir():
        print("[INFO] kuzu_db is a directory (legacy or alternate layout)")
        print(f"  Path: {kuzu_path}")
        print()
    else:
        print("[FAIL] UNKNOWN: kuzu_db exists but is neither file nor directory")
        print(f"  Path: {kuzu_path}")
        print("  Manual investigation required.")
        return False

    if not apply:
        print("Dry-run only. Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        return True

    if not _truthy_env("ELEFANTE_PRIVILEGED"):
        print("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        return False

    if (confirm or "").strip() != "DELETE":
        print("Refusing to apply: pass --confirm DELETE")
        return False

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = data_dir / f"kuzu_db.reset_backup.{timestamp}"

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
    print("3. Rebuild graph from ChromaDB memories if needed")
    return True

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Backup and remove corrupted Kuzu DB file (dry-run by default)")
    p.add_argument("--apply", action="store_true", help="Apply removal (otherwise dry-run)")
    p.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    args = p.parse_args()

    success = nuclear_reset_kuzu(apply=bool(args.apply), confirm=str(args.confirm))
    exit(0 if success else 1)

