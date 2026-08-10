"""Record exact user-owned files emitted by Elefante installation flows."""

from __future__ import annotations

import os
import hashlib
import json
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile


MANIFEST_NAME = "install-manifest.json"
MANIFEST_SCHEMA_VERSION = 2


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest_path(home: Path | None = None) -> Path:
    return (home or Path.home()) / ".elefante" / MANIFEST_NAME


def configuration_hash(configuration_output: str) -> str:
    """Hash an inspectable host config, canonicalizing JSON when available."""
    try:
        structured = json.loads(configuration_output)
    except json.JSONDecodeError:
        payload = configuration_output
    else:
        payload = json.dumps(structured, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def json_value_hash(value: object) -> str:
    """Hash one JSON value independently from unrelated settings in its file."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def text_value_hash(value: str) -> str:
    """Hash one managed text value independently from its surrounding file."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text_block(document: str, start_marker: str, end_marker: str) -> str | None:
    """Return one complete marked block, rejecting missing or ambiguous markers."""
    if document.count(start_marker) != 1 or document.count(end_marker) != 1:
        return None
    start = document.index(start_marker)
    end = document.index(end_marker, start) + len(end_marker)
    return document[start:end]


def is_elefante_runtime_entry(value: object) -> bool:
    """Identify an existing Elefante stdio registration without trusting its path.

    Customer upgrades may adopt an older Elefante registration that predates
    installer ownership metadata.  The MCP module is the stable product
    fingerprint; a shared server name or a path containing ``elefante`` is not.
    """
    if not isinstance(value, dict):
        return False
    transport = value.get("transport", value)
    if not isinstance(transport, dict):
        return False
    args = transport.get("args")
    if not isinstance(args, list) or not all(isinstance(part, str) for part in args):
        return False
    return any(module in {"src.mcp.server", "src.mcp.stdio_bridge"} for module in args)


def _json_entry(document: object, entry_path: list[str]) -> object | None:
    current = document
    for part in entry_path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _load_manifest(target: Path) -> dict:
    try:
        data = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    except json.JSONDecodeError as error:
        raise RuntimeError(f"Refusing to overwrite invalid install manifest: {target}") from error
    if not isinstance(data, dict):
        raise RuntimeError(f"Refusing to overwrite invalid install manifest: {target}")
    files = data.setdefault("files", {})
    if not isinstance(files, dict):
        raise RuntimeError(f"Refusing to overwrite invalid install manifest: {target}")
    data["schema_version"] = MANIFEST_SCHEMA_VERSION
    return data


def _write_manifest(target: Path, data: dict) -> None:
    with NamedTemporaryFile("w", encoding="utf-8", dir=target.parent, delete=False) as stream:
        json.dump(data, stream, indent=2, sort_keys=True)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, target)


def record_emitted_file(path: Path, surface: str, home: Path | None = None) -> Path:
    """Atomically record a whole file that Elefante owns and may later remove."""
    target = manifest_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_manifest(target)
    data["files"][str(path.resolve())] = {
        "kind": "file",
        "surface": surface,
        "sha256": file_hash(path),
    }
    _write_manifest(target, data)
    return target


def record_runtime_installation(
    *,
    app_root: Path,
    data_root: Path,
    version: str,
    scope: str,
    home: Path | None = None,
) -> Path:
    """Record the runtime identity that customer readiness must verify."""
    if scope not in {"customer", "developer"}:
        raise ValueError("runtime installation scope must be customer or developer")
    target = manifest_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_manifest(target)
    data["runtime"] = {
        "app_root": str(Path(app_root).expanduser().resolve()),
        "data_root": str(Path(data_root).expanduser().resolve()),
        "scope": scope,
        "version": version,
    }
    _write_manifest(target, data)
    return target


def read_runtime_installation(home: Path | None = None) -> dict[str, str] | None:
    """Read a valid runtime identity without adopting malformed state."""
    target = manifest_path(home)
    if not target.exists():
        return None
    try:
        runtime = _load_manifest(target).get("runtime")
    except (OSError, RuntimeError):
        return None
    required = {"app_root", "data_root", "scope", "version"}
    if not isinstance(runtime, dict) or not required <= runtime.keys():
        return None
    if not all(isinstance(runtime[key], str) and runtime[key] for key in required):
        return None
    if runtime["scope"] not in {"customer", "developer"}:
        return None
    return {key: runtime[key] for key in required}


def configured_surfaces(
    home: Path | None = None,
    *,
    runner=subprocess.run,
) -> set[str]:
    """Return only installer-owned surfaces whose current state still verifies."""
    target = manifest_path(home)
    if not target.exists():
        return set()
    try:
        data = _load_manifest(target)
    except (OSError, RuntimeError):
        return set()
    verified: set[str] = set()
    for raw_path, details in data.get("files", {}).items():
        if not isinstance(details, dict) or not isinstance(details.get("surface"), str):
            continue
        path = Path(raw_path)
        expected = details.get("sha256")
        try:
            if details.get("kind") == "json-entry":
                entry_path = details.get("entry_path")
                entry_hash = details.get("entry_sha256")
                document = json.loads(path.read_text(encoding="utf-8"))
                current_entry = _json_entry(document, entry_path) if isinstance(entry_path, list) else None
                matches = isinstance(entry_hash, str) and json_value_hash(current_entry) == entry_hash
            elif details.get("kind") == "text-block":
                start_marker = details.get("start_marker")
                end_marker = details.get("end_marker")
                block_hash = details.get("block_sha256")
                document = path.read_text(encoding="utf-8")
                current_block = (
                    _text_block(document, start_marker, end_marker)
                    if isinstance(start_marker, str) and isinstance(end_marker, str)
                    else None
                )
                matches = (
                    current_block is not None
                    and isinstance(block_hash, str)
                    and text_value_hash(current_block) == block_hash
                )
            else:
                matches = path.exists() and isinstance(expected, str) and file_hash(path) == expected
        except (OSError, json.JSONDecodeError):
            matches = False
        if matches:
            verified.add(details["surface"])
    for details in data.get("commands", {}).values():
        if not isinstance(details, dict) or not isinstance(details.get("surface"), str):
            continue
        command = details.get("get")
        expected = details.get("sha256")
        if not (
            isinstance(command, list)
            and all(isinstance(part, str) for part in command)
            and isinstance(expected, str)
        ):
            continue
        try:
            current = runner(command, capture_output=True, text=True, check=False)
        except OSError:
            continue
        if current.returncode == 0 and configuration_hash(current.stdout) == expected:
            verified.add(details["surface"])
    # Codex is customer-ready only when both its MCP registration and its
    # installer-managed global Recall routing rule still verify.
    codex_routing = "codex-recall-routing"
    if "codex" in verified and codex_routing not in verified:
        verified.remove("codex")
    verified.discard(codex_routing)
    return verified


def record_emitted_json_entry(
    path: Path,
    surface: str,
    entry_path: tuple[str, ...],
    *,
    created: bool,
    home: Path | None = None,
) -> Path:
    """Record an Elefante-owned JSON entry without claiming the whole file.

    IDE settings files commonly contain servers owned by other tools.  Their
    Elefante entry can be removed only when the exact installer-emitted file is
    still present; the rest of the file must survive uninstall.
    """
    if not entry_path:
        raise ValueError("entry_path must identify a JSON entry")
    target = manifest_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_manifest(target)
    document = json.loads(path.read_text(encoding="utf-8"))
    entry_value = _json_entry(document, list(entry_path))
    if entry_value is None:
        raise RuntimeError(f"Cannot record missing JSON entry {'.'.join(entry_path)} in {path}")
    data["files"][str(path.resolve())] = {
        "created": created,
        "entry_path": list(entry_path),
        "entry_sha256": json_value_hash(entry_value),
        "kind": "json-entry",
        "surface": surface,
        "sha256": file_hash(path),
    }
    _write_manifest(target, data)
    return target


def record_emitted_text_block(
    path: Path,
    surface: str,
    start_marker: str,
    end_marker: str,
    *,
    created: bool,
    leading_separator: str,
    trailing_separator: str,
    home: Path | None = None,
) -> Path:
    """Record one marked block inside a shared user-owned text file."""
    target = manifest_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_manifest(target)
    document = path.read_text(encoding="utf-8")
    block = _text_block(document, start_marker, end_marker)
    if block is None:
        raise RuntimeError(f"Cannot record missing or ambiguous text block in {path}")
    data["files"][str(path.resolve())] = {
        "block_sha256": text_value_hash(block),
        "created": created,
        "end_marker": end_marker,
        "kind": "text-block",
        "leading_separator": leading_separator,
        "sha256": file_hash(path),
        "start_marker": start_marker,
        "surface": surface,
        "trailing_separator": trailing_separator,
    }
    _write_manifest(target, data)
    return target


def is_unchanged_emitted_json_entry(
    path: Path,
    surface: str,
    entry_path: tuple[str, ...],
    home: Path | None = None,
) -> bool:
    """Return true only for an unchanged JSON entry emitted by this surface.

    A shared host config can contain a user-managed ``elefante`` entry.  A
    later installer run may refresh only the exact entry and file state it
    previously wrote; it must not adopt or replace a user registration.
    """
    target = manifest_path(home)
    if not target.exists() or not path.exists():
        return False
    try:
        data = _load_manifest(target)
        details = data["files"].get(str(path.resolve()))
        actual_hash = file_hash(path)
    except (OSError, RuntimeError):
        return False
    return (
        isinstance(details, dict)
        and details.get("kind") == "json-entry"
        and details.get("surface") == surface
        and details.get("entry_path") == list(entry_path)
        and details.get("sha256") == actual_hash
    )


def is_unchanged_emitted_text_block(
    path: Path,
    surface: str,
    start_marker: str,
    end_marker: str,
    home: Path | None = None,
) -> bool:
    """Return true only when the exact installer-owned marked block remains."""
    if not emitted_text_block_recorded(
        path, surface, start_marker, end_marker, home=home
    ):
        return False
    target = manifest_path(home)
    try:
        data = _load_manifest(target)
        details = data["files"].get(str(path.resolve()))
        block = _text_block(path.read_text(encoding="utf-8"), start_marker, end_marker)
    except (OSError, RuntimeError):
        return False
    return (
        isinstance(details, dict)
        and details.get("kind") == "text-block"
        and details.get("surface") == surface
        and details.get("start_marker") == start_marker
        and details.get("end_marker") == end_marker
        and isinstance(block, str)
        and details.get("block_sha256") == text_value_hash(block)
    )


def emitted_text_block_recorded(
    path: Path,
    surface: str,
    start_marker: str,
    end_marker: str,
    home: Path | None = None,
) -> bool:
    """Report whether the manifest owns this precise marked block location."""
    target = manifest_path(home)
    if not target.exists():
        return False
    try:
        details = _load_manifest(target)["files"].get(str(path.resolve()))
    except (OSError, RuntimeError):
        return False
    return (
        isinstance(details, dict)
        and details.get("kind") == "text-block"
        and details.get("surface") == surface
        and details.get("start_marker") == start_marker
        and details.get("end_marker") == end_marker
    )


def write_json_atomically(path: Path, document: dict, *, indent: int = 2) -> None:
    """Replace a JSON configuration only after its complete serialization succeeds."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else None
    temporary: Path | None = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            json.dump(document, stream, indent=indent)
            stream.write("\n")
            temporary = Path(stream.name)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def write_text_atomically(path: Path, document: str) -> None:
    """Replace a text file atomically while preserving its existing mode."""
    mode = path.stat().st_mode & 0o7777 if path.exists() else None
    temporary: Path | None = None
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            stream.write(document)
            temporary = Path(stream.name)
        if mode is not None:
            os.chmod(temporary, mode)
        os.replace(temporary, path)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise


def record_host_command(
    key: str,
    surface: str,
    get_command: list[str],
    add_command: list[str],
    remove_command: list[str],
    configuration_output: str,
    home: Path | None = None,
) -> Path:
    """Track a host-owned registration by its exact readable configuration.

    Some clients manage their own configuration format through a CLI.  We do
    not claim that file as ours; uninstall is authorized only if the host's
    current ``get`` output still hashes to the configuration we registered.
    """
    target = manifest_path(home)
    target.parent.mkdir(parents=True, exist_ok=True)
    data = _load_manifest(target)
    commands = data.setdefault("commands", {})
    if not isinstance(commands, dict):
        raise RuntimeError(f"Refusing to overwrite invalid install manifest: {target}")
    commands[key] = {
        "add": add_command,
        "get": get_command,
        "remove": remove_command,
        "sha256": configuration_hash(configuration_output),
        "surface": surface,
    }
    _write_manifest(target, data)
    return target


def matching_host_add_command(
    key: str, configuration_output: str, home: Path | None = None
) -> list[str] | None:
    """Return the prior installer command only for an unchanged owned registration.

    This lets an upgrade replace its own host registration and restore the old
    command if the replacement fails. Entries from manifests written before
    add commands were recorded deliberately remain user-preserved.
    """
    target = manifest_path(home)
    if not target.exists():
        return None
    data = _load_manifest(target)
    commands = data.get("commands", {})
    if not isinstance(commands, dict):
        return None
    details = commands.get(key)
    if not isinstance(details, dict):
        return None
    add_command = details.get("add")
    expected = details.get("sha256")
    if not (
        isinstance(add_command, list)
        and all(isinstance(part, str) for part in add_command)
        and isinstance(expected, str)
    ):
        return None
    actual = configuration_hash(configuration_output)
    return add_command if actual == expected else None


def forget_emitted_file(path: Path, home: Path | None = None) -> None:
    """Remove one manifest record after its owned artifact was removed safely."""
    target = manifest_path(home)
    if not target.exists():
        return
    data = _load_manifest(target)
    data["files"].pop(str(path.resolve()), None)
    if data["files"] or data.get("commands") or data.get("runtime"):
        _write_manifest(target, data)
    else:
        target.unlink(missing_ok=True)


def clear_runtime_installation(home: Path | None = None) -> None:
    """Forget runtime identity after a complete manifest-owned uninstall."""
    target = manifest_path(home)
    if not target.exists():
        return
    data = _load_manifest(target)
    data.pop("runtime", None)
    if data["files"] or data.get("commands"):
        _write_manifest(target, data)
    else:
        target.unlink(missing_ok=True)


def remove_unchanged_host_commands(
    home: Path | None = None,
    apply: bool = False,
    *,
    runner=subprocess.run,
) -> tuple[list[str], list[str]]:
    """Remove only host registrations whose current config still matches ours."""
    target = manifest_path(home)
    if not target.exists():
        return [], []
    data = _load_manifest(target)
    commands = data.get("commands", {})
    if not isinstance(commands, dict):
        raise RuntimeError(f"Invalid install manifest: {target}")
    removed, preserved = [], []
    for key, details in list(commands.items()):
        if not isinstance(details, dict):
            preserved.append(key)
            continue
        get_command = details.get("get")
        remove_command = details.get("remove")
        expected = details.get("sha256")
        if not (
            isinstance(get_command, list)
            and all(isinstance(part, str) for part in get_command)
            and isinstance(remove_command, list)
            and all(isinstance(part, str) for part in remove_command)
            and isinstance(expected, str)
        ):
            preserved.append(key)
            continue
        try:
            current = runner(get_command, capture_output=True, text=True, check=False)
        except OSError:
            preserved.append(key)
            continue
        current_hash = configuration_hash(current.stdout)
        if current.returncode != 0 or current_hash != expected:
            preserved.append(key)
            continue
        if apply:
            try:
                result = runner(remove_command, capture_output=True, text=True, check=False)
            except OSError:
                preserved.append(key)
                continue
            if result.returncode != 0:
                preserved.append(key)
                continue
            commands.pop(key, None)
        removed.append(key)
    if apply:
        if not data["files"] and not commands and not data.get("runtime"):
            target.unlink(missing_ok=True)
        else:
            _write_manifest(target, data)
    return removed, preserved


def _remove_json_entry(path: Path, details: dict, apply: bool) -> bool:
    entry_path = details.get("entry_path")
    if not isinstance(entry_path, list) or not entry_path or not all(isinstance(part, str) for part in entry_path):
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(document, dict):
        return False

    parent = document
    for part in entry_path[:-1]:
        child = parent.get(part)
        if not isinstance(child, dict):
            return False
        parent = child
    if entry_path[-1] not in parent:
        return False
    del parent[entry_path[-1]]

    # Remove now-empty containers, but never delete a pre-existing user file.
    for index in range(len(entry_path) - 1, 0, -1):
        container = document
        for part in entry_path[:index - 1]:
            container = container[part]
        key = entry_path[index - 1]
        if isinstance(container.get(key), dict) and not container[key]:
            del container[key]
        else:
            break

    if not apply:
        return True
    if details.get("created") and not document:
        path.unlink()
        return True
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        json.dump(document, stream, indent=2)
        stream.write("\n")
        temporary = Path(stream.name)
    os.replace(temporary, path)
    return True


def _remove_text_block(path: Path, details: dict, apply: bool) -> bool:
    start_marker = details.get("start_marker")
    end_marker = details.get("end_marker")
    expected = details.get("block_sha256")
    leading = details.get("leading_separator")
    trailing = details.get("trailing_separator")
    if not all(isinstance(value, str) for value in (start_marker, end_marker, expected, leading, trailing)):
        return False
    try:
        document = path.read_text(encoding="utf-8")
    except OSError:
        return False
    block = _text_block(document, start_marker, end_marker)
    if block is None or text_value_hash(block) != expected:
        return False
    start = document.index(start_marker)
    end = start + len(block)
    if document[max(0, start - len(leading)):start] != leading:
        return False
    if document[end:end + len(trailing)] != trailing:
        return False
    updated = document[:start - len(leading)] + document[end + len(trailing):]
    if not apply:
        return True
    if details.get("created") and not updated:
        path.unlink()
    else:
        write_text_atomically(path, updated)
    return True


def remove_unchanged_files(home: Path | None = None, apply: bool = False) -> tuple[list[Path], list[Path]]:
    """Remove only installer-owned files or entries that remain unchanged."""
    target = manifest_path(home)
    if not target.exists():
        return [], []
    data = _load_manifest(target)
    files = data["files"]
    removed, preserved = [], []
    for raw_path, details in list(files.items()):
        path = Path(raw_path)
        if not path.exists() or not isinstance(details, dict):
            preserved.append(path)
            continue
        kind = details.get("kind", "file")
        if kind == "json-entry":
            expected = details.get("sha256")
            if not isinstance(expected, str) or file_hash(path) != expected:
                preserved.append(path)
                continue
            if not _remove_json_entry(path, details, apply):
                preserved.append(path)
                continue
        elif kind == "text-block":
            if not _remove_text_block(path, details, apply):
                preserved.append(path)
                continue
        elif kind == "file":
            expected = details.get("sha256")
            if not isinstance(expected, str) or file_hash(path) != expected:
                preserved.append(path)
                continue
            if apply:
                path.unlink()
        else:
            preserved.append(path)
            continue
        removed.append(path)
        if apply:
            files.pop(raw_path, None)
    if apply and not preserved and not data.get("commands") and not data.get("runtime"):
        target.unlink(missing_ok=True)
    elif apply:
        _write_manifest(target, data)
    return removed, preserved


def is_unchanged_emitted_file(path: Path, home: Path | None = None) -> bool:
    """Return true only when a path is recorded and unchanged since emission."""
    target = manifest_path(home)
    if not target.exists() or not path.exists():
        return False
    data = _load_manifest(target)
    details = data["files"].get(str(path.resolve()))
    return isinstance(details, dict) and details.get("sha256") == file_hash(path)
