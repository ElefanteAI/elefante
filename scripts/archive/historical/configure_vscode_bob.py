"""Automatic VS Code/Bob MCP configuration.

Configures VS Code (including Insiders) and Bob-IDE to use the Elefante MCP server.

Important:
- VS Code can load MCP servers from **mcp.json** (built-in MCP).
- Some builds/extensions also support **chat.mcp.servers** in settings.json.

If you configure BOTH, VS Code may show two Elefante entries.
Default behavior of this script is to configure **mcp.json** and remove
settings-based duplicates for VS Code.
"""

import json
import os
import sys
import io
from pathlib import Path


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

def get_settings_paths():
    """Get potential settings.json paths for VS Code, Cursor, and Bob-IDE."""
    paths = []
    
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA')
        if appdata:
            # Standard VSCode
            paths.append(Path(appdata) / "Code" / "User" / "settings.json")
            # VS Code Insiders
            paths.append(Path(appdata) / "Code - Insiders" / "User" / "settings.json")
            # Cursor
            paths.append(Path(appdata) / "Cursor" / "User" / "settings.json")
            # Bob-IDE (User provided path)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "globalStorage" / "ibm.bob-code" / "settings" / "mcp_settings.json")
            # Bob-IDE (Standard User settings)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "settings.json")
            
    elif os.name == 'posix':  # macOS/Linux
        home = Path.home()
        if os.uname().sysname == 'Darwin':  # macOS
            paths.append(home / "Library" / "Application Support" / "Code" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Code - Insiders" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Cursor" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Bob-IDE" / "User" / "settings.json")
        else:  # Linux
            paths.append(home / ".config" / "Code" / "User" / "settings.json")
            paths.append(home / ".config" / "Code - Insiders" / "User" / "settings.json")
            paths.append(home / ".config" / "Cursor" / "User" / "settings.json")
            paths.append(home / ".config" / "Bob-IDE" / "User" / "settings.json")
            
    return paths


def get_mcp_json_paths():
    """Get potential VS Code MCP configuration file paths (mcp.json)."""
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


def configure_vscode_mcp_json(mcp_json_path: Path, elefante_path: Path, python_cmd: str) -> bool:
    """Add/update the Elefante server config in a VS Code mcp.json file."""
    try:
        mcp_json_path.parent.mkdir(parents=True, exist_ok=True)
        if mcp_json_path.exists():
            with open(mcp_json_path, 'r', encoding='utf-8') as f:
                config = json.load(f) or {}
        else:
            config = {}
    except Exception:
        config = {}

    if not isinstance(config, dict):
        config = {}

    if 'servers' not in config or not isinstance(config.get('servers'), dict):
        config['servers'] = {}

    config['servers']['elefante'] = {
        "type": "stdio",
        "command": python_cmd,
        "args": ["-m", "src.mcp.server"],
        "env": {
            "PYTHONPATH": str(elefante_path),
            "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
            "ANONYMIZED_TELEMETRY": "False",
        },
    }

    try:
        with open(mcp_json_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
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
    elefante_path = Path(__file__).parent.parent.absolute()
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
    args = parser.parse_args(argv)

    configure_vscode_mcp = args.vscode in {"mcp.json", "both"}
    configure_vscode_chat_settings = args.vscode in {"chat-settings", "both"}
    clean_duplicates = not bool(args.no_clean_duplicates)

    # Configure VS Code MCP (mcp.json) when available
    mcp_paths = get_mcp_json_paths()
    mcp_configured = False
    if configure_vscode_mcp:
        for mcp_path in mcp_paths:
            if mcp_path.parent.exists():
                print(f"\nConfiguring VS Code MCP config: {mcp_path}")
                if configure_vscode_mcp_json(mcp_path, elefante_path, python_cmd):
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
    potential_paths = get_settings_paths()
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
            "args": ["-m", "src.mcp.server"],
            "cwd": str(elefante_path),
            "env": {
                "PYTHONPATH": str(elefante_path),
                "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
                "ANONYMIZED_TELEMETRY": "False" # Disable ChromaDB telemetry
            },
            "disabled": False,
            "alwaysAllow": [
                "elefanteMemorySearch",
                "elefanteMemoryAdd",
                "elefanteSystemStatusGet",
                "elefanteDashboardOpen",
                "elefanteGraphConnect",
                "elefanteContextGet",
                "elefanteGraphEntityCreate",
                "elefanteGraphRelationshipCreate",
                "elefanteGraphQuery",
                "elefanteSystemEnable",
                "elefanteSystemDisable",
                "elefanteSessionsList",
                "elefanteMemoryListAll",
                "elefanteMemoryConsolidate",
                "elefanteMemoryMigrateToV3",
            ]
        }
        
        # Inject config
        if is_mcp_settings:
            # Bob-IDE specific mcp_settings.json structure
            if "mcpServers" not in settings:
                settings["mcpServers"] = {}
            settings["mcpServers"]["elefante"] = elefante_config
        else:
            # Standard VSCode settings.json structure
            # Default behavior: avoid duplicating built-in MCP (mcp.json). Only write
            # settings-based config if explicitly requested.
            if _is_vscode_settings_path(settings_path) and mcp_configured and clean_duplicates:
                removed = _remove_vscode_chat_server(settings, "elefante")
                if removed:
                    print("Removed duplicate VS Code settings entry: chat.mcp.servers.elefante")

            if configure_vscode_chat_settings:
                if not settings.get('chat.mcp.gallery.enabled'):
                    settings['chat.mcp.gallery.enabled'] = True

                if 'chat.mcp.servers' not in settings:
                    settings['chat.mcp.servers'] = {}

                # VSCode uses a slightly different format for autoStart
                vscode_config = elefante_config.copy()
                vscode_config["autoStart"] = True
                settings['chat.mcp.servers']['elefante'] = vscode_config
            
        # Save settings
        print("Saving configuration...")
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
            
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
