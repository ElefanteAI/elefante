"""
Test semantic search with different queries to understand why only 4 memories are retrieved
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import chromadb
from chromadb.config import Settings
from src.utils.config import get_config
from src.core.embeddings import get_embedding_service
import asyncio

async def test_search(query: str, min_similarity: float = 0.0):
    """Test semantic search with a specific query"""
    config = get_config()
    persist_dir = config.elefante.vector_store.persist_directory
    collection_name = config.elefante.vector_store.collection_name
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=False
        )
    )
    
    collection = client.get_collection(name=collection_name)
    
    # Generate embedding for query
    embedding_service = get_embedding_service()
    query_embedding = await embedding_service.generate_embedding(query)
    
    # Perform search
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=50,  # Request all possible results
        include=["documents", "metadatas", "distances"]
    )
    
    print(f"\n{'='*120}")
    print(f"Query: '{query}'")
    print(f"Min Similarity Threshold: {min_similarity}")
    print(f"{'='*120}\n")
    
    if not results['ids'] or len(results['ids'][0]) == 0:
        print("No results found!")
        return
    
    print(f"{'Rank':<6} | {'Similarity':<12} | {'Type':<15} | {'Content Preview':<70}")
    print("-" * 120)
    
    filtered_count = 0
    for i in range(len(results['ids'][0])):
        distance = results['distances'][0][i]
        similarity = 1.0 - distance
        similarity = max(0.0, min(1.0, similarity))
        
        if similarity < min_similarity:
            filtered_count += 1
            continue
        
        metadata = results['metadatas'][0][i]
        content = results['documents'][0][i]
        
        memory_type = metadata.get('memory_type', 'unknown')
        content_preview = content[:70] + "..." if len(content) > 70 else content
        
        print(f"{i+1:<6} | {similarity:<12.4f} | {memory_type:<15} | {content_preview:<70}")
    
    print("-" * 120)
    print(f"Total results: {len(results['ids'][0])}")
    print(f"Filtered out (below {min_similarity}): {filtered_count}")
    print(f"Returned: {len(results['ids'][0]) - filtered_count}")

async def main():
    """Run multiple test queries"""
    
    test_queries = [
        ("user preferences project information code decisions tasks", 0.0),
        ("user preferences project information code decisions tasks", 0.3),
        ("Elefante system architecture database configuration", 0.0),
        ("Jaime communication style workflow", 0.0),
        ("all memories", 0.0),
        ("*", 0.0),
        ("", 0.0),  # Empty query
    ]
    
    for query, min_sim in test_queries:
        try:
            await test_search(query, min_sim)
        except Exception as e:
            print(f"\nERROR with query '{query}': {e}\n")

if __name__ == "__main__":
    asyncio.run(main())

# Made with Bob
