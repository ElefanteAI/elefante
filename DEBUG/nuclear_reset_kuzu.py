#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nuclear Reset Script for Kuzu Database
Backs up and removes corrupted kuzu_db file, allowing fresh initialization.
"""

import os
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def nuclear_reset_kuzu():
    """Backup and remove corrupted Kuzu database file."""
    
    # Paths
    data_dir = Path.home() / ".elefante" / "data"
    kuzu_path = data_dir / "kuzu_db"
    
    print("=" * 70)
    print("KUZU DATABASE NUCLEAR RESET")
    print("=" * 70)
    print()
    
    # Check if kuzu_db exists
    if not kuzu_path.exists():
        print(f"✓ No kuzu_db found at: {kuzu_path}")
        print("  Database is ready for fresh initialization.")
        return True
    
    # Check if it's a file (corrupted) or directory (normal)
    if kuzu_path.is_file():
        print(f"[!] CORRUPTION DETECTED: kuzu_db is a FILE (should be directory)")
        print(f"  Path: {kuzu_path}")
        print(f"  Size: {kuzu_path.stat().st_size:,} bytes")
        print()
        
        # Create backup
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = data_dir / f"kuzu_db.corrupted.{timestamp}.backup"
        
        print(f"[1/2] Creating backup...")
        print(f"      From: {kuzu_path}")
        print(f"      To:   {backup_path}")
        
        try:
            shutil.copy2(kuzu_path, backup_path)
            print(f"      [OK] Backup created successfully")
        except Exception as e:
            print(f"      [FAIL] Backup failed: {e}")
            return False
        
        print()
        print(f"[2/2] Removing corrupted file...")
        
        try:
            kuzu_path.unlink()
            print(f"      [OK] Corrupted file removed")
            print()
            print("=" * 70)
            print("SUCCESS: Kuzu database reset complete")
            print("=" * 70)
            print()
            print("Next steps:")
            print("1. Kuzu will auto-create proper directory structure on next init")
            print("2. Run verify_memories.py to test database access")
            print("3. Rebuild graph from ChromaDB memories (43 memories available)")
            return True
            
        except Exception as e:
            print(f"      [FAIL] Removal failed: {e}")
            print()
            print("Manual intervention required:")
            print(f"  del \"{kuzu_path}\"")
            return False
    
    elif kuzu_path.is_dir():
        print(f"[OK] kuzu_db is a directory (correct structure)")
        print(f"  Path: {kuzu_path}")
        print()
        
        # Check for lock file
        lock_file = kuzu_path / ".lock"
        if lock_file.exists():
            print(f"[!] Lock file exists: {lock_file}")
            print("  This indicates another process may be using the database.")
            print("  Or a previous process crashed without cleanup.")
            print()
            print("Options:")
            print("  1. Stop all processes using Elefante")
            print("  2. Manually remove lock file if you're sure no process is using it")
            return False
        else:
            print(f"[OK] No lock file found")
            print("  Database appears ready for use.")
            return True
    
    else:
        print(f"[FAIL] UNKNOWN: kuzu_db exists but is neither file nor directory")
        print(f"  Path: {kuzu_path}")
        print("  Manual investigation required.")
        return False

if __name__ == "__main__":
    success = nuclear_reset_kuzu()
    exit(0 if success else 1)

# Made with Bob
