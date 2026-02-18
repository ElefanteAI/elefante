"""Audit memory data quality for v2.0.0 migration planning."""
import json
import sys
from pathlib import Path
from collections import Counter

snapshot_path = Path.home() / ".elefante" / "data" / "dashboard_snapshot.json"
with open(snapshot_path) as f:
    data = json.load(f)

memories = [n for n in data["nodes"] if n.get("type") == "memory"]
total = len(memories)
print(f"Total memories: {total}\n")

# 1. Title prefix pollution
print("=" * 60)
print("AUDIT 1: TITLE PREFIX POLLUTION")
print("=" * 60)
prefix_count = 0
prefixes = Counter()
for m in memories:
    title = m.get("properties", {}).get("title", m.get("name", ""))
    for p in ["self.", "world.", "intent."]:
        if title.lower().startswith(p):
            prefix_count += 1
            prefix = title.split(":")[0] if ":" in title else title[:30]
            prefixes[prefix] += 1
            break
print(f"With V3 layer.sublayer prefix: {prefix_count}/{total} ({round(prefix_count/total*100)}%)")
for p, c in prefixes.most_common(20):
    print(f"  {p}: {c}")

# 2. Topic distribution
print(f"\n{'=' * 60}")
print("AUDIT 2: TOPIC DISTRIBUTION")
print("=" * 60)
topics = Counter()
for m in memories:
    t = m.get("properties", {}).get("topic", "MISSING")
    topics[t] += 1
for t, c in topics.most_common():
    print(f"  {t}: {c} ({round(c/total*100)}%)")

# 3. Tags quality
print(f"\n{'=' * 60}")
print("AUDIT 3: TAG QUALITY")
print("=" * 60)
no_tags = 0
tag_counts = Counter()
for m in memories:
    tags = m.get("properties", {}).get("tags", "")
    if not tags or tags.strip() == "":
        no_tags += 1
    else:
        for tag in tags.split(","):
            tag = tag.strip()
            if tag:
                tag_counts[tag] += 1
print(f"Memories with no tags: {no_tags}/{total}")
print(f"Unique tags: {len(tag_counts)}")
print(f"Top 20 tags:")
for t, c in tag_counts.most_common(20):
    print(f"  {t}: {c}")

# 4. Summary quality
print(f"\n{'=' * 60}")
print("AUDIT 4: SUMMARY QUALITY")
print("=" * 60)
same_as_content = 0
no_summary = 0
long_content = 0
for m in memories:
    p = m.get("properties", {})
    summary = p.get("summary", "")
    content = p.get("content", "")
    if not summary:
        no_summary += 1
    elif summary.strip() == content.strip():
        same_as_content += 1
    if len(content) > 500:
        long_content += 1
print(f"No summary: {no_summary}/{total}")
print(f"Summary == Content (useless duplication): {same_as_content}/{total} ({round(same_as_content/total*100)}%)")
print(f"Content > 500 chars: {long_content}/{total}")

# 5. Score distribution
print(f"\n{'=' * 60}")
print("AUDIT 5: SCORE DISTRIBUTION")
print("=" * 60)
scores = Counter()
for m in memories:
    s = m.get("properties", {}).get("score", "MISSING")
    scores[s] += 1
for s, c in sorted(scores.items(), key=lambda x: str(x[0])):
    print(f"  score={s}: {c}")

# 6. Processing status
print(f"\n{'=' * 60}")
print("AUDIT 6: PROCESSING STATUS")
print("=" * 60)
statuses = Counter()
for m in memories:
    s = m.get("properties", {}).get("processing_status", "MISSING")
    statuses[s] += 1
for s, c in statuses.items():
    print(f"  {s}: {c}")

# 7. Content duplication / near-duplication
print(f"\n{'=' * 60}")
print("AUDIT 7: CONTENT DUPLICATION")
print("=" * 60)
contents = Counter()
for m in memories:
    c = m.get("properties", {}).get("content", "")[:100]  # first 100 chars
    contents[c] += 1
dupes = {k: v for k, v in contents.items() if v > 1}
print(f"Near-duplicate content (same first 100 chars): {len(dupes)} groups")
for c, count in sorted(dupes.items(), key=lambda x: -x[1])[:10]:
    print(f"  [{count}x] {c[:80]}...")

# 8. Knowledge type distribution
print(f"\n{'=' * 60}")
print("AUDIT 8: KNOWLEDGE_TYPE DISTRIBUTION")
print("=" * 60)
ktypes = Counter()
for m in memories:
    k = m.get("properties", {}).get("knowledge_type", "MISSING")
    ktypes[k] += 1
for k, c in ktypes.most_common():
    print(f"  {k}: {c}")

# 9. Ring distribution
print(f"\n{'=' * 60}")
print("AUDIT 9: RING DISTRIBUTION")
print("=" * 60)
rings = Counter()
for m in memories:
    r = m.get("properties", {}).get("ring", "MISSING")
    rings[r] += 1
for r, c in rings.most_common():
    print(f"  {r}: {c}")

# 10. Sample 5 worst memories (low score, general topic, raw status)
print(f"\n{'=' * 60}")
print("AUDIT 10: SAMPLE — 5 WORST MEMORIES")
print("=" * 60)
worst = sorted(memories, key=lambda m: (
    m.get("properties", {}).get("score", 0),
    1 if m.get("properties", {}).get("topic") != "general" else 0,
))
for m in worst[:5]:
    p = m.get("properties", {})
    print(f"\n  ID: {m['id'][:12]}...")
    print(f"  Title: {p.get('title', 'N/A')[:80]}")
    print(f"  Type: {p.get('memory_type')} | Topic: {p.get('topic')} | Score: {p.get('score')} | Status: {p.get('processing_status')}")
    print(f"  Content: {p.get('content', '')[:120]}")

# 11. Sample 5 best memories
print(f"\n{'=' * 60}")
print("AUDIT 11: SAMPLE — 5 BEST MEMORIES")
print("=" * 60)
best = sorted(memories, key=lambda m: -(m.get("properties", {}).get("score", 0)))
for m in best[:5]:
    p = m.get("properties", {})
    print(f"\n  ID: {m['id'][:12]}...")
    print(f"  Title: {p.get('title', 'N/A')[:80]}")
    print(f"  Type: {p.get('memory_type')} | Topic: {p.get('topic')} | Score: {p.get('score')} | Status: {p.get('processing_status')}")
    print(f"  Content: {p.get('content', '')[:120]}")
