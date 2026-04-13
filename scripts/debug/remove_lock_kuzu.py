"""Remove Kuzu database lock file (safe-by-default).

Default is dry-run. To actually delete the lock file you must provide:
- environment: ELEFANTE_PRIVILEGED=1
- flag: --apply
- flag: --confirm DELETE

This is a debug tool. Deleting a lock file while Kuzu is genuinely in use can
corrupt the database; prefer stopping the MCP/dashboard process first.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _default_lock_path() -> Path:
    # Best-effort: use config if importable, otherwise default location.
    try:
        repo_root = Path(__file__).resolve().parents[2]
        sys.path.insert(0, str(repo_root))
        from src.utils.config import get_config  # type: ignore

        cfg = get_config()
        return Path(cfg.elefante.graph_store.database_path) / ".lock"
    except Exception:
        return Path.home() / ".elefante" / "data" / "kuzu_db" / ".lock"


def remove_lock(*, apply: bool, confirm: str) -> bool:
    """Remove stale Kuzu lock file."""
    lock_path = _default_lock_path()

    print(f"Lock file path: {lock_path}")

    if not lock_path.exists():
        print("No lock file found.")
        return True

    try:
        stat = lock_path.stat()
        print("Lock file exists.")
        print(f"size_bytes={stat.st_size}")
        print(f"mtime={stat.st_mtime}")
    except Exception:
        print("Lock file exists (could not stat).")

    if not apply:
        print("Dry-run only. Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        return True

    if not _truthy_env("ELEFANTE_PRIVILEGED"):
        print("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        return False
    if (confirm or "").strip() != "DELETE":
        print("Refusing to apply: pass --confirm DELETE")
        return False

    try:
        lock_path.unlink()
        print("Lock file removed.")
        return True
    except Exception as e:
        print(f"Failed to remove lock: {e}")
        return False


def main() -> int:
    p = argparse.ArgumentParser(description="Remove Kuzu lock file (dry-run by default)")
    p.add_argument("--apply", action="store_true", help="Actually delete lock file")
    p.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    args = p.parse_args()

    ok = remove_lock(apply=bool(args.apply), confirm=str(args.confirm))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
