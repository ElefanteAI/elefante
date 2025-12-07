"""
Automatic Antigravity MCP Configuration Script
Configures Antigravity IDE to use Elefante MCP server automatically
"""

import json
import os
import sys
import shutil
from pathlib import Path

def get_antigravity_config_path():
    """Get the path to Antigravity's mcp_config.json"""
    # Check the standard location provided by the user
    # /Users/jay/.gemini/antigravity/mcp_config.json
    # We should make this dynamic for the user "jay"
    
    home = Path.home()
    config_path = home / ".gemini" / "antigravity" / "mcp_config.json"
    
    if config_path.exists():
        return config_path
    return None

def configure_mcp():
    """Configure Antigravity to use Elefante MCP server"""
    
    print("\n" + "="*70)
    print("🐘 ELEFANTE - Antigravity MCP Configuration")
    print("="*70 + "\n")
    
    elefante_path = Path(__file__).parent.parent.absolute()
    config_path = get_antigravity_config_path()
    
    if not config_path:
        print("⚠️  Antigravity configuration file not found.")
        print(f"   Expected at: ~/.gemini/antigravity/mcp_config.json")
        return False
        
    print(f"📄 Found Antigravity config: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
    except json.JSONDecodeError:
        print(f"⚠️  Error reading {config_path}. Skipping.")
        return False
    except Exception as e:
        print(f"⚠️  Error accessing {config_path}: {e}")
        return False
        
    # Prepare Elefante config
    # Use absolute path to the current python executable (in .venv)
    elefante_config = {
        "command": sys.executable,
        "args": ["-m", "src.mcp.server"],
        "cwd": str(elefante_path),
        "env": {
            "PYTHONPATH": str(elefante_path),
            "unbuffer": "true" 
        }
    }
    
    # Inject config
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}
        
    settings["mcpServers"]["elefante"] = elefante_config
    
    # Save settings
    print("💾 Saving configuration...")
    # 4. Create backup if exists (Versioning/Rollback)
    if config_path.exists():
        backup_path = config_path.with_suffix('.json.bak')
        try:
            shutil.copy2(config_path, backup_path)
            print(f"📦 Created backup at: {backup_path}")
        except Exception as e:
            print(f"⚠️  Failed to create backup: {e}")

    # 5. Write configuration
    try:
        with open(config_path, "w", encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
        print(f"✅ Antigravity configured successfully at: {config_path}")
        return True
    except PermissionError:
        print("❌ Permission denied writing to config file.")
        print("   This is a known issue in some agentic environments.")
        print("   👇 PLEASE MANUALLY PASTE THIS INTO: " + str(config_path))
        print("\n" + json.dumps(settings, indent=2) + "\n")
        return False
    except Exception as e:
        print(f"❌ Error writing config: {e}")
        return False

if __name__ == "__main__":
    configure_mcp()

