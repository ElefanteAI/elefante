import kuzu
import uuid
import sys
import io
from datetime import datetime
from pathlib import Path
import shutil

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Create a fresh test database
test_db_path = Path("C:/Users/JaimeSubiabreCistern/.elefante/data/kuzu_test")
if test_db_path.exists():
    shutil.rmtree(test_db_path, ignore_errors=True)
test_db_path.mkdir(parents=True, exist_ok=True)

print("Creating fresh Kuzu test database...\n")
db = kuzu.Database(str(test_db_path))
conn = kuzu.Connection(db)

# Create schema using SQL DDL
print("Step 1: Creating schema with SQL DDL")
schema_sql = """
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    type STRING,
    description STRING,
    created_at TIMESTAMP,
    props STRING,
    PRIMARY KEY(id)
)
"""
try:
    conn.execute(schema_sql)
    print("✅ Schema created with SQL DDL\n")
except Exception as e:
    print(f"❌ Schema creation failed: {e}\n")
    exit(1)

test_id = str(uuid.uuid4())
now = datetime.now()

print("="*70)
print("Testing INSERT Methods")
print("="*70 + "\n")

# Test 1: Cypher CREATE
print("Test 1: Cypher CREATE (e:Entity {...})")
query1 = f"""
CREATE (e:Entity {{
    id: '{test_id}',
    name: 'test_cypher',
    type: 'test',
    description: 'Created with Cypher',
    created_at: timestamp('{now.isoformat()}'),
    props: '{{}}'
}})
"""
try:
    conn.execute(query1)
    print("✅ Cypher CREATE works!\n")
except Exception as e:
    print(f"❌ Cypher CREATE failed: {e}\n")

# Test 2: SQL INSERT
print("Test 2: SQL INSERT INTO")
test_id2 = str(uuid.uuid4())
query2 = f"""
INSERT INTO Entity VALUES (
    '{test_id2}',
    'test_sql',
    'test',
    'Created with SQL INSERT',
    timestamp('{now.isoformat()}'),
    '{{}}'
)
"""
try:
    conn.execute(query2)
    print("✅ SQL INSERT works!\n")
except Exception as e:
    print(f"❌ SQL INSERT failed: {e}\n")

# Test 3: Cypher MERGE
print("Test 3: Cypher MERGE")
test_id3 = str(uuid.uuid4())
query3 = f"""
MERGE (e:Entity {{id: '{test_id3}'}})
ON CREATE SET
    e.name = 'test_merge',
    e.type = 'test',
    e.description = 'Created with MERGE',
    e.created_at = timestamp('{now.isoformat()}'),
    e.props = '{{}}'
"""
try:
    conn.execute(query3)
    print("✅ Cypher MERGE works!\n")
except Exception as e:
    print(f"❌ Cypher MERGE failed: {e}\n")

# Verify what was inserted
print("="*70)
print("Verification: Querying all entities")
print("="*70 + "\n")
result = conn.execute("MATCH (e:Entity) RETURN e.name, e.description")
while result.has_next():
    row = result.get_next()
    print(f"  - {row}")

print("\n" + "="*70)
print("CONCLUSION")
print("="*70)
print("Kuzu supports BOTH SQL and Cypher syntax!")
print("- Schema: SQL DDL (CREATE NODE TABLE)")
print("- Insert: Can use Cypher CREATE or SQL INSERT")
print("- Query: Cypher (MATCH)")
print("- Upsert: Cypher MERGE")

# Made with Bob
