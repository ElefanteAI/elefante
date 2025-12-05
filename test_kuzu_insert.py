import kuzu
import uuid
import sys
import io
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

db = kuzu.Database('C:/Users/JaimeSubiabreCistern/.elefante/data/kuzu_db')
conn = kuzu.Connection(db)

test_id = str(uuid.uuid4())
now = datetime.now().isoformat()

print("Testing different insert syntaxes in Kuzu:\n")

# Test 1: Cypher CREATE (what we're using)
print("Test 1: Cypher CREATE syntax")
query1 = f"""
CREATE (e:Entity {{
    id: '{test_id}',
    name: 'test1',
    type: 'test',
    description: 'test',
    created_at: '{now}',
    props: '{{}}'
}})
"""
try:
    conn.execute(query1)
    print("✅ Cypher CREATE works\n")
except Exception as e:
    print(f"❌ Cypher CREATE failed: {e}\n")

# Test 2: SQL-style INSERT (Kuzu's native way?)
print("Test 2: SQL INSERT syntax")
test_id2 = str(uuid.uuid4())
query2 = f"""
INSERT INTO Entity VALUES (
    '{test_id2}',
    'test2',
    'test',
    'test',
    '{now}',
    '{{}}'
)
"""
try:
    conn.execute(query2)
    print("✅ SQL INSERT works\n")
except Exception as e:
    print(f"❌ SQL INSERT failed: {e}\n")

# Test 3: COPY FROM (bulk insert)
print("Test 3: Check what Kuzu actually expects")
print("Let's see if we can query the schema...")
try:
    result = conn.execute("CALL table_info('Entity')")
    print("✅ Schema info:")
    while result.has_next():
        print(f"  {result.get_next()}")
except Exception as e:
    print(f"❌ Schema query failed: {e}")

print("\nDone!")

# Made with Bob
