#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────────────
# NAME    : dump_memories_all.py
# VERSION : 2.5.2
# CHANGED : 2026-04-15
# PURPOSE : Bypass-the-orchestrator raw ChromaDB dump for emergency visibility
#           when normal routes are broken or filtered.
# WHEN    : When elefante-MemorySearch returns unexpected results and you need to
#           confirm what is actually stored in ChromaDB without any filtering. Also
#           useful before and after a surgical delete to verify the raw count.
# USAGE   : python scripts/debug/dump_memories_all.py
# NOTES   : Reads directly from ChromaDB — bypasses all orchestrator logic. Output
#           may contain memories that the intelligence pipeline would normally filter.
#           Safe to run with Elefante ON or OFF.
# LASTRUN : yyyy-mm-dd hh:mm — update manually
# ─────────────────────────────────────────────────────────────────────────────
"""Dump all memories from ChromaDB — raw inspection."""
import os
import sys
import chromadb
import yaml

# Resolve config path
config_path = os.environ.get(
    "ELEFANTE_CONFIG_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config.yaml")
)

with open(config_path) as f:
    config = yaml.safe_load(f)

# Resolve ChromaDB path from config (mirrors config.py resolution)
data_dir = os.path.join(os.path.dirname(config_path), "data")
chroma_path = os.path.join(data_dir, "chroma")

if not os.path.isdir(chroma_path):
    print(f"ChromaDB directory not found: {chroma_path}")
    sys.exit(1)

client = chromadb.PersistentClient(path=chroma_path)
col = client.get_collection("memories")
results = col.get(include=["documents", "metadatas"])

total = len(results["ids"])
print(f"TOTAL MEMORIES: {total}")
print("=" * 80)

for i in range(total):
    mid = results["ids"][i]
    doc = results["documents"][i]
    meta = results["metadatas"][i]
    
    print(f"\n--- MEMORY {i+1}/{total} ---")
    print(f"ID: {mid}")
    print(f"CONTENT: {doc[:300]}")
    
    score = meta.get("score", "N/A")
    memory_type = meta.get("memory_type", "N/A")
    domain = meta.get("domain", "N/A")
    category = meta.get("category", "N/A")
    created = meta.get("created_at", "N/A")
    status = meta.get("processing_status", "N/A")
    tags = meta.get("tags", "N/A")
    access_count = meta.get("access_count", "N/A")
    deprecated = meta.get("deprecated", "N/A")
    
    print(f"  score={score} | type={memory_type} | domain={domain}")
    print(f"  category={category}")
    print(f"  created={created} | status={status} | access_count={access_count}")
    print(f"  tags={tags} | deprecated={deprecated}")
