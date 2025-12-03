#!/usr/bin/env python3
"""
Quick test to verify V2 memory creation works
"""

import asyncio
from src.core.orchestrator import get_orchestrator

async def test_v2_memory():
    """Test creating a memory with V2 schema"""
    
    orchestrator = get_orchestrator()
    
    print("Testing V2 memory creation...")
    
    try:
        memory = await orchestrator.add_memory(
            content="CRITICAL OPERATIONAL RULE: Never claim a task is finished without explicit user testing and approval.",
            memory_type="decision",
            importance=10,
            tags=["operational-rule", "workflow", "quality-assurance"],
            entities=[
                {"name": "User Approval Protocol", "type": "concept"},
                {"name": "Quality Assurance", "type": "concept"}
            ],
            metadata={
                "domain": "work",
                "category": "workflow",
                "intent": "decision_log",
                "confidence": 1.0,
                "source": "user_input"
            }
        )
        
        print(f"\n✓ Memory created successfully!")
        print(f"  ID: {memory.id}")
        print(f"  Domain: {memory.metadata.domain}")
        print(f"  Category: {memory.metadata.category}")
        print(f"  Intent: {memory.metadata.intent}")
        print(f"  Confidence: {memory.metadata.confidence}")
        print(f"  Source: {memory.metadata.source}")
        print(f"  Custom metadata: {memory.metadata.custom_metadata}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_v2_memory())
    exit(0 if success else 1)

# Made with Bob
