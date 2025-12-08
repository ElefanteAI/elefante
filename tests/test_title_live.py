
import asyncio
import sys
import os
from unittest.mock import MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.orchestrator import MemoryOrchestrator
from src.core.vector_store import get_vector_store
from src.core.llm import get_llm_service
from src.utils.logger import get_logger

logger = get_logger(__name__)

async def run_test():
    print("🧪 STARTING LIVE TEST: Semantic Title Generation")
    print("-" * 50)
    
    # 1. Setup Dependencies
    # Use REAL VectorStore (ChromaDB is safe for concurrent access mostly, or at least doesn't lock like Kuzu)
    # Actually ChromaDB might lock if sqlite... but usually handled better. Let's see.
    try:
        vector_store = get_vector_store()
        print("✅ VectorStore initialized")
    except Exception as e:
        print(f"❌ VectorStore failed: {e}")
        return

    # Use REAL LLM Service (Crucial for title generation)
    llm_service = get_llm_service()
    print(f"✅ LLMService initialized (Model: {llm_service.model})")

    # MOCK GraphStore (To avoid Kuzu Lock)
    # We need AsyncMock behavior because orchestrator awaits these calls
    mock_graph_store = MagicMock()
    
    async def async_mock_create(*args, **kwargs):
        if args and hasattr(args[0], 'name'):
            print(f"   [MockGraph] Created Entity: {args[0].name} w/ props {args[0].properties}")
        return None

    mock_graph_store.create_entity = MagicMock(side_effect=async_mock_create)
    mock_graph_store.create_relationship = MagicMock(side_effect=async_mock_create)
    mock_graph_store.create_or_get_entity = MagicMock(side_effect=async_mock_create)
    mock_graph_store.execute_query = MagicMock(side_effect=async_mock_create)
    
    print("✅ GraphStore mocked (Bypassing Kuzu Lock)")

    # 2. Initialize Orchestrator
    orchestrator = MemoryOrchestrator(
        vector_store=vector_store,
        graph_store=mock_graph_store,
        embedding_service=None # Will use default
    )
    # Inject the real LLM service in case init created a new one
    orchestrator.llm_service = llm_service 
    
    # 3. Define Test Input - A clear preference that should trigger a specific title
    test_content = "I absolutely prefer using Pytest over Unittest because the syntax is much cleaner and less boilerplate."
    print(f"\n📥 Adding Memory: '{test_content}'")
    
    # 4. Execute add_memory
    try:
        memory = await orchestrator.add_memory(
            content=test_content,
            metadata={"layer": "self", "sublayer": "preference"}
        )
        
        if not memory:
            print("❌ Memory was None (Ignored?)")
            return

        # 5. Verify Title
        title = memory.metadata.custom_metadata.get("title") # It's put in metadata dict, which maps to custom_metadata in V2 object?
        # Wait, in orchestrator.py: metadata["title"] = title. 
        # Then memory_metadata = MemoryMetadata(..., custom_metadata=custom_metadata)
        # So it should be in custom_metadata['title'] OR directly on memory.metadata if we added a field?
        # The MemoryMetadata class usually puts unknown fields in custom_metadata.
        # Let's check where it ended up.
        
        print(f"\n📤 Resulting Title: {title}")
        print(f"   Full Metadata: {memory.metadata}")
        
        # Validation Logic
        if title and "-" in title and len(title) <= 30:
            print("\n✅ TEST PASSED: Title follows Semantic Format!")
        else:
            print(f"\n⚠️ TEST WARNING: Title '{title}' might not be compliant.")
            
    except Exception as e:
        print(f"\n❌ TEST FAILED with Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_test())
