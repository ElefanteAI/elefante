"""
Automatic VSCode/Bob MCP Configuration Script
Configures VSCode (Bob fork) to use Elefante MCP server automatically
"""

import json
import os
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def get_settings_paths():
    """Get potential settings.json paths for VSCode and Bob-IDE"""
    paths = []
    
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA')
        if appdata:
            # Standard VSCode
            paths.append(Path(appdata) / "Code" / "User" / "settings.json")
            # Bob-IDE (User provided path)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "globalStorage" / "ibm.bob-code" / "settings" / "mcp_settings.json")
            # Bob-IDE (Standard User settings)
            paths.append(Path(appdata) / "Bob-IDE" / "User" / "settings.json")
            
    elif os.name == 'posix':  # macOS/Linux
        home = Path.home()
        if os.uname().sysname == 'Darwin':  # macOS
            paths.append(home / "Library" / "Application Support" / "Code" / "User" / "settings.json")
            paths.append(home / "Library" / "Application Support" / "Bob-IDE" / "User" / "settings.json")
        else:  # Linux
            paths.append(home / ".config" / "Code" / "User" / "settings.json")
            paths.append(home / ".config" / "Bob-IDE" / "User" / "settings.json")
            
    return paths

def configure_mcp():
    """Configure IDE to use Elefante MCP server"""
    
    print("\n" + "="*70)
    print("🐘 ELEFANTE - IDE MCP Configuration")
    print("="*70 + "\n")
    
    # Get current Elefante path (AGNOSTIC)
    # We use the parent of the 'scripts' directory where this script resides
    elefante_path = Path(__file__).parent.parent.absolute()
    
    print(f"📁 Elefante Location: {elefante_path}")
    
    # Find valid settings files
    potential_paths = get_settings_paths()
    found_paths = [p for p in potential_paths if p.exists()]
    
    if not found_paths:
        print("❌ No compatible IDE settings found!")
        print("Checked locations:")
        for p in potential_paths:
            print(f" - {p}")
        return False
        
    print(f"✅ Found {len(found_paths)} configuration file(s).")
    
    # Configure each found settings file
    for settings_path in found_paths:
        print(f"\n📄 Configuring: {settings_path}")
        
        try:
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        except json.JSONDecodeError:
            print(f"⚠️  Error reading {settings_path}. Skipping.")
            continue
            
        # Determine config structure based on file type
        is_mcp_settings = "mcp_settings.json" in str(settings_path)
        
        # Prepare Elefante config
        elefante_config = {
            "command": sys.executable,
            "args": ["-m", "src.mcp.server"],
            "cwd": str(elefante_path),
            "env": {
                "PYTHONPATH": str(elefante_path),
                "ANONYMIZED_TELEMETRY": "False" # Disable ChromaDB telemetry
            },
            "disabled": False,
            "alwaysAllow": [
                "searchMemories", "addMemory", "getStats", 
                "getContext", "createEntity", "createRelationship", "queryGraph"
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
            if not settings.get('chat.mcp.gallery.enabled'):
                settings['chat.mcp.gallery.enabled'] = True
                
            if 'chat.mcp.servers' not in settings:
                settings['chat.mcp.servers'] = {}
            
            # VSCode uses a slightly different format for autoStart
            vscode_config = elefante_config.copy()
            vscode_config["autoStart"] = True
            settings['chat.mcp.servers']['elefante'] = vscode_config
            
        # Save settings
        print("💾 Saving configuration...")
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=4)
            
    print("\n" + "="*70)
    print("✅ Configuration complete!")
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
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)
