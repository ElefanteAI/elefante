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

# Test 1: CREATE without properties field
print("Test 1: CREATE without 'properties' field...")
query1 = f"""
CREATE (e:Entity {{
    id: '{test_id}',
    name: 'test_entity',
    type: 'test',
    description: 'test description',
    created_at: '{now}'
}})
"""
try:
    conn.execute(query1)
    print("✅ SUCCESS - CREATE without properties works")
except Exception as e:
    print(f"❌ FAILED: {e}")

# Test 2: CREATE with properties field
print("\nTest 2: CREATE with 'properties' field...")
test_id2 = str(uuid.uuid4())
query2 = f"""
CREATE (e:Entity {{
    id: '{test_id2}',
    name: 'test_entity2',
    type: 'test',
    description: 'test description',
    created_at: '{now}',
    properties: '{{}}'
}})
"""
try:
    conn.execute(query2)
    print("✅ SUCCESS - CREATE with properties works")
except Exception as e:
    print(f"❌ FAILED: {e}")

# Test 3: Check if 'properties' is a reserved word
print("\nTest 3: Using backticks around 'properties'...")
test_id3 = str(uuid.uuid4())
query3 = f"""
CREATE (e:Entity {{
    id: '{test_id3}',
    name: 'test_entity3',
    type: 'test',
    description: 'test description',
    created_at: '{now}',
    `properties`: '{{}}'
}})
"""
try:
    conn.execute(query3)
    print("✅ SUCCESS - Backticks work")
except Exception as e:
    print(f"❌ FAILED: {e}")

print("\nDone!")

# Made with Bob
