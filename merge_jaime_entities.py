"""
Merge 'Jaime Suiabre Cisterna' into 'Jaime' entity
"""

import asyncio
from src.core.graph_store import GraphStore


async def merge_jaime():
    """Merge the two Jaime entities into one"""
    
    print("\n" + "="*80)
    print("MERGING JAIME ENTITIES")
    print("="*80)
    
    graph_store = GraphStore()
    graph_store._initialize_connection()
    
    # Find both Jaime entities
    query_find = """
        MATCH (e:Entity)
        WHERE e.type = 'person' AND (e.name = 'Jaime' OR e.name = 'Jaime Suiabre Cisterna')
        RETURN e.id, e.name, e.created_at
        ORDER BY e.created_at
    """
    
    result = await asyncio.to_thread(
        graph_store._conn.execute,
        query_find,
        {}
    )
    
    rows = graph_store._get_query_results(result)
    
    if len(rows) < 2:
        print("[INFO] Only one Jaime entity found. Nothing to merge.")
        return
    
    # Keep the oldest (first created)
    keep_id, keep_name, keep_created = rows[0]
    remove_id, remove_name, remove_created = rows[1]
    
    print(f"\n[KEEP] {keep_name} (ID: {keep_id}, created: {keep_created})")
    print(f"[REMOVE] {remove_name} (ID: {remove_id}, created: {remove_created})")
    
    # Find all relationships from the entity to be removed
    query_find_rels = """
        MATCH (source:Entity)-[r]->(target:Entity)
        WHERE source.id = $remove_id
        RETURN target.id, target.name
    """
    
    rel_result = await asyncio.to_thread(
        graph_store._conn.execute,
        query_find_rels,
        {"remove_id": remove_id}
    )
    
    rel_rows = graph_store._get_query_results(rel_result)
    
    if rel_rows:
        print(f"\n[STEP 1] Redirecting {len(rel_rows)} relationships...")
        
        for target_id, target_name in rel_rows:
            print(f"  - Redirecting relationship to '{target_name}'")
            
            # Create new relationship from keep_id to target
            query_create_rel = """
                MATCH (source:Entity), (target:Entity)
                WHERE source.id = $keep_id AND target.id = $target_id
                CREATE (source)-[:RELATES_TO {strength: 1.0}]->(target)
            """
            
            try:
                await asyncio.to_thread(
                    graph_store._conn.execute,
                    query_create_rel,
                    {"keep_id": keep_id, "target_id": target_id}
                )
            except Exception as e:
                # Relationship might already exist
                if "already exists" not in str(e).lower():
                    print(f"    [WARNING] Could not create relationship: {e}")
    
    # Delete the duplicate entity
    print(f"\n[STEP 2] Deleting duplicate entity '{remove_name}'...")
    
    query_delete = """
        MATCH (e:Entity)
        WHERE e.id = $remove_id
        DETACH DELETE e
    """
    
    try:
        await asyncio.to_thread(
            graph_store._conn.execute,
            query_delete,
            {"remove_id": remove_id}
        )
        print(f"[OK] Successfully deleted '{remove_name}'")
    except Exception as e:
        print(f"[ERROR] Failed to delete: {e}")
        return
    
    # Verify
    print("\n[STEP 3] Verifying merge...")
    
    verify_result = await asyncio.to_thread(
        graph_store._conn.execute,
        query_find,
        {}
    )
    
    verify_rows = graph_store._get_query_results(verify_result)
    
    if len(verify_rows) == 1:
        print(f"[SUCCESS] Merge complete! Only '{verify_rows[0][1]}' remains.")
    else:
        print(f"[WARNING] Still have {len(verify_rows)} Jaime entities")
    
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(merge_jaime())

# Made with Bob
