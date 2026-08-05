"""Canonical host-selection contract shared by Elefante installers."""

from __future__ import annotations

from collections.abc import Iterable
import os
import platform
import shutil
from pathlib import Path
from typing import Callable


SUPPORTED_HOSTS = (
    "vscode-copilot",
    "cursor",
    "kiro",
    "gemini",
    "claude-code",
    "codex",
    "openclaw",
    "bob",
    "antigravity",
)

HOST_LABELS = {
    "vscode-copilot": "VS Code + Copilot",
    "cursor": "Cursor",
    "kiro": "Kiro",
    "gemini": "Gemini CLI",
    "claude-code": "Claude Code",
    "codex": "Codex",
    "openclaw": "OpenClaw",
    "bob": "IBM Bob",
    "antigravity": "Antigravity",
}

VSCODE_FAMILY = frozenset({"vscode-copilot", "bob"})
JSON_HOSTS = frozenset({"cursor", "kiro", "gemini"})
CLI_HOSTS = frozenset({"claude-code", "codex", "openclaw"})
MANIFEST_SURFACE_ALIASES = {"ibm-bob": "bob"}


def detect_supported_hosts(
    *,
    home: Path | None = None,
    env: dict[str, str] | None = None,
    system: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
) -> set[str]:
    """Detect compatible user-level hosts without creating configuration paths."""
    home = Path(home or Path.home())
    env = env or os.environ
    system = system or platform.system()
    detected: set[str] = set()

    if system == "Windows":
        appdata = Path(env.get("APPDATA", home / "AppData" / "Roaming"))
        vscode_roots = (appdata / "Code" / "User", appdata / "Code - Insiders" / "User")
        bob_roots = (appdata / "Bob-IDE" / "User", home / ".bob")
    elif system == "Darwin":
        app_support = home / "Library" / "Application Support"
        vscode_roots = (app_support / "Code" / "User", app_support / "Code - Insiders" / "User")
        bob_roots = (app_support / "Bob-IDE" / "User", home / ".bob")
    else:
        config_home = Path(env.get("XDG_CONFIG_HOME", home / ".config"))
        vscode_roots = (config_home / "Code" / "User", config_home / "Code - Insiders" / "User")
        bob_roots = (config_home / "Bob-IDE" / "User", home / ".bob")

    if any(path.is_dir() for path in vscode_roots):
        detected.add("vscode-copilot")
    if any(path.is_dir() for path in bob_roots):
        detected.add("bob")
    if (home / ".cursor").is_dir():
        detected.add("cursor")
    if (home / ".kiro").is_dir():
        detected.add("kiro")
    if (home / ".gemini" / "antigravity").is_dir():
        detected.add("antigravity")
    if (home / ".gemini").is_dir() and which("gemini"):
        detected.add("gemini")

    for host, executable in (
        ("claude-code", "claude"),
        ("codex", "codex"),
        ("openclaw", "openclaw"),
    ):
        if which(executable):
            detected.add(host)
    return detected


def normalize_manifest_surfaces(surfaces: Iterable[str]) -> set[str]:
    """Normalize historical adapter labels to canonical host-selection IDs."""
    return {MANIFEST_SURFACE_ALIASES.get(surface, surface) for surface in surfaces}


def normalize_selected_hosts(hosts: Iterable[str] | None) -> set[str] | None:
    """Return an explicit validated selection, or None for all detected hosts."""
    if hosts is None:
        return None
    selected = set(hosts)
    unsupported = selected.difference(SUPPORTED_HOSTS)
    if unsupported:
        names = ", ".join(sorted(unsupported))
        raise ValueError(f"Unsupported host selection: {names}")
    return selected


def select_family(
    selected_hosts: set[str] | None,
    family: frozenset[str],
) -> set[str] | None:
    """Preserve detect-all semantics or return the explicit family subset."""
    if selected_hosts is None:
        return None
    return selected_hosts.intersection(family)
