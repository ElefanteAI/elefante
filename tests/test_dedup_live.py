import asyncio
import os
import sys
from datetime import datetime
from uuid import UUID

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.orchestrator import MemoryOrchestrator as Orchestrator
from src.core.vector_store import VectorStore
from src.core.llm import LLMService

async def test_dedup_live():
    print("\n🧪 STARTING LIVE DEDUPLICATION TEST...")
    
    # 1. Initialize Components
    orchestrator = Orchestrator()
    
    # Mock LLM Service to ensure deterministic titles for this test
    # This isolates the Deduplication Logic from Generation Logic
    from unittest.mock import AsyncMock, MagicMock
    orchestrator.llm_service = MagicMock()
    orchestrator.llm_service.analyze_memory = AsyncMock(return_value={
        "action": "ADD", "intent": "statement"
    })
    orchestrator.llm_service.generate_semantic_title = AsyncMock(return_value="Self-Pref-ElectricBlue")

    # Mock GraphStore to avoid lock
    orchestrator.graph_store = MagicMock()
    orchestrator.graph_store.create_entity = AsyncMock(return_value="mock_entity_id")
    orchestrator.graph_store.create_relationship = AsyncMock(return_value="mock_rel_id")
    orchestrator.graph_store.close = AsyncMock() 

    # Clean up any previous test memory to ensure clean slate
    # We will use a very specific test case
    test_content_1 = "My favorite color is definitely Electric Blue."
    test_content_2 = "I really love Electric Blue, it is my favorite color."
    
    print(f"📝 Ingesting Memory 1: '{test_content_1}'")
    mem_result_1 = await orchestrator.add_memory(
        content=test_content_1, 
        metadata={"source": "user_input", "layer": "self", "sublayer": "preference"}
    )
    mem_id_1 = str(mem_result_1.id)
    print(f"   ✅ Memory 1 Created: {mem_id_1}")
    
    # Verify title
    mem1 = await orchestrator.vector_store.find_by_title("Self-Pref-Color") # LLM likely generates this or similar
    if not mem1: 
        # Fallback if title is slightly different, let's just get by ID
        mem1 = await orchestrator.vector_store.get_memory(UUID(mem_id_1))
        # Title is stored in custom_metadata in V2 schema
        print(f"   ℹ️  Title generated: {mem1.metadata.custom_metadata.get('title')}")
    
    title_1 = mem1.metadata.custom_metadata.get('title')
    print(f"   ℹ️  Concept Title: {title_1}")

    print(f"\n📝 Ingesting Memory 2 (Semantic Duplicate): '{test_content_2}'")
    mem_result_2 = await orchestrator.add_memory(
        content=test_content_2,
        metadata={"source": "user_input", "layer": "self", "sublayer": "preference"}
    )
    mem_id_2 = str(mem_result_2.id)
    print(f"   ❓ Memory 2 Result ID: {mem_id_2}")
    
    # VERIFICATION
    if mem_id_1 == mem_id_2:
        print(f"\n✅ SUCCESS: Deduplication Worked! IDs match ({mem_id_1})")
        
        # Check access count
        mem2 = await orchestrator.vector_store.get_memory(UUID(mem_id_1))
        print(f"   📊 Access Count: {mem2.metadata.access_count} (Expected > 0)")
        if mem2.metadata.access_count > 0:
             print("   ✅ Reinforcement verified.")
    else:
        print(f"\n❌ FAILURE: Duplication occurred. IDs differ.")
        print(f"   ID 1: {mem_id_1}")
        print(f"   ID 2: {mem_id_2}")
        
        mem2 = await orchestrator.vector_store.get_memory(UUID(mem_id_2))
        print(f"   ID 2 Title: {mem2.metadata.custom_metadata.get('title')}")

if __name__ == "__main__":
    asyncio.run(test_dedup_live())
