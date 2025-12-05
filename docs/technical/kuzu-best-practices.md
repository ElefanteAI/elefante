# Kuzu Best Practices for Elefante

**Critical Reading for All Developers Working with Graph Store**

---

## 🎯 The Golden Rule

**Kuzu uses SQL for schema, Cypher for operations. Property names must be valid in BOTH.**

---

## ⚠️ Reserved Words to NEVER Use

These words are reserved in Cypher and will cause runtime errors:

### Critical (Confirmed to Break)
- ❌ `properties` - **MOST DANGEROUS** - Valid in SQL schema, breaks in Cypher CREATE
- ❌ `type` - Use `entity_type`, `node_type`, or `item_type`
- ❌ `label` - Use `entity_label` or `tag`
- ❌ `id` - Use `entity_id` or `identifier` (though `id` often works, be cautious)

### High Risk (Avoid)
- ❌ `node`
- ❌ `relationship`
- ❌ `path`
- ❌ `match`
- ❌ `create`
- ❌ `merge`
- ❌ `delete`
- ❌ `set`
- ❌ `remove`
- ❌ `return`
- ❌ `where`
- ❌ `with`
- ❌ `union`
- ❌ `optional`
- ❌ `limit`
- ❌ `skip`
- ❌ `order`
- ❌ `distinct`

---

## ✅ Safe Alternatives

| ❌ Don't Use | ✅ Use Instead |
|-------------|---------------|
| `properties` | `props`, `metadata`, `attributes`, `data` |
| `type` | `entity_type`, `node_type`, `category` |
| `label` | `entity_label`, `tag`, `name` |
| `id` | `entity_id`, `identifier`, `uid` |
| `node` | `entity`, `item`, `record` |
| `relationship` | `relation`, `edge`, `link` |
| `path` | `route`, `trail`, `sequence` |

---

## 📋 Schema Definition Checklist

When adding new properties to Entity or other node tables:

```python
# ✅ GOOD
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    entity_type STRING,      # Not 'type'
    props STRING,            # Not 'properties'
    metadata_json STRING,    # Not 'metadata' (might conflict)
    PRIMARY KEY(id)
)

# ❌ BAD
CREATE NODE TABLE Entity(
    id STRING,
    name STRING,
    type STRING,             # Reserved in Cypher!
    properties STRING,       # Reserved in Cypher!
    label STRING,            # Reserved in Cypher!
    PRIMARY KEY(id)
)
```

---

## 🔧 Testing New Properties

Before deploying schema changes:

```python
# 1. Create test database
import kuzu
db = kuzu.Database('./test_db')
conn = kuzu.Connection(db)

# 2. Create schema with new property
conn.execute("""
    CREATE NODE TABLE TestEntity(
        id STRING,
        your_new_property STRING,  # Test this!
        PRIMARY KEY(id)
    )
""")

# 3. Try to insert data
conn.execute("""
    CREATE (e:TestEntity {
        id: 'test123',
        your_new_property: 'test_value'  # Does this work?
    })
""")

# 4. If no error, property name is safe!
```

---

## 🎓 Understanding Kuzu's Hybrid Nature

### Schema Layer (SQL DDL)
```sql
-- Uses SQL syntax
CREATE NODE TABLE Entity(...)
CREATE REL TABLE RELATES_TO(...)
DROP TABLE Entity
```

### Operation Layer (Cypher DML)
```cypher
-- Uses Cypher syntax
CREATE (e:Entity {...})
MATCH (e:Entity) WHERE e.id = 'x'
MERGE (e:Entity {id: 'x'})
DELETE e
```

### Why This Matters
- SQL accepts more property names than Cypher
- A property name can be valid in schema but fail in operations
- Always test both schema AND operations

---

## 🚨 Common Errors and Solutions

### Error: "Cannot find property X for e"
```
RuntimeError: Binder exception: Cannot find property properties for e.
```

**Cause:** Property name is a Cypher reserved word

**Solution:**
1. Rename property in schema
2. Update all CREATE/MERGE queries
3. Reset database completely
4. Re-import data

### Error: "Parser exception: Invalid input"
```
Parser exception: Invalid input <INSERT>
```

**Cause:** Trying to use SQL INSERT instead of Cypher CREATE

**Solution:** Use Cypher syntax:
```cypher
-- ❌ Don't use
INSERT INTO Entity VALUES (...)

-- ✅ Use instead
CREATE (e:Entity {...})
```

---

## 📖 Quick Reference

### Valid Operations

| Operation | Syntax | Example |
|-----------|--------|---------|
| Create Schema | SQL | `CREATE NODE TABLE Entity(...)` |
| Insert Node | Cypher | `CREATE (e:Entity {...})` |
| Query Node | Cypher | `MATCH (e:Entity) RETURN e` |
| Update Node | Cypher | `MATCH (e) SET e.prop = 'val'` |
| Upsert Node | Cypher | `MERGE (e:Entity {id: 'x'})` |
| Delete Node | Cypher | `MATCH (e) DELETE e` |
| Create Edge | Cypher | `CREATE (a)-[r:REL]->(b)` |

### String Escaping

```python
# Always escape single quotes in Cypher strings
def escape_string(s):
    return str(s).replace("'", "\\'")

# Use in queries
query = f"CREATE (e:Entity {{name: '{escape_string(user_input)}'}})"
```

---

## 🔗 Related Documentation

- [kuzu-reserved-words-issue.md](../debug/kuzu-reserved-words-issue.md) - Full analysis of the `properties` bug
- [Kuzu Official Docs](https://kuzudb.com/docs/) - Official documentation
- [OpenCypher Spec](https://opencypher.org/) - Cypher language specification

---

## ✨ Best Practices Summary

1. **Never use Cypher reserved words as property names**
2. **Test schema changes with actual data insertion**
3. **Use descriptive, non-reserved alternatives**
4. **Document all property names in schema**
5. **Escape user input in Cypher queries**
6. **Use Cypher for all data operations (not SQL)**
7. **Reset database completely after schema changes**

---

**Remember: If it works in the schema but fails in CREATE, it's probably a reserved word!**

---

**Last Updated:** 2025-12-04  
**Maintainer:** Elefante Development Team  
**Status:** Production Guidelines