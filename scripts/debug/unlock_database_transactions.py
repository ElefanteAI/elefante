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
    # scripts/debug/unlock_database.py -> scripts -> repo root
    return Path(__file__).resolve().parents[2]


def _default_db_paths() -> list[Path]:
    paths: list[Path] = []

    # Prefer configured database path.
    try:
        sys.path.insert(0, str(_repo_root()))
        from src.utils.config import get_config  # type: ignore

        cfg = get_config()
        paths.append(Path(cfg.elefante.graph_store.database_path))
    except Exception:
        pass

    # Common defaults.
    paths.append(Path.home() / ".elefante" / "data" / "kuzu_db")
    paths.append(Path("kuzu_db").resolve())

    # De-dupe while preserving order.
    seen: set[str] = set()
    uniq: list[Path] = []
    for p in paths:
        key = str(p)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq


def unlock_database(*, apply: bool, confirm: str, kill: bool) -> bool:
    """Attempt to unlock the Kuzu database (safe-by-default).

    Default is dry-run. To actually kill processes / delete lock files you must provide:
    - environment: ELEFANTE_PRIVILEGED=1
    - flag: --apply
    - flag: --confirm DELETE
    """
    print("KUZU DATABASE UNLOCKER")
    print("----------------------")

    db_paths = _default_db_paths()
    lock_files = [p / ".lock" for p in db_paths]

    print("DB paths checked:")
    for p in db_paths:
        print(f"- {p}")

    found = [lf for lf in lock_files if lf.exists()]
    if not found:
        print("No lock file found in known locations.")
        return True

    print("Lock files found:")
    for lf in found:
        print(f"- {lf}")

    if not apply:
        print("Dry-run only.")
        print("Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        print("Optional: add --kill to attempt stopping src.mcp.server processes.")
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

        # Wait briefly for OS to release handles.
        time.sleep(1)

    lock_removed = False
    for lf in found:
        try:
            lf.unlink()
            print(f"Removed: {lf}")
            lock_removed = True
        except Exception as e:
            print(f"Failed to remove {lf}: {e}")

    if lock_removed:
        print("Database lock file(s) removed.")
        return True

    print("No lock files could be removed.")
    return False


def main() -> int:
    p = argparse.ArgumentParser(description="Unlock Kuzu database (dry-run by default)")
    p.add_argument("--apply", action="store_true", help="Actually remove lock file(s)")
    p.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    p.add_argument("--kill", action="store_true", help="Also attempt to stop src.mcp.server processes")
    args = p.parse_args()

    ok = unlock_database(apply=bool(args.apply), confirm=str(args.confirm), kill=bool(args.kill))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
