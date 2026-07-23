# ─────────────────────────────────────────────────────────────────────────────
# NAME    : reset_factory.py
# VERSION : 2.5.2
# CHANGED : 2026-07-23
# PURPOSE : Destructive full reset of all Elefante durable state with backup
#           gates; for unrecoverable corruption or an explicit wipe.
# WHEN    : Last resort only — when the configured vector store AND Kuzu are unrecoverable, or
#           when an operator explicitly wants a clean-slate install. NOT for
#           Kuzu-only issues (use reset_kuzu_nuclear.py) or lock issues (manage_lock.py).
# USAGE   : ELEFANTE_PRIVILEGED=1 python scripts/lifecycle/reset_factory.py --apply --confirm DELETE
# NOTES   : Backup is created automatically before deletion, but backup_elefante_data.py
#           beforehand is still recommended. Stop all Elefante processes first.
#           This moves configured and default local durable data into recovery.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
import argparse
import os
import shutil
from datetime import datetime
from pathlib import Path

import yaml


def _utc_ts() -> str:
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _configured_storage() -> tuple[Path, Path, Path]:
    """Read durable paths without loading database clients or creating state.

    This intentionally mirrors the storage-path portion of ``Config.load`` so
    a privileged reset moves the store the running Elefante instance actually
    uses, including a custom configuration path. Invalid configuration fails
    closed: a reset must not guess at destructive targets.
    """
    config_path = Path(os.getenv("ELEFANTE_CONFIG_PATH", "config.yaml")).expanduser()
    payload: dict = {}
    if config_path.exists():
        try:
            loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as error:
            raise RuntimeError(f"Cannot safely read Elefante configuration: {error}") from error
        if not isinstance(loaded, dict):
            raise RuntimeError("Cannot safely read Elefante configuration: root must be a mapping")
        payload = loaded.get("elefante", loaded)
        if not isinstance(payload, dict):
            raise RuntimeError("Cannot safely read Elefante configuration: elefante must be a mapping")

    raw_data_dir = os.getenv("ELEFANTE_DATA_DIR", "").strip() or payload.get("data_dir")
    data_dir = Path(raw_data_dir).expanduser() if raw_data_dir else Path.home() / ".elefante" / "data"
    data_dir = data_dir.resolve()
    vector_config = payload.get("vector_store") or {}
    graph_config = payload.get("graph_store") or {}
    if not isinstance(vector_config, dict) or not isinstance(graph_config, dict):
        raise RuntimeError("Cannot safely read Elefante configuration: storage sections must be mappings")
    vector_type = os.getenv("ELEFANTE_VECTOR_STORE_TYPE", "").strip() or vector_config.get("type", "chromadb")
    vector_default = "vector" if vector_type == "sqlite" else "chroma"
    vector_path = Path(vector_config.get("persist_directory") or data_dir / vector_default).expanduser().resolve()
    graph_path = Path(graph_config.get("database_path") or data_dir / "kuzu_db").expanduser().resolve()
    return data_dir, vector_path, graph_path


def _backup_dir() -> Path:
    data_dir, _vector_path, _graph_path = _configured_storage()
    return data_dir / "backups" / "factory_reset"


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


def _targets() -> tuple[tuple[str, Path], ...]:
    """Return configured durable paths plus in-root legacy default locations."""
    data_dir, vector_path, graph_path = _configured_storage()
    candidates = (
        ("Configured vector store", vector_path),
        ("Configured KuzuDB", graph_path),
        ("Default ChromaDB", data_dir / "chroma"),
        ("Default SQLite vector store", data_dir / "vector"),
        ("Default KuzuDB", data_dir / "kuzu_db"),
    )
    unique: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    for label, path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append((label, resolved))
    return tuple(unique)


def _contains(parent: Path, child: Path) -> bool:
    return parent == child or parent in child.parents


def factory_reset(*, apply: bool, confirm: str) -> bool:
    try:
        backup_root = _backup_dir()
        targets = _targets()
    except RuntimeError as error:
        print(f"Refusing to reset: {error}")
        return False

    print("WARNING: This will remove ALL Elefante local databases.")
    print("Default is dry-run (no writes).")
    print("Targeting:\n" + "\n".join(f" - {path}" for _, path in targets))

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

    unsafe_targets = [path for _label, path in targets if _contains(path, backup_root)]
    if unsafe_targets:
        print("Refusing to reset: a configured durable path contains the recovery directory")
        return False

    moved_any = False

    for label, path in targets:
        if path.exists():
            print(f"Moving {label} to backup...")
            try:
                dest = _move_to_backup(path, backup_root)
                print(f"{label} moved to: {dest}")
                moved_any = True
            except Exception as e:
                print(f"Failed to move {label}: {e}")
                return False
        else:
            print(f"{label} not found (already clean).")

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
