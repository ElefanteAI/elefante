"""Register Elefante's stdio bridge with supported local agent CLIs."""

from __future__ import annotations

import argparse
import json
import os
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
    emitted_text_block_recorded,
    is_elefante_runtime_entry,
    is_unchanged_emitted_text_block,
    matching_host_add_command,
    record_emitted_text_block,
    record_host_command,
    write_text_atomically,
)


DAEMON_URL = "http://127.0.0.1:8765/mcp/"
CODEX_GUIDANCE_START = "<!-- ELEFANTE MANAGED RECALL START -->"
CODEX_GUIDANCE_END = "<!-- ELEFANTE MANAGED RECALL END -->"
CODEX_GUIDANCE_SURFACE = "codex-recall-routing"
CODEX_GUIDANCE_BLOCK = f"""{CODEX_GUIDANCE_START}
## Elefante memory

- Before answering a question that may depend on stored preferences, prior decisions, or project context, call `elefante-Recall` at most once with the complete question. Skip it for a self-contained question.
- Treat `no_match`, `blocked`, and `unavailable` as terminal for that answer: do not retry or broaden retrieval. Continue from current evidence or say that prior context is unavailable; never invent it.
- When the user explicitly asks Elefante to remember something across sessions or declares a project decision canonical or non-negotiable, first call `elefante-Memory` with `action="search"` for the exact concept. Update an equivalent memory only when the user is correcting it; otherwise add one concise durable record with `invocation_mode="user_directed"`.
- Leave `scope` unset unless the user or current host provides an exact project, workspace, or task identifier; never put descriptive prose in `scope`. Prefer ranked delivery when relevant paraphrases should work. Use `injection_policy="triggered"` only when literal trigger phrases are intentionally required; never choose it merely to pass one verification question. Set `user_locked=true` or permanent retention only when the user explicitly requests that protection.
- After a successful write, call `elefante-Recall` with one likely future question. A stored receipt is not proof that the memory is deliverable. Never infer a memory request from ordinary conversation, and never store passwords, API keys, access tokens, or other secrets. Report the actual write and verification results.
{CODEX_GUIDANCE_END}"""
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


def _codex_guidance_path(codex_home: Path) -> Path:
    """Select the one global guidance file Codex actually reads."""
    override = codex_home / "AGENTS.override.md"
    try:
        if override.exists() and override.read_text(encoding="utf-8").strip():
            return override
    except OSError:
        return override
    return codex_home / "AGENTS.md"


def configure_codex_guidance(
    *,
    codex_home: Path | None = None,
    manifest_home: Path | None = None,
) -> str:
    """Install one reversible Recall/capture rule without owning other guidance."""
    resolved_codex_home = codex_home or Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    path = _codex_guidance_path(resolved_codex_home)
    created = not path.exists()
    try:
        original = path.read_text(encoding="utf-8") if path.exists() else ""
    except OSError:
        return "failed"

    recorded = emitted_text_block_recorded(
        path,
        CODEX_GUIDANCE_SURFACE,
        CODEX_GUIDANCE_START,
        CODEX_GUIDANCE_END,
        home=manifest_home,
    )
    marker_count = original.count(CODEX_GUIDANCE_START) + original.count(CODEX_GUIDANCE_END)
    if marker_count:
        if marker_count != 2 or not is_unchanged_emitted_text_block(
            path,
            CODEX_GUIDANCE_SURFACE,
            CODEX_GUIDANCE_START,
            CODEX_GUIDANCE_END,
            home=manifest_home,
        ):
            return "preserved"
        start = original.index(CODEX_GUIDANCE_START)
        end = original.index(CODEX_GUIDANCE_END, start) + len(CODEX_GUIDANCE_END)
        current = original[start:end]
        if current == CODEX_GUIDANCE_BLOCK:
            return "already-present"
        updated = original[:start] + CODEX_GUIDANCE_BLOCK + original[end:]
        leading_separator = "\n" if start and original[start - 1:start] == "\n" else ""
        trailing_separator = "\n" if original[end:end + 1] == "\n" else ""
        status = "updated"
    else:
        if recorded:
            # The user removed or changed a previously managed rule. Respect it.
            return "preserved"
        leading_separator = "" if not original else ("\n" if original.endswith("\n") else "\n\n")
        trailing_separator = "\n"
        updated = original + leading_separator + CODEX_GUIDANCE_BLOCK + trailing_separator
        status = "configured"

    try:
        write_text_atomically(path, updated)
        record_emitted_text_block(
            path,
            CODEX_GUIDANCE_SURFACE,
            CODEX_GUIDANCE_START,
            CODEX_GUIDANCE_END,
            created=created,
            leading_separator=leading_separator,
            trailing_separator=trailing_separator,
            home=manifest_home,
        )
    except Exception:
        try:
            if created:
                path.unlink(missing_ok=True)
            else:
                write_text_atomically(path, original)
        except OSError:
            pass
        return "failed"
    return status


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
    codex_home: Path | None = None,
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
    if host == "codex":
        guidance_home = codex_home or (home / ".codex" if home is not None else None)
        guidance = configure_codex_guidance(
            codex_home=guidance_home,
            manifest_home=home,
        )
        if guidance not in {"configured", "updated", "already-present"}:
            try:
                removed = runner(remove, capture_output=True, text=True, check=False)
            except OSError:
                return "partial"
            if removed.returncode != 0:
                return "partial"
            if old_add is not None:
                try:
                    restored = runner(
                        old_add, capture_output=True, text=True, check=False
                    )
                except OSError:
                    return "partial"
                if restored.returncode != 0:
                    return "partial"
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
    codex_home: Path | None = None,
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
                codex_home=codex_home,
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
