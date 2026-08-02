# ─────────────────────────────────────────────────────────────────────────────
# NAME    : configure_vscode_bob.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Write VS Code mcp.json (and clean settings.json duplicates) to wire
#           Elefante as an MCP server for VS Code and Bob IDE. Called by install.py.
# WHEN    : Initial VS Code/Bob IDE setup, or after moving the repo to a new path.
#           Re-run if VS Code shows two Elefante entries (duplicate config) or
#           stops seeing Elefante tools after a repo move or Python env change.
# USAGE   : python scripts/setup/configure_vscode_bob.py
# NOTES   : Writes to .vscode/mcp.json and removes settings.json duplicates.
#           If you see two Elefante entries in VS Code, this script is the fix —
#           it detects and removes the settings.json-based duplicate.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Automatic VS Code/Bob MCP configuration.

Configures VS Code (including Insiders) and Bob-IDE to use the Elefante MCP server.

Important:
- VS Code can load MCP servers from **mcp.json** (built-in MCP).
- Some builds/extensions also support **chat.mcp.servers** in settings.json.

If you configure BOTH, VS Code may show two Elefante entries.
Default behavior of this script is to configure **mcp.json** and remove
settings-based duplicates for VS Code.
"""

from __future__ import annotations

import json
import os
import sys
import io
from pathlib import Path

_SETUP_DIR = str(Path(__file__).resolve().parent)
if _SETUP_DIR not in sys.path:
    sys.path.insert(0, _SETUP_DIR)

from install_manifest import (  # noqa: E402
    forget_emitted_file,
    is_unchanged_emitted_json_entry,
    record_emitted_json_entry,
    write_json_atomically,
)
from host_selection import VSCODE_FAMILY  # noqa: E402


def _infer_repo_python(elefante_path: Path) -> str:
    """Prefer the repo venv Python for stability; fall back to sys.executable."""
    if os.name == "nt":
        candidate = elefante_path / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = elefante_path / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable


def _is_vscode_settings_path(path: Path) -> bool:
    """Best-effort check for VS Code (stable/insiders) settings.json."""
    s = str(path)
    return (
        s.endswith("settings.json")
        and ("/Code/" in s or "/Code - Insiders/" in s or "\\Code\\" in s or "\\Code - Insiders\\" in s)
        and "Cursor" not in s
        and "Bob-IDE" not in s
    )


def _remove_vscode_chat_server(settings: dict, server_name: str) -> bool:
    """Remove settings-based MCP server definition if present."""
    changed = False
    chat_servers = settings.get("chat.mcp.servers")
    if isinstance(chat_servers, dict) and server_name in chat_servers:
        del chat_servers[server_name]
        changed = True
        # If empty, remove container key for neatness.
        if not chat_servers:
            settings.pop("chat.mcp.servers", None)

    return changed

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def _host_for_path(path: Path) -> str | None:
    normalized = str(path).replace("\\", "/")
    if "/Bob-IDE/" in normalized or "/.bob/" in normalized:
        return "bob"
    if "/Code/User/" in normalized or "/Code - Insiders/User/" in normalized:
        return "vscode-copilot"
    return None


def get_settings_paths(selected: set[str] | None = None):
    """Get potential settings paths for the selected VS Code-family hosts."""
    paths = []
    
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA')
        if appdata:
            # Standard VSCode
            paths.append(Path(appdata) / "Code" / "User" / "settings.json")
            # VS Code Insiders
            paths.append(Path(appdata) / "Code - Insiders" / "User" / "settings.json")
            # Bob-IDE (User provided path)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "globalStorage" / "ibm.bob-code" / "settings" / "mcp_settings.json")
            # Bob-IDE (Standard User settings)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "settings.json")
            
    elif os.name == 'posix':  # macOS/Linux
        home = Path.home()
        if os.uname().sysname == 'Darwin':  # macOS
            paths.append(home / "Library" / "Application Support" / "Code" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Code - Insiders" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Bob-IDE" / "User" / "settings.json")
        else:  # Linux
            paths.append(home / ".config" / "Code" / "User" / "settings.json")
            paths.append(home / ".config" / "Code - Insiders" / "User" / "settings.json")
            paths.append(home / ".config" / "Bob-IDE" / "User" / "settings.json")

    selected_hosts = selected or set(VSCODE_FAMILY)
    return [path for path in paths if _host_for_path(path) in selected_hosts]


def get_mcp_json_paths(selected: set[str] | None = None):
    """Get potential VS Code MCP configuration file paths (mcp.json)."""
    if selected is not None and "vscode-copilot" not in selected:
        return []
    paths = []

    if os.name == 'nt':
        appdata = os.environ.get('APPDATA')
        if appdata:
            paths.append(Path(appdata) / "Code" / "User" / "mcp.json")
            paths.append(Path(appdata) / "Code - Insiders" / "User" / "mcp.json")
    elif os.name == 'posix':
        home = Path.home()
        if os.uname().sysname == 'Darwin':
            paths.append(home / "Library" / "Application Support" / "Code" / "User" / "mcp.json")
            paths.append(home / "Library" / "Application Support" / "Code - Insiders" / "User" / "mcp.json")
        else:
            paths.append(home / ".config" / "Code" / "User" / "mcp.json")
            paths.append(home / ".config" / "Code - Insiders" / "User" / "mcp.json")

    return paths


def configure_vscode_mcp_json(
    mcp_json_path: Path,
    elefante_path: Path,
    python_cmd: str,
    *,
    manifest_home: Path,
) -> bool:
    """Add/update the Elefante server config in a VS Code mcp.json file."""
    existed_before = mcp_json_path.exists()
    try:
        if existed_before:
            with open(mcp_json_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {}
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(config, dict):
        return False

    if 'servers' not in config:
        config['servers'] = {}
    if not isinstance(config.get('servers'), dict):
        return False
    entry_path = ("servers", "elefante")
    if 'elefante' in config['servers'] and not is_unchanged_emitted_json_entry(
        mcp_json_path, "vscode-copilot", entry_path, home=manifest_home
    ):
        return False

    config['servers']['elefante'] = {
        "type": "stdio",
        "command": python_cmd,
        "args": ["-m", "src.mcp.stdio_bridge"],
        "env": {
            "PYTHONPATH": str(elefante_path),
            "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
            "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
            "ELEFANTE_CLIENT_TOOL": "vscode-copilot",
            "ANONYMIZED_TELEMETRY": "False",
        },
    }

    try:
        mcp_json_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomically(mcp_json_path, config)
        record_emitted_json_entry(
            mcp_json_path,
            "vscode-copilot",
            entry_path,
            created=not existed_before,
            home=manifest_home,
        )
        return True
    except Exception:
        return False

def configure_mcp(argv: list[str] | None = None):
    """Configure IDE to use Elefante MCP server"""
    
    print("\n" + "=" * 70)
    print("ELEFANTE - IDE MCP Configuration")
    print("=" * 70 + "\n")
    
    # Get current Elefante path (AGNOSTIC)
    # We use the parent of the 'scripts' directory where this script resides
    elefante_path = Path(__file__).resolve().parents[2]
    python_cmd = _infer_repo_python(elefante_path)
    
    print(f"Elefante Location: {elefante_path}")

    import argparse

    parser = argparse.ArgumentParser(description="Configure IDE MCP settings for Elefante")
    parser.add_argument(
        "--vscode",
        choices=["mcp.json", "chat-settings", "both"],
        default="mcp.json",
        help="How to configure VS Code (default: mcp.json).",
    )
    parser.add_argument(
        "--no-clean-duplicates",
        action="store_true",
        help="Do not remove settings-based duplicate servers in VS Code settings.json.",
    )
    parser.add_argument(
        "--write-user-mcp-json",
        action="store_true",
        help=(
            "Compatibility flag (no longer required). The script always writes VS Code user-level mcp.json for global enablement."
        ),
    )
    parser.add_argument(
        "--host",
        choices=tuple(sorted(VSCODE_FAMILY)),
        action="append",
        help="Configure only this detected host. Repeat to select both.",
    )
    args = parser.parse_args(argv)
    selected_hosts = set(args.host or VSCODE_FAMILY)

    configure_vscode_mcp = args.vscode in {"mcp.json", "both"}
    configure_vscode_chat_settings = args.vscode in {"chat-settings", "both"}
    clean_duplicates = not bool(args.no_clean_duplicates)

    # Configure VS Code MCP (mcp.json) when available
    mcp_paths = get_mcp_json_paths(selected_hosts)
    mcp_configured = False
    if configure_vscode_mcp:
        for mcp_path in mcp_paths:
            if mcp_path.parent.exists():
                print(f"\nConfiguring VS Code MCP config: {mcp_path}")
                if configure_vscode_mcp_json(
                    mcp_path,
                    elefante_path,
                    python_cmd,
                    manifest_home=Path.home(),
                ):
                    mcp_configured = True
                else:
                    print(f"Warning: Failed to write {mcp_path}")

        # Warn about duplicate scope definitions (User + Workspace).
        workspace_mcp = elefante_path / ".vscode" / "mcp.json"
        if workspace_mcp.exists():
            print("\nNOTE: Workspace MCP config exists:")
            print(f"  {workspace_mcp}")
            print("If it defines servers.elefante, VS Code will show duplicates.")
            print("Recommendation: keep workspace mcp.json empty and use .vscode/mcp.example.jsonc as a template.")
    
    # Find valid settings files
    potential_paths = get_settings_paths(selected_hosts)
    found_paths = [p for p in potential_paths if p.exists()]
    
    if not found_paths and not mcp_configured:
        print("No compatible IDE settings found!")
        print("Checked locations:")
        for p in potential_paths:
            print(f" - {p}")
        for p in mcp_paths:
            print(f" - {p}")
        return False
        
    if found_paths:
        print(f"Found {len(found_paths)} IDE settings file(s).")
    
    # Configure each found settings file
    for settings_path in found_paths:
        print(f"\nConfiguring: {settings_path}")
        
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Error reading {settings_path}. Skipping.")
            continue
            
        # Determine config structure based on file type
        is_mcp_settings = "mcp_settings.json" in str(settings_path)
        
        # Prepare Elefante config
        elefante_config = {
            "command": python_cmd,
            "args": ["-m", "src.mcp.stdio_bridge"],
            "cwd": str(elefante_path),
            "env": {
                "PYTHONPATH": str(elefante_path),
                "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
                "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
                "ELEFANTE_CLIENT_TOOL": "ibm-bob" if is_mcp_settings else "vscode-copilot",
                "ANONYMIZED_TELEMETRY": "False" # Disable ChromaDB telemetry
            },
            "disabled": False,
            "alwaysAllow": [
                "elefante-Memory",  # consolidated v2.10.0: action=add|search|update|delete|consolidate
                "elefante-GraphConnect",
                "elefante-GraphQuery",
                "elefante-ContextGet",
                "elefante-SessionsList",
                "elefante-SystemStatusGet",
                "elefante-DashboardOpen",
                "elefante-System",
                "elefante-TaskCreate",
                "elefante-TaskUpdate",
                "elefante-TaskGraph",
                "elefante-ETLProcess",
                "elefante-ETLClassify",
            ]
        }
        
        # Inject config
        changed = False
        existed_before = settings_path.exists()
        emitted_surface = None
        emitted_entry_path = None
        removed_owned_entry = False
        if is_mcp_settings:
            # Bob-IDE specific mcp_settings.json structure
            if "mcpServers" not in settings:
                settings["mcpServers"] = {}
            if not isinstance(settings["mcpServers"], dict):
                print("Warning: mcpServers is not an object. Preserving configuration.")
                continue
            entry_path = ("mcpServers", "elefante")
            if "elefante" in settings["mcpServers"] and not is_unchanged_emitted_json_entry(
                settings_path, "ibm-bob", entry_path
            ):
                print("Preserved existing user-managed Bob Elefante registration.")
            else:
                settings["mcpServers"]["elefante"] = elefante_config
                changed = True
                emitted_surface = "ibm-bob"
                emitted_entry_path = entry_path
        else:
            # Standard VSCode settings.json structure
            # Default behavior: avoid duplicating built-in MCP (mcp.json). Only write
            # settings-based config if explicitly requested.
            if _is_vscode_settings_path(settings_path) and mcp_configured and clean_duplicates:
                chat_servers = settings.get("chat.mcp.servers")
                if isinstance(chat_servers, dict) and "elefante" in chat_servers:
                    entry_path = ("chat.mcp.servers", "elefante")
                    if is_unchanged_emitted_json_entry(
                        settings_path, "vscode-copilot", entry_path
                    ):
                        removed = _remove_vscode_chat_server(settings, "elefante")
                        if removed:
                            print("Removed duplicate VS Code settings entry: chat.mcp.servers.elefante")
                            changed = True
                            removed_owned_entry = True
                    else:
                        print("Preserved user-managed VS Code chat Elefante registration; duplicate not removed.")

            if configure_vscode_chat_settings:
                if not settings.get('chat.mcp.gallery.enabled'):
                    settings['chat.mcp.gallery.enabled'] = True

                if 'chat.mcp.servers' not in settings:
                    settings['chat.mcp.servers'] = {}
                if not isinstance(settings['chat.mcp.servers'], dict):
                    print("Warning: chat.mcp.servers is not an object. Preserving configuration.")
                    continue

                # VSCode uses a slightly different format for autoStart
                vscode_config = elefante_config.copy()
                vscode_config["autoStart"] = True
                entry_path = ("chat.mcp.servers", "elefante")
                if "elefante" in settings['chat.mcp.servers'] and not is_unchanged_emitted_json_entry(
                    settings_path, "vscode-copilot", entry_path
                ):
                    print("Preserved existing user-managed VS Code chat Elefante registration.")
                else:
                    settings['chat.mcp.servers']['elefante'] = vscode_config
                    changed = True
                    emitted_surface = "vscode-copilot"
                    emitted_entry_path = entry_path
            
        # Save settings
        if changed:
            print("Saving configuration...")
            write_json_atomically(settings_path, settings, indent=4)
            if removed_owned_entry:
                forget_emitted_file(settings_path)
            if emitted_surface is not None and emitted_entry_path is not None:
                record_emitted_json_entry(
                    settings_path, emitted_surface, emitted_entry_path, created=not existed_before
                )
            
    print("\n" + "="*70)
    print("Configuration complete!")
    print("="*70)
    print("1. Restart your IDE")
    print("2. Elefante will auto-connect from:")
    print(f"   {elefante_path}")
    print("="*70 + "\n")
    
    return True

if __name__ == "__main__":
    try:
        success = configure_mcp()
        if not success:
            sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}\n")
        sys.exit(1)
