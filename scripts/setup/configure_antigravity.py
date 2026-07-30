# ─────────────────────────────────────────────────────────────────────────────
# NAME    : configure_antigravity.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Write the Antigravity IDE mcp_config.json to wire Elefante as an
#           MCP server in that IDE. Called by install.py; safe to run standalone.
# WHEN    : Initial Antigravity IDE setup, or after moving the repo to a new
#           path (the config embeds the absolute Python path). Re-run if
#           Antigravity stops seeing Elefante tools after a move or reinstall.
# USAGE   : python scripts/setup/configure_antigravity.py
# NOTES   : Writes to ~/.gemini/antigravity/mcp_config.json. If both this and
#           configure_vscode_bob.py are run, each IDE gets its own config file —
#           there is no conflict. Safe to re-run; user-owned entries are preserved.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""
Automatic Antigravity MCP Configuration Script
Configures Antigravity IDE to use Elefante MCP server automatically
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_SETUP_DIR = str(Path(__file__).resolve().parent)
if _SETUP_DIR not in sys.path:
    sys.path.insert(0, _SETUP_DIR)

from install_manifest import (
    is_unchanged_emitted_json_entry,
    record_emitted_json_entry,
    write_json_atomically,
)


def _infer_repo_python(elefante_path: Path) -> str:
    if sys.platform == "win32":
        candidate = elefante_path / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = elefante_path / ".venv" / "bin" / "python"
    if candidate.exists():
        return str(candidate)
    return sys.executable

def get_antigravity_config_path():
    """Get the path to Antigravity's mcp_config.json"""
    # Check the standard location provided by the user
    # /Users/jay/.gemini/antigravity/mcp_config.json
    # We should make this dynamic for the user "jay"
    
    home = Path.home()
    return home / ".gemini" / "antigravity" / "mcp_config.json"


def host_is_detected() -> bool:
    """Return true only when Antigravity has created its user configuration root."""
    return get_antigravity_config_path().parent.is_dir()


def configure_mcp(argv: list[str] | None = None):
    """Configure Antigravity to use Elefante MCP server"""
    
    print("\n" + "=" * 70)
    print("ELEFANTE - Antigravity MCP Configuration")
    print("=" * 70 + "\n")
    
    elefante_path = Path(__file__).resolve().parents[2]
    config_path = get_antigravity_config_path()

    existed_before = config_path.exists()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not existed_before:
        print("Antigravity configuration file not found.")
        print(f"Creating: {config_path}")
        settings = {}
    else:
        print(f"Found Antigravity config: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {config_path}. Skipping.")
            return False
        except Exception as e:
            print(f"Error accessing {config_path}: {e}")
            return False
        
    # Prepare Elefante config
    # Use absolute path to the current python executable (in .venv)
    elefante_config = {
        "command": _infer_repo_python(elefante_path),
        "args": ["-m", "src.mcp.stdio_bridge"],
        "cwd": str(elefante_path),
        "env": {
            "PYTHONPATH": str(elefante_path),
            "ELEFANTE_CONFIG_PATH": str(elefante_path / "config.yaml"),
            "ELEFANTE_DAEMON_URL": "http://127.0.0.1:8765/mcp/",
            "ELEFANTE_CLIENT_TOOL": "antigravity",
            "ANONYMIZED_TELEMETRY": "False",
            "unbuffer": "true",
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
        ],
    }
    
    # Inject config
    if not isinstance(settings, dict):
        print(f"Error reading {config_path}: expected a JSON object. Skipping.")
        return False
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}
    if not isinstance(settings.get("mcpServers"), dict):
        print(f"Error reading {config_path}: mcpServers is not an object. Skipping.")
        return False
    entry_path = ("mcpServers", "elefante")
    if "elefante" in settings["mcpServers"] and not is_unchanged_emitted_json_entry(
        config_path, "antigravity", entry_path
    ):
        print("Preserved existing user-managed Antigravity Elefante registration.")
        return False
        
    settings["mcpServers"]["elefante"] = elefante_config
    
    # Save settings atomically. Ownership-aware writes preserve user-managed
    # entries, so creating an untracked full-file backup would add stale data
    # without improving recovery.
    print("Saving configuration...")
    try:
        write_json_atomically(config_path, settings)
        record_emitted_json_entry(
            config_path,
            "antigravity",
            entry_path,
            created=not existed_before,
        )
        print(f"Antigravity configured successfully at: {config_path}")
        return True
    except PermissionError:
        print("Permission denied writing to config file.")
        print("   This is a known issue in some agentic environments.")
        print("   PLEASE MANUALLY PASTE THIS INTO: " + str(config_path))
        print("\n" + json.dumps(settings, indent=2) + "\n")
        return False
    except Exception as e:
        print(f"Error writing config: {e}")
        return False

if __name__ == "__main__":
    configure_mcp()
