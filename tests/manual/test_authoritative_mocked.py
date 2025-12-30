import sys
import asyncio
from unittest.mock import MagicMock, AsyncMock
from uuid import uuid4
from datetime import datetime

if "pytest" in sys.modules:
    import pytest

    pytest.skip(
        "Manual mocked script (mutates sys.modules); not collected by pytest.",
        allow_module_level=True,
    )

# =============================================================================
# MOCK DEPENDENCIES BEFORE IMPORT
# =============================================================================
sys.modules["aiosqlite"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["kuzu"] = MagicMock()

# Mock internal modules that might fail to import due to missing deps
mock_vec_store = MagicMock()
mock_graph_store = MagicMock()
mock_embed_service = MagicMock()
mock_llm_service = MagicMock()

# Setup Metadata Store Mock specifically
mock_metadata_store_module = MagicMock()
mock_store_instance = MagicMock()
mock_store_instance.initialize = AsyncMock() # Make it awaitable
mock_metadata_store_module.get_metadata_store.return_value = mock_store_instance

sys.modules["src.core.vector_store"] = mock_vec_store
sys.modules["src.core.graph_store"] = mock_graph_store
sys.modules["src.core.embeddings"] = mock_embed_service
sys.modules["src.core.llm"] = mock_llm_service
sys.modules["src.core.metadata_store"] = mock_metadata_store_module

# Now we can import the target module (it will import the mocks)
# We need to ensure src is in path
import os
sys.path.append(os.getcwd())

# We need to manually define the real classes we want to test if they are in the mocked files?
# No, MemoryOrchestrator is in src.core.orchestrator.
# But it imports from src.models... which we presumably have.

from src.models.memory import Memory, MemoryMetadata, MemoryType, MemoryStatus
from src.core.orchestrator import MemoryOrchestrator

async def test_authoritative_pipeline():
    print("TESTING AUTHORITATIVE 5-STEP PIPELINE (MOCKED)")
    
    # 1. Setup Mocks
    vector_store = AsyncMock()
    vector_store.search.return_value = [] # No duplicates for now
    
    graph_store = AsyncMock()
    
    embedding_service = AsyncMock()
    embedding_service.generate_embedding.return_value = [0.1, 0.2, 0.3]
    
    # Instantiate Orchestrator with mocks
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=graph_store,
        embedding_service=embedding_service
    )
    
    # 2. Test Payload (Authoritative)
    content = "I prefer to use Python 3.10"
    payload_metadata = {
        "layer": "self",
        "sublayer": "preference",
        "title": "Self.preference: Python version preference",
        "intent": "statement",
        "tags": ["python", "coding"]
    }
    
    print(f"\nINPUT: {content} | {payload_metadata}")
    
    # 3. Execute add_memory
    memory = await orchestrator.add_memory(
        content=content,
        metadata=payload_metadata
    )
    
    # 4. Verify OUTPUT correctness
    print("\nVERIFICATION:")
    
    # Check Layer/Sublayer
    print(f"   - Layer: {memory.metadata.layer} (Expected: self) -> {'OK' if memory.metadata.layer == 'self' else 'FAIL'}")
    print(f"   - Sublayer: {memory.metadata.sublayer} (Expected: preference) -> {'OK' if memory.metadata.sublayer == 'preference' else 'FAIL'}")
    
    # Check Reinforcement
    print(f"   - Access Count: {memory.metadata.access_count} (Expected: 1) -> {'OK' if memory.metadata.access_count == 1 else 'FAIL'}")
    
    # Check Persistence Calls
    print(f"   - Vector Store Called: {'OK' if vector_store.add_memory.called else 'FAIL'}")
    print(f"   - Graph Store Called: {'OK' if graph_store.create_entity.called else 'FAIL'}")
    
    # Check Graph Entity Properties
    if graph_store.create_entity.called:
        entity_arg = graph_store.create_entity.call_args[0][0]
        print(f"   - Graph Entity Layer: {entity_arg.properties.get('layer')} -> {'OK' if entity_arg.properties.get('layer') == 'self' else 'FAIL'}")

    return memory

async def test_retrieval_plasticity():
    print("\nTESTING READ-SIDE PLASTICITY (MOCKED)")
    
    # Setup Mocks
    vector_store = AsyncMock()
    # Mock search result
    mock_memory = Memory(content="Test Memory", metadata=MemoryMetadata(memory_type=MemoryType.CONVERSATION))
    mock_result = MagicMock()
    mock_result.memory = mock_memory
    mock_result.score = 0.9
    
    vector_store.search.return_value = [mock_result]
    
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=AsyncMock(),
        embedding_service=AsyncMock()
    )
    
    # Execute semantic search (private method for direct test)
    # We need to create a dummy plan
    from src.models.query import QueryPlan, QueryMode
    plan = QueryPlan(mode=QueryMode.SEMANTIC, vector_weight=1.0, graph_weight=0.0, limit=1, min_similarity=0.5)
    
    await orchestrator._search_semantic("query", plan, apply_temporal_decay=True)
    
    print(f"   - Vector Store Access Update Called: {'' if vector_store.update_memory_access.called else ''}")

async def test_graph_authoritative():
    print("\n TESTING GRAPH AUTHORITATIVE (MOCKED)")
    
    orchestrator = MemoryOrchestrator(
        vector_store=AsyncMock(),
        graph_store=AsyncMock(),
        embedding_service=AsyncMock()
    )
    
    # Test 1: Idempotency (create_or_get_entity used)
    await orchestrator.create_entity("TestEntity", "project")
    print(f"   - create_or_get_entity Called: {'' if orchestrator.graph_store.create_or_get_entity.called else ''}")
    
    # Test 2: Strict Schema (Entity)
    try:
        await orchestrator.create_entity("InvalidEntity", "invalid_type")
        print("   - Entity Type Strictness:  (Should have failed)")
    except ValueError:
        print("   - Entity Type Strictness:  (Caught invalid type)")
        
    # Test 3: Strict Schema (Relationship)
    from uuid import uuid4
    try:
        await orchestrator.create_relationship(uuid4(), uuid4(), "invalid_rel")
        print("   - Relationship Type Strictness:  (Should have failed)")
    except ValueError:
        print("   - Relationship Type Strictness:  (Caught invalid type)")

async def test_maintenance_authoritative():
    print("\n TESTING MAINTENANCE AUTHORITATIVE (MOCKED)")
    
    # Mock LLM and Stores
    llm_service = AsyncMock()
    # Mock response with authoritative structure
    llm_service.generate_response.return_value = """
    {
        "insights": [
            {
                "content": "Consolidated Fact",
                "type": "fact",
                "layer": "world",
                "sublayer": "fact",
                "source_memory_ids": ["c2d29867-3d0b-4497-9e9a-471d830d1603"]
            }
        ]
    }
    """
    
    orchestrator = AsyncMock()
    # Mock add_memory return
    orchestrator.add_memory.return_value = Memory(id=uuid4(), content="Consolidated Fact", metadata=MemoryMetadata(memory_type=MemoryType.FACT))
    
    # Patch get_orchestrator to return our mock
    # Patch get_orchestrator to return our mock
    import src.core.consolidation
    import src.core.orchestrator # Import the module where get_orchestrator is defined
    src.core.orchestrator.get_orchestrator = MagicMock(return_value=orchestrator)
    src.core.consolidation.get_llm_service = MagicMock(return_value=llm_service)
    src.core.consolidation.get_vector_store = MagicMock(return_value=AsyncMock())
    graph_store_mock = AsyncMock()
    # Mock query result for recent memories
    mock_node = MagicMock()
    mock_node.id = uuid4()
    mock_node.properties = {"content": "Raw memory", "timestamp": datetime.utcnow().isoformat()}
    graph_store_mock.execute_query.return_value = [{"m": mock_node}]
    src.core.consolidation.get_graph_store = MagicMock(return_value=graph_store_mock)
    
    from src.core.consolidation import MemoryConsolidator
    consolidator = MemoryConsolidator()
    consolidator.llm_service = llm_service
    consolidator.graph_store = graph_store_mock
    
    # Run consolidation
    await consolidator.consolidate_recent(force=True)
    
    call_kwargs = orchestrator.add_memory.call_args[1]
    metadata_arg = call_kwargs.get('metadata', {})
    
    print(f"   - Layer Passed: {metadata_arg.get('layer')} -> {'' if metadata_arg.get('layer') == 'world' else ''}")
    print(f"   - Sublayer Passed: {metadata_arg.get('sublayer')} -> {'' if metadata_arg.get('sublayer') == 'fact' else ''}")
    
    # Verify PARENT_OF relationship
    rel_call_args = orchestrator.create_relationship.call_args[1]
    print(f"   - Relationship Type: {rel_call_args.get('relationship_type')} -> {'' if rel_call_args.get('relationship_type') == 'PARENT_OF' else ''}")

if __name__ == "__main__":
    asyncio.run(test_authoritative_pipeline())
    asyncio.run(test_retrieval_plasticity())
    asyncio.run(test_graph_authoritative())
    asyncio.run(test_maintenance_authoritative())
