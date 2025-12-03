"""
Fix ChromaDB segments table - Add missing 'topic' column
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def fix_segments_table():
    """Add topic column to segments table"""
    
    # Paths
    data_dir = Path.home() / ".elefante" / "data" / "chroma"
    db_path = data_dir / "chroma.sqlite3"
    backup_dir = Path.home() / ".elefante" / "backups"
    
    print("=" * 80)
    print("FIXING SEGMENTS TABLE")
    print("=" * 80)
    
    if not db_path.exists():
        print(f"\n[ERROR] Database not found at: {db_path}")
        return False
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"chroma_backup_segments_{timestamp}.sqlite3"
    
    print(f"\n[BACKUP] Creating backup...")
    shutil.copy2(db_path, backup_path)
    print(f"[SUCCESS] Backup: {backup_path}")
    
    # Fix database
    print(f"\n[REPAIR] Connecting to database...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Check segments table
    cursor.execute("PRAGMA table_info(segments);")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    if 'topic' in column_names:
        print("[INFO] 'topic' column already exists in segments table")
        conn.close()
        return True
    
    print("[REPAIR] Adding 'topic' column to segments table...")
    cursor.execute("ALTER TABLE segments ADD COLUMN topic TEXT;")
    conn.commit()
    
    # Verify
    cursor.execute("PRAGMA table_info(segments);")
    columns_after = cursor.fetchall()
    column_names_after = [col[1] for col in columns_after]
    
    if 'topic' in column_names_after:
        print("[SUCCESS] 'topic' column added to segments table!")
        print("\n[SCHEMA] Updated segments table:")
        print("Column ID | Name          | Type")
        print("-" * 50)
        for col in columns_after:
            print(f"{col[0]:9} | {col[1]:13} | {col[2]:7}")
        conn.close()
        print("\n" + "=" * 80)
        print("[SUCCESS] SEGMENTS TABLE REPAIR COMPLETE")
        print("=" * 80)
        return True
    else:
        print("[ERROR] Failed to add 'topic' column")
        conn.close()
        return False

if __name__ == "__main__":
    import sys
    success = fix_segments_table()
    sys.exit(0 if success else 1)

# Made with Bob
