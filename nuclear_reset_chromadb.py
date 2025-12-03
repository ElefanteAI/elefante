#!/usr/bin/env python3
"""
Nuclear reset of ChromaDB - Delete and recreate collection
This will lose all 43 existing memories but fix the search issue
"""

import asyncio
import shutil
from pathlib import Path
from datetime import datetime

async def nuclear_reset():
    """Backup and reset ChromaDB"""
    
    chroma_dir = Path.home() / ".elefante" / "data" / "chroma"
    
    print("=" * 70)
    print("CHROMADB NUCLEAR RESET")
    print("=" * 70)
    print()
    
    if not chroma_dir.exists():
        print(f"✓ ChromaDB directory doesn't exist: {chroma_dir}")
        print("  Nothing to reset.")
        return True
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = chroma_dir.parent / f"chroma_backup_{timestamp}"
    
    print(f"[1/3] Creating backup...")
    print(f"      From: {chroma_dir}")
    print(f"      To:   {backup_dir}")
    
    try:
        shutil.copytree(chroma_dir, backup_dir)
        print(f"      [OK] Backup created")
    except Exception as e:
        print(f"      [FAIL] Backup failed: {e}")
        return False
    
    print()
    print(f"[2/3] Removing ChromaDB directory...")
    
    try:
        shutil.rmtree(chroma_dir)
        print(f"      [OK] Directory removed")
    except Exception as e:
        print(f"      [FAIL] Removal failed: {e}")
        return False
    
    print()
    print(f"[3/3] Testing reinitialization...")
    
    try:
        from src.core.vector_store import get_vector_store
        vs = get_vector_store()
        print(f"      [OK] VectorStore reinitialized")
        print(f"      Collection will be created on first use")
    except Exception as e:
        print(f"      [FAIL] Reinitialization failed: {e}")
        return False
    
    print()
    print("=" * 70)
    print("SUCCESS: ChromaDB reset complete")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. ChromaDB will auto-create collection on first memory add")
    print("2. All new memories will use V2 schema")
    print("3. Search should work properly now")
    print(f"4. Old data backed up to: {backup_dir}")
    
    return True

if __name__ == "__main__":
    success = asyncio.run(nuclear_reset())
    exit(0 if success else 1)

# Made with Bob
