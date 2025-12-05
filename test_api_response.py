#!/usr/bin/env python3
"""Test API response structure"""
import asyncio
import json
from src.core.graph_store import get_graph_store

async def test():
    store = get_graph_store()
    results = await store.execute_query('MATCH (n:Entity) RETURN n LIMIT 2')
    
    print("=" * 80)
    print("RAW QUERY RESULTS:")
    print("=" * 80)
    for i, row in enumerate(results):
        print(f"\nRow {i}:")
        print(json.dumps(row, indent=2, default=str))
    
    print("\n" + "=" * 80)
    print("CHECKING ENTITY STRUCTURE:")
    print("=" * 80)
    for row in results:
        values = row.get("values", [])
        if values and len(values) > 0:
            entity = values[0]
            print(f"\nEntity ID: {entity.get('id')}")
            print(f"Entity Type: {entity.get('type')}")
            print(f"Entity Name: {entity.get('name')}")
            print(f"Has 'props' field: {'props' in entity}")
            if 'props' in entity:
                props = entity['props']
                print(f"Props type: {type(props)}")
                if isinstance(props, str):
                    print(f"Props (first 200 chars): {props[:200]}")
                else:
                    print(f"Props: {props}")

if __name__ == "__main__":
    asyncio.run(test())

# Made with Bob
