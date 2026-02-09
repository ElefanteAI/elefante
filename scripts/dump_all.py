#!/usr/bin/env python3
import sys, json, asyncio
sys.path.append('/Users/jay/Documents/VSCODE/Chile2026/Elefante/Elefante_early_dec2025')
import logging
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger().setLevel(logging.CRITICAL)

from src.core.vector_store import get_vector_store

async def dump():
    vs = get_vector_store()
    vs._initialize_client()
    collection = vs._collection
    results = collection.get(include=['documents','metadatas'])

    total = len(results['ids'])
    print(f"=== TOTAL MEMORIES IN DATABASE: {total} ===\n")

    for i, (doc_id, doc, meta) in enumerate(zip(results['ids'], results['documents'], results['metadatas'])):
        mem_type = meta.get('memory_type', 'unknown')
        importance = meta.get('importance', '?')
        category = meta.get('category', '?')
        domain = meta.get('domain', '?')
        layer = meta.get('layer', '?')
        created = meta.get('created_at', '?')
        preview = (doc[:200].replace('\n', ' ')) if doc else '(empty)'
        print(f"--- Memory #{i+1} ({doc_id}) ---")
        print(f"  type={mem_type} | importance={importance} | category={category}")
        print(f"  domain={domain} | layer={layer} | created={created}")
        print(f"  content: {preview}")
        print()

asyncio.run(dump())
