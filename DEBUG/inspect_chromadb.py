"""
Emergency ChromaDB metadata inspector
Directly queries the SQLite database to understand schema corruption
"""

import sqlite3
import json
from pathlib import Path
import sys

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

def inspect_chromadb():
    db_path = Path.home() / ".elefante" / "data" / "chroma" / "chroma.sqlite3"
    
    if not db_path.exists():
        print(f"[ERROR] Database not found at: {db_path}")
        return
    
    print(f"[INFO] Inspecting: {db_path}")
    print("=" * 80)
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all tables
        print("\n[TABLES] TABLES IN DATABASE:")
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
        
        # Inspect collections table schema
        print("\n[SCHEMA] COLLECTIONS TABLE SCHEMA:")
        cursor.execute("PRAGMA table_info(collections);")
        columns = cursor.fetchall()
        
        print("\nColumn ID | Name          | Type    | NotNull | Default | PK")
        print("-" * 70)
        for col in columns:
            print(f"{col[0]:9} | {col[1]:13} | {col[2]:7} | {col[3]:7} | {col[4] or 'NULL':7} | {col[5]}")
        
        # Check if 'topic' column exists
        column_names = [col[1] for col in columns]
        has_topic = 'topic' in column_names
        
        print(f"\n[CHECK] 'topic' column exists: {has_topic}")
        
        # Get collections data
        print("\n[DATA] COLLECTIONS DATA:")
        cursor.execute("SELECT * FROM collections;")
        collections = cursor.fetchall()
        
        if collections:
            print(f"\nFound {len(collections)} collection(s):")
            for i, coll in enumerate(collections, 1):
                print(f"\n  Collection {i}:")
                for j, col_name in enumerate(column_names):
                    value = coll[j]
                    if isinstance(value, str) and len(value) > 100:
                        value = value[:100] + "..."
                    print(f"    {col_name}: {value}")
        else:
            print("  No collections found")
        
        # Check for other relevant tables
        print("\n[TABLES] OTHER RELEVANT TABLES:")
        
        for table_name in ['embeddings', 'segments', 'collections_metadata']:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
                count = cursor.fetchone()[0]
                print(f"  {table_name}: {count} rows")
            except sqlite3.OperationalError:
                print(f"  {table_name}: Table does not exist")
        
        conn.close()
        
        print("\n" + "=" * 80)
        print("[SUCCESS] Inspection complete")
        
        # Provide diagnosis
        print("\n[DIAGNOSIS]:")
        if not has_topic:
            print("  [WARNING] 'topic' column is MISSING from collections table")
            print("  This is causing the 'no such column: collections.topic' error")
            print("\n  RECOMMENDED FIX:")
            print("  ALTER TABLE collections ADD COLUMN topic TEXT;")
        else:
            print("  [OK] 'topic' column exists - error may be elsewhere")
        
    except Exception as e:
        print(f"\n[ERROR] Error inspecting database: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    inspect_chromadb()

# Made with Bob
