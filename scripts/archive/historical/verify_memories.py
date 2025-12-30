"""Quick script to verify stored memories in Elefante"""
import asyncio
from src.core.orchestrator import MemoryOrchestrator
from src.models.query import QueryMode

async def verify_memories():
    print("\n" + "="*70)
    print("VERIFYING STORED MEMORIES IN ELEFANTE")
    print("="*70)
    
    orchestrator = MemoryOrchestrator()
    
    # Search for user profile memories
    queries = [
        "User Profile Senior AI Data Leader",
        "Communication Preferences direct technical",
        "Workflow Enforcement requirements design",
        "Development Environment macOS Windows",
        "Active Project Elefante memory system",
        "Skill Profile AI ML data science",
        "Communication Anti-Patterns avoid",
        "Privacy Requirements local-first"
    ]
    
    all_results = []
    for query in queries:
        results = await orchestrator.search_memories(
            query=query,
            mode=QueryMode.HYBRID,
            limit=2
        )
        if results:
            all_results.extend(results)
    
    # Remove duplicates by memory_id
    seen_ids = set()
    unique_results = []
    for result in all_results:
        if result.memory.id not in seen_ids:
            seen_ids.add(result.memory.id)
            unique_results.append(result)
    
    print(f"\nFound {len(unique_results)} unique memories:\n")
    
    for i, result in enumerate(unique_results, 1):
        memory = result.memory
        print(f"[{i}] ID: {memory.id}")
        print(f"    Type: {memory.metadata.memory_type}")
        print(f"    Importance: {memory.metadata.importance}")
        print(f"    Score: {result.score:.3f}")
        print(f"    Content: {memory.content[:150]}...")
        print(f"    Tags: {', '.join(memory.metadata.tags) if memory.metadata.tags else 'None'}")
        print()
    
    # Get stats
    stats = await orchestrator.get_stats()
    print("="*70)
    print("SYSTEM STATISTICS")
    print("="*70)
    print(f"Total memories in ChromaDB: {stats.get('vector_store', {}).get('total_memories', 'N/A')}")
    print(f"Total entities in Kuzu: {stats.get('graph_store', {}).get('total_entities', 'N/A')}")
    print(f"Total relationships: {stats.get('graph_store', {}).get('total_relationships', 'N/A')}")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(verify_memories())

