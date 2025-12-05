# Kuzu Reserved Words Issue - Critical Bug Documentation

**Date:** 2025-12-04  
**Severity:** HIGH  
**Status:** FIXED  
**Component:** Graph Store (Kuzu Database)

---

## 🔴 The Problem

Elefante's graph store was failing with this error:
```
RuntimeError: Binder exception: Cannot find property properties for e.
```

This occurred when trying to create Entity nodes in the Kuzu graph database.

---

## 🔬 Root Cause Analysis

### The Anomaly: Kuzu's Hybrid Syntax

Kuzu uses a **hybrid approach** combining SQL and Cypher:

1. **Schema Definition (SQL DDL)**
   ```sql
   CREATE NODE TABLE Entity(
       id STRING,
       name STRING,
       properties STRING,  -- ❌ THIS IS THE PROBLEM
       PRIMARY KEY(id)
   )
   ```
   - Uses SQL-like syntax
   - Defines table structure
   - Works fine with `properties` as column name

2. **Data Operations (Cypher)**
   ```cypher
   CREATE (e:Entity {
       id: 'abc123',
       name: 'test',
       properties: '{}'  -- ❌ FAILS HERE
   })
   ```
   - Uses Cypher syntax
   - `properties` is a RESERVED WORD in Cypher
   - Cannot be used as property name in CREATE statements

### Why This Is Confusing

The schema accepts `properties` as a column name (SQL), but you cannot insert data into it (Cypher). This creates a **semantic mismatch** between schema and operations.

---

## 🧪 Proof of Concept

Created `test_kuzu_syntax.py` to verify:

```python
# Schema with 'props' (renamed from 'properties')
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    props STRING,  -- ✅ NOT a reserved word
    PRIMARY KEY(id)
)

# Test 1: Cypher CREATE with 'properties'
CREATE (e:Entity {properties: '{}'})
# Result: ❌ FAILED - "Cannot find property properties"

# Test 2: Cypher CREATE with 'props'
CREATE (e:Entity {props: '{}'})
# Result: ✅ SUCCESS

# Test 3: SQL INSERT
INSERT INTO Entity VALUES (...)
# Result: ❌ NOT SUPPORTED - Kuzu only accepts Cypher for DML
```

---

## ✅ The Fix

### 1. Schema Change
**File:** `src/core/graph_store.py` (Line 172-179)

```python
# BEFORE (BROKEN)
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    type STRING,
    description STRING,
    created_at TIMESTAMP,
    properties STRING,  # ❌ Reserved word
    PRIMARY KEY(id)
)

# AFTER (FIXED)
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    type STRING,
    description STRING,
    created_at TIMESTAMP,
    props STRING,  # ✅ Not reserved
    PRIMARY KEY(id)
)
```

### 2. Query Change
**File:** `src/core/graph_store.py` (Line 268-276)

```python
# BEFORE (BROKEN)
query = f"""
    CREATE (e:Entity {{
        id: '{str(entity.id)}',
        name: '{escape_string(entity.name)}',
        properties: '{props_json}'  # ❌ Reserved word
    }})
"""

# AFTER (FIXED)
query = f"""
    CREATE (e:Entity {{
        id: '{str(entity.id)}',
        name: '{escape_string(entity.name)}',
        props: '{props_json}'  # ✅ Not reserved
    }})
"""
```

### 3. Database Reset Required

After schema changes, the database must be completely recreated:

```bash
# Remove old database
python reset_kuzu_schema.py

# Reinitialize with new schema
python scripts/init_databases.py
```

---

## 📚 Lessons Learned

### 1. Kuzu's Dual Nature

Kuzu is NOT purely SQL or purely Cypher. It's a hybrid:

| Operation | Syntax | Example |
|-----------|--------|---------|
| Schema | SQL DDL | `CREATE NODE TABLE` |
| Insert | Cypher | `CREATE (n:Label {...})` |
| Query | Cypher | `MATCH (n) RETURN n` |
| Update | Cypher | `MATCH (n) SET n.prop = value` |
| Upsert | Cypher | `MERGE (n:Label {id: 'x'})` |

### 2. Reserved Words Are Context-Dependent

A word can be:
- ✅ Valid as SQL column name
- ❌ Reserved in Cypher operations

**Known Cypher Reserved Words to Avoid:**
- `properties` (most critical)
- `type` (use with caution)
- `id` (use with caution)
- `label`
- `relationship`
- `node`
- `path`

### 3. Schema-Operation Mismatch

The schema definition language (SQL) and operation language (Cypher) have different rules. Always test that:
1. Schema accepts the column name
2. Cypher operations can use the property name

### 4. String Interpolation vs Parameters

We switched from parameterized queries to string interpolation because:
- Kuzu had issues with parameter binding for property names
- String interpolation works reliably
- Must escape single quotes: `str.replace("'", "\\'")`

---

## 🔧 Prevention Strategy

### For Future Development

1. **Naming Convention**
   - Avoid common Cypher keywords
   - Use descriptive, non-reserved names
   - Prefix with underscore if needed: `_properties`

2. **Testing Protocol**
   - Test schema creation
   - Test data insertion
   - Test data querying
   - All three must work together

3. **Documentation**
   - Document all property names in schema
   - Note any that might conflict with Cypher
   - Keep list of tested reserved words

### Recommended Property Names

```python
# ❌ AVOID
properties = {}
type = "entity"
label = "test"

# ✅ USE INSTEAD
props = {}
entity_type = "entity"
entity_label = "test"
metadata = {}
attributes = {}
```

---

## 🎯 Impact on Elefante

### What Was Affected
- Entity creation in graph store
- Memory storage (entities are created for each memory)
- All graph operations dependent on entity creation

### What Was NOT Affected
- Vector store (ChromaDB) - completely independent
- Semantic search - uses vector store only
- Existing data in vector store

### Migration Path
1. Export existing memories from vector store
2. Reset Kuzu database with new schema
3. Re-import memories (will recreate entities with new schema)

---

## 📖 References

### Kuzu Documentation
- Schema: https://kuzudb.com/docs/cypher/data-definition
- Cypher: https://kuzudb.com/docs/cypher/query-clauses
- Reserved Words: https://kuzudb.com/docs/cypher/expressions/reserved-keywords

### Cypher Specification
- OpenCypher: https://opencypher.org/
- Reserved Keywords: https://s3.amazonaws.com/artifacts.opencypher.org/openCypher9.pdf

---

## 🚀 Verification

To verify the fix works:

```bash
cd Elefante

# 1. Reset database
python reset_kuzu_schema.py

# 2. Initialize with new schema
python scripts/init_databases.py

# 3. Run comprehensive demo
python examples/comprehensive_demo.py

# 4. Verify entities are created
python -c "
from src.core.graph_store import get_graph_store
import asyncio

async def check():
    store = get_graph_store()
    result = await store.execute_query('MATCH (e:Entity) RETURN count(e)')
    print(f'Entities in database: {result}')

asyncio.run(check())
"
```

---

## 🎓 Key Takeaway

**Kuzu is a graph database that uses SQL for schema and Cypher for operations. This dual nature means you must be aware of reserved words in BOTH languages, even though they apply at different stages.**

The `properties` keyword is valid in SQL DDL but reserved in Cypher DML, creating a trap for developers. Always use non-reserved property names like `props`, `metadata`, or `attributes`.

---

**This issue is now documented and fixed. Future developers: read this before adding new properties to the Entity schema!**