"""Audit all 121 memories for golden demo readiness."""
import json
from pathlib import Path

snap_path = Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"
with open(snap_path) as f:
    snap = json.load(f)

memories = [n for n in snap["nodes"] if n.get("type") == "memory"]
print(f"Total memories: {len(memories)}\n")

# Topic distribution
topics = {}
for m in memories:
    t = m.get("properties", {}).get("topic", "general")
    topics[t] = topics.get(t, 0) + 1
print("=== TOPIC DISTRIBUTION ===")
for t, c in sorted(topics.items(), key=lambda x: -x[1]):
    pct = round(c / len(memories) * 100)
    print(f"  {t}: {c} ({pct}%)")

print()

# Type distribution
types = {}
for m in memories:
    t = m.get("properties", {}).get("memory_type", "unknown")
    types[t] = types.get(t, 0) + 1
print("=== TYPE DISTRIBUTION ===")
for t, c in sorted(types.items(), key=lambda x: -x[1]):
    print(f"  {t}: {c} ({round(c / len(memories) * 100)}%)")

print()

# Edge connectivity
mem_ids = {m["id"] for m in memories}
connected = set()
for e in snap["edges"]:
    src = e.get("source") or e.get("src") or e.get("from", "")
    tgt = e.get("target") or e.get("tgt") or e.get("to", "")
    if src in mem_ids:
        connected.add(src)
    if tgt in mem_ids:
        connected.add(tgt)
orphan_count = len(memories) - len(connected)
print("=== CONNECTIVITY ===")
print(f"  Connected: {len(connected)} / {len(memories)}")
print(f"  Orphans: {orphan_count}")

print()

# Score distribution
scores = [m.get("properties", {}).get("score", 0) for m in memories]
print("=== SCORES ===")
print(f"  Min: {min(scores)}, Max: {max(scores)}, Avg: {round(sum(scores) / len(scores), 1)}")
low = sum(1 for s in scores if s < 3)
mid = sum(1 for s in scores if 3 <= s < 7)
high = sum(1 for s in scores if s >= 7)
print(f"  Low (<3): {low}, Mid (3-6): {mid}, High (7+): {high}")

print()

# Ring distribution
rings = {}
for m in memories:
    r = m.get("properties", {}).get("ring", "unknown")
    rings[r] = rings.get(r, 0) + 1
print("=== RING DISTRIBUTION ===")
for r, c in sorted(rings.items(), key=lambda x: -x[1]):
    print(f"  {r}: {c}")

print()

# Status
archived = sum(1 for m in memories if m.get("properties", {}).get("archived"))
deprecated = sum(1 for m in memories if m.get("properties", {}).get("deprecated"))
statuses = {}
for m in memories:
    s = m.get("properties", {}).get("status", "unknown")
    statuses[s] = statuses.get(s, 0) + 1
print("=== STATUS ===")
print(f"  Archived: {archived}, Deprecated: {deprecated}")
for s, c in sorted(statuses.items(), key=lambda x: -x[1]):
    print(f"  {s}: {c}")

print()

# Title/content quality
no_title = sum(1 for m in memories if not m.get("properties", {}).get("title"))
no_summary = sum(1 for m in memories if not m.get("properties", {}).get("summary"))
short_content = sum(1 for m in memories if len(m.get("properties", {}).get("content", "")) < 20)
print("=== CONTENT QUALITY ===")
print(f"  No title: {no_title}")
print(f"  No summary: {no_summary}")
print(f"  Short content (<20 chars): {short_content}")

print()

# Sample: show first 10 "general" topic memories (title + content excerpt)
print("=== SAMPLE GENERAL-TOPIC MEMORIES (first 15) ===")
general = [m for m in memories if m.get("properties", {}).get("topic", "general") == "general"]
for m in general[:15]:
    p = m.get("properties", {})
    title = p.get("title", "NO TITLE")
    content = (p.get("content", "") or "")[:100]
    mtype = p.get("memory_type", "?")
    score = p.get("score", 0)
    print(f"  [{mtype}|s={score}] {title}")
    print(f"    -> {content}...")
    print()
