import asyncio
from src.core.orchestrator import MemoryOrchestrator

async def run():
    orch = MemoryOrchestrator()
    print("🐘 Elefante Advanced Features Demo")
    print("=================================\n")

    # 1. SEARCH (Vector/Hybrid)
    # User asks: "Find memories about languages"
    query = "languages"
    print(f"🔍 FEATURE: SEARCH\n   User asks: 'Find memories about {query}'")
    results = await orch.search_memories(query, limit=1)
    if results:
        print(f"   🤖 Elefante found: \"{results[0].memory.content}\" (Relevance: {results[0].score:.2f})")
    else:
        print("   (No results found)")
    print("-" * 40)

    # 2. GRAPH CONNECTIONS
    # User asks: "What is connected to me (EnterpriseUser)?"
    print(f"\n🕸️ FEATURE: GRAPH CONNECTIONS\n   User asks: 'What is connected to me?'")
    # We query the graph for entities linked to the user
    cypher = """
    MATCH (u:Entity {name: 'EnterpriseUser'})-[r]-(n:Entity)
    RETURN n.description, label(r)
    LIMIT 3
    """
    res = await orch.graph_store.execute_query(cypher)
    if res:
        print("   🤖 Elefante sees these connections:")
        for row in res:
            desc = row['values'][0]
            rel_type = row['values'][1]
            # Clean up description if it's None (fallback to name/ID)
            if not desc: desc = "Memory Node"
            print(f"      - [{rel_type}] -> \"{desc}\"")
    else:
        print("   (No connections found)")
    print("-" * 40)

    # 3. EPISODIC MEMORY
    # User asks: "What sessions have I had?"
    print(f"\n📅 FEATURE: EPISODIC MEMORY\n   User asks: 'List my recent sessions'")
    # We use the getEpisodes tool logic (simulated here via graph query for unique sessions)
    # Actually, let's just query Session nodes if they exist, or distinct session_ids from memories
    cypher_sessions = """
    MATCH (m:Entity {type: 'memory'})
    RETURN DISTINCT m.properties.session_id
    LIMIT 5
    """
    # Note: In our previous steps we might not have created explicit Session entities for the one-off scripts 
    # unless add_memory did it automatically. Let's check.
    res_sessions = await orch.graph_store.execute_query(cypher_sessions)
    if res_sessions:
        print("   🤖 Elefante recalls these sessions:")
        for row in res_sessions:
            sid = row['values'][0]
            print(f"      - Session ID: {sid}")
    else:
        print("   (No sessions found)")

if __name__ == "__main__":
    asyncio.run(run())
