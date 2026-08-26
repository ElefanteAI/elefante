"""Black-box acceptance for customer host-coverage reporting."""

from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_doctor_cli_reports_a_detected_unconfigured_host(tmp_path) -> None:
    """Exercise the documented CLI; do not import or patch doctor internals."""
    home = tmp_path / "home"
    (home / ".cursor").mkdir(parents=True)
    (home / ".kiro").mkdir()
    (home / ".gemini" / "antigravity").mkdir(parents=True)
    system = platform.system()
    if system == "Windows":
        appdata = home / "AppData" / "Roaming"
        (appdata / "Code" / "User").mkdir(parents=True)
        (appdata / "Bob-IDE" / "User").mkdir(parents=True)
    elif system == "Darwin":
        app_support = home / "Library" / "Application Support"
        (app_support / "Code" / "User").mkdir(parents=True)
        (app_support / "Bob-IDE" / "User").mkdir(parents=True)
    else:
        config_home = home / ".config"
        (config_home / "Code" / "User").mkdir(parents=True)
        (config_home / "Bob-IDE" / "User").mkdir(parents=True)

    isolated_path = tmp_path / "bin"
    isolated_path.mkdir()
    for command in ("claude", "codex", "gemini", "openclaw"):
        executable = isolated_path / command
        executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        executable.chmod(0o755)
        if system == "Windows":
            (isolated_path / f"{command}.cmd").write_text(
                "@exit /b 0\n", encoding="utf-8"
            )

    # A manifest claim without a matching current artifact is not verification.
    manifest = home / ".elefante" / "install-manifest.json"
    manifest.parent.mkdir()
    manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "files": {
                    str(home / ".cursor" / "mcp.json"): {
                        "kind": "file",
                        "surface": "cursor",
                        "sha256": "0" * 64,
                    }
                },
                "commands": {},
            }
        ),
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "APPDATA": str(home / "AppData" / "Roaming"),
        "HOME": str(home),
        "PATHEXT": os.environ.get("PATHEXT", ".COM;.EXE;.BAT;.CMD"),
        "USERPROFILE": str(home),
        "XDG_CONFIG_HOME": str(home / ".config"),
        "PATH": str(isolated_path),
        "PYTHONPATH": str(ROOT),
    }

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/lifecycle/doctor.py"), "--json"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert report["schema_version"] == 2
    assert report["customer_ready"] is False
    assert report["host_coverage"] == {
        "detected": [
            "antigravity",
            "bob",
            "claude-code",
            "codex",
            "cursor",
            "gemini",
            "kiro",
            "openclaw",
            "vscode-copilot",
        ],
        "verified": [],
        "uncovered": [
            "antigravity",
            "bob",
            "claude-code",
            "codex",
            "cursor",
            "gemini",
            "kiro",
            "openclaw",
            "vscode-copilot",
        ],
    }
    assert "detected_hosts_unconfigured" in report["customer_diagnostics"]
