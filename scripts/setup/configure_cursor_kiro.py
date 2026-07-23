"""Configure Cursor, Kiro, and Gemini CLI to use Elefante's local stdio bridge.

Only an already-detected user configuration directory is modified.  Both
hosts use a shared JSON ``mcpServers`` object, so this module owns only the
``elefante`` entry and records that precise ownership for safe uninstall.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable

_SETUP_DIR = str(Path(__file__).resolve().parent)
if _SETUP_DIR not in sys.path:
    sys.path.insert(0, _SETUP_DIR)

from install_manifest import (
    is_unchanged_emitted_json_entry,
    record_emitted_json_entry,
    write_json_atomically,
)


DAEMON_URL = "http://127.0.0.1:8765/mcp/"


def infer_repo_python(elefante_path: Path) -> str:
    """Prefer the repository virtual environment used by the daemon."""
    candidate = elefante_path / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def bridge_server_config(
    elefante_path: Path,
    python_cmd: str,
    tool: str,
    *,
    include_disabled: bool = True,
) -> dict:
    """Return the portable stdio bridge configuration shared by JSON hosts."""
    server = {
        "command": python_cmd,
        "args": ["-m", "src.mcp.stdio_bridge"],
        "cwd": str(elefante_path),
        "env": {
            "PYTHONPATH": str(elefante_path),
            "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
            "ELEFANTE_DAEMON_URL": DAEMON_URL,
            "ELEFANTE_CLIENT_TOOL": tool,
            "ANONYMIZED_TELEMETRY": "False",
        },
    }
    # Cursor and Kiro accept an explicit disabled flag. Gemini CLI's documented
    # schema does not include it, so omit it rather than relying on unknown-key
    # tolerance in a user-owned configuration file.
    if include_disabled:
        server["disabled"] = False
    return server


def configure_json_mcp(
    config_path: Path,
    elefante_path: Path,
    python_cmd: str,
    tool: str,
    *,
    manifest_home: Path | None = None,
    include_disabled: bool = True,
) -> bool:
    """Add/update one bridge entry while preserving every other MCP server."""
    existed_before = config_path.exists()
    try:
        document = json.loads(config_path.read_text(encoding="utf-8")) if existed_before else {}
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(document, dict):
        return False
    servers = document.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return False
    entry_path = ("mcpServers", "elefante")
    if "elefante" in servers and not is_unchanged_emitted_json_entry(
        config_path, tool, entry_path, home=manifest_home
    ):
        return False
    servers["elefante"] = bridge_server_config(
        elefante_path, python_cmd, tool, include_disabled=include_disabled
    )
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(config_path, document)
        record_emitted_json_entry(
            config_path,
            tool,
            entry_path,
            created=not existed_before,
            home=manifest_home,
        )
    except (OSError, RuntimeError):
        return False
    return True


def candidate_paths(home: Path) -> dict[str, Path]:
    """Return only global paths supported by the vendor configuration docs."""
    return {
        "cursor": home / ".cursor" / "mcp.json",
        "kiro": home / ".kiro" / "settings" / "mcp.json",
        "gemini": home / ".gemini" / "settings.json",
    }


def host_is_detected(host: str, config_path: Path) -> bool:
    """Detect the host root rather than requiring its config file to exist."""
    root = config_path.parents[1] if host == "kiro" else config_path.parent
    return root.is_dir()


def configure_detected_hosts(
    elefante_path: Path,
    python_cmd: str,
    *,
    home: Path | None = None,
    selected: set[str] | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> dict[str, bool]:
    """Configure only installed hosts, leaving absent host directories alone."""
    home = home or Path.home()
    selected = selected or {"cursor", "kiro", "gemini"}
    results: dict[str, bool] = {}
    for host, config_path in candidate_paths(home).items():
        if host not in selected or not host_is_detected(host, config_path):
            continue
        # Antigravity also uses ~/.gemini. Require the real Gemini CLI before
        # writing its separate user configuration, rather than treating a
        # shared parent directory as proof that this host is installed.
        if host == "gemini" and not which("gemini"):
            continue
        results[host] = configure_json_mcp(
            config_path,
            elefante_path,
            python_cmd,
            host,
            manifest_home=home,
            include_disabled=host != "gemini",
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("cursor", "kiro", "gemini"), action="append")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    results = configure_detected_hosts(root, infer_repo_python(root), selected=set(args.host or []) or None)
    if not results:
        print("No detected Cursor, Kiro, or Gemini configuration directory; no files changed.")
        return 0
    for host, configured in results.items():
        print(f"{host}: {'configured' if configured else 'not changed'}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
