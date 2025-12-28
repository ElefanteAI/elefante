import argparse
import json
import os
import sys
from collections import defaultdict, deque
from pathlib import Path


# Allow running as a standalone script by making repo root importable.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _default_snapshot_path() -> Path:
    # Prefer Elefante config location if importable; fall back to repo-local data/.
    try:
        from src.utils.config import DATA_DIR  # type: ignore

        return Path(DATA_DIR) / "dashboard_snapshot.json"
    except Exception:
        repo_root = Path(__file__).resolve().parents[1]
        return repo_root / "data" / "dashboard_snapshot.json"


def _load_snapshot(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _build_adjacency(edges: list[dict]) -> dict[str, set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        a = e.get("from") or e.get("source")
        b = e.get("to") or e.get("target")
        if not a or not b:
            continue
        a = str(a)
        b = str(b)
        if a == b:
            continue
        adj[a].add(b)
        adj[b].add(a)
    return adj


def _components_among_memories(node_type: dict[str, str], adj: dict[str, set[str]]) -> list[int]:
    mem_ids = [nid for nid, t in node_type.items() if t == "memory"]
    visited: set[str] = set()
    component_sizes: list[int] = []

    for start in mem_ids:
        if start in visited:
            continue
        q: deque[str] = deque([start])
        visited.add(start)
        mem_count = 0

        while q:
            x = q.popleft()
            if node_type.get(x) == "memory":
                mem_count += 1
            for y in adj.get(x, ()):  # traverse via any node type
                if y in visited:
                    continue
                visited.add(y)
                q.append(y)

        component_sizes.append(mem_count)

    component_sizes.sort(reverse=True)
    return component_sizes


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze Elefante dashboard_snapshot.json")
    parser.add_argument(
        "--snapshot",
        type=Path,
        default=_default_snapshot_path(),
        help="Path to dashboard_snapshot.json",
    )
    args = parser.parse_args()

    path: Path = args.snapshot
    if not path.exists():
        raise SystemExit(f"Snapshot not found: {path}")

    snap = _load_snapshot(path)
    nodes = snap.get("nodes", []) or []
    edges = snap.get("edges", []) or []

    node_type: dict[str, str] = {str(n.get("id")): str(n.get("type")) for n in nodes if n.get("id") is not None}

    signal_nodes = [n for n in nodes if str(n.get("id", "")).startswith("signal:")]
    signal_edges = [e for e in edges if e.get("type") == "signal"]

    cluster_nodes = [n for n in nodes if n.get("type") == "cluster"]
    backbone_edges = [e for e in edges if e.get("type") == "cluster_backbone"]

    semantic_edges = [e for e in edges if e.get("type") == "semantic"]
    kuzu_edges = [e for e in edges if "type" not in e and e.get("label")]

    adj = _build_adjacency(edges)
    comps = _components_among_memories(node_type, adj)

    print(f"snapshot={path}")
    print(f"nodes={len(nodes)} edges={len(edges)}")
    print(f"memories={sum(1 for t in node_type.values() if t == 'memory')} entities_or_other={len(nodes) - sum(1 for t in node_type.values() if t == 'memory')}")
    print(f"signal_nodes={len(signal_nodes)} signal_edges={len(signal_edges)}")
    print(f"cluster_nodes={len(cluster_nodes)} cluster_backbone_edges={len(backbone_edges)}")
    print(f"semantic_edges={len(semantic_edges)} kuzu_edges={len(kuzu_edges)}")
    print(f"components_among_memories={len(comps)} sizes={comps}")

    # Small breakdown of signal hub types
    by_kind: dict[str, int] = defaultdict(int)
    for n in signal_nodes:
        props = n.get("properties") if isinstance(n.get("properties"), dict) else {}
        kind = props.get("signal_type") or "unknown"
        by_kind[str(kind)] += 1
    if by_kind:
        items = ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items()))
        print(f"signal_kinds: {items}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
