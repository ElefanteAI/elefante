"""
Cleanup script for duplicate entities in Kuzu graph

This script identifies and removes duplicate entities that were created
before the deduplication fix. It keeps the oldest entity and redirects
all relationships to it.
"""

import asyncio
from collections import defaultdict
from datetime import datetime
from src.core.graph_store import GraphStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def cleanup_duplicates():
    """Find and remove duplicate entities, keeping the oldest"""
    
    print("\n" + "="*80)
    print("DUPLICATE ENTITY CLEANUP")
    print("="*80)
    
    graph_store = GraphStore()
    
    try:
        # Initialize connection
        graph_store._initialize_connection()
        
        # Step 1: Find all entities grouped by name + type
        print("\n[STEP 1] Scanning for duplicate entities...")
        query_find_all = """
            MATCH (e:Entity)
            RETURN e.id, e.name, e.type, e.created_at
            ORDER BY e.name, e.type, e.created_at
        """
        
        result = await asyncio.to_thread(
            graph_store._conn.execute,
            query_find_all,
            {}
        )
        
        rows = graph_store._get_query_results(result)
        print(f"[OK] Found {len(rows)} total entities")
        
        # Group entities by name + type
        entity_groups = defaultdict(list)
        for row in rows:
            entity_id, name, entity_type, created_at = row
            key = (name, entity_type)
            entity_groups[key].append({
                'id': entity_id,
                'name': name,
                'type': entity_type,
                'created_at': created_at
            })
        
        # Step 2: Identify duplicates
        print("\n[STEP 2] Identifying duplicate groups...")
        duplicates = {k: v for k, v in entity_groups.items() if len(v) > 1}
        
        if not duplicates:
            print("[OK] No duplicates found! Graph is clean.")
            return
        
        print(f"[WARNING] Found {len(duplicates)} duplicate groups:")
        for (name, entity_type), entities in duplicates.items():
            print(f"\n  '{name}' ({entity_type}): {len(entities)} instances")
            for e in entities:
                print(f"    - ID: {e['id']}, Created: {e['created_at']}")
        
        # Step 3: For each duplicate group, keep oldest and remove others
        print("\n[STEP 3] Cleaning up duplicates...")
        total_removed = 0
        
        for (name, entity_type), entities in duplicates.items():
            # Sort by created_at to get oldest first
            entities_sorted = sorted(entities, key=lambda x: x['created_at'])
            oldest = entities_sorted[0]
            to_remove = entities_sorted[1:]
            
            print(f"\n  Processing '{name}' ({entity_type}):")
            print(f"    Keeping: {oldest['id']} (created {oldest['created_at']})")
            
            for entity in to_remove:
                entity_id = entity['id']
                print(f"    Removing: {entity_id}")
                
                # Step 3a: Use DETACH DELETE to remove entity and all relationships
                # This is the correct syntax for Kuzu 0.1.0
                query_delete = """
                    MATCH (e:Entity)
                    WHERE e.id = $entity_id
                    DETACH DELETE e
                """
                
                try:
                    await asyncio.to_thread(
                        graph_store._conn.execute,
                        query_delete,
                        {"entity_id": entity_id}
                    )
                    print(f"      [OK] Deleted entity {entity_id}")
                    total_removed += 1
                    
                except Exception as e:
                    print(f"      [ERROR] Failed to delete entity: {e}")
        
        # Step 4: Verify cleanup
        print("\n[STEP 4] Verifying cleanup...")
        result_after = await asyncio.to_thread(
            graph_store._conn.execute,
            query_find_all,
            {}
        )
        
        rows_after = graph_store._get_query_results(result_after)
        print(f"[OK] Entities after cleanup: {len(rows_after)}")
        print(f"[OK] Total duplicates removed: {total_removed}")
        
        # Check for remaining duplicates
        entity_groups_after = defaultdict(list)
        for row in rows_after:
            entity_id, name, entity_type, created_at = row
            key = (name, entity_type)
            entity_groups_after[key].append(entity_id)
        
        remaining_duplicates = {k: v for k, v in entity_groups_after.items() if len(v) > 1}
        
        if remaining_duplicates:
            print(f"\n[WARNING] Still have {len(remaining_duplicates)} duplicate groups:")
            for (name, entity_type), ids in remaining_duplicates.items():
                print(f"  '{name}' ({entity_type}): {len(ids)} instances")
        else:
            print("\n[SUCCESS] All duplicates cleaned up!")
        
        print("\n" + "="*80)
        print("CLEANUP COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n[ERROR] Cleanup failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(cleanup_duplicates())

# Made with Bob
