"""Manage Elefante's user-scope daemon service (dry-run by default)."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen
from xml.sax.saxutils import escape


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.setup.install_manifest import (  # noqa: E402
    forget_emitted_file,
    is_unchanged_emitted_file,
    record_emitted_file,
)

LABEL = "ai.elefante.daemon"
DEFAULT_DAEMON_PORT = 8765
STANDARD_UNIX_EXECUTABLE_DIRS = (
    "/opt/homebrew/bin",
    "/usr/local/bin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
)


def _python() -> Path:
    candidate = REPO_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return candidate if candidate.exists() else Path(sys.executable)


def service_path(home: Path, system: str | None = None) -> Path:
    system = system or platform.system()
    if system == "Darwin":
        return home / "Library/LaunchAgents" / f"{LABEL}.plist"
    if system == "Linux":
        return home / ".config/systemd/user" / f"{LABEL}.service"
    if system == "Windows":
        return home / ".elefante/services" / f"{LABEL}.xml"
    raise RuntimeError(f"Unsupported daemon service platform: {system}")


def _service_executable_path(system: str) -> str:
    """Keep certified host discovery available in a minimal service environment."""
    if system not in {"Darwin", "Linux"}:
        return ""
    candidates: list[str] = []
    codex_command = shutil.which("codex")
    if codex_command:
        candidates.append(str(Path(codex_command).parent))
    if system == "Darwin":
        for app_root in (Path("/Applications"), Path.home() / "Applications"):
            bundled_codex = app_root / "ChatGPT.app/Contents/Resources/codex"
            if bundled_codex.is_file():
                candidates.append(str(bundled_codex.parent))
    candidates.extend(STANDARD_UNIX_EXECUTABLE_DIRS)
    safe_directories = [
        directory
        for directory in candidates
        if Path(directory).is_absolute()
        and not any(character in directory for character in ('"', "\\r", "\\n"))
    ]
    return os.pathsep.join(dict.fromkeys(safe_directories))


def render_service(home: Path, system: str | None = None) -> str:
    system = system or platform.system()
    python = _python()
    if system == "Darwin":
        executable_path = escape(_service_executable_path(system))
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>{LABEL}</string>
<key>ProgramArguments</key><array><string>{python}</string><string>-m</string><string>src.mcp.daemon</string></array>
<key>WorkingDirectory</key><string>{REPO_ROOT}</string>
<key>EnvironmentVariables</key><dict><key>PYTHONPATH</key><string>{REPO_ROOT}</string><key>PATH</key><string>{executable_path}</string></dict>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>{home}/.elefante/logs/daemon.out.log</string>
<key>StandardErrorPath</key><string>{home}/.elefante/logs/daemon.err.log</string>
</dict></plist>
'''
    if system == "Linux":
        executable_path = _service_executable_path(system)
        return f'''[Unit]
Description=Elefante local MCP daemon
After=network.target

[Service]
Type=simple
WorkingDirectory={REPO_ROOT}
Environment=PYTHONPATH={REPO_ROOT}
Environment="PATH={executable_path}"
ExecStart={python} -m src.mcp.daemon
Restart=on-failure
RestartSec=2

[Install]
WantedBy=default.target
'''
    if system == "Windows":
        command = escape(str(python))
        arguments = escape("-m src.mcp.daemon")
        working_directory = escape(str(REPO_ROOT))
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers><LogonTrigger><Enabled>true</Enabled></LogonTrigger></Triggers>
  <Principals><Principal id="Author"><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings><MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy><DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries><AllowHardTerminate>true</AllowHardTerminate><StartWhenAvailable>true</StartWhenAvailable><ExecutionTimeLimit>PT0S</ExecutionTimeLimit><RestartOnFailure><Interval>PT1M</Interval><Count>3</Count></RestartOnFailure><Enabled>true</Enabled></Settings>
  <Actions Context="Author"><Exec><Command>{command}</Command><Arguments>{arguments}</Arguments><WorkingDirectory>{working_directory}</WorkingDirectory></Exec></Actions>
</Task>
'''
    raise RuntimeError(f"Unsupported daemon service platform: {system}")


def _run(command: list[str], apply: bool) -> None:
    print(" ".join(command))
    if apply:
        subprocess.run(command, check=True)


def _run_optional(command: list[str], apply: bool) -> None:
    """Run an idempotent lifecycle cleanup command without masking the next action."""
    print(" ".join(command))
    if apply:
        subprocess.run(command, check=False)


def _status_command(system: str) -> list[str]:
    """Return the read-only platform command that inspects the user service."""
    if system == "Darwin":
        return ["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"]
    if system == "Linux":
        return ["systemctl", "--user", "is-active", LABEL]
    if system == "Windows":
        return ["schtasks", "/query", "/tn", LABEL]
    raise RuntimeError(f"Unsupported daemon service platform: {system}")


def _runtime_status(
    system: str, runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run
) -> str:
    """Inspect service-manager state without starting, stopping, or editing anything."""
    try:
        result = runner(_status_command(system), capture_output=True, text=True, check=False)
    except OSError:
        return "unavailable"
    if system == "Linux":
        return "active" if result.returncode == 0 else "inactive"
    return "registered" if result.returncode == 0 else "not_registered"


def daemon_healthy(port: int = DEFAULT_DAEMON_PORT) -> bool:
    """Return whether the loopback daemon's non-mutating health endpoint responds."""
    try:
        with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, ValueError, json.JSONDecodeError):
        return False
    return payload == {
        "status": "ok",
        "service": "elefante-daemon",
        "transport": "streamable-http",
    }


def service_status(
    home: Path,
    system: str | None = None,
    *,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    health_check: Callable[[], bool] = daemon_healthy,
) -> dict[str, str | bool]:
    """Return a read-only, machine-readable diagnosis of service ownership and health."""
    system = system or platform.system()
    path = service_path(home, system)
    if not path.exists():
        ownership = "absent"
    elif is_unchanged_emitted_file(path, home):
        ownership = "owned"
    else:
        ownership = "modified_or_untracked"
    return {
        "platform": system,
        "service_file": str(path),
        "service_file_exists": path.exists(),
        "service_file_ownership": ownership,
        "service_runtime": _runtime_status(system, runner),
        "daemon_health": health_check(),
    }


def _wait_for_health_state(
    expected: bool,
    *,
    health_check: Callable[[], bool] = daemon_healthy,
    timeout_seconds: float = 15.0,
    poll_seconds: float = 0.25,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        if health_check() is expected:
            return True
        time.sleep(poll_seconds)
    return False


def stop(
    home: Path,
    apply: bool,
    *,
    system: str | None = None,
    health_check: Callable[[], bool] = daemon_healthy,
) -> bool:
    """Stop only Elefante's unchanged owned service without deleting its unit."""
    system = system or platform.system()
    path = service_path(home, system)
    if not path.exists():
        print(f"service absent: {path}")
        return not apply or not health_check()
    if not is_unchanged_emitted_file(path, home):
        print(f"preserve {path} (not recorded or modified)")
        return False

    print(f"stop {path}")
    try:
        if system == "Darwin":
            _run_optional(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], apply)
        elif system == "Linux":
            _run_optional(["systemctl", "--user", "stop", LABEL], apply)
        else:
            _run_optional(["schtasks", "/end", "/tn", LABEL], apply)
    except OSError:
        return False
    return not apply or _wait_for_health_state(False, health_check=health_check)


def start(
    home: Path,
    apply: bool,
    *,
    system: str | None = None,
    health_check: Callable[[], bool] = daemon_healthy,
) -> bool:
    """Start only Elefante's unchanged owned service without rewriting its unit."""
    system = system or platform.system()
    path = service_path(home, system)
    if not path.exists() or not is_unchanged_emitted_file(path, home):
        print(f"preserve {path} (service is absent, unrecorded, or modified)")
        return False

    print(f"start {path}")
    try:
        if system == "Darwin":
            _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], apply)
        elif system == "Linux":
            _run(["systemctl", "--user", "start", LABEL], apply)
        else:
            _run(["schtasks", "/run", "/tn", LABEL], apply)
    except (OSError, subprocess.CalledProcessError):
        return False
    return not apply or _wait_for_health_state(True, health_check=health_check)


def install(home: Path, apply: bool) -> Path:
    system = platform.system()
    path = service_path(home, system)
    refresh = path.exists()
    if refresh and not is_unchanged_emitted_file(path, home):
        print(f"preserve {path} (not recorded or modified)")
        return path
    print(f"{'refresh' if refresh else 'write'} {path}")
    if apply:
        path.parent.mkdir(parents=True, exist_ok=True)
        (home / ".elefante/logs").mkdir(parents=True, exist_ok=True)
        path.write_text(render_service(home), encoding="utf-8")
        record_emitted_file(path, "daemon-service", home)
    if system == "Darwin":
        if refresh:
            # A stale or absent launchd job is harmless here; bootstrap below
            # remains the authoritative action for the refreshed unit.
            _run_optional(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], apply)
        _run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(path)], apply)
    elif system == "Linux":
        _run(["systemctl", "--user", "daemon-reload"], apply)
        _run(["systemctl", "--user", "enable", "--now", LABEL], apply)
        if refresh:
            _run(["systemctl", "--user", "try-restart", LABEL], apply)
    else:
        _run(["schtasks", "/create", "/tn", LABEL, "/xml", str(path), "/f"], apply)
        _run(["schtasks", "/run", "/tn", LABEL], apply)
    return path


def uninstall(home: Path, apply: bool) -> Path:
    system = platform.system()
    path = service_path(home, system)
    if not is_unchanged_emitted_file(path, home):
        print(f"preserve {path} (not recorded or modified)")
        return path
    if system == "Darwin":
        _run(["launchctl", "bootout", f"gui/{os.getuid()}", str(path)], apply)
    elif system == "Linux":
        _run(["systemctl", "--user", "disable", "--now", LABEL], apply)
        _run(["systemctl", "--user", "daemon-reload"], apply)
    else:
        _run(["schtasks", "/delete", "/tn", LABEL, "/f"], apply)
    print(f"remove {path}")
    if apply:
        path.unlink()
        forget_emitted_file(path, home)
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall", "start", "stop", "status"))
    parser.add_argument("--apply", action="store_true", help="perform the action; default is dry-run")
    args = parser.parse_args()
    home = Path.home()
    if args.action == "install":
        path = service_path(home)
        conflict = path.exists() and not is_unchanged_emitted_file(path, home)
        install(home, args.apply)
        if conflict:
            print("service_install=preserved_conflict")
            raise SystemExit(2)
    elif args.action == "uninstall":
        uninstall(home, args.apply)
    elif args.action == "stop":
        if not stop(home, args.apply):
            print("service_stop=not_verified")
            raise SystemExit(2)
    elif args.action == "start":
        if not start(home, args.apply):
            print("service_start=not_verified")
            raise SystemExit(2)
    else:
        for key, value in service_status(home).items():
            print(f"{key}={value}")


if __name__ == "__main__":
    main()
