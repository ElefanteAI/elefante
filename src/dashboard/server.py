import os
import threading
import traceback
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from typing import Dict, Any, List, Optional

from src.core.graph_store import get_graph_store
from src.utils.logger import get_logger
from src.utils.config import get_config

logger = get_logger(__name__)

app = FastAPI(title="Elefante Knowledge Garden")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Endpoints
@app.get("/api/graph")
async def get_graph(limit: int = 1000, space: Optional[str] = None):
    """
    Fetch graph data (nodes and edges) for visualization.
    """
    try:
        import traceback
        graph_store = get_graph_store()
        
        # Base query for nodes
        # We fetch entities and memories
        # TODO: Implement space filtering when 'space' property is added to schema
        
        # Fetch Nodes
        nodes_cypher = f"""
        MATCH (n:Entity)
        RETURN n
        LIMIT {limit}
        """
        node_results = await graph_store.execute_query(nodes_cypher)
        
        nodes = []
        node_ids = set()
        
        for row in node_results:
            # Kuzu returns {'values': [entity_dict]}
            values = row.get("values", [])
            if values and len(values) > 0:
                entity = values[0]  # Get first value which is the entity
                if isinstance(entity, dict):
                    node_id = str(entity.get("id", ""))
                    if node_id:
                        node_ids.add(node_id)
                        
                        # Determine visual type
                        entity_type = entity.get("type", "entity")
                        visual_type = "memory" if entity_type == "memory" else "entity"
                        if entity_type == "session":
                            visual_type = "session"
                        
                        nodes.append({
                            "id": node_id,
                            "label": entity.get("name", "Unknown"),
                            "type": visual_type,
                            "entityType": entity_type,
                            "properties": {
                                "description": entity.get("description", ""),
                                "created_at": str(entity.get("created_at", ""))
                            }
                        })
        
        # Fetch Relationships
        # Only fetch relationships where both nodes are in our node set
        # Note: Kuzu 0.11.x doesn't support type(r) function, we'll get relationship type differently
        edges_cypher = f"""
        MATCH (a:Entity)-[r]->(b:Entity)
        RETURN a.id AS source_id, b.id AS target_id, r
        LIMIT {limit * 2}
        """
        edge_results = await graph_store.execute_query(edges_cypher)
        
        edges = []
        for row in edge_results:
            # Kuzu returns {'values': [source_id, target_id, relationship]}
            values = row.get("values", [])
            if values and len(values) >= 3:
                source_id = str(values[0])
                target_id = str(values[1])
                rel = values[2]
                
                # Get relationship type from the relationship object
                rel_type = rel.get("type", "relates_to") if isinstance(rel, dict) else "relates_to"
                
                # Only include edges where both nodes exist
                if source_id in node_ids and target_id in node_ids:
                    edges.append({
                        "source": source_id,
                        "target": target_id,
                        "type": rel_type,
                        "properties": rel if isinstance(rel, dict) else {}
                    })
                
        return {
            "nodes": nodes,
            "edges": edges,
            "stats": {
                "node_count": len(nodes),
                "edge_count": len(edges)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch graph data: {e}", exc_info=True)
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    try:
        from src.core.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()
        return await orchestrator.get_stats()
    except Exception as e:
        logger.error(f"Failed to fetch stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Serve Frontend
# We assume the frontend is built to src/dashboard/ui/dist
frontend_path = os.path.join(os.path.dirname(__file__), "ui", "dist")

if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
else:
    @app.get("/")
    def index():
        return {"message": "Elefante Dashboard API is running. Frontend not found (run 'npm run build' in src/dashboard/ui)."}

def start_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the dashboard server"""
    uvicorn.run(app, host=host, port=port, log_level="info")

def serve_dashboard_in_thread(host: str = "127.0.0.1", port: int = 8000):
    """Start the dashboard server in a background thread"""
    thread = threading.Thread(target=start_server, args=(host, port), daemon=True)
    thread.start()
    return thread

if __name__ == "__main__":
    start_server()
