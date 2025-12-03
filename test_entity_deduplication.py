"""
Test entity deduplication in graph store

This test verifies that create_or_get_entity() prevents duplicate entities
by returning the same ID for entities with matching name + type.
"""

import asyncio
import sys
from uuid import UUID
from src.core.graph_store import GraphStore
from src.models.entity import Entity, EntityType
from src.utils.logger import get_logger

# Fix Windows console encoding for Unicode characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

logger = get_logger(__name__)


async def test_entity_deduplication():
    """Test that duplicate entities are prevented"""
    
    print("\n" + "="*80)
    print("ENTITY DEDUPLICATION TEST")
    print("="*80)
    
    # Initialize graph store
    graph_store = GraphStore()
    
    try:
        # Test 1: Create first entity
        print("\n[TEST 1] Creating first 'Test Concept' entity...")
        entity1 = Entity(
            name="Test Concept",
            type=EntityType.CONCEPT,
            description="First instance"
        )
        id1 = await graph_store.create_or_get_entity(entity1)
        print(f"[OK] Created entity with ID: {id1}")
        
        # Test 2: Try to create duplicate - should return same ID
        print("\n[TEST 2] Creating second 'Test Concept' entity (should return existing ID)...")
        entity2 = Entity(
            name="Test Concept",
            type=EntityType.CONCEPT,
            description="Second instance (should be ignored)"
        )
        id2 = await graph_store.create_or_get_entity(entity2)
        print(f"[OK] Returned entity ID: {id2}")
        
        # Verify IDs match
        if id1 == id2:
            print(f"\n[SUCCESS] Both calls returned same ID ({id1})")
            print("   Deduplication working correctly!")
        else:
            print(f"\n[FAILURE] Different IDs returned!")
            print(f"   First ID:  {id1}")
            print(f"   Second ID: {id2}")
            return False
        
        # Test 3: Different type should create new entity
        print("\n[TEST 3] Creating 'Test Concept' with different type (TECHNOLOGY)...")
        entity3 = Entity(
            name="Test Concept",
            type=EntityType.TECHNOLOGY,
            description="Different type"
        )
        id3 = await graph_store.create_or_get_entity(entity3)
        print(f"[OK] Created entity with ID: {id3}")
        
        if id3 != id1:
            print(f"\n[SUCCESS] Different type created new entity")
            print(f"   CONCEPT ID:    {id1}")
            print(f"   TECHNOLOGY ID: {id3}")
        else:
            print(f"\n[FAILURE] Same ID returned for different type!")
            return False
        
        # Test 4: Verify entity count
        print("\n[TEST 4] Verifying entity count in graph...")
        query = """
            MATCH (e:Entity)
            WHERE e.name = 'Test Concept'
            RETURN e.name, e.type, e.id
        """
        result = await asyncio.to_thread(
            graph_store._conn.execute,
            query,
            {}
        )
        rows = graph_store._get_query_results(result)
        
        print(f"\n[OK] Found {len(rows)} 'Test Concept' entities:")
        for row in rows:
            print(f"   - {row[0]} ({row[1]}): {row[2]}")
        
        if len(rows) == 2:
            print(f"\n[SUCCESS] Correct number of entities (2)")
            print("   - 1 CONCEPT entity (deduplicated)")
            print("   - 1 TECHNOLOGY entity (different type)")
        else:
            print(f"\n[FAILURE] Expected 2 entities, found {len(rows)}")
            return False
        
        print("\n" + "="*80)
        print("ALL TESTS PASSED")
        print("="*80)
        return True
        
    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup: Remove test entities
        print("\n[CLEANUP] Removing test entities...")
        try:
            cleanup_query = """
                MATCH (e:Entity)
                WHERE e.name = 'Test Concept'
                DELETE e
            """
            await asyncio.to_thread(
                graph_store._conn.execute,
                cleanup_query,
                {}
            )
            print("[OK] Test entities removed")
        except Exception as e:
            print(f"[WARNING] Cleanup warning: {e}")


if __name__ == "__main__":
    success = asyncio.run(test_entity_deduplication())
    exit(0 if success else 1)

# Made with Bob
