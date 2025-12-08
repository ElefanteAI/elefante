#!/usr/bin/env python3
"""
V3 Migration Script - Direct ChromaDB Update

This script bypasses the MCP server and directly updates ChromaDB metadata
with proper layer/sublayer classification. Run this standalone to migrate
all memories to V3 schema.
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from collections import Counter
from src.core.classifier import classify_memory_full
from src.utils.config import get_config


async def migrate_v3():
    """
    Direct migration: Read from ChromaDB, classify content, 
    update metadata with layer/sublayer/importance using ChromaDB's update API.
    """
    config = get_config()
    chroma_path = config.elefante.vector_store.persist_directory
    
    print(f"[*] Connecting to ChromaDB at: {chroma_path}", file=sys.stderr)
    
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("memories")
    
    # Get all memories
    all_data = collection.get(include=["documents", "metadatas"])
    
    print(f"[*] Found {len(all_data['ids'])} memories to migrate", file=sys.stderr)
    
    # Track classification results
    layer_counts = Counter()
    sublayer_counts = Counter()
    importance_counts = Counter()
    migrated = 0
    errors = 0
    
    for i, memory_id in enumerate(all_data['ids']):
        try:
            content = all_data['documents'][i]
            existing_meta = all_data['metadatas'][i]
            
            # Classify content with importance
            layer, sublayer, importance = classify_memory_full(content)
            layer_counts[layer] += 1
            sublayer_counts[sublayer] += 1
            importance_counts[importance] += 1
            
            # Update metadata with layer/sublayer/importance
            new_meta = existing_meta.copy()
            new_meta['layer'] = layer
            new_meta['sublayer'] = sublayer
            new_meta['importance'] = importance
            
            # Use ChromaDB's update API
            collection.update(
                ids=[memory_id],
                metadatas=[new_meta]
            )
            
            migrated += 1
            
            if i % 20 == 0:
                print(f"   Migrating... {i+1}/{len(all_data['ids'])}", file=sys.stderr)
                
        except Exception as e:
            print(f"   [!] Error migrating {memory_id}: {e}", file=sys.stderr)
            errors += 1
    
    print(f"\n[OK] Migration complete!", file=sys.stderr)
    print(f"   Migrated: {migrated}", file=sys.stderr)
    print(f"   Errors: {errors}", file=sys.stderr)
    print(f"\n=== LAYER DISTRIBUTION ===", file=sys.stderr)
    for layer, count in layer_counts.most_common():
        pct = count * 100 / len(all_data['ids'])
        bar = '█' * int(pct // 5)
        print(f"   {layer}: {count} ({pct:.0f}%) {bar}", file=sys.stderr)
    
    print(f"\n=== SUBLAYER DISTRIBUTION ===", file=sys.stderr)
    for sublayer, count in sublayer_counts.most_common():
        pct = count * 100 / len(all_data['ids'])
        bar = '█' * int(pct // 5)
        print(f"   {sublayer}: {count} ({pct:.0f}%) {bar}", file=sys.stderr)
    
    print(f"\n=== IMPORTANCE DISTRIBUTION ===", file=sys.stderr)
    for imp in sorted(importance_counts.keys()):
        count = importance_counts[imp]
        pct = count * 100 / len(all_data['ids'])
        bar = '█' * int(pct // 2)
        print(f"   imp={imp}: {count} ({pct:.0f}%) {bar}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(migrate_v3())
