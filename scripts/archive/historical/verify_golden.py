"""Quick verification of golden cleanup results via dashboard API."""
import json
import urllib.request

resp = urllib.request.urlopen("http://127.0.0.1:8000/api/graph")
d = json.loads(resp.read())
nodes = d.get("nodes", [])
edges = d.get("edges", [])

mems = [n for n in nodes if n.get("type") == "memory"]

topics = {}
scores = []
statuses = {}
for m in mems:
    p = m.get("properties", {})
    t = p.get("topic", "general")
    topics[t] = topics.get(t, 0) + 1
    s = p.get("score", 0)
    scores.append(s)
    st = p.get("status", "unknown")
    statuses[st] = statuses.get(st, 0) + 1

print(f"Total nodes: {len(nodes)}")
print(f"Total edges: {len(edges)}")
print(f"Memories: {len(mems)}")
print()
print("TOPICS:")
for t in sorted(topics.keys()):
    print(f"  {t:<22} {topics[t]:>4}")
gen = topics.get("general", 0)
print(f"\n  General:     {gen}/{len(mems)} ({100*gen/len(mems):.0f}%)")
print(f"  Categorized: {len(mems)-gen}/{len(mems)} ({100*(len(mems)-gen)/len(mems):.0f}%)")
print()
print("SCORES:")
print(f"  Average: {sum(scores)/len(scores):.1f}")
print(f"  Non-zero: {sum(1 for s in scores if s > 0)}/{len(scores)}")
score_dist = {}
for s in scores:
    score_dist[s] = score_dist.get(s, 0) + 1
for s in sorted(score_dist.keys()):
    print(f"  Score {s:>2}: {score_dist[s]:>3}")
print()
print("STATUSES:")
for st in sorted(statuses.keys()):
    print(f"  {st:<20} {statuses[st]:>4}")
contra = statuses.get("contradictory", 0)
print(f"\n  Contradictory: {contra} (was 25)")
