#!/usr/bin/env python3
"""Verify dashboard snapshot scores are live-computed, not stale."""
import json, sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

snap = json.load(open(os.path.expanduser("~/.elefante/data/dashboard_snapshot.json")))
mem_nodes = [n for n in snap["nodes"] if n["type"] == "memory" and "score" in n.get("properties", {})]
scores = [n["properties"]["score"] for n in mem_nodes]

print(f"Memories: {len(scores)}")
print(f"Score=100: {sum(1 for s in scores if s == 100)}")
print(f"Avg: {sum(scores)/len(scores):.1f}")
print(f"Min: {min(scores)}, Max: {max(scores)}")
print(f"Std dev: {(sum((s - sum(scores)/len(scores))**2 for s in scores)/len(scores))**0.5:.1f}")

buckets = {"50-59": 0, "60-69": 0, "70-79": 0, "80-89": 0, "90-100": 0}
for s in scores:
    if s < 60: buckets["50-59"] += 1
    elif s < 70: buckets["60-69"] += 1
    elif s < 80: buckets["70-79"] += 1
    elif s < 90: buckets["80-89"] += 1
    else: buckets["90-100"] += 1

print("\nDistribution:")
for k, v in buckets.items():
    bar = "#" * v
    print(f"  {k}: {v:2d} {bar}")

meta = snap.get("metadata", {})
print(f"\nGenerated: {meta.get('generated_at', 'N/A')}")

# Cross-validate: recompute a sample score from raw ChromaDB
from src.utils.dashboard_serializer import compute_live_score_from_raw
import chromadb
from src.utils.config import get_config

config = get_config()
client = chromadb.PersistentClient(path=config.elefante.vector_store.persist_directory)
collection = client.get_collection("memories")
all_mem = collection.get(include=["metadatas"], limit=5)

print("\nCross-validation (5 samples):")
mismatches = 0
for mid, meta in zip(all_mem["ids"], all_mem["metadatas"]):
    live = compute_live_score_from_raw(meta)
    snap_node = next((n for n in mem_nodes if n["id"] == mid), None)
    snap_score = snap_node["properties"]["score"] if snap_node else "N/A"
    # Allow ±1 for time-decay drift between snapshot generation and verification
    delta = abs(snap_score - live) if isinstance(snap_score, int) else 999
    match = "OK" if delta <= 1 else f"MISMATCH (delta={delta})"
    if delta > 1: mismatches += 1
    title = (meta.get("title") or mid[:20])[:40]
    print(f"  {title}: snap={snap_score} live={live} {match}")

if mismatches:
    print(f"\nFAILED: {mismatches} mismatches found")
    sys.exit(1)
else:
    print("\nALL SCORES VERIFIED")
