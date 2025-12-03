"""
Debug script to directly query ChromaDB and retrieve ALL memories
This bypasses the semantic search to verify database state
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import chromadb
from chromadb.config import Settings
from src.utils.config import get_config

def main():
    """Query ChromaDB directly to retrieve all memories"""
    config = get_config()
    persist_dir = config.elefante.vector_store.persist_directory
    collection_name = config.elefante.vector_store.collection_name
    
    print(f"Connecting to ChromaDB at: {persist_dir}")
    print(f"Collection: {collection_name}\n")
    
    # Initialize ChromaDB client
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(
            anonymized_telemetry=False,
            allow_reset=False
        )
    )
    
    # Get collection
    collection = client.get_collection(name=collection_name)
    
    # Get total count
    total_count = collection.count()
    print(f"Total memories in ChromaDB: {total_count}\n")
    
    if total_count == 0:
        print("No memories found in database.")
        return
    
    # Retrieve ALL memories using get() without filters
    print("Retrieving all memories...\n")
    results = collection.get(
        include=["documents", "metadatas"]
    )
    
    # Display results in table format
    print("=" * 120)
    print(f"{'ID':<38} | {'Type':<15} | {'Importance':<10} | {'Content Preview':<50}")
    print("=" * 120)
    
    for i, memory_id in enumerate(results['ids']):
        metadata = results['metadatas'][i]
        content = results['documents'][i]
        
        memory_type = metadata.get('memory_type', 'unknown')
        importance = metadata.get('importance', 'N/A')
        content_preview = content[:50] + "..." if len(content) > 50 else content
        
        print(f"{memory_id:<38} | {memory_type:<15} | {importance:<10} | {content_preview:<50}")
    
    print("=" * 120)
    print(f"\nTotal retrieved: {len(results['ids'])} memories")
    
    # Additional statistics
    print("\n--- Memory Type Distribution ---")
    type_counts = {}
    for metadata in results['metadatas']:
        mem_type = metadata.get('memory_type', 'unknown')
        type_counts[mem_type] = type_counts.get(mem_type, 0) + 1
    
    for mem_type, count in sorted(type_counts.items()):
        print(f"{mem_type}: {count}")

if __name__ == "__main__":
    main()

# Made with Bob
