#!/usr/bin/env python3
"""
Migrate ChromaDB embeddings from all-MiniLM-L6-v2 (384-dim) to thenlper/gte-base (768-dim)

This script:
1. Backs up current collection to a timestamped backup
2. Extracts all documents and metadata
3. Deletes the old collection
4. Creates new collection with gte-base embeddings
5. Re-embeds all documents

Run:
  PYTHONPATH=. .venv/bin/python scripts/migrate_embeddings_gte_base.py
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.embeddings import get_embedding_service
from src.utils.config import get_config


async def migrate():
    config = get_config()
    persist_dir = config.elefante.vector_store.persist_directory
    collection_name = config.elefante.vector_store.collection_name
    new_model = config.elefante.embeddings.model
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"{collection_name}_backup_{timestamp}"
    
    print(f"\n{'='*80}")
    print("ELEFANTE EMBEDDING MIGRATION")
    print(f"{'='*80}")
    print(f"Source collection: {collection_name}")
    print(f"Backup collection: {backup_name}")
    print(f"New model: {new_model}")
    print(f"Persist directory: {persist_dir}")
    print(f"{'='*80}\n")
    
    # Connect to ChromaDB
    client = chromadb.PersistentClient(
        path=persist_dir,
        settings=Settings(anonymized_telemetry=False, allow_reset=True),
    )
    
    # Get existing collection
    try:
        old_collection = client.get_collection(name=collection_name)
    except Exception as e:
        print(f"ERROR: Collection '{collection_name}' not found: {e}")
        return False
    
    total_memories = old_collection.count()
    print(f"Found {total_memories} memories in '{collection_name}'")
    
    if total_memories == 0:
        print("No memories to migrate. Exiting.")
        return True
    
    # Step 1: Extract all data
    print("\n[1/5] Extracting all documents and metadata...")
    all_data = old_collection.get(include=["documents", "metadatas"])
    
    ids = all_data["ids"]
    documents = all_data["documents"]
    metadatas = all_data["metadatas"]
    
    print(f"      Extracted {len(ids)} memories")
    
    # Step 2: Create backup collection (copy old embeddings)
    print(f"\n[2/5] Creating backup collection '{backup_name}'...")
    old_embeddings = old_collection.get(include=["embeddings"])["embeddings"]
    
    backup_collection = client.create_collection(
        name=backup_name,
        metadata={"hnsw:space": "cosine", "backup_of": collection_name, "backup_date": timestamp}
    )
    
    # Add to backup in batches
    batch_size = 50
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i+batch_size]
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        batch_embs = old_embeddings[i:i+batch_size]
        
        backup_collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=batch_embs
        )
    
    print(f"      Backup created with {backup_collection.count()} memories")
    
    # Step 3: Delete old collection
    print(f"\n[3/5] Deleting old collection '{collection_name}'...")
    client.delete_collection(name=collection_name)
    print(f"      Deleted")
    
    # Step 4: Create new collection
    print(f"\n[4/5] Creating new collection with {new_model}...")
    new_collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )
    
    # Step 5: Re-embed and add all documents
    print(f"\n[5/5] Re-embedding {len(ids)} memories with {new_model}...")
    
    embedding_service = get_embedding_service()
    
    for i in range(0, len(ids), batch_size):
        batch_ids = ids[i:i+batch_size]
        batch_docs = documents[i:i+batch_size]
        batch_metas = metadatas[i:i+batch_size]
        
        # Generate new embeddings
        embeddings = []
        for doc in batch_docs:
            emb = await embedding_service.generate_embedding(doc)
            embeddings.append(emb)
        
        new_collection.add(
            ids=batch_ids,
            documents=batch_docs,
            metadatas=batch_metas,
            embeddings=embeddings
        )
        
        print(f"      Migrated {min(i+batch_size, len(ids))}/{len(ids)} memories")
    
    # Verify
    final_count = new_collection.count()
    print(f"\n{'='*80}")
    print("MIGRATION COMPLETE")
    print(f"{'='*80}")
    print(f"Original count: {total_memories}")
    print(f"Migrated count: {final_count}")
    print(f"Backup location: {backup_name}")
    
    if final_count == total_memories:
        print(f"Status: SUCCESS - All memories migrated")
        print(f"\nTo delete backup (after verification):")
        print(f"  python -c \"import chromadb; c=chromadb.PersistentClient('{persist_dir}'); c.delete_collection('{backup_name}')\"")
        return True
    else:
        print(f"Status: WARNING - Count mismatch!")
        print(f"         Backup preserved at '{backup_name}'")
        return False


if __name__ == "__main__":
    success = asyncio.run(migrate())
    sys.exit(0 if success else 1)
