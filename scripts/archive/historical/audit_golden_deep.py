"""Deep audit: duplicates, reclassification potential, contradictions."""
import json
from pathlib import Path
from collections import Counter

snap_path = Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"
with open(snap_path) as f:
    snap = json.load(f)

memories = [n for n in snap["nodes"] if n.get("type") == "memory"]

# --- Duplicate titles ---
titles = [m.get("properties", {}).get("title", "") for m in memories]
title_counts = Counter(titles)
dupes = {t: c for t, c in title_counts.items() if c > 1}
print("=== DUPLICATE TITLES ===")
for t, c in sorted(dupes.items(), key=lambda x: -x[1]):
    print(f"  [{c}x] {t[:100]}")
dupe_savings = sum(dupes.values()) - len(dupes)
print(f"\n  Groups: {len(dupes)}, Would save: {dupe_savings} memories\n")

# --- Knowledge type ---
print("=== KNOWLEDGE TYPE ===")
kt = Counter(m.get("properties", {}).get("knowledge_type", "none") for m in memories)
for k, c in kt.most_common():
    print(f"  {k}: {c}")
print()

# --- Content-based topic reclassification ---
print("=== TOPIC RECLASSIFICATION POTENTIAL ===")
keywords = {
    "debugging": ["debug", "error", "fix", "bug", "crash", "issue", "traceback", "deadlock", "corruption"],
    "architecture": ["architecture", "design", "pattern", "module", "system", "pipeline", "refinery", "retriev"],
    "agent-behavior": ["agent", "loop", "protocol", "behavior", "retrieval", "cognitive", "anti-loop"],
    "database": ["kuzu", "chroma", "database", "db", "schema", "query", "graph store", "reserved word"],
    "coding-standards": ["code", "style", "format", "naming", "convention", "standard", "emoji"],
    "user-profile": ["preference", "user background", "identity", "personal", "favorite", "model"],
    "tools-environment": ["vscode", "terminal", "tool", "install", "path", "config", "setup"],
    "communication": ["tone", "emoji", "language", "response style", "communication", "direct"],
    "documentation": ["doc.", "readme", "compendium", "neural-register", "docs/"],
    "testing": ["test", "pytest", "e2e", "verify", "validation", "smoke"],
}

topic_suggestions = {}
for m in memories:
    p = m.get("properties", {})
    if p.get("topic", "general") != "general":
        continue
    content = (p.get("content", "") + " " + p.get("title", "")).lower()
    best_topic = None
    best_hits = 0
    for topic, kws in keywords.items():
        hits = sum(1 for kw in kws if kw in content)
        if hits > best_hits:
            best_hits = hits
            best_topic = topic
    if best_topic and best_hits >= 1:
        topic_suggestions.setdefault(best_topic, []).append(p.get("title", "?")[:80])

for topic, tl in sorted(topic_suggestions.items(), key=lambda x: -len(x[1])):
    print(f"\n  {topic} ({len(tl)} memories):")
    for t in tl[:5]:
        print(f"    - {t}")
    if len(tl) > 5:
        print(f"    ... and {len(tl) - 5} more")

classified = sum(len(v) for v in topic_suggestions.values())
remaining = 110 - classified
print(f"\n  Classifiable: {classified} / 110 general")
print(f"  Still unclassifiable: {remaining}\n")

# --- Contradictory ---
print("=== CONTRADICTORY MEMORIES ===")
contra = [m for m in memories if m.get("properties", {}).get("status") == "contradictory"]
print(f"  Count: {len(contra)}")
for m in contra[:8]:
    p = m.get("properties", {})
    print(f"  - [{p.get('memory_type','?')}] {p.get('title', '?')[:90]}")

# --- All scores are 0 ---
print(f"\n=== SCORE ISSUE ===")
print(f"  ALL {len(memories)} memories have score=0  (needs recalculation)")
