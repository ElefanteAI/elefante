"""
Graph Service for Dashboard
---------------------------
Handles data fetching from KuzuDB for visualization.
"""

import networkx as nx
from typing import Dict, List, Tuple
from pathlib import Path
from datetime import datetime
import kuzu
import numpy as np
from src.utils.config import get_config

class GraphService:
    def __init__(self):
        self.config = get_config()
        self.db_path = self.config.elefante.graph_store.database_path
        # Open in READ_ONLY mode to avoid locking conflicts with the main MCP server
        # self.db = kuzu.Database(self.db_path, read_only=True)
        # self.conn = kuzu.Connection(self.db)
        pass

    def get_graph_data(
        self, 
        limit: int = 100, 
        node_types: List[str] = None,
        search_query: str = "",
        date_range: Tuple[datetime, datetime] = None
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch nodes and edges from snapshot JSON with advanced filtering.
        """
        import json
        from datetime import datetime
        
        snapshot_path = Path("data/dashboard_snapshot.json")
        if not snapshot_path.exists():
            return [], [], ["Snapshot not found"]
            
        debug_log = []
            
        try:
            with open(snapshot_path, "r") as f:
                data = json.load(f)
                
            # 1. Build Node Registry by UNIQUE ID (not name - names can collide!)
            # FIXED: Previously used (name, type) which caused deduplication of
            # memories with similar content (same first 50 chars = same name)
            node_registry = {}  # id -> node_data
            
            for n in data.get("nodes", []):
                node_id = n.get("id")
                if node_id and node_id not in node_registry:
                    node_registry[node_id] = n
            
            # 2. Process Edges & Calculate Degree
            processed_edges = []
            node_degrees = {nid: 0 for nid in node_registry}
            
            for e in data.get("edges", []):
                src = e.get("from")
                dst = e.get("to")
                if src and dst and src != dst and src in node_registry and dst in node_registry:
                    processed_edges.append({
                        "from": src,
                        "to": dst,
                        "label": e.get("label", "RELATED"),
                        "title": e.get("label", "RELATED")
                    })
                    node_degrees[src] = node_degrees.get(src, 0) + 1
                    node_degrees[dst] = node_degrees.get(dst, 0) + 1

            # 3. Finalize Nodes with Filters
            nodes = []
            msg = f"Starting node processing. Registry size: {len(node_registry)}"
            debug_log.append(msg)
            with open("rejection.log", "a") as logf: logf.write(msg + "\n")
            
            # NUCLEAR OPTION: Remove User entity from backend
            user_node_id = None
            for nid, n in node_registry.items():
                if n.get("type", "").lower() == "person" and n.get("name", "").lower() == "user":
                    user_node_id = nid
                    debug_log.append(f"BACKEND: Found User node (ID: {nid}), will exclude from output")
                    break
            
            for nid, n in node_registry.items():
                # Skip User entity entirely
                if nid == user_node_id:
                    continue
                # Parse properties if string
                if isinstance(n.get("properties"), str):
                    try:
                        n["properties"] = json.loads(n["properties"])
                    except:
                        n["properties"] = {}
                        

                # Type Filter
                if node_types and n["type"] not in node_types:
                    msg = f"Rejected {n.get('name', 'Unknown')} (ID: {nid}) due to type filter: {n['type']} not in {node_types}"
                    debug_log.append(msg)
                    continue
                
                # Search Filter
                if search_query:
                    query = search_query.lower()
                    content = (n["name"] + " " + n.get("description", "")).lower()
                    if query not in content:
                        msg = f"Rejected {n.get('name', 'Unknown')} (ID: {nid}) due to search query: '{search_query}' not in '{content}'"
                        debug_log.append(msg)
                        continue
                        
                # Date Filter
                if date_range:
                    try:
                        created_at = datetime.fromisoformat(n.get("created_at", ""))
                        # Handle naive/aware comparison by ignoring timezone for simplicity in this view
                        if created_at.replace(tzinfo=None) < date_range[0].replace(tzinfo=None) or \
                           created_at.replace(tzinfo=None) > date_range[1].replace(tzinfo=None):
                            msg = f"Rejected {n.get('name', 'Unknown')} (ID: {nid}) due to date filter: {created_at.replace(tzinfo=None)} not in [{date_range[0].replace(tzinfo=None)}, {date_range[1].replace(tzinfo=None)}]"
                            debug_log.append(msg)
                            continue
                    except Exception as e:
                        debug_log.append(f"Date parsing error for node {n.get('name', 'Unknown')} (ID: {nid}): {e}. Keeping node.")
                        pass # Keep if date parsing fails
                
                # Smart Labeling
                label = n["name"]
                if n["type"] == "memory":
                    desc = n.get("description", "")
                    label = (desc[:30] + '...') if len(desc) > 30 else desc
                    if not label: label = "Memory"
                
                # Dynamic Sizing
                degree = node_degrees.get(nid, 0)
                size = min(50, 10 + (degree * 2))
                
                # Color Palette
                color_map = {
                    "person": "#E6E6FA",      # Lavender (User)
                    "company": "#FF8C00",     # DarkOrange (KnownStorm)
                    "project": "#FF6347",     # Tomato (Elefante, AI Tutor)
                    "goal": "#FFD700",        # Gold (High Valuation Exit)
                    "concept": "#BA55D3",     # MediumOrchid
                    "technology": "#00FA9A",  # MediumSpringGreen
                    "memory": "#4682B4",      # SteelBlue
                    "rule": "#DC143C",        # Crimson (Protocols)
                    "protocol": "#DC143C",    # Crimson
                    "metric": "#00FF00",      # Lime (Valuation)
                    "role": "#DA70D6",        # Orchid (Builder)
                    "location": "#20B2AA",    # LightSeaGreen
                    "event": "#F08080"        # LightCoral
                }
                color = color_map.get(n["type"].lower(), "#97C2FC") # Default Blue
                
                # Extract Cognitive Data
                cognitive_data = {
                    "intent": n.get("intent") or n.get("properties", {}).get("cognitive_analysis", {}).get("intent"),
                    "mood": n.get("emotional_context", {}).get("mood") or n.get("properties", {}).get("cognitive_analysis", {}).get("emotional_context", {}).get("mood"),
                    "insight": n.get("strategic_insight") or n.get("properties", {}).get("cognitive_analysis", {}).get("strategic_insight"),
                    "importance": n.get("importance") or n.get("properties", {}).get("importance", 1)
                }

                nodes.append({
                    "id": nid,
                    "label": label,
                    "group": n["type"],
                    "title": f"Type: {n['type']}\nName: {n['name']}\n{n.get('description', '')}",
                    "value": size,
                    "color": color,
                    "full_data": n, # Pass full data for inspector
                    "cognitive": cognitive_data # Pass extracted cognitive data
                })

            # 4. Finalize Edges (exclude User entity edges)
            edges = []
            visible_ids = {n["id"] for n in nodes}
            for e in processed_edges:
                # Skip edges connected to User entity
                if user_node_id and (e["from"] == user_node_id or e["to"] == user_node_id):
                    continue
                if e["from"] in visible_ids and e["to"] in visible_ids:
                    edges.append(e)
                else:
                    # debug_log.append(f"Rejected edge ...")
                    pass
                    
            # DUMMY NODE REMOVED
            
            # 5. Compute Semantic Similarity Edges
            semantic_edges = self._compute_similarity_edges(nodes, top_k=3, min_threshold=0.5)
            edges.extend(semantic_edges)
            
            debug_log.append(f"Added {len(semantic_edges)} semantic similarity edges")
            
            return nodes, edges, debug_log # Return debug_log
            
        except Exception as e:
            logger.error(f"Error in get_graph_data: {e}")
            msg = f"Critical error in get_graph_data: {e}"
            debug_log.append(msg)
            return [], [], debug_log # Return debug_log even on error

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """Get min and max dates from snapshot"""
        import json
        from datetime import datetime, timedelta
        
        snapshot_path = Path("data/dashboard_snapshot.json")
        if not snapshot_path.exists():
            return datetime.now(), datetime.now()
            
        try:
            with open(snapshot_path, "r") as f:
                data = json.load(f)
            
            dates = []
            for n in data.get("nodes", []):
                if "created_at" in n:
                    try:
                        dates.append(datetime.fromisoformat(n["created_at"]))
                    except:
                        pass
            
            if not dates:
                return datetime.now() - timedelta(days=1), datetime.now()
                
            return min(dates), max(dates)
        except:
            return datetime.now(), datetime.now()
            


    def get_stats(self) -> Dict[str, int]:
        """Get basic graph statistics from snapshot"""
        import json
        snapshot_path = Path("data/dashboard_snapshot.json")
        if not snapshot_path.exists():
            return {"nodes": 0, "edges": 0}
            
        try:
            with open(snapshot_path, "r") as f:
                data = json.load(f)
            return {
                "nodes": len(data.get("nodes", [])),
                "edges": len(data.get("edges", []))
            }
        except:
            return {"nodes": 0, "edges": 0}
    
    def _compute_similarity_edges(self, nodes: List[Dict], top_k: int = 3, min_threshold: float = 0.5) -> List[Dict]:
        """
        Compute semantic similarity edges using Top-K neighbor approach
        
        Strategy: For each memory, connect to its K most similar neighbors (if similarity > min_threshold).
        This guarantees mesh structure even with diverse datasets.
        
        Args:
            nodes: List of node dicts with embeddings
            top_k: Number of nearest neighbors per node (default 3)
            min_threshold: Minimum similarity to consider (default 0.5)
        
        Returns:
            List of edge dicts with {from, to, label, similarity, type: 'semantic'}
        """
        try:
            from sklearn.metrics.pairwise import cosine_similarity
            
            # Filter memory nodes with embeddings
            memory_nodes = [n for n in nodes if n.get('group') == 'memory']
            
            # Extract embeddings from full_data
            nodes_with_embeddings = []
            for node in memory_nodes:
                full_data = node.get('full_data', {})
                # Try to get embedding from properties or direct field
                embedding = None
                if isinstance(full_data.get('properties'), dict):
                    embedding = full_data['properties'].get('embedding')
                if not embedding:
                    embedding = full_data.get('embedding')
                
                if embedding and isinstance(embedding, list) and len(embedding) > 0:
                    nodes_with_embeddings.append({
                        'id': node['id'],
                        'embedding': embedding
                    })
            
            if len(nodes_with_embeddings) < 2:
                return []
            
            # Build embedding matrix
            embeddings = np.array([n['embedding'] for n in nodes_with_embeddings])
            node_ids = [n['id'] for n in nodes_with_embeddings]
            
            # Compute pairwise similarities
            sim_matrix = cosine_similarity(embeddings)
            
            # Top-K neighbor approach: For each node, find K most similar
            edges = []
            seen_pairs = set()  # Avoid duplicate edges
            
            for i in range(len(node_ids)):
                # Get similarities for this node (excluding self)
                similarities = sim_matrix[i].copy()
                similarities[i] = -1  # Exclude self
                
                # Get indices of top-K most similar nodes
                top_indices = np.argsort(similarities)[-top_k:][::-1]
                
                for j in top_indices:
                    similarity = float(sim_matrix[i][j])
                    
                    # Only add if above minimum threshold
                    if similarity < min_threshold:
                        continue
                    
                    # Create canonical pair (smaller ID first) to avoid duplicates
                    pair = tuple(sorted([node_ids[i], node_ids[j]]))
                    if pair in seen_pairs:
                        continue
                    
                    seen_pairs.add(pair)
                    edges.append({
                        'from': pair[0],
                        'to': pair[1],
                        'label': f'similar ({similarity:.2f})',
                        'title': f'Semantic similarity: {similarity:.2f}',
                        'similarity': similarity,
                        'type': 'semantic'
                    })
            
            return edges
            
        except ImportError:
            logger.warning("scikit-learn not installed, skipping similarity edges")
            return []
        except Exception as e:
            logger.error(f"Failed to compute similarity edges: {e}")
            return []
