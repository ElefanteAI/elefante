"""
Remove Kuzu database lock file
"""

from pathlib import Path
import sys

def remove_lock():
    """Remove stale Kuzu lock file"""
    
    lock_path = Path.home() / ".elefante" / "data" / "kuzu_db" / ".lock"
    
    print(f"Checking for lock file: {lock_path}")
    
    if not lock_path.exists():
        print("[INFO] No lock file found - database is not locked")
        return True
    
    print(f"[FOUND] Lock file exists")
    print(f"[INFO] File size: {lock_path.stat().st_size} bytes")
    print(f"[INFO] Last modified: {lock_path.stat().st_mtime}")
    
    try:
        lock_path.unlink()
        print("[SUCCESS] Lock file removed")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to remove lock: {e}")
        return False

if __name__ == "__main__":
    success = remove_lock()
    sys.exit(0 if success else 1)

# Made with Bob
