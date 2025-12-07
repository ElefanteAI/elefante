import os
import time
import subprocess
import shutil
from pathlib import Path

def unlock_database():
    """
    Force unlock the Kuzu database by killing Python processes and removing .lock file.
    Follows Law #2 and Prevention Protocols from DATABASE_NEURAL_REGISTER.md
    """
    print("🔒 KUZU DATABASE UNLOCKER 🔒")
    print("----------------------------")
    
    # 1. Kill MCP server processes specifically
    print(f"1. Attempting to stop Elefante MCP server processes...")
    try:
        # Pkill is standard on Mac/Linux
        # Targeting the specific module execution
        subprocess.run(["pkill", "-f", "src.mcp.server"], check=False)
        print("   ✓ Sent kill signal to src.mcp.server processes.")
    except FileNotFoundError:
        print("   ⚠ pkill command not found. Skipping process kill.")
    except Exception as e:
        print(f"   ⚠ Error killing processes: {e}")

    time.sleep(1) # Wait for OS to release handles

    # 2. Find and remove log file
    # We need to find where the DB is. Using default location or looking at config
    # hardcoded for now based on standard Elefante path, or trying to find it.
    
    # Assuming standard path from register: $env:USERPROFILE\.elefante\data\kuzu_db
    # But checking multiple potential locations just in case
    
    potential_paths = [
        Path.home() / ".elefante" / "data" / "kuzu_db",
        Path("kuzu_db").absolute(), 
        Path("/Volumes/X10Pro/X10-2025/Documents2025/Elefante_early_dec2025/kuzu_db")
    ]
    
    lock_removed = False
    
    for db_path in potential_paths:
        lock_file = db_path / ".lock"
        if lock_file.exists():
            print(f"2. Found lock file at: {lock_file}")
            try:
                os.remove(lock_file)
                print("   ✓ Lock file REMOVED.")
                lock_removed = True
            except Exception as e:
                print(f"   ❌ Failed to remove lock: {e}")
        else:
             # Check if it is a file (corruption check Law #4)
             if db_path.exists() and db_path.is_file():
                 print(f"   ❌ CRITICAL: {db_path} is a FILE, not a directory! Database corrupt.")
                 print("      Please run init_databases.py to reset.")
    
    if not lock_removed:
        print("2. No lock file found in standard locations.")
        
    print("\n✅ Database should be unlocked.")
    print("   You may now restart the MCP server or run verify scripts.")

if __name__ == "__main__":
    try:
        unlock_database()
    except Exception as e:
        print(f"\n❌ Script failed: {e}")
