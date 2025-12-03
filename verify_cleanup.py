"""
Verify the cleanup was successful by directly querying the database
"""

import asyncio
from src.core.graph_store import GraphStore


async def verify():
    """Verify cleanup results"""
    
    print("\n" + "="*80)
    print("VERIFICATION: Current Database State")
    print("="*80)
    
    # Create a fresh connection
    graph_store = GraphStore()
    graph_store._initialize_connection()
    
    # Query all entities
    query = """
        MATCH (e:Entity)
        RETURN e.name, e.type, e.created_at
        ORDER BY e.type, e.name, e.created_at
    """
    
    result = await asyncio.to_thread(
        graph_store._conn.execute,
        query,
        {}
    )
    
    rows = graph_store._get_query_results(result)
    
    print(f"\n[TOTAL ENTITIES] {len(rows)}\n")
    
    # Group by type
    by_type = {}
    for name, entity_type, created_at in rows:
        if entity_type not in by_type:
            by_type[entity_type] = []
        by_type[entity_type].append((name, created_at))
    
    # Display grouped results
    for entity_type in sorted(by_type.keys()):
        entities = by_type[entity_type]
        print(f"[{entity_type.upper()}] ({len(entities)} entities)")
        
        # Check for duplicates
        names = [name for name, _ in entities]
        unique_names = set(names)
        
        if len(names) != len(unique_names):
            print("  ⚠️  DUPLICATES DETECTED:")
            for name in unique_names:
                count = names.count(name)
                if count > 1:
                    print(f"    - '{name}': {count} instances")
        
        for name, created_at in entities:
            print(f"  - {name} (created: {created_at})")
        print()
    
    print("="*80)
    
    # Final verdict
    all_names = [row[0] for row in rows]
    unique_count = len(set(all_names))
    
    if len(all_names) == unique_count:
        print("✅ DATABASE IS CLEAN - No duplicates found")
    else:
        print(f"❌ DUPLICATES EXIST - {len(all_names)} total, {unique_count} unique")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(verify())

# Made with Bob
