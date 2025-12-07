#!/usr/bin/env python
"""
🐘 ELEFANTE INTERACTIVE DEMO
Walk through all MCP features step by step
"""
import asyncio
import os
import sys
import json

sys.path.append(os.getcwd())

from src.mcp.server import ElefanteMCPServer

def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")

def print_result(result):
    print(json.dumps(result, indent=2, default=str))

async def demo():
    server = ElefanteMCPServer()
    
    # =========================================================================
    # FEATURE 1: addMemory
    # =========================================================================
    print_header("FEATURE 1: addMemory")
    print("Adding a NEW memory about user preference...")
    
    result = await server._handle_add_memory({
        "content": "Jay prefers dark mode in all applications.",
        "layer": "self",
        "sublayer": "preference",
        "importance": 8,
        "tags": ["ui", "preference"]
    })
    print_result(result)
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 2: addMemory (REDUNDANT detection)
    # =========================================================================
    print_header("FEATURE 2: addMemory (REDUNDANT Detection)")
    print("Adding the SAME memory again to trigger REDUNDANT classification...")
    
    result = await server._handle_add_memory({
        "content": "Jay prefers dark mode in all applications.",
        "layer": "self",
        "sublayer": "preference",
        "importance": 8
    })
    print_result(result)
    print("\n👆 Notice classification is 'REDUNDANT'")
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 3: addMemory (CONTRADICTORY detection)
    # =========================================================================
    print_header("FEATURE 3: addMemory (CONTRADICTORY Detection)")
    print("Adding a CONTRADICTING memory...")
    
    result = await server._handle_add_memory({
        "content": "Jay does NOT prefer dark mode in applications.",
        "layer": "self",
        "sublayer": "preference",
        "importance": 8
    })
    print_result(result)
    print("\n👆 If similar enough, classification should be 'CONTRADICTORY'")
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 4: searchMemories
    # =========================================================================
    print_header("FEATURE 4: searchMemories")
    print("Searching for 'dark mode'...")
    
    result = await server._handle_search_memories({
        "query": "dark mode preference",
        "limit": 5
    })
    print_result(result)
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 5: getStats
    # =========================================================================
    print_header("FEATURE 5: getStats")
    print("Getting system statistics...")
    
    result = await server._handle_get_stats({})
    print_result(result)
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 6: listAllMemories
    # =========================================================================
    print_header("FEATURE 6: listAllMemories")
    print("Listing all memories (no query needed)...")
    
    result = await server._handle_list_all_memories({"limit": 10})
    print(f"Total memories: {result.get('count', 0)}")
    if result.get('memories'):
        for i, mem in enumerate(result['memories'][:3]):
            print(f"  {i+1}. {mem.get('content', '')[:50]}...")
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 7: createEntity
    # =========================================================================
    print_header("FEATURE 7: createEntity")
    print("Creating a custom entity 'Elefante Project'...")
    
    result = await server._handle_create_entity({
        "name": "Elefante Project",
        "type": "project",
        "properties": {"status": "active", "language": "python"}
    })
    entity_id = result.get("entity_id")
    print_result(result)
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # FEATURE 8: queryGraph
    # =========================================================================
    print_header("FEATURE 8: queryGraph (Raw Cypher)")
    print("Querying graph for all entities...")
    
    result = await server._handle_query_graph({
        "cypher_query": "MATCH (e:Entity) RETURN e.name, e.type LIMIT 5"
    })
    print_result(result)
    input("\nPress Enter to continue...")
    
    # =========================================================================
    # DONE
    # =========================================================================
    print_header("🎉 DEMO COMPLETE")
    print("You've seen the core Elefante features:")
    print("  1. addMemory     - Store with classification")
    print("  2. searchMemories - Semantic search")
    print("  3. getStats       - System health")
    print("  4. listAllMemories - Browse all")
    print("  5. createEntity   - Custom graph nodes")
    print("  6. queryGraph     - Raw Cypher queries")
    print("\nThe MCP server is still running. Use these tools from your IDE!")

if __name__ == "__main__":
    try:
        asyncio.run(demo())
    except KeyboardInterrupt:
        print("\n\n⚠ Demo interrupted")
