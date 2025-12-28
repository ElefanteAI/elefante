#!/usr/bin/env python3
"""
Title Migration Script for Elefante
Regenerates semantic titles for all existing memories using LLM.
Format: Subject-Aspect-Qualifier (max 30 chars, no truncation)
"""

import asyncio
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from collections import Counter

# Import LLM service and config
from src.core.llm import get_llm_service
from src.utils.config import get_config


async def migrate_titles():
    """Regenerate titles for all memories using LLM."""
    print("=" * 60)
    print("ELEFANTE TITLE MIGRATION")
    print("Format: Subject-Aspect-Qualifier (max 30 chars)")
    print("=" * 60)
    
    # Initialize ChromaDB using config
    config = get_config()
    chroma_path = config.elefante.vector_store.persist_directory
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("memories")
    
    # Get all memories
    all_data = collection.get(include=["documents", "metadatas"])
    
    if not all_data["ids"]:
        print("No memories found!")
        return
    
    total = len(all_data["ids"])
    print(f"\n📊 Found {total} memories to process\n")
    
    # Initialize LLM service
    llm = get_llm_service()
    
    if not llm.client:
        print("⚠️  LLM not configured - using fallback title generation")
    else:
        print(f"✅ LLM configured with model: {llm.model}")
    
    # Track results
    updated = 0
    errors = 0
    title_lengths = []
    sample_titles = []
    
    for i, (mem_id, content, metadata) in enumerate(zip(
        all_data["ids"],
        all_data["documents"],
        all_data["metadatas"]
    )):
        try:
            layer = metadata.get("layer", "world")
            sublayer = metadata.get("sublayer", "fact")
            old_title = metadata.get("title", "")
            
            # Generate new semantic title
            new_title = await llm.generate_semantic_title(
                content=content,
                layer=layer,
                sublayer=sublayer,
                max_chars=30
            )
            
            # Update metadata
            metadata["title"] = new_title
            
            # Update in ChromaDB
            collection.update(
                ids=[mem_id],
                metadatas=[metadata]
            )
            
            updated += 1
            title_lengths.append(len(new_title))
            
            # Keep samples
            if len(sample_titles) < 10:
                sample_titles.append({
                    "content": content[:60] + "..." if len(content) > 60 else content,
                    "old": old_title or "(none)",
                    "new": new_title,
                    "layer": layer
                })
            
            # Progress
            if (i + 1) % 10 == 0:
                print(f"  Processed {i + 1}/{total}...")
                
        except Exception as e:
            print(f"  ❌ Error processing {mem_id}: {e}")
            errors += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("MIGRATION COMPLETE")
    print("=" * 60)
    print(f"✅ Updated: {updated}/{total}")
    print(f"❌ Errors: {errors}")
    
    if title_lengths:
        print(f"\n📏 Title Length Stats:")
        print(f"  Min: {min(title_lengths)} chars")
        print(f"  Max: {max(title_lengths)} chars")
        print(f"  Avg: {sum(title_lengths)/len(title_lengths):.1f} chars")
        
        # Check for truncation (none should exceed 30)
        over_30 = sum(1 for l in title_lengths if l > 30)
        if over_30 > 0:
            print(f"  ⚠️  OVER 30 CHARS: {over_30} (SHOULD BE ZERO)")
        else:
            print(f"  ✅ All titles within 30 char limit")
    
    print(f"\n📝 Sample Titles:")
    for s in sample_titles:
        print(f"\n  Layer: {s['layer']}")
        print(f"  Content: {s['content']}")
        print(f"  Old: {s['old']}")
        print(f"  New: {s['new']}")
    
    print("\n💡 Run 'python scripts/update_dashboard_data.py' to refresh dashboard")


if __name__ == "__main__":
    asyncio.run(migrate_titles())
