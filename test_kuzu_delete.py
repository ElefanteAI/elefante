"""
Test different Kuzu deletion approaches for version 0.1.0
"""

import asyncio
from src.core.graph_store import GraphStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


async def test_delete_methods():
    """Test various deletion approaches"""
    
    print("\n" + "="*80)
    print("TESTING KUZU DELETE METHODS (v0.1.0)")
    print("="*80)
    
    graph_store = GraphStore()
    graph_store._initialize_connection()
    
    # Get one duplicate entity to test with
    query_find = """
        MATCH (e:Entity)
        WHERE e.name = 'Jaime' AND e.type = 'person'
        RETURN e.id, e.created_at
        ORDER BY e.created_at DESC
        LIMIT 1
    """
    
    result = await asyncio.to_thread(
        graph_store._conn.execute,
        query_find,
        {}
    )
    
    rows = graph_store._get_query_results(result)
    if not rows:
        print("[ERROR] No duplicate Jaime entity found")
        return
    
    test_entity_id = rows[0][0]
    print(f"\n[INFO] Testing with entity ID: {test_entity_id}")
    
    # Method 1: Simple DELETE (already failed)
    print("\n[TEST 1] Simple DELETE")
    try:
        query1 = """
            MATCH (e:Entity)
            WHERE e.id = $entity_id
            DELETE e
        """
        await asyncio.to_thread(
            graph_store._conn.execute,
            query1,
            {"entity_id": test_entity_id}
        )
        print("[OK] Simple DELETE worked!")
        return
    except Exception as e:
        print(f"[FAILED] {e}")
    
    # Method 2: Try with DETACH
    print("\n[TEST 2] DETACH DELETE")
    try:
        query2 = """
            MATCH (e:Entity)
            WHERE e.id = $entity_id
            DETACH DELETE e
        """
        await asyncio.to_thread(
            graph_store._conn.execute,
            query2,
            {"entity_id": test_entity_id}
        )
        print("[OK] DETACH DELETE worked!")
        return
    except Exception as e:
        print(f"[FAILED] {e}")
    
    # Method 3: Try DROP instead of DELETE
    print("\n[TEST 3] DROP")
    try:
        query3 = """
            MATCH (e:Entity)
            WHERE e.id = $entity_id
            DROP e
        """
        await asyncio.to_thread(
            graph_store._conn.execute,
            query3,
            {"entity_id": test_entity_id}
        )
        print("[OK] DROP worked!")
        return
    except Exception as e:
        print(f"[FAILED] {e}")
    
    # Method 4: Try REMOVE
    print("\n[TEST 4] REMOVE")
    try:
        query4 = """
            MATCH (e:Entity)
            WHERE e.id = $entity_id
            REMOVE e
        """
        await asyncio.to_thread(
            graph_store._conn.execute,
            query4,
            {"entity_id": test_entity_id}
        )
        print("[OK] REMOVE worked!")
        return
    except Exception as e:
        print(f"[FAILED] {e}")
    
    # Method 5: Check if we need to use a different syntax
    print("\n[TEST 5] DELETE without MATCH")
    try:
        query5 = f"""
            DELETE (e:Entity {{id: '{test_entity_id}'}})
        """
        await asyncio.to_thread(
            graph_store._conn.execute,
            query5,
            {}
        )
        print("[OK] Direct DELETE worked!")
        return
    except Exception as e:
        print(f"[FAILED] {e}")
    
    print("\n[CONCLUSION] All deletion methods failed. This is a Kuzu 0.1.0 bug.")
    print("[RECOMMENDATION] Upgrade Kuzu to latest version (0.7+)")
    print("\n" + "="*80)


if __name__ == "__main__":
    asyncio.run(test_delete_methods())

# Made with Bob
