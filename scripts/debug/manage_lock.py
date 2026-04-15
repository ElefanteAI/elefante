#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : manage_lock.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Inspect and remove the Elefante write lock; optional MCP process kill.
#           Merged from remove_lock_kuzu.py + unlock_database_transactions.py.
# WHEN    : When write operations hang, MemoryAdd times out, or the server reports
#           "lock held" on restart. Always dry-run first (no flags) to confirm the
#           lock exists before applying. Use --kill if the MCP server is unresponsive.
# USAGE   : python scripts/debug/manage_lock.py [--apply --confirm DELETE [--kill]]
# NOTES   : Requires ELEFANTE_PRIVILEGED=1 env var to apply. Deleting the lock
#           while a write is genuinely in progress can corrupt state — stop or
#           kill the server first. Default (no flags) is always dry-run / inspect.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Manage Elefante's transaction write lock (safe-by-default).

Default is dry-run (inspect only). To actually remove the lock file you must set:
  - env : ELEFANTE_PRIVILEGED=1
  - flag: --apply
  - flag: --confirm DELETE

Add --kill to also attempt stopping src.mcp.server processes before removing the
lock — useful when the server is hanging and holds the lock open.

Deleting the write lock while another process is genuinely writing can corrupt
state; prefer stopping the MCP process (or using --kill) first.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_lock_path() -> Path:
    """Resolve lock path from config if possible; fall back to well-known default."""
    # Try config-aware resolution first.
    try:
        sys.path.insert(0, str(_repo_root()))
        from src.utils.elefante_mode import WRITE_LOCK_FILE  # type: ignore

        return Path(WRITE_LOCK_FILE)
    except Exception:
        pass
    # Try config for database path (supplemental awareness).
    try:
        from src.utils.config import get_config  # type: ignore

        cfg = get_config()
        _ = cfg.elefante.graph_store.database_path  # ensure config parses
    except Exception:
        pass
    return Path.home() / ".elefante" / "locks" / "write.lock"


def manage_lock(*, apply: bool, confirm: str, kill: bool) -> bool:
    """Inspect and optionally remove the Elefante write lock."""
    print("ELEFANTE WRITE LOCK MANAGER")
    print("---------------------------")

    lock_path = _default_lock_path()
    print(f"Lock path: {lock_path}")

    if not lock_path.exists():
        print("No write lock file found.")
        return True

    try:
        stat = lock_path.stat()
        print(f"Lock file found: size_bytes={stat.st_size}  mtime={stat.st_mtime}")
    except Exception:
        print("Lock file found (could not stat).")

    if not apply:
        print("Dry-run only.")
        print("Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        print("Optional: add --kill to stop src.mcp.server processes first.")
        return True

    if not _truthy_env("ELEFANTE_PRIVILEGED"):
        print("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        return False
    if (confirm or "").strip() != "DELETE":
        print("Refusing to apply: pass --confirm DELETE")
        return False

    if kill:
        print("Attempting to stop Elefante MCP server processes (best-effort)...")
        try:
            subprocess.run(["pkill", "-f", "src.mcp.server"], check=False)
            print("Kill signal sent to src.mcp.server processes (if any).")
        except FileNotFoundError:
            print("pkill not found; skipping process kill.")
        except Exception as e:
            print(f"Error killing processes: {e}")
        time.sleep(1)

    try:
        lock_path.unlink()
        print(f"Write lock removed: {lock_path}")
        return True
    except Exception as e:
        print(f"Failed to remove lock: {e}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(
        description="Manage Elefante write lock file (dry-run by default)"
    )
    p.add_argument("--apply", action="store_true", help="Actually remove lock file")
    p.add_argument(
        "--confirm",
        type=str,
        default="",
        help="Must be exactly 'DELETE' to apply",
    )
    p.add_argument(
        "--kill",
        action="store_true",
        help="Attempt to stop src.mcp.server processes before removing lock",
    )
    args = p.parse_args()
    ok = manage_lock(apply=bool(args.apply), confirm=str(args.confirm), kill=bool(args.kill))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
