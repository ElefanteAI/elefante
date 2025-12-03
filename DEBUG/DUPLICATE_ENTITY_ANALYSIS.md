# Duplicate Entity Creation Analysis

**Date:** 2025-12-03  
**Issue:** Graph store creating duplicate entities with same name but different IDs

## Problem Statement

When storing memories with entities, the system creates duplicate entity nodes in Kuzu:
- "User Approval Protocol" appears twice (IDs: 81b0c0cb, 69dab3a0)
- "Quality Assurance" appears twice (IDs: 35feb88f, 8c6725bf)

This happened when storing two memories that both referenced the same conceptual entities.

## Root Cause

**Location:** [`src/core/orchestrator.py`](../src/core/orchestrator.py:314-321)

```python
entity = Entity(
    name=entity_data["name"],
    type=entity_type,
    properties=props
)

# Create or update entity
await self.graph_store.create_entity(entity)
```

**Problem:** The code comment says "Create or update entity" but the implementation only creates. There is NO deduplication logic.

**Location:** [`src/core/graph_store.py`](../src/core/graph_store.py:236-287)

```python
async def create_entity(self, entity: Entity) -> UUID:
    """Create an entity in the graph"""
    query = """
        CREATE (e:Entity {
            id: $id,
            name: $name,
            type: $type,
            description: $description,
            created_at: $created_at
        })
    """
```

**Problem:** Uses `CREATE` instead of `MERGE`. Every call creates a new node, even if an entity with the same name already exists.

## Impact

1. **Graph Pollution:** Multiple nodes for same concept
2. **Relationship Fragmentation:** Different memories link to different instances of same entity
3. **Query Inefficiency:** Graph traversal returns duplicate results
4. **Semantic Confusion:** "User Approval Protocol" concept split across multiple nodes

## Solution Design

### Option 1: MERGE by Name + Type (Recommended)

**Pros:**
- Kuzu-native solution using MERGE
- Automatic deduplication
- Preserves first creation timestamp
- Updates last_seen timestamp

**Cons:**
- Requires Cypher query modification
- Need to handle UUID generation carefully

**Implementation:**
```python
async def create_or_get_entity(self, entity: Entity) -> UUID:
    """Create entity if not exists, or return existing entity ID"""
    
    # First, try to find existing entity by name + type
    query_find = """
        MATCH (e:Entity)
        WHERE e.name = $name AND e.type = $type
        RETURN e.id
    """
    
    result = await asyncio.to_thread(
        self._conn.execute,
        query_find,
        {"name": entity.name, "type": entity.type.value}
    )
    
    rows = self._get_query_results(result)
    if rows:
        # Entity exists, return its ID
        existing_id = UUID(rows[0][0])
        logger.debug(f"Entity already exists: {entity.name} ({existing_id})")
        return existing_id
    
    # Entity doesn't exist, create it
    query_create = """
        CREATE (e:Entity {
            id: $id,
            name: $name,
            type: $type,
            description: $description,
            created_at: $created_at
        })
    """
    
    await asyncio.to_thread(
        self._conn.execute,
        query_create,
        {
            "id": str(entity.id),
            "name": entity.name,
            "type": entity.type.value,
            "description": entity.description or "",
            "created_at": entity.created_at
        }
    )
    
    logger.info(f"Entity created: {entity.name} ({entity.id})")
    return entity.id
```

### Option 2: Pre-flight Check in Orchestrator

**Pros:**
- Keeps graph_store.py simple
- Orchestrator controls deduplication logic

**Cons:**
- Two database calls per entity (check + create)
- Race condition risk in concurrent scenarios

### Option 3: Unique Constraint + Error Handling

**Pros:**
- Database-enforced uniqueness
- No duplicate entities possible

**Cons:**
- Kuzu may not support unique constraints on properties
- Error handling complexity

## Recommended Action

**Implement Option 1** with these steps:

1. Rename `create_entity()` → `create_or_get_entity()` in [`graph_store.py`](../src/core/graph_store.py:236)
2. Add MATCH query before CREATE
3. Return existing ID if found, create new if not
4. Update [`orchestrator.py`](../src/core/orchestrator.py:321) to use new method name
5. Add test case for duplicate entity prevention

## Testing Strategy

```python
# Test: Same entity name should return same ID
entity1 = Entity(name="Test Concept", type=EntityType.CONCEPT)
id1 = await graph_store.create_or_get_entity(entity1)

entity2 = Entity(name="Test Concept", type=EntityType.CONCEPT)
id2 = await graph_store.create_or_get_entity(entity2)

assert id1 == id2  # Should be same ID
```

## Migration Plan

**For existing duplicates:**

1. Query all entities grouped by name + type
2. Identify duplicates (count > 1)
3. For each duplicate set:
   - Keep oldest entity (by created_at)
   - Redirect all relationships to oldest entity
   - Delete newer duplicates
4. Verify graph integrity

**Cypher for cleanup:**
```cypher
// Find duplicates
MATCH (e:Entity)
WITH e.name as name, e.type as type, collect(e) as entities
WHERE size(entities) > 1
RETURN name, type, entities

// For each duplicate set (manual or scripted):
// 1. Get oldest entity ID
// 2. Update all relationships pointing to newer entities
// 3. Delete newer entities
```

## Prevention

After fix is deployed:
- Add integration test for entity deduplication
- Monitor graph stats for duplicate entity growth
- Consider adding periodic cleanup job

## Status

- [x] Root cause identified
- [ ] Solution designed (Option 1 recommended)
- [ ] Implementation pending user approval
- [ ] Testing strategy defined
- [ ] Migration plan for existing duplicates defined