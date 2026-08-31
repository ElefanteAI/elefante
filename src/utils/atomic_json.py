"""Small private-file JSON replacement primitive for local product state."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any, Callable


@dataclass(frozen=True)
class PrivateFileState:
    """Exact recoverable state for one private local product file."""

    existed: bool
    payload: bytes | None
    mode: int | None


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("JSON contains duplicate keys")
        result[key] = value
    return result


def read_json_strict(path: Path) -> Any:
    """Read UTF-8 JSON while rejecting duplicate object keys at every depth."""
    return json.loads(
        Path(path).expanduser().read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def capture_private_file(path: Path) -> PrivateFileState:
    """Capture exact bytes and permission bits without following a missing file."""
    target = Path(path).expanduser()
    if not target.is_file():
        return PrivateFileState(existed=False, payload=None, mode=None)
    return PrivateFileState(
        existed=True,
        payload=target.read_bytes(),
        mode=target.stat().st_mode & 0o777,
    )


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def restore_private_file(path: Path, state: PrivateFileState) -> Path:
    """Atomically restore exact captured state, including prior absence."""
    target = Path(path).expanduser()
    if not state.existed:
        if target.exists():
            target.unlink()
            _fsync_directory(target.parent)
        return target
    if state.payload is None or state.mode is None:
        raise ValueError("Existing private file state is incomplete")

    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.restore.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as output:
            output.write(state.payload)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, state.mode)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def write_json_atomically(
    path: Path,
    payload: Any,
    *,
    default: Callable[[Any], Any] | None = None,
) -> Path:
    """Write complete JSON beside ``path`` and atomically replace it mode 0600."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(
                payload,
                output,
                ensure_ascii=True,
                sort_keys=True,
                indent=2,
                default=default,
            )
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


__all__ = [
    "PrivateFileState",
    "capture_private_file",
    "read_json_strict",
    "restore_private_file",
    "write_json_atomically",
]
