"""Canonical host-selection contract shared by Elefante installers."""

from __future__ import annotations

from collections.abc import Iterable


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
