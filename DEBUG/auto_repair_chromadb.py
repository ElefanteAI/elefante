"""
Autonomous ChromaDB Repair - No user input required
Adds missing 'topic' column to fix corruption
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
import sys

def auto_repair_chromadb():
    """
    Automatically repairs ChromaDB by adding the missing 'topic' column.
    Creates backup before making changes.
    """
    
    # Paths
    data_dir = Path.home() / ".elefante" / "data" / "chroma"
    db_path = data_dir / "chroma.sqlite3"
    backup_dir = Path.home() / ".elefante" / "backups"
    
    print("=" * 80)
    print("AUTONOMOUS CHROMADB REPAIR")
    print("=" * 80)
    
    # Validate database exists
    if not db_path.exists():
        print(f"\n[ERROR] Database not found at: {db_path}")
        return False
    
    print(f"\n[INFO] Database: {db_path}")
    print(f"[INFO] Database size: {db_path.stat().st_size / 1024:.2f} KB")
    
    # Create backup
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"chroma_backup_{timestamp}.sqlite3"
    
    print(f"\n[BACKUP] Creating backup at: {backup_path}")
    try:
        shutil.copy2(db_path, backup_path)
        print(f"[SUCCESS] Backup created successfully")
        print(f"[INFO] Backup size: {backup_path.stat().st_size / 1024:.2f} KB")
    except Exception as e:
        print(f"[ERROR] Failed to create backup: {e}")
        return False
    
    # Connect to database
    print(f"\n[REPAIR] Connecting to database...")
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if 'topic' column already exists
        cursor.execute("PRAGMA table_info(collections);")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'topic' in column_names:
            print("[INFO] 'topic' column already exists - no repair needed")
            conn.close()
            return True
        
        print("[REPAIR] 'topic' column is missing - adding it now...")
        
        # Add the missing column
        cursor.execute("ALTER TABLE collections ADD COLUMN topic TEXT;")
        conn.commit()
        
        # Verify the fix
        cursor.execute("PRAGMA table_info(collections);")
        columns_after = cursor.fetchall()
        column_names_after = [col[1] for col in columns_after]
        
        if 'topic' in column_names_after:
            print("[SUCCESS] 'topic' column added successfully!")
            
            # Show updated schema
            print("\n[SCHEMA] Updated collections table:")
            print("Column ID | Name          | Type    | NotNull | Default | PK")
            print("-" * 70)
            for col in columns_after:
                print(f"{col[0]:9} | {col[1]:13} | {col[2]:7} | {col[3]:7} | {col[4] or 'NULL':7} | {col[5]}")
            
            conn.close()
            
            print("\n" + "=" * 80)
            print("[SUCCESS] REPAIR COMPLETED SUCCESSFULLY")
            print("=" * 80)
            print(f"\n[INFO] Backup preserved at: {backup_path}")
            print("[INFO] Database is now ready for use")
            
            return True
        else:
            print("[ERROR] Failed to add 'topic' column")
            conn.close()
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Repair failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Restore from backup
        print(f"\n[RESTORE] Attempting to restore from backup...")
        try:
            shutil.copy2(backup_path, db_path)
            print("[SUCCESS] Database restored from backup")
        except Exception as restore_error:
            print(f"[ERROR] Failed to restore backup: {restore_error}")
            print(f"[CRITICAL] Manual restore required from: {backup_path}")
        
        return False

if __name__ == "__main__":
    success = auto_repair_chromadb()
    sys.exit(0 if success else 1)

# Made with Bob
