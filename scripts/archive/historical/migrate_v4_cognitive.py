#!/usr/bin/env python3
"""
V4 Migration Script - Backfill cognitive retrieval fields for existing memories.

Adds: concepts, surfaces_when, authority_score to all memories in ChromaDB.
"""

import asyncio
import sys
import os
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from src.utils.config import get_config
from src.utils.curation import (
    extract_concepts,
    infer_surfaces_when,
    compute_authority_score,
)


async def migrate_v4():
    """Backfill V4 cognitive fields for all memories."""
    config = get_config()
    chroma_path = config.elefante.vector_store.persist_directory
    
    print(f"[*] Connecting to ChromaDB at {chroma_path}")
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("memories")
    
    # Get all memories
    all_memories = collection.get(include=["documents", "metadatas"])
    total = len(all_memories["ids"])
    print(f"[*] Found {total} memories to migrate")
    
    updated = 0
    skipped = 0
    
    for i, memory_id in enumerate(all_memories["ids"]):
        doc = all_memories["documents"][i] if all_memories["documents"] else ""
        meta = all_memories["metadatas"][i] if all_memories["metadatas"] else {}
        
        # Check if already has V4 fields
        existing_concepts = meta.get("concepts")
        if existing_concepts and isinstance(existing_concepts, str) and len(existing_concepts) > 2:
            skipped += 1
            continue
        
        # Extract concepts
        concepts = extract_concepts(doc, max_concepts=5)
        
        # Infer surfaces_when
        surfaces_when = infer_surfaces_when(doc, concepts)
        
        # Compute authority score
        importance = int(meta.get("importance", 5))
        access_count = int(meta.get("access_count", 1))
        
        created_str = meta.get("created_at") or meta.get("timestamp")
        accessed_str = meta.get("last_accessed")
        
        now = datetime.utcnow()
        days_since_created = 0
        days_since_accessed = 0
        
        if created_str:
            try:
                created = datetime.fromisoformat(created_str.replace("Z", "+00:00").replace("+00:00", ""))
                days_since_created = (now - created).days
            except:
                pass
        
        if accessed_str:
            try:
                accessed = datetime.fromisoformat(accessed_str.replace("Z", "+00:00").replace("+00:00", ""))
                days_since_accessed = (now - accessed).days
            except:
                pass
        
        authority_score = compute_authority_score(
            importance=importance,
            access_count=access_count,
            days_since_created=days_since_created,
            days_since_accessed=days_since_accessed,
        )
        
        # Update metadata
        # ChromaDB stores lists as JSON strings
        import json
        new_meta = dict(meta)
        new_meta["concepts"] = json.dumps(concepts)
        new_meta["surfaces_when"] = json.dumps(surfaces_when)
        new_meta["authority_score"] = authority_score
        
        # Update in ChromaDB
        collection.update(
            ids=[memory_id],
            metadatas=[new_meta],
        )
        
        updated += 1
        
        if (i + 1) % 10 == 0:
            print(f"   [{i + 1}/{total}] Processed...")
    
    print(f"\n[OK] Migration complete!")
    print(f"   Updated: {updated}")
    print(f"   Skipped (already had V4 fields): {skipped}")
    
    # Show sample
    print("\n[*] Sample migrated memory:")
    sample = collection.get(ids=[all_memories["ids"][0]], include=["metadatas"])
    if sample["metadatas"]:
        meta = sample["metadatas"][0]
        print(f"   concepts: {meta.get('concepts')}")
        print(f"   surfaces_when: {meta.get('surfaces_when')}")
        print(f"   authority_score: {meta.get('authority_score')}")


if __name__ == "__main__":
    asyncio.run(migrate_v4())
