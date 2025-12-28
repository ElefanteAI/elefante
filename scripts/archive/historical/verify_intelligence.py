import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from src.core.orchestrator import MemoryOrchestrator
from src.utils.config import get_config

async def main():
    print("🐘 Verifying Memory Intelligence Pipeline...")
    
    orchestrator = MemoryOrchestrator()
    
    # Mock LLM Service to verify pipeline logic without API Key
    async def mock_analyze(content):
        return {
            "title": "Python GIL vs Rust",
            "summary": "User expresses frustration with Python's GIL performance and suggests Rust as an alternative.",
            "intent": "deciding",
            "emotional_context": {"valence": -0.6, "arousal": 0.7, "mood": "Frustrated"},
            "entities": [
                {"name": "User", "type": "Person"},
                {"name": "Python", "type": "Technology"},
                {"name": "Rust", "type": "Technology"},
                {"name": "GIL", "type": "Concept"}
            ],
            "relationships": [
                {"source": "User", "target": "Python", "type": "DISLIKES", "reason": "GIL performance"},
                {"source": "User", "target": "Rust", "type": "PREFERS", "reason": "Performance"},
                {"source": "Python", "target": "GIL", "type": "HAS_PART"}
            ],
            "strategic_insight": "User prefers Rust over Python for performance-critical tasks due to GIL limitations.",
            "action": "ADD"
        }
    
    orchestrator.llm_service.analyze_memory = mock_analyze
    print("🤖 Mocked LLM Service for verification")
    
    # Test Content
    content = "I absolutely hate Python because of the GIL, but I love Rust for its memory safety and speed."
    print(f"\nInput: '{content}'")
    
    # Add Memory
    print("Ingesting memory...")
    memory = await orchestrator.add_memory(content, tags=["test"])
    
    if not memory:
        print("❌ Memory was ignored!")
        return
        
    print(f"✅ Memory Added: {memory.id}")
    
    # Verify Graph Node
    print("\nVerifying Graph Node...")
    
    context = await orchestrator.get_context(limit=10)
    
    # Check Memory Node
    found_memory = False
    for entity in context.get("entities", []):
        if entity["id"] == str(memory.id):
            found_memory = True
            print(f"Found Memory Entity: {entity['name']}")
            props = entity.get("properties", {})
            
            # Check for Cognitive Analysis
            if "cognitive_analysis" in props:
                print("✅ SUCCESS: Cognitive Analysis stored in properties!")
                ca = props["cognitive_analysis"]
                print(f"   Intent: {ca.get('intent')}")
                print(f"   Mood: {ca.get('emotional_context', {}).get('mood')}")
                print(f"   Insight: {ca.get('strategic_insight')}")
            else:
                print("⚠️ WARNING: No cognitive_analysis found in properties.")
            break
            
    if not found_memory:
        print("❌ Failed to find the new memory entity.")
        
    # Check for Created Relationships (Graph Execution)
    print("\nVerifying Graph Execution (Entities & Relationships)...")
    # We look for entities named "Python" and "Rust"
    found_python = False
    found_rust = False
    
    for entity in context.get("entities", []):
        if entity["name"] == "Python":
            found_python = True
            print("✅ Found Entity: Python")
        if entity["name"] == "Rust":
            found_rust = True
            print("✅ Found Entity: Rust")
            
    if found_python and found_rust:
        print("✅ SUCCESS: Graph Executor created derived entities!")
    else:
        print("⚠️ WARNING: Derived entities not found.")

if __name__ == "__main__":
    asyncio.run(main())
