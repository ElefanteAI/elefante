#!/usr/bin/env python3
"""Query specific memory by ID"""
import sys
from src.core.vector_store import VectorStore

def query_memory(memory_id: str):
    # Initialize vector store
    vector_store = VectorStore()
    vector_store._initialize_client()
    
    # Query the memory
    results = vector_store._collection.get(
        ids=[memory_id],
        include=['documents', 'metadatas']
    )
    
    if not results['documents']:
        print(f"Memory ID {memory_id} NOT FOUND")
        return
    
    doc = results['documents'][0]
    meta = results['metadatas'][0]
    
    print("=" * 80)
    print(f"MEMORY ID: {memory_id}")
    print("=" * 80)
    print("\nCONTENT:")
    print(doc)
    print("\n" + "=" * 80)
    print("METADATA:")
    for key, value in meta.items():
        print(f"  {key}: {value}")
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python query_memory.py <memory_id>")
        sys.exit(1)
    
    query_memory(sys.argv[1])

# Made with Bob
