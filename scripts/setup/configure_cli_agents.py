"""Register Elefante's stdio bridge with supported local agent CLIs."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

# Setup adapters are both executable scripts and importable installer helpers.
# Make their sibling ownership module available in either invocation mode.
_SETUP_DIR = str(Path(__file__).resolve().parent)
if _SETUP_DIR not in sys.path:
    sys.path.insert(0, _SETUP_DIR)

from install_manifest import (  # noqa: E402
    is_elefante_runtime_entry,
    matching_host_add_command,
    record_host_command,
)


DAEMON_URL = "http://127.0.0.1:8765/mcp/"
Runner = Callable[..., subprocess.CompletedProcess[str]]


def infer_repo_python(elefante_path: Path) -> str:
    candidate = elefante_path / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def bridge_environment(elefante_path: Path, tool: str) -> dict[str, str]:
    return {
        "PYTHONPATH": str(elefante_path),
        "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
        "ELEFANTE_DAEMON_URL": DAEMON_URL,
        "ELEFANTE_CLIENT_TOOL": tool,
        "ANONYMIZED_TELEMETRY": "False",
    }


def host_commands(host: str, executable: str, elefante_path: Path, python_cmd: str) -> tuple[list[str], list[str], list[str]]:
    """Return host-native get, add, and remove commands for a user registration."""
    tool = {
        "claude-code": "claude-code",
        "codex": "codex",
        "openclaw": "openclaw",
    }.get(host)
    if tool is None:
        raise ValueError(f"Unsupported CLI host: {host}")
    environment = bridge_environment(elefante_path, tool)
    if host == "claude-code":
        get = [executable, "mcp", "get", "elefante"]
        remove = [executable, "mcp", "remove", "elefante"]
        add = [executable, "mcp", "add", "--scope", "user"]
    elif host == "codex":
        get = [executable, "mcp", "get", "elefante", "--json"]
        remove = [executable, "mcp", "remove", "elefante"]
        add = [executable, "mcp", "add"]
        # The human-oriented command masks environment values. JSON is the
        # host-supported canonical view we fingerprint for safe upgrades.
    elif host == "openclaw":
        # OpenClaw owns its client-side registry. Its JSON show command is the
        # inspection contract, while unset removes exactly one named server.
        get = [executable, "mcp", "show", "elefante", "--json"]
        remove = [executable, "mcp", "unset", "elefante"]
        add = [
            executable,
            "mcp",
            "add",
            "elefante",
            "--command",
            python_cmd,
            "--arg",
            "-m",
            "--arg",
            "src.mcp.stdio_bridge",
            "--cwd",
            str(elefante_path),
        ]
        for key, value in environment.items():
            add.extend(["--env", f"{key}={value}"])
        return get, add, remove
    for key, value in environment.items():
        add.extend(["--env", f"{key}={value}"])
    if host == "claude-code":
        # Claude's CLI needs a non-`--env` option before the server name.
        add.extend(["--transport", "stdio"])
    add.extend(["elefante", "--", python_cmd, "-m", "src.mcp.stdio_bridge"])
    return get, add, remove


def configure_cli_host(
    host: str,
    executable: str,
    elefante_path: Path,
    python_cmd: str,
    *,
    home: Path | None = None,
    runner: Runner = subprocess.run,
    adopt_legacy: bool = False,
) -> str:
    """Add or safely refresh one host registration without overwriting user entries."""
    get, add, remove = host_commands(host, executable, elefante_path, python_cmd)
    key = f"{host}:elefante"
    try:
        existing = runner(get, capture_output=True, text=True, check=False)
    except OSError:
        return "unavailable"
    old_add: list[str] | None = None
    if existing.returncode == 0:
        old_add = matching_host_add_command(key, existing.stdout, home=home)
        if old_add is None and adopt_legacy and host == "codex":
            try:
                existing_document = json.loads(existing.stdout)
            except json.JSONDecodeError:
                existing_document = None
            if is_elefante_runtime_entry(existing_document):
                transport = existing_document["transport"]
                command = transport.get("command")
                args = transport.get("args")
                environment = transport.get("env", {})
                if (
                    isinstance(command, str)
                    and isinstance(args, list)
                    and all(isinstance(part, str) for part in args)
                    and isinstance(environment, dict)
                    and all(isinstance(key, str) and isinstance(value, str) for key, value in environment.items())
                ):
                    old_add = [executable, "mcp", "add"]
                    for name, value in environment.items():
                        old_add.extend(["--env", f"{name}={value}"])
                    old_add.extend(["elefante", "--", command, *args])
        if old_add is None:
            return "already-present"
        try:
            removed = runner(remove, capture_output=True, text=True, check=False)
        except OSError:
            return "unavailable"
        if removed.returncode != 0:
            return "failed"
    try:
        added = runner(add, capture_output=True, text=True, check=False)
    except OSError:
        return "unavailable"
    if added.returncode != 0:
        if old_add is not None:
            runner(old_add, capture_output=True, text=True, check=False)
        return "failed"
    try:
        registered = runner(get, capture_output=True, text=True, check=False)
    except OSError:
        registered = subprocess.CompletedProcess(get, returncode=1, stdout="", stderr="")
    if registered.returncode != 0:
        # Do not leave an untrackable replacement behind; restore our prior
        # registration when the host accepted the command but cannot inspect it.
        runner(remove, capture_output=True, text=True, check=False)
        if old_add is not None:
            runner(old_add, capture_output=True, text=True, check=False)
        return "failed"
    record_host_command(
        key, host, get, add, remove, registered.stdout, home=home
    )
    return "updated" if old_add is not None else "configured"


def configure_detected_cli_hosts(
    elefante_path: Path,
    python_cmd: str,
    *,
    home: Path | None = None,
    which: Callable[[str], str | None] = shutil.which,
    runner: Runner = subprocess.run,
    selected: set[str] | None = None,
    adopt_legacy: bool = False,
) -> dict[str, str]:
    """Use native CLIs only when installed; no raw host config is edited."""
    results: dict[str, str] = {}
    selected = selected or {"claude-code", "codex", "openclaw"}
    for host, binary in (("claude-code", "claude"), ("codex", "codex"), ("openclaw", "openclaw")):
        if host not in selected:
            continue
        executable = which(binary)
        if executable:
            results[host] = configure_cli_host(
                host,
                executable,
                elefante_path,
                python_cmd,
                home=home,
                runner=runner,
                adopt_legacy=adopt_legacy,
            )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("claude-code", "codex", "openclaw"), action="append")
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    selected = set(args.host or {"claude-code", "codex", "openclaw"})
    results = configure_detected_cli_hosts(root, infer_repo_python(root), selected=selected)
    if not results:
        print("No detected Claude Code, Codex, or OpenClaw CLI; no files changed.")
        return 0
    for host, result in results.items():
        print(f"{host}: {result}")
    return 0 if all(result in {"configured", "updated", "already-present"} for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
