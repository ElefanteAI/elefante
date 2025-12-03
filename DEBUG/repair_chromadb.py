"""
ChromaDB Repair Script - Adds missing 'topic' column
SAFE: Creates backup before modification
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

def repair_chromadb():
    """
    Repairs ChromaDB by adding the missing 'topic' column to collections table.
    Creates a backup before making any changes.
    """
    
    # Paths
    data_dir = Path.home() / ".elefante" / "data" / "chroma"
    db_path = data_dir / "chroma.sqlite3"
    backup_dir = Path.home() / ".elefante" / "backups"
    
    # Validate database exists
    if not db_path.exists():
        print(f"[ERROR] Database not found at: {db_path}")
        return False
    
    print("=" * 80)
    print("CHROMADB REPAIR SCRIPT")
    print("=" * 80)
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
        
        # Verify 'topic' column is missing
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
            print("[INFO] You can now restart the MCP server")
            
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
    print("\n" + "!" * 80)
    print("WARNING: This script will modify your ChromaDB database")
    print("A backup will be created automatically before any changes")
    print("!" * 80)
    
    response = input("\nProceed with repair? (yes/no): ").strip().lower()
    
    if response == 'yes':
        success = repair_chromadb()
        exit(0 if success else 1)
    else:
        print("\n[CANCELLED] Repair cancelled by user")
        exit(0)

# Made with Bob
