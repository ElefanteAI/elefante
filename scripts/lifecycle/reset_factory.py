import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path

def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _backup_dir() -> Path:
    return (Path.home() / ".elefante" / "data" / "backups" / "factory_reset").resolve()


def _move_to_backup(path: Path, backup_root: Path) -> Path:
    backup_root.mkdir(parents=True, exist_ok=True)
    dest = backup_root / f"{path.name}.{_utc_ts()}"
    # Avoid collisions if run multiple times in the same second.
    i = 0
    while dest.exists():
        i += 1
        dest = backup_root / f"{path.name}.{_utc_ts()}.{i}"
    shutil.move(str(path), str(dest))
    return dest


def _targets() -> tuple[Path, Path]:
    data_dir = (Path.home() / ".elefante" / "data").resolve()
    chroma_dir = data_dir / "chroma"
    kuzu_dir = data_dir / "kuzu_db"
    return chroma_dir, kuzu_dir


def factory_reset(*, apply: bool, confirm: str) -> bool:
    chroma_dir, kuzu_dir = _targets()
    backup_root = _backup_dir()

    print("WARNING: This will remove ALL Elefante local databases.")
    print("Default is dry-run (no writes).")
    print(f"Targeting:\n - {chroma_dir}\n - {kuzu_dir}")

    if not apply:
        print("\n[DRY-RUN] No changes applied.")
        print("Re-run with: ELEFANTE_PRIVILEGED=1 --apply --confirm DELETE")
        return True

    if not _truthy_env("ELEFANTE_PRIVILEGED"):
        print("Refusing to apply: set ELEFANTE_PRIVILEGED=1")
        return False

    if (confirm or "").strip() != "DELETE":
        print("Refusing to apply: pass --confirm DELETE")
        return False

    moved_any = False

    if chroma_dir.exists():
        print("Moving ChromaDB to backup...")
        try:
            dest = _move_to_backup(chroma_dir, backup_root)
            print(f"ChromaDB moved to: {dest}")
            moved_any = True
        except Exception as e:
            print(f"Failed to move ChromaDB: {e}")
            return False
    else:
        print("ChromaDB not found (already clean).")

    if kuzu_dir.exists():
        print("Moving KuzuDB to backup...")
        try:
            dest = _move_to_backup(kuzu_dir, backup_root)
            print(f"KuzuDB moved to: {dest}")
            moved_any = True
        except Exception as e:
            print(f"Failed to move KuzuDB: {e}")
            return False
    else:
        print("KuzuDB not found (already clean).")

    if moved_any:
        print("\nFactory reset complete. Next init will recreate databases.")
        print(f"Backups are under: {backup_root}")
    else:
        print("\nNothing to do. Databases already absent.")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Factory reset Elefante local databases (dry-run by default)")
    parser.add_argument("--apply", action="store_true", help="Apply reset (otherwise dry-run)")
    parser.add_argument("--confirm", type=str, default="", help="Must be exactly 'DELETE' to apply")
    args = parser.parse_args()

    ok = factory_reset(apply=bool(args.apply), confirm=str(args.confirm))
    raise SystemExit(0 if ok else 1)
