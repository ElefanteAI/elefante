"""Configure Zed and Continue against Elefante's storage-free stdio bridge.

Both adapters are detect-first and ownership-safe. Zed receives one exact JSON
entry in its documented ``context_servers`` object. Continue receives one
dedicated local MCP block file, so no user-owned YAML must be parsed or
rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Callable

_SETUP_DIR = str(Path(__file__).resolve().parent)
if _SETUP_DIR not in sys.path:
    sys.path.insert(0, _SETUP_DIR)

from install_manifest import (  # noqa: E402
    is_elefante_runtime_entry,
    is_unchanged_emitted_file,
    is_unchanged_emitted_json_entry,
    record_emitted_file,
    record_emitted_json_entry,
    write_json_atomically,
    write_text_atomically,
)


DAEMON_URL = "http://127.0.0.1:8765/mcp/"


def infer_repo_python(elefante_path: Path) -> str:
    candidate = elefante_path / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    return str(candidate) if candidate.exists() else sys.executable


def bridge_environment(elefante_path: Path, host: str) -> dict[str, str]:
    return {
        "PYTHONPATH": str(elefante_path),
        "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
        "ELEFANTE_DAEMON_URL": DAEMON_URL,
        "ELEFANTE_CLIENT_TOOL": host,
        "ANONYMIZED_TELEMETRY": "False",
    }


def zed_settings_path(
    home: Path, *, system: str | None = None, env: dict[str, str] | None = None
) -> Path:
    system = system or platform.system()
    env = env or os.environ
    if system == "Windows":
        return Path(env.get("APPDATA", home / "AppData" / "Roaming")) / "Zed" / "settings.json"
    return home / ".config" / "zed" / "settings.json"


def zed_entry(elefante_path: Path, python_cmd: str) -> dict:
    return {
        "command": python_cmd,
        "args": ["-m", "src.mcp.stdio_bridge"],
        "env": bridge_environment(elefante_path, "zed"),
    }


def configure_zed(
    path: Path,
    elefante_path: Path,
    python_cmd: str,
    *,
    manifest_home: Path,
    adopt_legacy: bool = False,
) -> bool:
    existed = path.exists()
    try:
        document = json.loads(path.read_text(encoding="utf-8")) if existed else {}
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(document, dict):
        return False
    servers = document.setdefault("context_servers", {})
    if not isinstance(servers, dict):
        return False
    entry_path = ("context_servers", "elefante")
    if "elefante" in servers:
        owned = is_unchanged_emitted_json_entry(
            path, "zed", entry_path, home=manifest_home
        )
        legacy = is_elefante_runtime_entry(servers["elefante"])
        if not owned and not (adopt_legacy and legacy):
            return False
    servers["elefante"] = zed_entry(elefante_path, python_cmd)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(path, document)
        record_emitted_json_entry(
            path,
            "zed",
            entry_path,
            created=not existed,
            home=manifest_home,
        )
    except (OSError, RuntimeError):
        return False
    return True


def continue_block(elefante_path: Path, python_cmd: str) -> str:
    env = bridge_environment(elefante_path, "continue")
    lines = [
        "name: Elefante Local Memory",
        "version: 1.0.0",
        "schema: v1",
        "mcpServers:",
        "  - name: Elefante",
        "    type: stdio",
        f"    command: {json.dumps(python_cmd)}",
        "    args:",
        "      - -m",
        "      - src.mcp.stdio_bridge",
        f"    cwd: {json.dumps(str(elefante_path))}",
        "    env:",
    ]
    lines.extend(
        f"      {name}: {json.dumps(value)}" for name, value in sorted(env.items())
    )
    return "\n".join(lines) + "\n"


def configure_continue(
    path: Path,
    elefante_path: Path,
    python_cmd: str,
    *,
    manifest_home: Path,
) -> bool:
    if path.exists() and not is_unchanged_emitted_file(path, manifest_home):
        return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomically(path, continue_block(elefante_path, python_cmd))
        record_emitted_file(path, "continue", manifest_home)
    except (OSError, RuntimeError):
        return False
    return True


def candidate_paths(
    home: Path, *, system: str | None = None, env: dict[str, str] | None = None
) -> dict[str, Path]:
    return {
        "zed": zed_settings_path(home, system=system, env=env),
        "continue": home / ".continue" / "mcpServers" / "elefante.yaml",
    }


def detect_additional_hosts(
    *,
    home: Path,
    system: str | None = None,
    env: dict[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> set[str]:
    paths = candidate_paths(home, system=system, env=env)
    detected: set[str] = set()
    if paths["zed"].parent.is_dir() or which("zed"):
        detected.add("zed")
    if (home / ".continue").is_dir() or which("cn"):
        detected.add("continue")
    return detected


def configure_detected_additional_hosts(
    elefante_path: Path,
    python_cmd: str,
    *,
    home: Path | None = None,
    selected: set[str] | None = None,
    system: str | None = None,
    env: dict[str, str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    adopt_legacy: bool = False,
) -> dict[str, bool]:
    home = home or Path.home()
    detected = detect_additional_hosts(
        home=home, system=system, env=env, which=which
    )
    selected = selected if selected is not None else {"zed", "continue"}
    paths = candidate_paths(home, system=system, env=env)
    results: dict[str, bool] = {}
    if "zed" in detected and "zed" in selected:
        results["zed"] = configure_zed(
            paths["zed"],
            elefante_path,
            python_cmd,
            manifest_home=home,
            adopt_legacy=adopt_legacy,
        )
    if "continue" in detected and "continue" in selected:
        results["continue"] = configure_continue(
            paths["continue"],
            elefante_path,
            python_cmd,
            manifest_home=home,
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("zed", "continue"), action="append")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    selected = set(args.host or []) or None
    results = configure_detected_additional_hosts(
        root, infer_repo_python(root), selected=selected
    )
    if not results:
        print("No detected Zed or Continue host; no files changed.")
        return 0
    for host, configured in results.items():
        print(f"{host}: {'configured' if configured else 'not changed'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
