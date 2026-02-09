#!/usr/bin/env python3
import sys
import os
import json
import asyncio

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(project_root)

# Set environment to avoid potential issues with interactive modes or defaults
os.environ["ELEFANTE_ENV"] = "production" 

try:
    from src.core.orchestrator import MemoryOrchestrator
except ImportError as e:
    print(json.dumps({"error": f"Import failed: {str(e)}", "path": sys.path}))
    sys.exit(1)

async def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No query provided"}))
        sys.exit(1)

    query = sys.argv[1]
    
    try:
        # Initialize Orchestrator
        # Silence logging to avoid JSON pollution
        import logging
        logging.basicConfig(level=logging.CRITICAL)
        logging.getLogger().setLevel(logging.CRITICAL)
        
        # Specific silence for kuzu/chroma if they bypass root
        logging.getLogger("kuzu").setLevel(logging.CRITICAL)
        logging.getLogger("chromadb").setLevel(logging.CRITICAL)
        logging.getLogger("src.core.orchestrator").setLevel(logging.CRITICAL)

        orchestrator = MemoryOrchestrator()
        
        # Search with higher limit to capture project knowledge beyond LAW noise
        results = await orchestrator.search_memories(
            query=query,
            limit=20
        )
        
        # Serialize
        output = []
        for r in results:
            # Check structure based on analysis: r is SearchResult, r.memory is Memory
            try:
                mem = r.memory  # This is the Memory object
                mem_id = mem.id if hasattr(mem, 'id') else 'unknown'
                content = mem.content if hasattr(mem, 'content') else ''
                
                # REPAIR: Extract type from metadata.memory_type instead of root property
                mem_type = 'unknown'
                if hasattr(mem, 'metadata'):
                    # Access pydantic model via attribute
                    if hasattr(mem.metadata, 'memory_type'):
                        mem_type = mem.metadata.memory_type
                    # Or dictionary access if it was converted
                    elif isinstance(mem.metadata, dict) and 'memory_type' in mem.metadata:
                        mem_type = mem.metadata['memory_type']
                    # Fallback for old schema
                    elif hasattr(mem.metadata, 'type'):
                        mem_type = mem.metadata.type
                # Fallback to root (if flat object)
                elif hasattr(mem, 'type'):
                    mem_type = mem.type
                elif hasattr(mem, 'memory_type'):
                    mem_type = mem.memory_type

                score = r.score
                
                # Extract rich metadata for LLM context
                domain = 'unknown'
                category = 'unknown'
                layer = 'unknown'
                importance = 5
                if hasattr(mem, 'metadata'):
                    if hasattr(mem.metadata, 'domain'):
                        domain = str(mem.metadata.domain)
                    elif isinstance(mem.metadata, dict):
                        domain = mem.metadata.get('domain', 'unknown')
                    if hasattr(mem.metadata, 'category'):
                        category = str(mem.metadata.category)
                    elif isinstance(mem.metadata, dict):
                        category = mem.metadata.get('category', 'unknown')
                    if hasattr(mem.metadata, 'layer'):
                        layer = str(mem.metadata.layer)
                    elif isinstance(mem.metadata, dict):
                        layer = mem.metadata.get('layer', 'unknown')
                    if hasattr(mem.metadata, 'importance'):
                        importance = int(mem.metadata.importance)
                    elif isinstance(mem.metadata, dict):
                        importance = int(mem.metadata.get('importance', 5))

                output.append({
                    "id": str(mem_id),
                    "content": content,
                    "type": str(mem_type),
                    "domain": domain,
                    "category": category,
                    "layer": layer,
                    "importance": importance,
                    "score": float(score)
                })
            except Exception as e:
                # debug log in case of failure, but printed to stderr to not spoil stdout details
                print(f"DEBUG: Failed to serialize result: {e}", file=sys.stderr)
                continue
        
        print(json.dumps(output))
        
    except Exception as e:
        # Print error in JSON format so Node can parse it
        import traceback
        trace = traceback.format_exc()
        print(json.dumps({"error": str(e), "trace": trace}))
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
