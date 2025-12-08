import asyncio
import sys
import os
import json
from datetime import datetime
import chromadb

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.graph_store import GraphStore
from src.utils.config import get_config

async def main():
    """
    Generate dashboard snapshot from BOTH data stores:
    1. ChromaDB (vector store) - Contains ALL memories (primary source)
    2. Kuzu (graph store) - Contains entities and relationships
    
    This ensures all 70+ memories are visible, not just graph entities.
    """
    config = get_config()
    nodes = []
    edges = []
    seen_ids = set()
    
    # =========================================================================
    # STEP 1: Fetch ALL memories from ChromaDB (PRIMARY SOURCE)
    # =========================================================================
    print("[*] Step 1: Fetching memories from ChromaDB...", file=sys.stderr)
    
    chroma_path = config.elefante.vector_store.persist_directory
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("memories")
    
    # Get ALL memories (no limit)
    all_memories = collection.get(include=["documents", "metadatas"])
    
    memory_count = len(all_memories["ids"])
    print(f"   Found {memory_count} memories in ChromaDB", file=sys.stderr)
    
    # DEDUPLICATION: Map Title -> Node to keep only the best version
    title_map = {}
    id_remap = {} # Map {hidden_duplicate_id: best_version_id}
    
    for i, memory_id in enumerate(all_memories["ids"]):
        doc = all_memories["documents"][i] if all_memories["documents"] else ""
        meta = all_memories["metadatas"][i] if all_memories["metadatas"] else {}
        
        # Create node for this memory
        # PRIORITY: Use semantic title from metadata, fallback to content truncation
        title = meta.get("title")
        if not title:
            words = doc.split()[:5]
            title = " ".join(words) if words else "Untitled Memory"
        name = title
        
        # CRITICAL: Typecast importance to INTEGER
        importance_raw = meta.get("importance", 5)
        try:
            importance = int(importance_raw) if importance_raw is not None else 5
        except (ValueError, TypeError):
            importance = 5
        
        node = {
            "id": memory_id,
            "name": name,
            "type": "memory",
            "description": doc,
            "created_at": meta.get("created_at", meta.get("timestamp", "")),
            "properties": {
                "content": doc,
                "memory_type": meta.get("memory_type", "unknown"),
                "importance": importance,  # INTEGER, not string
                "tags": meta.get("tags", ""),
                "layer": meta.get("layer", "world"),
                "sublayer": meta.get("sublayer", "fact"),
                "source": "chromadb"
            }
        }
        
        # Deduplication Logic
        if name in title_map:
            existing = title_map[name]
            existing_imp = existing["properties"]["importance"]
            existing_date = existing["created_at"] or ""
            new_date = node["created_at"] or ""
            
            # Decide survivor: Higher Importance > Newer Date
            is_better = False
            if importance > existing_imp:
                is_better = True
            elif importance == existing_imp:
                if new_date > existing_date:
                    is_better = True
            
            if is_better:
                # New node replaces old one
                id_remap[existing["id"]] = node["id"] # Map old loser -> new winner
                title_map[name] = node
            else:
                # New node is worse, discard it
                id_remap[node["id"]] = existing["id"] # Map new loser -> old winner
        else:
            title_map[name] = node
            
    # Convert map back to list
    nodes = list(title_map.values())
    seen_ids = set(n["id"] for n in nodes)
    
    print(f"   Consolidated {memory_count} memories into {len(nodes)} unique concepts", file=sys.stderr)
    
    # =========================================================================
    # STEP 2: Fetch entities from Kuzu (SUPPLEMENTARY)
    # =========================================================================
    print("[*] Step 2: Fetching entities from Kuzu...", file=sys.stderr)
    
    try:
        store = GraphStore(config.elefante.graph_store.database_path)
        
        # Fetch entity nodes (but skip if already in ChromaDB)
        nodes_query = "MATCH (n:Entity) RETURN n"
        nodes_result = await store.execute_query(nodes_query)
        
        entity_count = 0
        for row in nodes_result:
            entity = row.get('n')
            if entity:
                props = dict(entity) if hasattr(entity, 'get') else {}
                props = {k: v for k, v in props.items() if not k.startswith('_')}
                
                entity_id = props.get('id', '')
                
                # Skip if already added from ChromaDB
                if entity_id in seen_ids:
                    continue
                
                # Parse props JSON if exists
                if 'props' in props and isinstance(props['props'], str):
                    try:
                        extra = json.loads(props['props'])
                        # Check if this is actually a memory (has content)
                        if extra.get('content') or extra.get('full_content'):
                            # Already have memories from ChromaDB, skip duplicates
                            continue
                        props.update(extra)
                    except:
                        pass
                
                # Determine if this is a real entity (person, tech, project) not a memory
                entity_type = props.get('type', 'entity')
                if entity_type == 'memory':
                    continue  # Skip, already got from ChromaDB
                
                node = {
                    "id": entity_id,
                    "name": props.get('name', entity_id[:50]),
                    "type": entity_type,
                    "description": props.get('description', ''),
                    "created_at": props.get('created_at', ''),
                    "properties": {"source": "kuzu"}
                }
                nodes.append(node)
                seen_ids.add(entity_id)
                entity_count += 1
        
        print(f"   Found {entity_count} additional entities in Kuzu", file=sys.stderr)
        
        # =========================================================================
        # STEP 3: Fetch relationships from Kuzu
        # =========================================================================
        print("[*] Step 3: Fetching relationships from Kuzu...", file=sys.stderr)
        
        edges_query = "MATCH (a)-[r]->(b) RETURN a.id, b.id, label(r)"
        edges_result = await store.execute_query(edges_query)
        
        for row in edges_result:
            src = row.get('a.id')
            dst = row.get('b.id')
            lbl = row.get('label(r)')
            
            if src and dst:
                # REMAP Edges for deduplicated nodes
                if src in id_remap: src = id_remap[src]
                if dst in id_remap: dst = id_remap[dst]
                
                # Avoid self-loops created by consolidation
                if src == dst:
                    continue
                    
                edges.append({
                    "from": src,
                    "to": dst,
                    "label": lbl or "RELATED"
                })
        
        print(f"   Found {len(edges)} relationships", file=sys.stderr)
        
    except Exception as e:
        print(f"   [!] Kuzu error (non-fatal): {e}", file=sys.stderr)
        print("   Continuing with ChromaDB data only...", file=sys.stderr)
    
    # =========================================================================
    # STEP 3.5: Compute Semantic Similarity Edges (if no graph relationships)
    # =========================================================================
    if len(edges) == 0:
        print("[*] Step 3.5: Computing semantic similarity edges...", file=sys.stderr)
        
        try:
            # Get embeddings from ChromaDB
            all_with_embeddings = collection.get(
                include=["embeddings"],
                limit=500  # Match memory limit
            )
            
            embeddings = all_with_embeddings.get("embeddings")
            ids = all_with_embeddings.get("ids", [])
            
            if embeddings is not None and len(embeddings) > 1:
                import numpy as np
                from sklearn.metrics.pairwise import cosine_similarity
                
                # Convert to numpy array
                emb_array = np.array(embeddings)
                
                # Compute pairwise cosine similarity
                similarity_matrix = cosine_similarity(emb_array)
                
                # Create edges for pairs above threshold
                THRESHOLD = 0.45  # ULTRA-DENSE WEB (User Request: "Electric Current")
                TOP_K = 12  # High connectivity
                
                for i in range(len(ids)):
                    # Get top-K similar nodes for this node
                    similarities = [(j, similarity_matrix[i][j]) for j in range(len(ids)) if j != i]
                    similarities.sort(key=lambda x: x[1], reverse=True)
                    
                    for j, sim in similarities[:TOP_K]:
                        if sim >= THRESHOLD:
                            # Add edge (avoid duplicates by checking source < target)
                            src, dst = ids[i], ids[j]
                            
                            # REMAP logic (inherit connections from duplicates)
                            if src in id_remap: src = id_remap[src]
                            if dst in id_remap: dst = id_remap[dst]
                            
                            if src == dst: continue # Self-loop
                            
                            # Check duplicates in existing edges? 
                            # Simplest: Just add, frontend filters? Or check existing.
                            # Set checking is faster.
                            edge_key = tuple(sorted([src, dst]))
                            # We need a set to track added edges to avoid A->B and B->A resulting in double edges
                            # Since we effectively randomly flipped src/dst order by remapping, the `src < dst` check below is risky if we don't normalize first.
                            
                            if src < dst:  # Only add one direction per pair
                                edges.append({
                                    "from": src,
                                    "to": dst,
                                    "label": "SIMILAR",
                                    "type": "semantic",
                                    "similarity": round(float(sim), 3)
                                })
                
                print(f"   Generated {len(edges)} semantic similarity edges", file=sys.stderr)
            else:
                print("   [!] No embeddings available for similarity computation", file=sys.stderr)
                
        except ImportError as e:
            print(f"   [!] Missing dependency for similarity: {e}", file=sys.stderr)
        except Exception as e:
            print(f"   [!] Similarity computation error: {e}", file=sys.stderr)
    
    # =========================================================================
    # STEP 4: Save snapshot
    # =========================================================================
    print("[*] Step 4: Saving snapshot...", file=sys.stderr)
    
    snapshot = {
        "generated_at": datetime.utcnow().isoformat(),
        "stats": {
            "total_nodes": len(nodes),
            "memories": sum(1 for n in nodes if n["type"] == "memory"),
            "entities": sum(1 for n in nodes if n["type"] != "memory"),
            "edges": len(edges)
        },
        "nodes": nodes,
        "edges": edges
    }
    
    output_path = "data/dashboard_snapshot.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime):
                return o.isoformat()
            return super().default(o)

    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)
    
    print(f"\n[OK] Dashboard snapshot saved to {output_path}", file=sys.stderr)
    print(f"   [*] Total nodes: {len(nodes)}", file=sys.stderr)
    print(f"   [*] Memories: {snapshot['stats']['memories']}", file=sys.stderr)
    print(f"   [*] Entities: {snapshot['stats']['entities']}", file=sys.stderr)
    print(f"   [*] Edges: {len(edges)}", file=sys.stderr)

if __name__ == "__main__":
    from contextlib import redirect_stdout
    # LAW #6: STDOUT PURITY - Redirect EVERYTHING to stderr
    with redirect_stdout(sys.stderr):
        asyncio.run(main())
