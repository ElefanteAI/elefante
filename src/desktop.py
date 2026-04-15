import os
import sys
import json
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

def get_elefante_command():
    if getattr(sys, 'frozen', False):
        return sys.executable, ["--mcp"]
    else:
        # Assuming running from repo root
        return sys.executable, ["-m", "src.main", "--mcp"]

def configure_claude():
    cmd, args = get_elefante_command()
    if sys.platform == 'darwin':
        config_path = Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    elif sys.platform == 'win32':
        config_path = Path(os.environ.get('APPDATA', '')) / "Claude/claude_desktop_config.json"
    else:
        config_path = Path.home() / ".config/Claude/claude_desktop_config.json"

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                try: config = json.load(f)
                except Exception: pass
                
        if "mcpServers" not in config:
            config["mcpServers"] = {}
            
        config["mcpServers"]["elefante"] = {
            "command": cmd,
            "args": args,
            "env": {
                "ANONYMIZED_TELEMETRY": "False"
            }
        }
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
            
        messagebox.showinfo("Success", "Successfully integrated Elefante with Claude Desktop!\nRestart Claude Desktop to use it.")
    except Exception as e:
        messagebox.showerror("Error", f"Failed to configure Claude Desktop:\n{str(e)}")

def get_mcp_json_paths():
    paths = []
    if sys.platform == 'win32':
        appdata = os.environ.get('APPDATA')
        if appdata:
            paths.append(Path(appdata) / "Code/User/mcp.json")
            paths.append(Path(appdata) / "Code - Insiders/User/mcp.json")
            paths.append(Path(appdata) / "Cursor/User/mcp.json")
    else:
        home = Path.home()
        if sys.platform == 'darwin':
            paths.append(home / "Library/Application Support/Code/User/mcp.json")
            paths.append(home / "Library/Application Support/Code - Insiders/User/mcp.json")
            paths.append(home / "Library/Application Support/Cursor/User/mcp.json")
        else:
            paths.append(home / ".config/Code/User/mcp.json")
            paths.append(home / ".config/Code - Insiders/User/mcp.json")
            paths.append(home / ".config/Cursor/User/mcp.json")
    return paths

def configure_vscode():
    cmd, args = get_elefante_command()
    paths = get_mcp_json_paths()
    success_count = 0
    for mcp_path in paths:
        try:
            mcp_path.parent.mkdir(parents=True, exist_ok=True)
            config = {}
            if mcp_path.exists():
                with open(mcp_path, 'r', encoding='utf-8') as f:
                    try: config = json.load(f)
                    except Exception: pass
                    
            if "servers" not in config:
                config["servers"] = {}
                
            config["servers"]["elefante"] = {
                "command": cmd,
                "args": args,
                "env": {
                    "ANONYMIZED_TELEMETRY": "False"
                }
            }
            
            with open(mcp_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            success_count += 1
        except Exception:
            pass
            
    if success_count > 0:
        messagebox.showinfo("Success", f"Successfully integrated Elefante with VS Code / Cursor ({success_count} configs updated)!\nRestart your IDE to use it.")
    else:
        messagebox.showerror("Error", "Could not find VS Code/Cursor installations or failed to write config.")

def run_gui():
    root = tk.Tk()
    root.title("Elefante - The Zero-Friction AI Memory")
    root.geometry("500x350")
    root.eval('tk::PlaceWindow . center')
    
    style = ttk.Style()
    if sys.platform == 'win32':
        try: style.theme_use('clam')
        except Exception: pass
        
    frame = ttk.Frame(root, padding="20")
    frame.pack(fill=tk.BOTH, expand=True)
    
    ttk.Label(frame, text="Elefante Core", font=("Helvetica", 24, "bold")).pack(pady=(10, 5))
    ttk.Label(frame, text="The fastest, 100% local MCP Hybrid Memory Server.", font=("Helvetica", 12)).pack(pady=(0, 20))
    
    ttk.Label(frame, text="One-Click Integrations:", font=("Helvetica", 14, "bold")).pack(anchor="w", pady=(10, 5))
    
    btn_claude = ttk.Button(frame, text="Install to Claude Desktop", command=configure_claude)
    btn_claude.pack(pady=5, ipady=5, fill=tk.X)
    
    btn_vscode = ttk.Button(frame, text="Install to VS Code / Cursor", command=configure_vscode)
    btn_vscode.pack(pady=5, ipady=5, fill=tk.X)
    
    ttk.Label(frame, text="Status: Ready. Run this app anytime to auto-configure your agents.", foreground="gray").pack(side="bottom", pady=20)
    
    root.mainloop()
