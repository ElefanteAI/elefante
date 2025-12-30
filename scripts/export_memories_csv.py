#!/usr/bin/env python3
"""
Export all memories from Elefante to CSV with complete metadata.
For manual analysis of categorization and relationships.
"""
import asyncio
import csv
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.orchestrator import get_orchestrator

async def export_memories():
    orchestrator = get_orchestrator()
    
    print("Fetching all memories from Elefante...")
    
    # Use elefanteMemoryListAll to get everything without semantic filtering
    # Use the orchestrator's vector store which is already initialized (mostly)
    # Actually Orchestrator initializes components in background task in constructor, 
    # but we need to verify initialization 
    
    # Wait a moment for async init if needed, or explicitly access it
    vector_store = orchestrator.vector_store
    
    # We need to ensure the collection is loaded. 
    # Since we are inside async function, we can await initialization if needed, 
    # but VectorStore.initialize is async. It is called by Orchestrator.initialize() 
    # which is scheduled as task.
    # Let's ensure it's ready.
    # Let's ensure it's ready.
    if vector_store._collection is None:
        # Access internal init directly since it's lazy loaded
        vector_store._initialize_client()
        
    collection = vector_store._collection
    results = collection.get(
        limit=1000,
        include=["metadatas", "documents", "embeddings"]
    )
    
    if not results or not results['ids']:
        print("No memories found!")
        return
    
    print(f"Found {len(results['ids'])} memories")
    
    # Prepare CSV output
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"data/memory_export_{timestamp}.csv"
    
    # Define all possible metadata fields
    fieldnames = [
        'id',
        'content',
        'memory_type',
        'importance',
        'tags',
        'status',
        'created_at',
        'domain',
        'category',
        'subcategory',
        'intent',
        'urgency',
        'confidence',
        'relationship_type',
        'related_memory_ids',
        'conflict_ids',
        'supersedes_id',
        'superseded_by_id',
        'source',
        'source_detail',
        'verified',
        'author',
        'project',
        'last_accessed',
        'access_count',
        'decay_rate',
        'reinforcement_factor',
        'version',
        'deprecated',
        'archived',
        'title',
        'emotional_valence',
        'emotional_arousal',
        'emotional_mood',
        'has_embedding'
    ]
    
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        
        for i, memory_id in enumerate(results['ids']):
            metadata = results['metadatas'][i] if results['metadatas'] else {}
            content = results['documents'][i] if results['documents'] else ""
            embeddings = results.get('embeddings')
            has_embedding = embeddings[i] is not None if (embeddings is not None and len(embeddings) > i) else False
            
            # Extract nested metadata
            custom_meta = metadata.get('custom_metadata', {})
            if isinstance(custom_meta, str):
                try:
                    custom_meta = json.loads(custom_meta)
                except:
                    custom_meta = {}
            
            emotional = custom_meta.get('emotional_context', {})
            
            row = {
                'id': memory_id,
                'content': content[:500] + ('...' if len(content) > 500 else ''),  # Truncate for CSV
                'memory_type': metadata.get('memory_type', ''),
                'importance': metadata.get('importance', ''),
                'tags': metadata.get('tags', ''),
                'status': metadata.get('status', ''),
                'created_at': metadata.get('created_at', ''),
                'domain': metadata.get('domain', ''),
                'category': metadata.get('category', ''),
                'subcategory': metadata.get('subcategory', ''),
                'intent': metadata.get('intent', ''),
                'urgency': metadata.get('urgency', ''),
                'confidence': metadata.get('confidence', ''),
                'relationship_type': metadata.get('relationship_type', ''),
                'related_memory_ids': json.dumps(metadata.get('related_memory_ids', [])),
                'conflict_ids': json.dumps(metadata.get('conflict_ids', [])),
                'supersedes_id': metadata.get('supersedes_id', ''),
                'superseded_by_id': metadata.get('superseded_by_id', ''),
                'source': metadata.get('source', ''),
                'source_detail': metadata.get('source_detail', ''),
                'verified': metadata.get('verified', ''),
                'author': metadata.get('author', ''),
                'project': metadata.get('project', ''),
                'last_accessed': metadata.get('last_accessed', ''),
                'access_count': metadata.get('access_count', ''),
                'decay_rate': metadata.get('decay_rate', ''),
                'reinforcement_factor': metadata.get('reinforcement_factor', ''),
                'version': metadata.get('version', ''),
                'deprecated': metadata.get('deprecated', ''),
                'archived': metadata.get('archived', ''),
                'title': custom_meta.get('title', ''),
                'emotional_valence': emotional.get('valence', ''),
                'emotional_arousal': emotional.get('arousal', ''),
                'emotional_mood': emotional.get('mood', ''),
                'has_embedding': has_embedding
            }
            
            writer.writerow(row)
            
            if (i + 1) % 10 == 0:
                print(f"Exported {i + 1}/{len(results['ids'])} memories...")
    
    print(f"\n Export complete: {output_file}")
    print(f"Total memories exported: {len(results['ids'])}")
    
    # Print summary statistics
    print("\n Summary Statistics:")
    memory_types = {}
    statuses = {}
    for meta in results['metadatas']:
        mtype = meta.get('memory_type', 'unknown')
        memory_types[mtype] = memory_types.get(mtype, 0) + 1
        
        status = meta.get('status', 'unknown')
        statuses[status] = statuses.get(status, 0) + 1
    
    print("\nMemory Types:")
    for mtype, count in sorted(memory_types.items(), key=lambda x: x[1], reverse=True):
        print(f"  {mtype}: {count}")
    
    print("\nStatuses:")
    for status, count in sorted(statuses.items(), key=lambda x: x[1], reverse=True):
        print(f"  {status}: {count}")

if __name__ == "__main__":
    asyncio.run(export_memories())

