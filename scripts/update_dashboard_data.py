import asyncio
import sys
import os
import json
import re
from datetime import datetime
import chromadb

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.graph_store import GraphStore
from src.utils.config import get_config, DATA_DIR


_SECRET_PATTERNS: list[re.Pattern] = [
    # OpenAI-style
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    # Slack tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    # Generic API key mentions
    re.compile(r"(?i)(api[_ -]?key\s*[:=]\s*)([^\s\"']{8,})"),
    re.compile(r"(?i)(secret\s*[:=]\s*)([^\s\"']{8,})"),
    re.compile(r"(?i)(token\s*[:=]\s*)([^\s\"']{8,})"),
]


def _redact_secrets(text: str) -> str:
    if not text:
        return text
    redacted = text
    for pattern in _SECRET_PATTERNS:
        # If the pattern has a "prefix" capture group, preserve it.
        if pattern.groups >= 2:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def _is_test_artifact(*, content: str, title: str) -> bool:
    c = (content or "").strip().lower()
    t = (title or "").strip().lower()

    if c.startswith("elefante e2e test memory") or c.startswith("hybrid search test memory"):
        return True

    if c.startswith("entity relationship test ") or c.startswith("persistence test "):
        return True

    if t.startswith("e2e-test") or "hybrid_test_" in t:
        return True

    return False

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
    
    # DEDUPLICATION: Prefer (namespace, canonical_key) when available.
    # Fallback to title-based grouping only when no canonical identity exists.
    concept_map = {}
    id_remap = {} # Map {hidden_duplicate_id: best_version_id}

    def _truthy(v) -> bool:
        if isinstance(v, bool):
            return v
        if v is None:
            return False
        if isinstance(v, (int, float)):
            return v != 0
        if isinstance(v, str):
            return v.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    def _active(meta: dict) -> bool:
        status = str(meta.get("status") or "").strip().lower()
        return not (
            _truthy(meta.get("archived"))
            or _truthy(meta.get("deprecated"))
            or status == "redundant"
        )

    def _ps_rank(meta: dict) -> int:
        ps = str(meta.get("processing_status") or "").strip().lower()
        return {"processed": 3, "processing": 2, "raw": 1, "failed": 0}.get(ps, 0)

    def _safe_int(v, default: int = 0) -> int:
        try:
            return int(v)
        except Exception:
            return default

    def _winner_better(meta_new: dict, node_new: dict, meta_old: dict, node_old: dict) -> bool:
        # Prefer active > processed > importance > access_count > newer created_at
        a_new = 1 if _active(meta_new) else 0
        a_old = 1 if _active(meta_old) else 0
        if a_new != a_old:
            return a_new > a_old

        p_new = _ps_rank(meta_new)
        p_old = _ps_rank(meta_old)
        if p_new != p_old:
            return p_new > p_old

        imp_new = _safe_int(meta_new.get("importance"), 5)
        imp_old = _safe_int(meta_old.get("importance"), 5)
        if imp_new != imp_old:
            return imp_new > imp_old

        ac_new = _safe_int(meta_new.get("access_count"), 0)
        ac_old = _safe_int(meta_old.get("access_count"), 0)
        if ac_new != ac_old:
            return ac_new > ac_old

        new_date = str(meta_new.get("created_at") or meta_new.get("timestamp") or "")
        old_date = str(meta_old.get("created_at") or meta_old.get("timestamp") or "")
        return new_date > old_date
    
    for i, memory_id in enumerate(all_memories["ids"]):
        doc = all_memories["documents"][i] if all_memories["documents"] else ""
        meta = all_memories["metadatas"][i] if all_memories["metadatas"] else {}

        doc_redacted = _redact_secrets(doc)
        
        # Create node for this memory
        # PRIORITY: Use semantic title from metadata, fallback to content truncation
        title = meta.get("title")
        if not title:
            words = doc.split()[:5]
            title = " ".join(words) if words else "Untitled Memory"
        name = title

        if _is_test_artifact(content=doc, title=str(name)):
            continue
        
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
            "description": doc_redacted,
            "created_at": meta.get("created_at", meta.get("timestamp", "")),
            "properties": {
                "content": doc_redacted,
                # Curated-first fields (used by dashboard UI and snapshot validators)
                "title": _redact_secrets(str(title) if title is not None else ""),
                "memory_type": meta.get("memory_type", "unknown"),
                "importance": importance,  # INTEGER, not string
                "tags": meta.get("tags", ""),
                "layer": meta.get("layer", "world"),
                "sublayer": meta.get("sublayer", "fact"),
                "status": meta.get("status"),
                "relationship_type": meta.get("relationship_type"),
                "archived": _truthy(meta.get("archived")),
                "deprecated": _truthy(meta.get("deprecated")),
                "supersedes_id": meta.get("supersedes_id"),
                "superseded_by_id": meta.get("superseded_by_id"),
                "canonical_key": meta.get("canonical_key"),
                "namespace": meta.get("namespace"),
                "access_count": _safe_int(meta.get("access_count"), 0),
                "last_modified": meta.get("last_modified"),
                # V5 topology (best-effort pass-through)
                "ring": meta.get("ring"),
                "knowledge_type": meta.get("knowledge_type"),
                "topic": meta.get("topic"),
                "summary": _redact_secrets(meta.get("summary", "") or ""),
                "owner_id": meta.get("owner_id"),
                "processing_status": meta.get("processing_status"),
                # V4 cognitive retrieval fields (v1.6.1)
                "concepts": meta.get("concepts"),
                "surfaces_when": meta.get("surfaces_when"),
                "authority_score": meta.get("authority_score"),
                "source": "chromadb"
            }
        }
        
        canonical_key = meta.get("canonical_key")
        namespace = meta.get("namespace") or "prod"
        group_key = ("ck", namespace, canonical_key) if canonical_key else ("title", name)

        # Deduplication Logic
        if group_key in concept_map:
            existing = concept_map[group_key]
            existing_meta = existing.get("_raw_meta") or {}

            if _winner_better(meta, node, existing_meta, existing):
                # New node replaces old one
                id_remap[existing["id"]] = node["id"]  # Map old loser -> new winner
                node["_raw_meta"] = meta
                concept_map[group_key] = node
            else:
                # New node is worse, discard it
                id_remap[node["id"]] = existing["id"]  # Map new loser -> old winner
        else:
            node["_raw_meta"] = meta
            concept_map[group_key] = node
            
    # Convert map back to list
    nodes = list(concept_map.values())
    # Drop helper field
    for n in nodes:
        if "_raw_meta" in n:
            del n["_raw_meta"]
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
        
        # =========================================================================
        # STEP 3.25: Fetch Concept nodes from Kuzu (v1.6.4 Cognitive Hub)
        # =========================================================================
        print("[*] Step 3.25: Fetching Concept nodes from Kuzu...", file=sys.stderr)
        
        try:
            concepts_query = "MATCH (c:Concept) RETURN c.id, c.name, c.canonical_name, c.usage_count, c.created_at"
            concepts_result = await store.execute_query(concepts_query)
            
            concept_count = 0
            for row in concepts_result:
                concept_id = row.get('c.id')
                if not concept_id or concept_id in seen_ids:
                    continue
                
                node = {
                    "id": concept_id,
                    "name": row.get('c.name') or row.get('c.canonical_name') or concept_id[:20],
                    "type": "concept",
                    "description": f"Shared concept: {row.get('c.canonical_name', '')}",
                    "created_at": row.get('c.created_at') or "",
                    "properties": {
                        "source": "kuzu",
                        "canonical_name": row.get('c.canonical_name'),
                        "usage_count": row.get('c.usage_count') or 0,
                        "is_concept_hub": True,
                    }
                }
                nodes.append(node)
                seen_ids.add(concept_id)
                concept_count += 1
            
            print(f"   Found {concept_count} Concept nodes", file=sys.stderr)
            
            # Fetch HAS_CONCEPT edges
            has_concept_query = "MATCH (e:Entity)-[r:HAS_CONCEPT]->(c:Concept) RETURN e.id, c.id"
            has_concept_result = await store.execute_query(has_concept_query)
            
            has_concept_count = 0
            for row in has_concept_result:
                src = row.get('e.id')
                dst = row.get('c.id')
                
                if src and dst:
                    if src in id_remap: src = id_remap[src]
                    if dst in id_remap: dst = id_remap[dst]
                    
                    if src == dst:
                        continue
                    
                    edges.append({
                        "from": src,
                        "to": dst,
                        "label": "HAS_CONCEPT",
                        "type": "concept"
                    })
                    has_concept_count += 1
            
            print(f"   Found {has_concept_count} HAS_CONCEPT edges", file=sys.stderr)
            
        except Exception as e:
            print(f"   [!] Concept graph fetch error (non-fatal): {e}", file=sys.stderr)
        
    except Exception as e:
        print(f"   [!] Kuzu error (non-fatal): {e}", file=sys.stderr)
        print("   Continuing with ChromaDB data only...", file=sys.stderr)
    
    # =========================================================================
    # STEP 3.5: Compute Semantic Similarity Edges (memory-to-memory)
    # =========================================================================
    print("[*] Step 3.5: Computing semantic similarity edges...", file=sys.stderr)

    try:
        # Track existing edges to avoid duplicates when mixing sources
        existing_edge_keys: set[tuple[str, str, str]] = set()
        for e in edges:
            src = str(e.get("from") or e.get("source") or "")
            dst = str(e.get("to") or e.get("target") or "")
            lbl = str(e.get("label") or e.get("type") or "RELATED")
            if not src or not dst:
                continue
            a, b = (src, dst) if src < dst else (dst, src)
            existing_edge_keys.add((a, b, lbl))

        # Get embeddings from ChromaDB
        all_with_embeddings = collection.get(
            include=["embeddings"],
            limit=500  # Keep bounded for dashboard snapshot
        )

        embeddings = all_with_embeddings.get("embeddings")
        ids = all_with_embeddings.get("ids", [])

        if embeddings is None or len(embeddings) <= 1:
            print("   [!] No embeddings available for similarity computation", file=sys.stderr)
        else:
            import numpy as np
            from sklearn.metrics.pairwise import cosine_similarity

            def _env_int(name: str, default: int) -> int:
                try:
                    return int(os.getenv(name, str(default)).strip())
                except Exception:
                    return default

            def _env_float(name: str, default: float) -> float:
                try:
                    return float(os.getenv(name, str(default)).strip())
                except Exception:
                    return default

            def _env_bool(name: str, default: bool) -> bool:
                v = os.getenv(name, "").strip().lower()
                if not v:
                    return default
                return v in {"1", "true", "yes", "y", "on"}

            # Semantic similarity edges can feel subjective; keep available but default OFF.
            ENABLE_SEMANTIC = _env_bool("ELEFANTE_SNAPSHOT_SEMANTIC_EDGES", False)

            # Dedup/remap IDs so similarity edges connect to the surviving concept IDs
            id_to_embedding: dict[str, list[float]] = {}
            for raw_id, emb in zip(ids, embeddings):
                if raw_id in id_remap:
                    raw_id = id_remap[raw_id]
                if raw_id in id_to_embedding:
                    continue
                id_to_embedding[str(raw_id)] = emb

            remapped_ids = list(id_to_embedding.keys())
            remapped_embeddings = [id_to_embedding[i] for i in remapped_ids]

            if len(remapped_embeddings) <= 1:
                print("   [!] Not enough unique embeddings after remap", file=sys.stderr)
            else:
                emb_array = np.array(remapped_embeddings)

                if not ENABLE_SEMANTIC:
                    print(
                        "   Semantic edges disabled (set ELEFANTE_SNAPSHOT_SEMANTIC_EDGES=1 to enable)",
                        file=sys.stderr,
                    )

                similarity_matrix = cosine_similarity(emb_array) if ENABLE_SEMANTIC else None

                # Tunable parameters (environment overrides)
                # Goals:
                # - Agnostic: no hand-coded domain rules.
                # - Avoid overfitting: prefer mutual-kNN + higher thresholds.
                # - Logical + scalable: keep edges bounded per node and avoid isolated nodes.

                THRESHOLD = _env_float("ELEFANTE_SNAPSHOT_SEMANTIC_THRESHOLD", 0.60)
                TOP_K = _env_int("ELEFANTE_SNAPSHOT_SEMANTIC_TOPK", 6)
                MUTUAL = _env_bool("ELEFANTE_SNAPSHOT_SEMANTIC_MUTUAL", True)
                STRONG = _env_float("ELEFANTE_SNAPSHOT_SEMANTIC_STRONG", 0.90)
                ENSURE_CONNECTED = _env_bool("ELEFANTE_SNAPSHOT_SEMANTIC_ENSURE_CONNECTED", True)
                WEAK_MIN = _env_float("ELEFANTE_SNAPSHOT_SEMANTIC_WEAK_MIN", 0.30)

                n = len(remapped_ids)

                if ENABLE_SEMANTIC and similarity_matrix is not None:
                    top_neighbors: dict[int, list[int]] = {}
                    best_neighbor: dict[int, tuple[int, float]] = {}

                    for i in range(n):
                        sims = [(j, float(similarity_matrix[i][j])) for j in range(n) if j != i]
                        sims.sort(key=lambda x: x[1], reverse=True)
                        top_neighbors[i] = [j for j, _ in sims[:TOP_K]]
                        if sims:
                            best_neighbor[i] = (sims[0][0], sims[0][1])

                    def _is_mutual(i: int, j: int) -> bool:
                        return (j in top_neighbors.get(i, [])) and (i in top_neighbors.get(j, []))

                    added = 0
                    added_weak = 0
                    semantic_degree = [0 for _ in range(n)]

                    for i in range(n):
                        for j in top_neighbors.get(i, []):
                            sim = float(similarity_matrix[i][j])
                            if sim < THRESHOLD:
                                continue
                            if MUTUAL and (sim < STRONG) and (not _is_mutual(i, j)):
                                continue

                            src, dst = remapped_ids[i], remapped_ids[j]
                            if src == dst:
                                continue

                            a, b = (src, dst) if src < dst else (dst, src)
                            key = (a, b, "SIMILAR")
                            if key in existing_edge_keys:
                                continue
                            existing_edge_keys.add(key)

                            edges.append({
                                "from": src,
                                "to": dst,
                                "label": "SIMILAR",
                                "type": "semantic",
                                "similarity": round(sim, 3)
                            })
                            semantic_degree[i] += 1
                            semantic_degree[j] += 1
                            added += 1

                    # Optional: avoid isolated nodes by adding a single weak link to best neighbor.
                    if ENSURE_CONNECTED:
                        for i in range(n):
                            if semantic_degree[i] > 0:
                                continue
                            if i not in best_neighbor:
                                continue
                            j, sim = best_neighbor[i]
                            if sim < WEAK_MIN:
                                continue

                            src, dst = remapped_ids[i], remapped_ids[j]
                            a, b = (src, dst) if src < dst else (dst, src)
                            key = (a, b, "SIMILAR_WEAK")
                            if key in existing_edge_keys:
                                continue
                            existing_edge_keys.add(key)

                            edges.append({
                                "from": src,
                                "to": dst,
                                "label": "SIMILAR_WEAK",
                                "type": "semantic",
                                "similarity": round(float(sim), 3)
                            })
                            semantic_degree[i] += 1
                            semantic_degree[j] += 1
                            added_weak += 1

                    print(
                        f"   Added {added} semantic edges + {added_weak} weak edges "
                        f"(threshold={THRESHOLD}, top_k={TOP_K}, mutual={MUTUAL}) (total edges now {len(edges)})",
                        file=sys.stderr,
                    )

                # Optional: add cluster hub nodes for scalable connectivity (bipartite graph)
                CLUSTER = _env_bool("ELEFANTE_SNAPSHOT_CLUSTER", True)
                if CLUSTER and n >= 8:
                    try:
                        from math import sqrt
                        from sklearn.cluster import KMeans

                        max_clusters = _env_int("ELEFANTE_SNAPSHOT_CLUSTER_MAX", 30)
                        # Heuristic: sqrt(n) clusters, bounded.
                        n_clusters = max(2, min(max_clusters, int(sqrt(n))))

                        model = KMeans(n_clusters=n_clusters, n_init="auto", random_state=42)
                        labels = model.fit_predict(emb_array)

                        # Optional: connect clusters with a sparse backbone so the overall graph is connected.
                        # This stays scalable (O(k^2) over clusters, k << n) and avoids overfitting.
                        BACKBONE = _env_bool("ELEFANTE_SNAPSHOT_CLUSTER_BACKBONE", True)
                        BACKBONE_MIN_SIM = _env_float("ELEFANTE_SNAPSHOT_CLUSTER_BACKBONE_MIN_SIM", 0.0)

                        cluster_nodes_added = 0
                        cluster_edges_added = 0

                        for c in range(n_clusters):
                            cid = f"cluster:{c:02d}"
                            nodes.append({
                                "id": cid,
                                "name": f"Cluster {c:02d}",
                                "type": "cluster",
                                "description": "Embedding cluster (agnostic connectivity hub)",
                                "created_at": datetime.utcnow().isoformat(),
                                "properties": {
                                    "source": "snapshot",
                                    "cluster_id": c,
                                    "cluster_size": int(sum(1 for x in labels if int(x) == c)),
                                },
                            })
                            cluster_nodes_added += 1

                        for i, c in enumerate(labels):
                            src = remapped_ids[i]
                            dst = f"cluster:{int(c):02d}"
                            # Directed edge is fine; frontend treats as undirected visually.
                            edges.append({
                                "from": src,
                                "to": dst,
                                "label": "IN_CLUSTER",
                                "type": "cluster",
                                "similarity": None,
                            })
                            cluster_edges_added += 1

                        # Backbone: Minimum Spanning Tree over cluster centroids by cosine distance.
                        # Guarantees global connectivity while adding only (k-1) edges.
                        if BACKBONE and n_clusters >= 2:
                            try:
                                from sklearn.metrics.pairwise import cosine_similarity

                                centroids = model.cluster_centers_
                                sim = cosine_similarity(centroids)
                                # Build candidate edges (i<j) with weight = 1 - similarity
                                cand = []
                                for i in range(n_clusters):
                                    for j in range(i + 1, n_clusters):
                                        s = float(sim[i][j])
                                        if s < float(BACKBONE_MIN_SIM):
                                            continue
                                        cand.append((1.0 - s, i, j, s))
                                cand.sort(key=lambda x: x[0])

                                parent = list(range(n_clusters))

                                def find(x: int) -> int:
                                    while parent[x] != x:
                                        parent[x] = parent[parent[x]]
                                        x = parent[x]
                                    return x

                                def union(a: int, b: int) -> bool:
                                    ra, rb = find(a), find(b)
                                    if ra == rb:
                                        return False
                                    parent[rb] = ra
                                    return True

                                backbone_added = 0
                                for _, i, j, s in cand:
                                    if union(i, j):
                                        edges.append({
                                            "from": f"cluster:{i:02d}",
                                            "to": f"cluster:{j:02d}",
                                            "label": "CLUSTER_LINK",
                                            "type": "cluster_backbone",
                                            "similarity": round(float(s), 3),
                                        })
                                        backbone_added += 1
                                        if backbone_added >= (n_clusters - 1):
                                            break

                                # If we couldn't build a full MST (e.g., because of min-sim filtering),
                                # fall back to a simple star to guarantee connectivity.
                                if backbone_added < (n_clusters - 1):
                                    hub = 0
                                    for j in range(1, n_clusters):
                                        edges.append({
                                            "from": f"cluster:{hub:02d}",
                                            "to": f"cluster:{j:02d}",
                                            "label": "CLUSTER_LINK_FALLBACK",
                                            "type": "cluster_backbone",
                                            "similarity": None,
                                        })
                                    backbone_added = n_clusters - 1

                                print(
                                    f"   Added {backbone_added} cluster backbone edges (mst)",
                                    file=sys.stderr,
                                )
                            except Exception as e:
                                print(f"   [!] Cluster backbone skipped: {e}", file=sys.stderr)

                        print(
                            f"   Added {cluster_nodes_added} cluster nodes + {cluster_edges_added} cluster edges",
                            file=sys.stderr,
                        )
                    except Exception as e:
                        print(f"   [!] Clustering skipped: {e}", file=sys.stderr)

    except ImportError as e:
        print(f"   [!] Missing dependency for similarity: {e}", file=sys.stderr)
    except Exception as e:
        print(f"   [!] Similarity computation error: {e}", file=sys.stderr)

    # =========================================================================
    # STEP 3.6: Build V5 Signal Hubs (topic / knowledge_type / ring)
    # =========================================================================
    print("[*] Step 3.6: Building V5 signal hubs...", file=sys.stderr)

    try:
        def _env_bool(name: str, default: bool) -> bool:
            v = os.getenv(name, "").strip().lower()
            if not v:
                return default
            return v in {"1", "true", "yes", "y", "on"}

        ENABLE_SIGNALS = _env_bool("ELEFANTE_SNAPSHOT_SIGNALS", True)
        if not ENABLE_SIGNALS:
            print("   Signals disabled via ELEFANTE_SNAPSHOT_SIGNALS=0", file=sys.stderr)
        else:
            # Signals are "meaning metadata" hubs. They make the graph explainable and scalable.
            # Represent as type=entity (diamond) with a signal_type property.
            signal_nodes_added = 0
            signal_edges_added = 0
            cohesion_edges_added = 0

            signal_index: dict[tuple[str, str], str] = {}

            # Track which memory nodes belong to which signal hub so we can add
            # deterministic, explainable memorymemory cohesion edges.
            signal_members: dict[str, set[str]] = {}
            signal_kind_by_id: dict[str, str] = {}

            def _signal_id(kind: str, value: str) -> str:
                # Stable, human-readable IDs
                safe = (value or "").strip().lower().replace(" ", "-")
                return f"signal:{kind}:{safe}"

            def _ensure_signal_node(kind: str, value: str) -> str:
                nonlocal signal_nodes_added
                key = (kind, value)
                if key in signal_index:
                    return signal_index[key]

                sid = _signal_id(kind, value)
                signal_index[key] = sid

                nodes.append({
                    "id": sid,
                    "name": f"{kind}: {value}",
                    "type": "entity",
                    "description": f"V5 signal hub ({kind})",
                    "created_at": datetime.utcnow().isoformat(),
                    "properties": {
                        "source": "snapshot",
                        "signal_type": kind,
                        "value": value,
                    },
                })
                signal_nodes_added += 1
                signal_kind_by_id[sid] = kind
                if sid not in signal_members:
                    signal_members[sid] = set()
                return sid

            def _add_signal_edge(mem_id: str, sid: str, label: str) -> None:
                nonlocal signal_edges_added
                a, b = (mem_id, sid) if mem_id < sid else (sid, mem_id)
                key = (a, b, label)
                if key in existing_edge_keys:
                    return
                existing_edge_keys.add(key)
                edges.append({
                    "from": mem_id,
                    "to": sid,
                    "label": label,
                    "type": "signal",
                })
                signal_edges_added += 1

                # Membership tracking for cohesion edges.
                if mem_id:
                    signal_members.setdefault(sid, set()).add(mem_id)

            # Only connect memory nodes.
            for n in nodes:
                if n.get("type") != "memory":
                    continue
                mem_id = str(n.get("id") or "")
                props = n.get("properties") if isinstance(n.get("properties"), dict) else {}

                topic = props.get("topic")
                if isinstance(topic, str) and topic.strip():
                    sid = _ensure_signal_node("topic", topic.strip())
                    _add_signal_edge(mem_id, sid, "HAS_TOPIC")

                kt = props.get("knowledge_type")
                if isinstance(kt, str) and kt.strip():
                    sid = _ensure_signal_node("knowledge_type", kt.strip())
                    _add_signal_edge(mem_id, sid, "HAS_KNOWLEDGE_TYPE")

                ring = props.get("ring")
                if isinstance(ring, str) and ring.strip():
                    sid = _ensure_signal_node("ring", ring.strip())
                    _add_signal_edge(mem_id, sid, "IN_RING")

            # Deterministic memorymemory cohesion edges derived from shared signals.
            ENABLE_COHESION = _env_bool("ELEFANTE_SNAPSHOT_COHESION_EDGES", True)
            if ENABLE_COHESION:
                try:
                    max_per_signal = int(os.getenv("ELEFANTE_SNAPSHOT_COHESION_MAX_PER_SIGNAL", "200"))
                except Exception:
                    max_per_signal = 200

                def _add_cohesion_edge(a_id: str, b_id: str, label: str) -> None:
                    nonlocal cohesion_edges_added
                    if not a_id or not b_id or a_id == b_id:
                        return
                    x, y = (a_id, b_id) if a_id < b_id else (b_id, a_id)
                    key = (x, y, label)
                    if key in existing_edge_keys:
                        return
                    existing_edge_keys.add(key)
                    edges.append({
                        "from": a_id,
                        "to": b_id,
                        "label": label,
                        "type": "cohesion",
                    })
                    cohesion_edges_added += 1

                for sid, members in signal_members.items():
                    mem_ids = sorted(members)
                    if len(mem_ids) < 2:
                        continue
                    # Stable star topology: connect all members to the first.
                    anchor = mem_ids[0]
                    kind = signal_kind_by_id.get(sid, "signal")
                    label = {
                        "topic": "CO_TOPIC",
                        "knowledge_type": "CO_KNOWLEDGE_TYPE",
                        "ring": "CO_RING",
                    }.get(kind, "CO_SIGNAL")

                    for other in mem_ids[1 : 1 + max_per_signal]:
                        _add_cohesion_edge(anchor, other, label)

                print(
                    f"   Added {cohesion_edges_added} cohesion edges (deterministic)",
                    file=sys.stderr,
                )

            print(
                f"   Added {signal_nodes_added} signal nodes + {signal_edges_added} signal edges",
                file=sys.stderr,
            )

    except Exception as e:
        print(f"   [!] Signal hub computation error: {e}", file=sys.stderr)
    
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
    
    output_path = str(DATA_DIR / "dashboard_snapshot.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    class DateTimeEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, datetime):
                return o.isoformat()
            return super().default(o)

    with open(output_path, "w") as f:
        json.dump(snapshot, f, indent=2, cls=DateTimeEncoder)

    # =========================================================================
    # STEP 5: Validate snapshot (offline checks only)
    # =========================================================================
    try:
        node_ids = {n.get("id") for n in nodes if isinstance(n, dict) and isinstance(n.get("id"), str)}
        missing_endpoints = 0
        dangling_edges = 0
        degree = {nid: 0 for nid in node_ids if nid}

        for e in edges:
            if not isinstance(e, dict):
                continue
            src = e.get("from") or e.get("source")
            dst = e.get("to") or e.get("target")
            if not isinstance(src, str) or not isinstance(dst, str):
                missing_endpoints += 1
                continue
            if src not in node_ids or dst not in node_ids:
                dangling_edges += 1
                continue
            if src in degree:
                degree[src] += 1
            if dst in degree:
                degree[dst] += 1

        isolated = sum(1 for d in degree.values() if d == 0)
        if missing_endpoints:
            print(f"   [!] Snapshot validation: {missing_endpoints} edges missing endpoints", file=sys.stderr)
        if dangling_edges:
            print(f"   [!] Snapshot validation: {dangling_edges} edges reference unknown node ids", file=sys.stderr)
        if isolated:
            print(f"   [!] Snapshot validation: {isolated} isolated nodes (degree=0)", file=sys.stderr)
    except Exception as e:
        print(f"   [!] Snapshot validation error (non-fatal): {e}", file=sys.stderr)
    
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
