"""Investigate WHY 25 memories were marked contradictory."""
import json
from pathlib import Path

snap_path = Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"
with open(snap_path) as f:
    snap = json.load(f)

memories = [n for n in snap["nodes"] if n.get("type") == "memory"]
mem_by_id = {m["id"]: m for m in memories}

contra = [m for m in memories if m.get("properties", {}).get("status") == "contradictory"]
print(f"Total contradictory: {len(contra)}\n")

for i, m in enumerate(contra):
    p = m.get("properties", {})
    title = p.get("title", "NO TITLE")
    content = (p.get("content", "") or "")[:150]
    mtype = p.get("memory_type", "?")
    ktype = p.get("knowledge_type", "?")
    
    # Check if there's a related_id or contradiction reference
    related = p.get("related_memory_id") or p.get("superseded_by_id") or p.get("conflicting_memory_id")
    
    print(f"--- #{i+1} [{mtype}/{ktype}] ---")
    print(f"  Title: {title[:100]}")
    print(f"  Content: {content}")
    
    # Look for negation markers in content
    content_lower = content.lower()
    has_negation = any(w in content_lower for w in ["not ", "no ", "never ", "don't", "doesn't", "can't", "isn't", "avoid", "stop"])
    print(f"  Has negation words: {has_negation}")
    
    if related and related in mem_by_id:
        rp = mem_by_id[related].get("properties", {})
        print(f"  Conflicts with: {rp.get('title', '?')[:80]}")
    else:
        print(f"  Related ID: {related or 'NONE'}")
    print()
