import shutil
import time
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

kuzu_path = Path("C:/Users/JaimeSubiabreCistern/.elefante/data/kuzu_db")

print(f"Attempting to delete: {kuzu_path}")

if kuzu_path.exists():
    try:
        # Wait a moment for any locks to release
        time.sleep(2)
        shutil.rmtree(kuzu_path, ignore_errors=True)
        print("✅ Deleted kuzu_db directory")
    except Exception as e:
        print(f"❌ Error deleting: {e}")
        print("Please close any programs using the database and try again")
        exit(1)

# Recreate empty directory
kuzu_path.mkdir(parents=True, exist_ok=True)
print("✅ Created fresh kuzu_db directory")

print("\nNow run: python scripts/init_databases.py")

# Made with Bob
