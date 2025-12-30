"""
Topology Repair Script - v27.0 Semantic Topology
Injects semantic relationships between memories based on metadata analysis.

This script solves the "Bag of Dots" problem by creating edges between
memories that share critical tags, categories, or semantic themes.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.vector_store import VectorStore
from src.core.graph_store import GraphStore
from src.utils.logger import get_logger

logger = get_logger(__name__)


def repair_topology():
    """
    Scan all memories and inject semantic relationship edges.
    
    Creates edges based on:
    1. Identity Cluster: CORE_PERSONA tags
    2. Project Context: Same project (elefante)
    3. Domain Clustering: Shared tags (documentation, debug, etc.)
    4. Importance Hierarchy: High-importance memories linked to related lower-importance
    """
    
    print("[*] TOPOLOGY REPAIR v27.0 - Starting...")
    
    # Initialize stores
    vector_store = VectorStore()
    vector_store._initialize_client()
    
    # Get all memories
    print("[*] Fetching all memories...")
    all_memories = vector_store._collection.get(
        include=["documents", "metadatas"]
    )
    
    total_memories = len(all_memories['ids'])
    print(f"[OK] Found {total_memories} memories")
    
    # Build memory lookup
    memories = []
    for i in range(total_memories):
        mem = {
            'id': all_memories['ids'][i],
            'content': all_memories['documents'][i],
            'metadata': all_memories['metadatas'][i]
        }
        memories.append(mem)
    
    # Track edges created
    edges_created = {
        'IDENTITY_BOND': 0,
        'PROJECT_LINK': 0,
        'DOMAIN_CLUSTER': 0,
        'IMPORTANCE_HIERARCHY': 0
    }
    
    print("\n[*] Analyzing relationships...")
    
    # RULE 1: Identity Cluster (CORE_PERSONA)
    persona_memories = [m for m in memories if 'CORE_PERSONA' in str(m['metadata'].get('tags', []))]
    print(f"  [ID] Identity Cluster: {len(persona_memories)} memories")
    
    for i, mem_a in enumerate(persona_memories):
        for mem_b in persona_memories[i+1:]:
            # Link all persona memories together
            related_ids = mem_a['metadata'].get('related_memory_ids', [])
            if isinstance(related_ids, str):
                related_ids = eval(related_ids) if related_ids else []
            
            if mem_b['id'] not in related_ids:
                related_ids.append(mem_b['id'])
                mem_a['metadata']['related_memory_ids'] = related_ids
                edges_created['IDENTITY_BOND'] += 1
    
    # RULE 2: Project Context (elefante project)
    elefante_memories = [m for m in memories if m['metadata'].get('project') == 'elefante']
    print(f"  [PRJ] Elefante Project: {len(elefante_memories)} memories")
    
    # RULE 3: Domain Clustering (shared tags)
    critical_tags = ['documentation', 'debug', 'neural-register', 'critical-laws', 'workspace-hygiene']
    
    for tag in critical_tags:
        tag_memories = [m for m in memories if tag in str(m['metadata'].get('tags', []))]
        if len(tag_memories) > 1:
            print(f"  [TAG] Tag '{tag}': {len(tag_memories)} memories")
            
            # Link memories with same tag
            for i, mem_a in enumerate(tag_memories):
                for mem_b in tag_memories[i+1:]:
                    related_ids = mem_a['metadata'].get('related_memory_ids', [])
                    if isinstance(related_ids, str):
                        related_ids = eval(related_ids) if related_ids else []
                    
                    if mem_b['id'] not in related_ids:
                        related_ids.append(mem_b['id'])
                        mem_a['metadata']['related_memory_ids'] = related_ids
                        edges_created['DOMAIN_CLUSTER'] += 1
    
    # RULE 4: Importance Hierarchy (high-importance as hubs)
    high_importance = [m for m in memories if m['metadata'].get('importance', 5) >= 9]
    print(f"  [HUB] High Importance Hubs: {len(high_importance)} memories")
    
    for hub in high_importance:
        hub_tags = set(str(hub['metadata'].get('tags', [])).split(','))
        
        # Link to related lower-importance memories
        for mem in memories:
            if mem['id'] == hub['id']:
                continue
            
            mem_tags = set(str(mem['metadata'].get('tags', [])).split(','))
            
            # If they share at least 2 tags, create hierarchy link
            if len(hub_tags & mem_tags) >= 2:
                related_ids = hub['metadata'].get('related_memory_ids', [])
                if isinstance(related_ids, str):
                    related_ids = eval(related_ids) if related_ids else []
                
                if mem['id'] not in related_ids:
                    related_ids.append(mem['id'])
                    hub['metadata']['related_memory_ids'] = related_ids
                    edges_created['IMPORTANCE_HIERARCHY'] += 1
    
    # Update ChromaDB with new relationships
    print("\n[*] Updating database...")
    
    import json
    
    ids_to_update = []
    metadatas_to_update = []
    
    for mem in memories:
        if 'related_memory_ids' in mem['metadata']:
            # Convert list to JSON string for ChromaDB compatibility
            metadata_copy = mem['metadata'].copy()
            if isinstance(metadata_copy['related_memory_ids'], list):
                metadata_copy['related_memory_ids'] = json.dumps(metadata_copy['related_memory_ids'])
            
            ids_to_update.append(mem['id'])
            metadatas_to_update.append(metadata_copy)
    
    if ids_to_update:
        vector_store._collection.update(
            ids=ids_to_update,
            metadatas=metadatas_to_update
        )
        print(f"[OK] Updated {len(ids_to_update)} memories with new relationships")
    
    # Summary
    print("\n" + "="*60)
    print("[SUCCESS] TOPOLOGY REPAIR COMPLETE")
    print("="*60)
    print(f"Total Memories Analyzed: {total_memories}")
    print(f"\nEdges Created:")
    for edge_type, count in edges_created.items():
        print(f"  {edge_type}: {count}")
    print(f"\nTotal Semantic Threads: {sum(edges_created.values())}")
    print("="*60)
    
    return edges_created


if __name__ == "__main__":
    try:
        repair_topology()
    except Exception as e:
        logger.error(f"Topology repair failed: {e}")
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

